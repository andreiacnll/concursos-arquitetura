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
