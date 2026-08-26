from __future__ import annotations

import json
import base64
from contextlib import closing
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from pypdf import PdfReader

from ..auth import UtilizadorAutenticado, obter_utilizador_atual
from ..database import abrir_conexao, obter_analise
from .company_storage import (
    adicionar_membro,
    criar_empresa,
    listar_membros,
    obter_empresa_utilizador,
    pesquisar_empresas,
    utilizador_pode_gerir_membros,
)
from .compatibility_analysis import analyze_compatibility
from .company_context import build_company_context
from .competition_context import build_competition_context
from .intelligence_builder import build_company_intelligence
from .interview_storage import (
    create_interview_session,
    get_active_interview_session,
    get_question_answer,
    get_question_context,
    get_session_questions,
    save_answer,
    save_question,
)
from .answer_interpreter import interpret_answer
from .company_ingestion import ingest_company_information
from .knowledge_storage import apply_validation_answer, get_company_knowledge
from .knowledge_validation import generate_knowledge_validation_questions
from .profile_updater import apply_answer_to_profile
from .question_engine import generate_questions
from .member_storage import (
    criar_member_profile,
    guardar_member_profile,
    obter_member_profile,
)
from .profile_storage import (
    guardar_company_profile as guardar_company_profile_storage,
    obter_company_profile as obter_company_profile_storage,
)
from .recommendation_engine import generate_recommendation
from .recommendation_presenter import build_recommendation_card
from .models import CompanyMember, CompanyProfile, MemberProfile
from .source_management import delete_company_source, list_company_sources
from .website_ingestion import ingest_company_website


router = APIRouter(prefix="/company", tags=["Company Intelligence"])


class CompanyCreatePedido(BaseModel):
    name: str = Field(min_length=1)
    website: str | None = None


class CompanyMemberCreatePedido(BaseModel):
    user_id: str = Field(min_length=1)
    role: str = "member"


class InterviewAnswerPedido(BaseModel):
    answer: Any


class CompanyDocumentIngestionRequest(BaseModel):
    text: str
    source: str = ""


class CompanyDocumentFileIngestionRequest(BaseModel):
    filename: str = Field(min_length=1)
    content_base64: str = Field(min_length=1)
    source_type: str = "document"


class CompanyWebsiteIngestionRequest(BaseModel):
    url: str = Field(min_length=1)


class CompanySourceDeleteRequest(BaseModel):
    source_type: str = Field(min_length=1)
    source: str = Field(min_length=1)


def _listar_concursos_analisaveis() -> list[dict[str, Any]]:
    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT *
            FROM concursos
            WHERE COALESCE(relevante, 1) = 1
            ORDER BY id DESC
            """
        ).fetchall()

    return [dict(linha) for linha in linhas]


def _obter_dados_competicao(concurso: dict[str, Any]) -> dict[str, Any]:
    analise = obter_analise(int(concurso["id"]))
    if analise and analise.get("dados_json"):
        try:
            dados = json.loads(analise["dados_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            dados = {}
        if isinstance(dados, dict):
            return dados
    return concurso


def _membro_pertence_empresa(
    company_id: int,
    member_id: int,
) -> bool:
    return any(
        membro["id"] == member_id
        for membro in listar_membros(company_id)
    )


def _extrair_texto_pdf_bytes(conteudo: bytes) -> str:
    try:
        leitor = PdfReader(BytesIO(conteudo))
    except Exception as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nao foi possivel ler o PDF enviado.",
        ) from erro

    paginas: list[str] = []
    for pagina in leitor.pages:
        try:
            paginas.append(pagina.extract_text() or "")
        except Exception:
            continue
    return "\n".join(paginas).strip()


def _extrair_texto_ficheiro(filename: str, content_base64: str) -> str:
    try:
        conteudo = base64.b64decode(content_base64, validate=True)
    except Exception as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Conteudo do ficheiro invalido.",
        ) from erro

    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ficheiro vazio.",
        )

    nome = filename.lower()
    if nome.endswith(".pdf") or conteudo.startswith(b"%PDF"):
        texto = _extrair_texto_pdf_bytes(conteudo)
    else:
        texto = conteudo.decode("utf-8", errors="ignore").strip()

    if not texto:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nao foi extraido texto util do ficheiro.",
        )
    return texto


def _normalizar_url_website(url: str) -> str:
    texto = str(url or "").strip()
    if not texto:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Website obrigatorio.",
        )
    if not texto.startswith(("http://", "https://")):
        texto = f"https://{texto}"
    return texto


def _assinatura_pergunta(pergunta: Any) -> tuple[str, str]:
    if isinstance(pergunta, dict):
        question_source = str(
            pergunta.get("question_source") or "discovery"
        ).strip() or "discovery"
        knowledge_fact_id = pergunta.get("knowledge_fact_id")
        field = str(pergunta.get("field") or "").strip()
    else:
        question_source = str(
            getattr(pergunta, "question_source", "discovery")
        ).strip() or "discovery"
        knowledge_fact_id = getattr(pergunta, "knowledge_fact_id", None)
        field = str(getattr(pergunta, "field", "")).strip()

    if question_source == "validation" and knowledge_fact_id is not None:
        return ("validation", str(knowledge_fact_id))
    return (question_source, field)


def _gerar_perguntas_adaptadas(company_id: int) -> list[Any]:
    intelligence = build_company_intelligence(company_id)
    missing_information = intelligence["knowledge"][
        "missing_information"
    ]
    company_profile = obter_company_profile_storage(company_id)
    knowledge_facts = get_company_knowledge(company_id)

    perguntas_descoberta = generate_questions(
        missing_information,
        company_profile,
        knowledge_facts,
    )
    perguntas_validacao = generate_knowledge_validation_questions(company_id)
    return [
        *perguntas_descoberta,
        *perguntas_validacao,
    ]


def _sincronizar_perguntas_entrevista(
    session_id: int,
    company_id: int,
) -> list[dict[str, Any]]:
    perguntas_atuais = _gerar_perguntas_adaptadas(company_id)
    assinaturas_atuais = {
        _assinatura_pergunta(pergunta)
        for pergunta in perguntas_atuais
    }

    perguntas_sessao = get_session_questions(session_id)
    assinaturas_existentes = {
        _assinatura_pergunta(pergunta)
        for pergunta in perguntas_sessao
    }

    for pergunta in perguntas_atuais:
        if _assinatura_pergunta(pergunta) not in assinaturas_existentes:
            save_question(session_id, pergunta)

    perguntas_sessao = get_session_questions(session_id)

    # A sessao persiste para permitir interromper e continuar mais tarde.
    # Perguntas ja respondidas ou que deixaram de ser relevantes ficam
    # guardadas, mas nao sao reapresentadas como tarefas pendentes.
    return [
        pergunta
        for pergunta in perguntas_sessao
        if pergunta.get("answer_id") is None
        and _assinatura_pergunta(pergunta) in assinaturas_atuais
    ]


@router.get("/profile")
def obter_company_profile(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> CompanyProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    # Futuro: member_profiles, interviewer, extractor e matching vão
    # alimentar este profile persistido por company_id.
    return obter_company_profile_storage(empresa["id"])


@router.post("/profile", status_code=status.HTTP_201_CREATED)
def criar_company_profile(
    perfil: CompanyProfile,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> CompanyProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    return guardar_company_profile_storage(empresa["id"], perfil)


@router.put("/profile")
def atualizar_company_profile(
    perfil: CompanyProfile,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> CompanyProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    return guardar_company_profile_storage(empresa["id"], perfil)


@router.get("/intelligence")
def obter_company_intelligence(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    # Futuro: esta visão agregada será consumida por interviewer,
    # matching engine, response generator e knowledge base.
    return build_company_intelligence(empresa["id"])


@router.get("/recommendations")
def obter_company_recommendations(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    company_context = build_company_context(empresa["id"])
    concursos = _listar_concursos_analisaveis()
    if not concursos:
        return []

    recomendacoes = []
    for concurso in concursos:
        competition_context = build_competition_context(concurso)
        compatibility_result = analyze_compatibility(
            company_context,
            competition_context,
        )
        recomendacoes.append(
            generate_recommendation(
                empresa["id"],
                competition_context.competition_id or concurso.get("id"),
                compatibility_result,
            )
        )

    # Futuro: ranking, user feedback e conversão em favorito poderão
    # consumir esta lista sem alterar o worker ou as análises.
    return recomendacoes


@router.get("/recommendation-cards")
def obter_company_recommendation_cards(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    company_context = build_company_context(empresa["id"])
    concursos = _listar_concursos_analisaveis()
    if not concursos:
        return []

    cards = []
    for concurso in concursos:
        competition_context = build_competition_context(
            _obter_dados_competicao(concurso)
        )
        compatibility_result = analyze_compatibility(
            company_context,
            competition_context,
        )
        recommendation = generate_recommendation(
            empresa["id"],
            competition_context.competition_id or concurso.get("id"),
            compatibility_result,
        )
        cards.append(
            build_recommendation_card(
                recommendation,
                competition_context,
                concurso,
            )
        )

    # Futuro: frontend, ranking, score e favoritos poderão consumir
    # estes cards sem alterar a lógica de compatibilidade.
    return cards


@router.post("/documents/ingest")
def ingerir_company_document(
    pedido: CompanyDocumentIngestionRequest,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    # Futuro: PDF ingestion, website ingestion e source tracking poderão
    # alimentar este pipeline antes ou depois da extração documental.
    return ingest_company_information(
        empresa["id"],
        pedido.text,
        pedido.source,
    )


@router.post("/documents/ingest-file")
def ingerir_company_document_file(
    pedido: CompanyDocumentFileIngestionRequest,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa nao encontrada para o utilizador atual.",
        )

    texto = _extrair_texto_ficheiro(
        pedido.filename,
        pedido.content_base64,
    )
    source_type = str(pedido.source_type or "document").strip() or "document"
    return ingest_company_information(
        empresa["id"],
        texto,
        f"{source_type}:{pedido.filename}",
    )


@router.post("/website/ingest")
def ingerir_company_website(
    pedido: CompanyWebsiteIngestionRequest,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa nao encontrada para o utilizador atual.",
        )

    website_url = _normalizar_url_website(pedido.url)
    return ingest_company_website(
        empresa["id"],
        website_url,
    )


@router.get("/sources")
def listar_company_sources_endpoint(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa nao encontrada para o utilizador atual.",
        )

    return {
        "sources": list_company_sources(empresa["id"]),
    }


@router.delete("/sources")
def remover_company_source_endpoint(
    pedido: CompanySourceDeleteRequest,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa nao encontrada para o utilizador atual.",
        )

    deleted = delete_company_source(
        empresa["id"],
        pedido.source_type,
        pedido.source,
    )
    return {
        "deleted_facts": deleted,
        "sources": list_company_sources(empresa["id"]),
    }


@router.get("/search")
def pesquisar_company_suggestions(
    query: str = "",
    website: str = "",
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    # Pesquisa apenas para sugestoes seguras. Nao associa automaticamente
    # utilizadores a empresas encontradas por nome/dominio.
    return {
        "results": pesquisar_empresas(
            query=query,
            website=website,
            user_id=utilizador.id,
        ),
        "association_policy": (
            "suggestions_only_invite_or_owner_approval_required"
        ),
    }


@router.get("/questions")
def obter_company_questions(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    intelligence = build_company_intelligence(empresa["id"])
    missing_information = intelligence["knowledge"][
        "missing_information"
    ]
    company_profile = obter_company_profile_storage(empresa["id"])
    knowledge_facts = get_company_knowledge(empresa["id"])

    # Futuro: Question Engine será consumido pelo AI Interviewer e
    # por fluxos específicos de member profiles e company strategy.
    return {
        "company_id": empresa["id"],
        "questions": generate_questions(
            missing_information,
            company_profile,
            knowledge_facts,
        ),
    }


@router.get("/interview")
def obter_company_interview(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa nÃ£o encontrada para o utilizador atual.",
        )

    sessao = get_active_interview_session(empresa["id"])
    if sessao is None:
        sessao = create_interview_session(empresa["id"])

    perguntas = _sincronizar_perguntas_entrevista(
        sessao["id"],
        empresa["id"],
    )

    return {
        "session_id": sessao["id"],
        "status": sessao["status"],
        "questions": perguntas,
    }


@router.post("/interview/{question_id}/answer")
def responder_company_interview_question(
    question_id: int,
    pedido: InterviewAnswerPedido,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa nÃ£o encontrada para o utilizador atual.",
        )

    contexto = get_question_context(question_id)
    if contexto is None or contexto["company_id"] != empresa["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pergunta da entrevista nÃ£o encontrada para a empresa atual.",
        )

    if contexto["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A sessÃ£o de entrevista jÃ¡ nÃ£o estÃ¡ ativa.",
        )

    save_answer(question_id, pedido.answer)

    if contexto.get("question_source") == "validation":
        knowledge_fact_id = contexto.get("knowledge_fact_id")
        if knowledge_fact_id is not None:
            apply_validation_answer(
                int(knowledge_fact_id),
                pedido.answer,
            )

    return {
        "question_id": question_id,
        "answer": pedido.answer,
    }


@router.post("/interview/{question_id}/apply")
def aplicar_company_interview_answer(
    question_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> CompanyProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    contexto = get_question_context(question_id)
    if contexto is None or contexto["company_id"] != empresa["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pergunta da entrevista não encontrada para a empresa atual.",
        )

    resposta = get_question_answer(question_id)
    if resposta is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não existe resposta guardada para esta pergunta.",
        )

    perfil_atualizado = apply_answer_to_profile(
        empresa["id"],
        contexto["field"],
        interpret_answer(
            contexto["field"],
            resposta["answer"],
        ).value,
    )

    # Futuro: interviewer, extractor e scoring irão enriquecer esta
    # atualização determinística antes de qualquer lógica AI mais avançada.
    return guardar_company_profile_storage(
        empresa["id"],
        perfil_atualizado,
    )


@router.get(
    "/members/{member_id}/profile"
)
def obter_member_profile_endpoint(
    member_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> MemberProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    if not _membro_pertence_empresa(empresa["id"], member_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membro não encontrado na empresa atual.",
        )

    # Futuro: owner/admin, visibilidade e permissões individuais vão
    # controlar o acesso a este perfil.
    return obter_member_profile(member_id)


@router.post(
    "/members/{member_id}/profile",
    status_code=status.HTTP_201_CREATED,
)
def criar_member_profile_endpoint(
    member_id: int,
    perfil: MemberProfile,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> MemberProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    if not _membro_pertence_empresa(empresa["id"], member_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membro não encontrado na empresa atual.",
        )

    # Futuro: o member profile será usado por interviewer individual,
    # matching de concursos, resposta AI e agregação Company Intelligence.
    criar_member_profile(member_id)
    return guardar_member_profile(member_id, perfil)


@router.put("/members/{member_id}/profile")
def atualizar_member_profile_endpoint(
    member_id: int,
    perfil: MemberProfile,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> MemberProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    if not _membro_pertence_empresa(empresa["id"], member_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membro não encontrado na empresa atual.",
        )

    return guardar_member_profile(member_id, perfil)


@router.get("")
def obter_company(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )
    return empresa


@router.post("")
def criar_company(
    pedido: CompanyCreatePedido,
    response: Response,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa_existente = obter_empresa_utilizador(utilizador.id)
    if empresa_existente is not None:
        response.status_code = status.HTTP_200_OK
        return empresa_existente

    empresa = criar_empresa(
        utilizador.id,
        pedido.name,
        pedido.website,
    )

    response.status_code = status.HTTP_201_CREATED
    return empresa


@router.get("/members")
def listar_company_members(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    return {
        "company_id": empresa["id"],
        "members": listar_membros(empresa["id"]),
    }


@router.post("/members", status_code=status.HTTP_201_CREATED)
def adicionar_company_member(
    pedido: CompanyMemberCreatePedido,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> CompanyMember:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    # Futuro: regras de permissões, convites por email e papéis mais
    # granulares serão tratadas na camada de equipa/empresa.
    if not utilizador_pode_gerir_membros(empresa["id"], utilizador.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas owner/admin pode adicionar membros.",
        )

    role = str(pedido.role or "member").strip() or "member"
    if role not in {"member", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role invalido. Usa 'member' ou 'admin'.",
        )

    # Futuro: convites por email e aprovacao do owner/admin devem substituir
    # a adicao direta quando houver fluxo de associacao publico.
    membro, criado = adicionar_membro(
        empresa["id"],
        pedido.user_id,
        role,
    )
    if not criado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Utilizador ja pertence a esta empresa.",
        )

    return CompanyMember.model_validate(membro)

# CNLL_CV_MODAL_RECALC_V17_2
from typing import Any as _CVAny
import hashlib as _cv_hashlib
import json as _cv_json

from fastapi import Depends as _CVDepends, HTTPException as _CVHTTPException
from pydantic import BaseModel as _CVBaseModel, Field as _CVField

from app.auth import obter_utilizador_atual as _cv_user_dependency
from app.company_ai.company_storage import obter_empresa_utilizador as _cv_company_for_user
from app.company_ai.knowledge_storage import (
    delete_knowledge_by_field as _cv_delete_knowledge_by_field,
    get_company_knowledge as _cv_get_company_knowledge,
    upsert_knowledge_fact as _cv_upsert_knowledge_fact,
)
from app.company_ai.models import CompanyCVEntry as _CompanyCVEntry
from app.company_ai.profile_storage import (
    guardar_company_profile as _cv_save_profile,
    obter_company_profile as _cv_get_profile,
)
from app.database import abrir_conexao as _cv_open_db


class _CVAnalysisFactPayload(_CVBaseModel):
    reuse_key: str = _CVField(min_length=1, max_length=240)
    target: dict[str, _CVAny] = _CVField(default_factory=dict)
    requirement_id: str | None = None
    requirement_ids: list[str] = _CVField(default_factory=list)
    title: str | None = None
    description: str | None = None
    answer: str | None = None
    person: str | None = None
    project: str | None = None
    numeric_value: float | None = None
    metric: str | None = None
    unit: str | None = None
    confirmed_by_user: bool = True
    source: str = "analysis_question"


def _cv_company_id(company: _CVAny) -> int:
    if isinstance(company, dict):
        value = company.get("id") or company.get("company_id")
    else:
        value = getattr(company, "id", None) or getattr(company, "company_id", None)
    if value is None:
        raise _CVHTTPException(status_code=404, detail="Empresa não encontrada.")
    return int(value)


def _cv_clean(value: _CVAny) -> str:
    return " ".join(str(value or "").strip().split())


def _cv_entry_id(reuse_key: str) -> str:
    return "cv-" + _cv_hashlib.sha1(reuse_key.encode("utf-8")).hexdigest()[:16]


def _cv_derive_reuse_key(entry: _CompanyCVEntry) -> str:
    if _cv_clean(entry.reuse_key):
        return _cv_clean(entry.reuse_key)

    from app.analise.canonical_analysis import _reuse_key as _canonical_reuse_key
    combined = _cv_clean(
        " ".join(
            part
            for part in (
                entry.title,
                entry.description,
                entry.person,
                entry.project,
            )
            if _cv_clean(part)
        )
    )
    return _canonical_reuse_key(
        combined,
        _cv_clean(entry.metric) or None,
        _cv_clean(entry.scope) or "company",
        _cv_clean(entry.role),
    )


def _cv_fact_from_knowledge(item: _CVAny) -> dict[str, _CVAny] | None:
    field = _cv_clean(getattr(item, "field", ""))
    prefix = "analysis.requirements."
    if not field.startswith(prefix):
        return None
    value = getattr(item, "value", None)
    if not isinstance(value, dict):
        return None
    reuse_key = _cv_clean(value.get("reuse_key") or field[len(prefix):])
    if not reuse_key:
        return None
    return {
        **value,
        "reuse_key": reuse_key,
        "memory_id": getattr(item, "id", None),
        "status": getattr(item, "status", None),
        "confidence": getattr(item, "confidence", None),
    }


def _cv_analysis_facts(company_id: int) -> dict[str, dict[str, _CVAny]]:
    output: dict[str, dict[str, _CVAny]] = {}
    for item in _cv_get_company_knowledge(company_id):
        fact = _cv_fact_from_knowledge(item)
        if fact:
            output[fact["reuse_key"]] = fact
    return output


def _cv_upsert_profile_entry(
    company_id: int,
    entry: _CompanyCVEntry,
) -> _CompanyCVEntry:
    profile = _cv_get_profile(company_id)
    reuse_key = _cv_derive_reuse_key(entry)
    normalized = entry.model_copy(deep=True)
    normalized.reuse_key = reuse_key
    normalized.id = _cv_clean(normalized.id) or _cv_entry_id(reuse_key)

    indexes = {
        item.id: index
        for index, item in enumerate(profile.cv)
        if _cv_clean(item.id)
    }
    reuse_indexes = {
        item.reuse_key: index
        for index, item in enumerate(profile.cv)
        if _cv_clean(item.reuse_key)
    }

    index = indexes.get(normalized.id)
    if index is None:
        index = reuse_indexes.get(normalized.reuse_key)

    if index is None:
        profile.cv.append(normalized)
    else:
        profile.cv[index] = normalized

    _cv_save_profile(company_id, profile, merge_existing=False)

    _cv_upsert_knowledge_fact(
        company_id=company_id,
        field=f"analysis.requirements.{reuse_key}",
        value=normalized.model_dump(),
        source=normalized.source or "company_cv",
        source_type="company_cv",
        confidence=1.0 if normalized.status == "confirmed" else 0.85,
        status=normalized.status or "confirmed",
    )
    return normalized


def _cv_sync_legacy_to_profile(company_id: int) -> list[_CompanyCVEntry]:
    profile = _cv_get_profile(company_id)
    existing = {item.reuse_key for item in profile.cv if _cv_clean(item.reuse_key)}
    changed = False

    for reuse_key, fact in _cv_analysis_facts(company_id).items():
        if reuse_key in existing:
            continue
        target = fact.get("target") if isinstance(fact.get("target"), dict) else {}
        entry = _CompanyCVEntry(
            id=_cv_entry_id(reuse_key),
            category="fact",
            title=_cv_clean(fact.get("title")) or _cv_clean(fact.get("description")) or "Dado de análise",
            description=_cv_clean(fact.get("description")),
            reuse_key=reuse_key,
            scope=_cv_clean(fact.get("scope")) or _cv_clean(target.get("scope")) or "company",
            role=_cv_clean(fact.get("role")) or _cv_clean(target.get("role")),
            person=_cv_clean(fact.get("person")),
            project=_cv_clean(fact.get("project")),
            metric=_cv_clean(fact.get("metric")),
            numeric_value=fact.get("numeric_value"),
            unit=_cv_clean(fact.get("unit")),
            answer=_cv_clean(fact.get("answer")),
            status=_cv_clean(fact.get("status")) or "confirmed",
            source=_cv_clean(fact.get("source")) or "analysis",
            requirement_ids=[
                _cv_clean(x)
                for x in (
                    fact.get("requirement_ids")
                    if isinstance(fact.get("requirement_ids"), list)
                    else [fact.get("requirement_id")]
                )
                if _cv_clean(x)
            ],
        )
        profile.cv.append(entry)
        existing.add(reuse_key)
        changed = True

    if changed:
        _cv_save_profile(company_id, profile, merge_existing=False)
    return profile.cv


@router.get("/analysis-facts")
def cv_list_analysis_facts(
    utilizador=_CVDepends(_cv_user_dependency),
):
    company = _cv_company_for_user(utilizador.id)
    if company is None:
        raise _CVHTTPException(status_code=404, detail="Empresa não encontrada.")
    company_id = _cv_company_id(company)
    return {"facts": list(_cv_analysis_facts(company_id).values())}


@router.post("/analysis-facts")
def cv_save_analysis_fact(
    payload: _CVAnalysisFactPayload,
    utilizador=_CVDepends(_cv_user_dependency),
):
    company = _cv_company_for_user(utilizador.id)
    if company is None:
        raise _CVHTTPException(status_code=404, detail="Empresa não encontrada.")
    company_id = _cv_company_id(company)

    requirement_ids = [
        _cv_clean(x)
        for x in payload.requirement_ids
        if _cv_clean(x)
    ]
    if payload.requirement_id and _cv_clean(payload.requirement_id) not in requirement_ids:
        requirement_ids.append(_cv_clean(payload.requirement_id))

    value = {
        "reuse_key": _cv_clean(payload.reuse_key),
        "target": payload.target,
        "requirement_id": payload.requirement_id,
        "requirement_ids": requirement_ids,
        "title": _cv_clean(payload.title),
        "description": _cv_clean(payload.description),
        "answer": _cv_clean(payload.answer),
        "person": _cv_clean(payload.person),
        "project": _cv_clean(payload.project),
        "numeric_value": payload.numeric_value,
        "metric": _cv_clean(payload.metric),
        "unit": _cv_clean(payload.unit),
        "confirmed_by_user": payload.confirmed_by_user,
        "source": _cv_clean(payload.source) or "analysis_question",
    }

    _cv_upsert_knowledge_fact(
        company_id=company_id,
        field=f"analysis.requirements.{payload.reuse_key}",
        value=value,
        source=value["source"],
        source_type="analysis_requirement",
        confidence=1.0 if payload.confirmed_by_user else 0.85,
        status="confirmed" if payload.confirmed_by_user else "unknown",
    )

    entry = _CompanyCVEntry(
        id=_cv_entry_id(payload.reuse_key),
        category="fact",
        title=value["title"] or value["description"] or "Dado de análise",
        description=value["description"],
        reuse_key=value["reuse_key"],
        scope=_cv_clean(payload.target.get("scope")) or "company",
        role=_cv_clean(payload.target.get("role")),
        person=value["person"],
        project=value["project"],
        metric=value["metric"],
        numeric_value=payload.numeric_value,
        unit=value["unit"],
        answer=value["answer"],
        status="confirmed",
        source="analysis",
        requirement_ids=requirement_ids,
    )
    _cv_upsert_profile_entry(company_id, entry)

    return {"ok": True, "reuse_key": payload.reuse_key, "cv_entry": entry}


@router.get("/cv")
def cv_list(
    utilizador=_CVDepends(_cv_user_dependency),
):
    company = _cv_company_for_user(utilizador.id)
    if company is None:
        raise _CVHTTPException(status_code=404, detail="Empresa não encontrada.")
    company_id = _cv_company_id(company)
    entries = _cv_sync_legacy_to_profile(company_id)
    return {"cv": [entry.model_dump() for entry in entries]}


@router.post("/cv")
def cv_create(
    payload: _CompanyCVEntry,
    utilizador=_CVDepends(_cv_user_dependency),
):
    company = _cv_company_for_user(utilizador.id)
    if company is None:
        raise _CVHTTPException(status_code=404, detail="Empresa não encontrada.")
    company_id = _cv_company_id(company)
    payload.id = ""
    payload.source = payload.source or "manual"
    entry = _cv_upsert_profile_entry(company_id, payload)
    return {"ok": True, "entry": entry.model_dump()}


@router.put("/cv/{entry_id}")
def cv_update(
    entry_id: str,
    payload: _CompanyCVEntry,
    utilizador=_CVDepends(_cv_user_dependency),
):
    company = _cv_company_for_user(utilizador.id)
    if company is None:
        raise _CVHTTPException(status_code=404, detail="Empresa não encontrada.")
    company_id = _cv_company_id(company)

    profile = _cv_get_profile(company_id)
    old = next((item for item in profile.cv if item.id == entry_id), None)
    if old is None:
        raise _CVHTTPException(status_code=404, detail="Registo de CV não encontrado.")

    old_reuse_key = _cv_clean(old.reuse_key)
    payload.id = entry_id
    payload.source = payload.source or old.source or "manual"
    entry = _cv_upsert_profile_entry(company_id, payload)

    if old_reuse_key and old_reuse_key != entry.reuse_key:
        _cv_delete_knowledge_by_field(
            company_id,
            f"analysis.requirements.{old_reuse_key}",
        )

    return {"ok": True, "entry": entry.model_dump()}


@router.delete("/cv/{entry_id}")
def cv_delete(
    entry_id: str,
    utilizador=_CVDepends(_cv_user_dependency),
):
    company = _cv_company_for_user(utilizador.id)
    if company is None:
        raise _CVHTTPException(status_code=404, detail="Empresa não encontrada.")
    company_id = _cv_company_id(company)

    profile = _cv_get_profile(company_id)
    target = next((item for item in profile.cv if item.id == entry_id), None)
    if target is None:
        raise _CVHTTPException(status_code=404, detail="Registo de CV não encontrado.")

    profile.cv = [item for item in profile.cv if item.id != entry_id]
    _cv_save_profile(company_id, profile, merge_existing=False)

    if _cv_clean(target.reuse_key):
        _cv_delete_knowledge_by_field(
            company_id,
            f"analysis.requirements.{target.reuse_key}",
        )

    return {"ok": True, "deleted": entry_id}


@router.post("/analysis-facts/recalculate/{concurso_id}")
def cv_recalculate_analysis(
    concurso_id: int,
    utilizador=_CVDepends(_cv_user_dependency),
):
    company = _cv_company_for_user(utilizador.id)
    if company is None:
        raise _CVHTTPException(status_code=404, detail="Empresa não encontrada.")
    company_id = _cv_company_id(company)

    with _cv_open_db() as conn:
        row = conn.execute(
            """
            SELECT id, dados_json
            FROM analises
            WHERE concurso_id = ?
              AND (user_id = ? OR user_id IS NULL)
              AND (company_id = ? OR company_id IS NULL)
            ORDER BY
              CASE WHEN user_id = ? THEN 0 ELSE 1 END,
              CASE WHEN company_id = ? THEN 0 ELSE 1 END,
              updated_at DESC,
              id DESC
            LIMIT 1
            """,
            (
                concurso_id,
                utilizador.id,
                company_id,
                utilizador.id,
                company_id,
            ),
        ).fetchone()

        if row is None:
            raise _CVHTTPException(status_code=404, detail="Análise não encontrada.")

        try:
            ficha = _cv_json.loads(row["dados_json"] or "{}")
        except (TypeError, ValueError, _cv_json.JSONDecodeError):
            ficha = {}

        if not isinstance(ficha.get("analysis_canonical"), dict):
            raise _CVHTTPException(
                status_code=409,
                detail="Esta análise ainda não tem o motor canónico. Usa Refazer análise uma vez.",
            )

        facts = _cv_analysis_facts(company_id)
        profile = _cv_get_profile(company_id)
        for entry in profile.cv:
            if _cv_clean(entry.reuse_key):
                facts[entry.reuse_key] = entry.model_dump()

        from app.analise.canonical_analysis import apply_profile_facts_to_canonical

        canonical = apply_profile_facts_to_canonical(ficha, facts)
        decision_score = (canonical.get("decision") or {}).get("score")
        score = int(round(float(decision_score))) if isinstance(decision_score, (int, float)) else None

        conn.execute(
            """
            UPDATE analises
            SET dados_json = ?,
                score = COALESCE(?, score),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                _cv_json.dumps(ficha, ensure_ascii=False),
                score,
                int(row["id"]),
            ),
        )
        conn.commit()

    return {
        "ok": True,
        "analise_id": int(row["id"]),
        "concurso_id": concurso_id,
        "canonical": canonical,
    }

# CNLL_UNIVERSAL_ANALYSIS_POPUP_V17_4
# CNLL_PROCEDURAL_RECOVERY_V17_4_2
from app.analise.legacy_procedure_recovery import (
    analysis_body as _cv_analysis_body,
    procedural_richness as _cv_procedural_richness,
    recover_procedure_from_legacy as _cv_recover_legacy_procedure,
)


def _cv_procedure_from_existing_analysis(
    ficha: dict[str, _CVAny],
) -> dict[str, _CVAny]:
    candidates: list[_CVAny] = [
        ficha.get("procedure_analysis"),
        ficha.get("procedure"),
        ficha.get("procedimento"),
    ]

    extraction = ficha.get("design_competition_extraction")
    if isinstance(extraction, dict):
        candidates.extend(
            [
                extraction.get("procedure_analysis"),
                extraction.get("procedure"),
            ]
        )

    intelligence = ficha.get("architecture_intelligence")
    if isinstance(intelligence, dict):
        candidates.extend(
            [
                intelligence.get("procedure_analysis"),
                intelligence.get("procedure"),
            ]
        )

    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return candidate

    return {}


# CNLL_CANONICAL_VISIBLE_SYNC_V17_5_3B
def _cv_visible_procedure_is_material(
    ficha: dict[str, _CVAny],
) -> bool:
    candidates: list[_CVAny] = [ficha.get("procedure_analysis")]

    extraction = ficha.get("design_competition_extraction")
    if isinstance(extraction, dict):
        candidates.append(extraction.get("procedure_analysis"))

    for procedure in candidates:
        if not isinstance(procedure, dict):
            continue

        award = procedure.get("award_criteria")
        factors = (
            award.get("factors")
            if isinstance(award, dict)
            and isinstance(award.get("factors"), list)
            else []
        )
        scoring = (
            award.get("scoring_requirements")
            if isinstance(award, dict)
            and isinstance(award.get("scoring_requirements"), list)
            else []
        )
        team = (
            procedure.get("technical_team")
            if isinstance(procedure.get("technical_team"), list)
            else []
        )

        if factors or scoring or team:
            return True

    return False


def _cv_sync_recovered_procedure_to_visible_analysis(
    ficha: dict[str, _CVAny],
    recovered: dict[str, _CVAny],
) -> None:
    import copy as _cv_copy

    material = _cv_copy.deepcopy(recovered)
    ficha["procedure_analysis"] = material

    extraction = ficha.get("design_competition_extraction")
    if not isinstance(extraction, dict):
        extraction = {}
        ficha["design_competition_extraction"] = extraction
    extraction["procedure_analysis"] = _cv_copy.deepcopy(material)


def _cv_concurso_dict(conn, concurso_id: int) -> dict[str, _CVAny]:
    try:
        row = conn.execute(
            "SELECT * FROM concursos WHERE id = ? LIMIT 1",
            (concurso_id,),
        ).fetchone()
    except Exception:
        row = None

    if row is None:
        return {"id": concurso_id}

    try:
        return dict(row)
    except Exception:
        return {"id": concurso_id}


def _cv_team_role_key(item: _CVAny) -> str:
    if not isinstance(item, dict):
        return ""
    target = item.get("profile_target")
    role = (
        target.get("role")
        if isinstance(target, dict)
        else None
    ) or item.get("role") or item.get("title") or item.get("label")
    return _cv_clean(role).casefold()


def _cv_required_submission_team_roles(
    ficha: dict[str, _CVAny],
) -> set[str]:
    candidates: list[_CVAny] = [ficha.get("procedure_analysis")]
    extraction = ficha.get("design_competition_extraction")
    if isinstance(extraction, dict):
        candidates.append(extraction.get("procedure_analysis"))

    for procedure in candidates:
        if not isinstance(procedure, dict):
            continue
        team = procedure.get("technical_team")
        if not isinstance(team, list):
            continue
        items = [item for item in team if isinstance(item, dict)]
        explicit = {
            _cv_team_role_key(item)
            for item in items
            if item.get("required_at_submission") is True
            and _cv_team_role_key(item)
        }
        if explicit:
            return explicit

        roles = {_cv_team_role_key(item) for item in items if _cv_team_role_key(item)}
        documents = " ".join(
            _cv_clean(item.get("source_document")) for item in items
        ).casefold()
        headings = " ".join(
            _cv_clean(item.get("source_heading")) for item in items
        ).casefold()
        if len(roles) >= 3 and "programa" in documents and (
            "equipa" in headings or "anexo" in headings
        ):
            return roles

    return set()


def _cv_canonical_covers_visible_procedure(
    canonical: _CVAny,
    ficha: dict[str, _CVAny],
) -> bool:
    if not isinstance(canonical, dict):
        return False
    expected_roles = _cv_required_submission_team_roles(ficha)
    if not expected_roles:
        return True

    requirements = canonical.get("requirements")
    if not isinstance(requirements, list):
        return False
    covered_roles = {
        _cv_team_role_key(item)
        for item in requirements
        if isinstance(item, dict)
        and item.get("nature") == "team"
        and item.get("stage") == "pre_award"
        and item.get("profile_dependent") is True
        and item.get("required_at_submission") is not False
        and _cv_team_role_key(item)
    }
    return expected_roles.issubset(covered_roles)


def _cv_canonical_is_material(canonical: _CVAny) -> bool:
    if not isinstance(canonical, dict):
        return False
    requirements = canonical.get("requirements")
    questions = canonical.get("questions")
    criteria = canonical.get("criteria")
    factors = (
        criteria.get("factors")
        if isinstance(criteria, dict)
        else []
    )
    if isinstance(questions, list) and questions:
        return True
    if isinstance(requirements, list) and any(
        isinstance(item, dict) and item.get("profile_dependent") is True
        for item in requirements
    ):
        return True
    return bool(isinstance(factors, list) and factors)


def _cv_best_procedural_donor(
    conn,
    concurso_id: int,
    current_analysis_id: int,
):
    rows = conn.execute(
        """
        SELECT id, dados_json, user_id, company_id, updated_at
        FROM analises
        WHERE concurso_id = ?
          AND id <> ?
          AND estado = 'concluida'
        ORDER BY updated_at DESC, id DESC
        LIMIT 40
        """,
        (concurso_id, current_analysis_id),
    ).fetchall()

    best = None
    best_score = 0

    for candidate in rows:
        try:
            root = _cv_json.loads(candidate["dados_json"] or "{}")
        except Exception:
            continue

        ficha = _cv_analysis_body(root)
        score = _cv_procedural_richness(ficha)
        if score > best_score:
            best_score = score
            best = {
                "row": candidate,
                "root": root,
                "ficha": ficha,
                "score": score,
            }

    return best


def _cv_annotate_recovered_questions(
    canonical: dict[str, _CVAny],
    recovery_meta: dict[str, _CVAny],
) -> None:
    details = recovery_meta.get("subfactor_details")
    if not isinstance(details, dict):
        return

    questions = canonical.get("questions")
    if not isinstance(questions, list):
        return

    for question in questions:
        if not isinstance(question, dict):
            continue
        code = _cv_clean(question.get("subfactor_code"))
        detail = _cv_clean(details.get(code))
        if not detail:
            continue

        question["criterion_detail"] = detail[:1600]

        target = question.get("profile_target")
        scope = (
            _cv_clean(target.get("scope"))
            if isinstance(target, dict)
            else ""
        )
        if scope != "person":
            continue

        followups = question.get("followups")
        if not isinstance(followups, list):
            followups = []
            question["followups"] = followups

        if any(
            isinstance(item, dict)
            and _cv_clean(item.get("type")) == "project"
            for item in followups
        ):
            continue

        if "projeto" in detail.lower():
            followups.append(
                {
                    "id": "project",
                    "type": "project",
                    "label": "Que projeto comprova esta experiência?",
                    "placeholder": "Projeto de referência",
                    "required_when": ["yes"],
                }
            )


def _cv_persist_canonical(
    conn,
    *,
    row_id: int,
    root: dict[str, _CVAny],
    canonical: dict[str, _CVAny],
) -> None:
    decision_score = (canonical.get("decision") or {}).get("score")
    score = (
        int(round(float(decision_score)))
        if isinstance(decision_score, (int, float))
        else None
    )

    conn.execute(
        """
        UPDATE analises
        SET dados_json = ?,
            score = COALESCE(?, score),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            _cv_json.dumps(root, ensure_ascii=False),
            score,
            row_id,
        ),
    )
    conn.commit()


@router.post("/analysis-facts/ensure-canonical/{concurso_id}")
def cv_ensure_canonical_analysis(
    concurso_id: int,
    utilizador=_CVDepends(_cv_user_dependency),
):
    """
    Aplica o mesmo motor Parque/Lumiar a qualquer análise aberta.

    Quando a análise do utilizador tem canonical vazio, procura apenas dentro
    do MESMO concurso uma análise irmã com informação procedimental mais rica.
    Dessa análise recupera critérios/equipa, nunca score/matching/perfil.
    """
    company = _cv_company_for_user(utilizador.id)
    if company is None:
        raise _CVHTTPException(status_code=404, detail="Empresa não encontrada.")
    company_id = _cv_company_id(company)

    with _cv_open_db() as conn:
        row = conn.execute(
            """
            SELECT id, dados_json
            FROM analises
            WHERE concurso_id = ?
              AND (user_id = ? OR user_id IS NULL)
              AND (company_id = ? OR company_id IS NULL)
            ORDER BY
              CASE WHEN user_id = ? THEN 0 ELSE 1 END,
              CASE WHEN company_id = ? THEN 0 ELSE 1 END,
              updated_at DESC,
              id DESC
            LIMIT 1
            """,
            (
                concurso_id,
                utilizador.id,
                company_id,
                utilizador.id,
                company_id,
            ),
        ).fetchone()

        if row is None:
            raise _CVHTTPException(
                status_code=404,
                detail="Análise não encontrada.",
            )

        try:
            root = _cv_json.loads(row["dados_json"] or "{}")
        except Exception:
            root = {}

        if not isinstance(root, dict):
            root = {}

        ficha = _cv_analysis_body(root)
        canonical = ficha.get("analysis_canonical")

        if (
            _cv_canonical_is_material(canonical)
            and _cv_visible_procedure_is_material(ficha)
            and _cv_canonical_covers_visible_procedure(canonical, ficha)
        ):
            return {
                "ok": True,
                "changed": False,
                "created": False,
                "analise_id": int(row["id"]),
                "concurso_id": concurso_id,
                "question_count": len(canonical.get("questions") or []),
                "canonical": canonical,
            }

        base_procedure = _cv_procedure_from_existing_analysis(ficha)
        donor = _cv_best_procedural_donor(
            conn,
            concurso_id,
            int(row["id"]),
        )

        recovered = None
        recovery_meta: dict[str, _CVAny] = {}
        donor_id = None
        donor_score = 0

        # Primeiro tenta a própria análise (pode ter equipa legacy rica).
        recovered, recovery_meta = _cv_recover_legacy_procedure(
            ficha,
            base_procedure=base_procedure,
        )

        # Se a análise do utilizador estiver documentalmente pobre, usa a
        # análise irmã mais rica do MESMO concurso.
        if recovered is None and donor is not None:
            donor_ficha = donor["ficha"]
            donor_procedure = _cv_procedure_from_existing_analysis(
                donor_ficha
            )
            recovered, recovery_meta = _cv_recover_legacy_procedure(
                donor_ficha,
                base_procedure=donor_procedure or base_procedure,
            )
            donor_id = int(donor["row"]["id"])
            donor_score = int(donor["score"])

        from app.analise.canonical_analysis import (
            apply_canonical_analysis,
            apply_profile_facts_to_canonical,
        )

        concurso = _cv_concurso_dict(conn, concurso_id)

        if recovered is None:
            # Marca o caso para não entrar num ciclo de refresh. Não inventa
            # perguntas quando não existem peças/evidência procedural.
            if not isinstance(canonical, dict):
                canonical = apply_canonical_analysis(
                    ficha=ficha,
                    procedure=base_procedure,
                    textos=None,
                    concurso=concurso,
                )

            canonical["recovery_status"] = "no_procedural_evidence"
            canonical["recovery_note"] = (
                "Não existe informação procedimental suficiente nas análises "
                "guardadas para gerar perguntas de perfil com segurança."
            )
            ficha["analysis_canonical"] = canonical
            _cv_persist_canonical(
                conn,
                row_id=int(row["id"]),
                root=root,
                canonical=canonical,
            )
            return {
                "ok": True,
                "changed": True,
                "created": True,
                "recovery_status": canonical["recovery_status"],
                "analise_id": int(row["id"]),
                "concurso_id": concurso_id,
                "question_count": 0,
                "canonical": canonical,
            }

        _cv_sync_recovered_procedure_to_visible_analysis(
            ficha,
            recovered,
        )

        canonical = apply_canonical_analysis(
            ficha=ficha,
            procedure=recovered,
            textos=None,
            concurso=concurso,
        )

        canonical["recovery_status"] = (
            "recovered_from_existing_analysis"
            if donor_id is not None
            else "recovered_from_current_analysis"
        )
        canonical["recovery_source_analysis_id"] = donor_id
        canonical["recovery_source_score"] = donor_score
        canonical["recovery_mode"] = recovery_meta.get("mode")

        _cv_annotate_recovered_questions(
            canonical,
            recovery_meta,
        )

        facts = _cv_analysis_facts(company_id)
        profile = _cv_get_profile(company_id)
        for entry in profile.cv:
            if _cv_clean(entry.reuse_key):
                facts[entry.reuse_key] = entry.model_dump()

        canonical = apply_profile_facts_to_canonical(
            ficha,
            facts,
        )

        # apply_profile_facts_to_canonical reconstrói questions; reaplica as
        # anotações de contexto do critério depois desse passo.
        _cv_annotate_recovered_questions(
            canonical,
            recovery_meta,
        )

        _cv_persist_canonical(
            conn,
            row_id=int(row["id"]),
            root=root,
            canonical=canonical,
        )

    return {
        "ok": True,
        "changed": True,
        "created": True,
        "recovery_status": canonical.get("recovery_status"),
        "recovery_source_analysis_id": donor_id,
        "analise_id": int(row["id"]),
        "concurso_id": concurso_id,
        "question_count": len(canonical.get("questions") or []),
        "requirement_count": len(canonical.get("requirements") or []),
        "canonical": canonical,
    }
