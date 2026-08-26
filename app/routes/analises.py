import shutil
import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from ..auth import UtilizadorAutenticado, obter_utilizador_atual
from ..database import (
    analise_concluida_por_concurso,
    cancelar_analise_job,
    concurso_por_id,
    criar_ou_obter_analise_job,
    criar_ou_reiniciar_analise_job,
    listar_analises_utilizador,
    obter_estado_analise_job_utilizador,
    obter_analise_job_utilizador,
    remover_analise_job_utilizador,
    remover_analise_utilizador,
    repetir_analise_job,
)
from ..company_ai.company_storage import obter_empresa_utilizador
from ..company_ai.company_context import build_company_context
from ..architecture_intelligence.schemas import ConsolidatedCompetitionData
from ..architecture_intelligence.llm.presentation_builder import PresentationBuilder


router = APIRouter(prefix="/analises", tags=["Análises"])
BASE_DIR = Path(__file__).resolve().parents[2]
ANALISES_DIR = (BASE_DIR / "analise_documentos").resolve()
JOBS_TEMP_DIR = (ANALISES_DIR / ".jobs").resolve()
PRESENTATION_BUILDER = PresentationBuilder()
logger = logging.getLogger(__name__)


def _analysis_context(analise_id: int) -> tuple[dict, dict] | None:
    """Lê o registo da análise e o job associado, sem tocar nos documentos."""
    from ..database import abrir_conexao
    with abrir_conexao() as conn:
        row = conn.execute(
            "SELECT id, dados_json, concurso_id, job_id FROM analises WHERE id = ?",
            (analise_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        data = json.loads(row["dados_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        data = {}
    context = {
        "analysis_id": int(row["id"]),
        "concurso_id": int(row["concurso_id"]),
        "job_id": row["job_id"],
    }
    logger.info(
        "analysis_presentation_request analysis_id=%s concurso_id=%s job_id=%s",
        context["analysis_id"], context["concurso_id"], context["job_id"],
    )
    return data, context


def _consolidated_for_analysis(analise_id: int) -> tuple[ConsolidatedCompetitionData, dict] | None:
    """Resolve o consolidado persistido ou adapta o JSON estruturado histórico."""
    loaded = _analysis_context(analise_id)
    if loaded is None:
        logger.info("analysis_presentation_analysis_not_found analysis_id=%s", analise_id)
        return None
    data, context = loaded
    intelligence = data.get("architecture_intelligence")
    candidates = [data.get("consolidated"), data.get("consolidated_data"), intelligence.get("consolidated") if isinstance(intelligence, dict) else None]
    for candidate in candidates:
        if isinstance(candidate, dict):
            try:
                logger.info("analysis_presentation_consolidated_source analysis_id=%s source=embedded", analise_id)
                return ConsolidatedCompetitionData.model_validate(candidate), context
            except ValueError:
                continue
    # Artefacto separado produzido pelo pipeline experimental, quando disponível.
    for base in (ANALISES_DIR / str(context["concurso_id"]), ANALISES_DIR / str(analise_id)):
        path = base / "consolidated.json"
        if path.is_file():
            try:
                logger.info("analysis_presentation_consolidated_source analysis_id=%s source=%s", analise_id, path)
                return ConsolidatedCompetitionData.model_validate_json(path.read_text(encoding="utf-8")), context
            except (OSError, ValueError):
                pass
    adapted = _adapt_legacy_analysis(data)
    logger.info("analysis_presentation_consolidated_source analysis_id=%s source=legacy_json_adapter", analise_id)
    return adapted, context


def _adapt_legacy_analysis(data: dict) -> ConsolidatedCompetitionData:
    """Converte apenas JSON estruturado já guardado; nunca infere factos novos."""
    insights = data.get("document_insights") or {}
    summary = insights.get("procedure_summary") or {}
    procedure = {
        key: summary[key] for key in
        ("object", "contracting_entity", "procedure_type", "submission_deadline", "execution_deadline", "location")
        if summary.get(key) not in (None, "", {})
    }
    economy = data.get("economia") or {}
    prices = {}
    if economy.get("valor_procedimento"):
        prices["procedure_value"] = {"value": economy["valor_procedimento"], "evidence_ids": ["legacy:economia:valor_procedimento"]}
    if economy.get("valor_estimado_obra"):
        prices["estimated_construction_cost"] = {"value": economy["valor_estimado_obra"], "evidence_ids": ["legacy:economia:valor_estimado_obra"]}
    criteria = data.get("criterios") or {}
    award = {}
    if criteria.get("criterio_adjudicacao"):
        award["award_criterion"] = {"value": criteria["criterio_adjudicacao"], "evidence_ids": ["legacy:criterios:criterio_adjudicacao"]}
    if criteria.get("percentagens"):
        award["factors"] = {"value": criteria["percentagens"], "evidence_ids": ["legacy:criterios:percentagens"]}
    deliverables = insights.get("deliverables") or []
    required_team = insights.get("required_team") or data.get("equipa") or []
    checklist = {"administrative": [], "technical": [], "financial": [], "team": [], "post_award": []}
    for group in insights.get("required_documents") or []:
        name = str(group.get("group") or "").lower()
        target = "administrative" if "habil" in name else "technical" if "proposta" in name else "post_award"
        checklist[target].extend(group.get("items") or [])
    def marked(items, prefix):
        return [dict(item, evidence_ids=[f"legacy:{prefix}:{index}"]) if isinstance(item, dict) else {"value": item, "evidence_ids": [f"legacy:{prefix}:{index}"]} for index, item in enumerate(items or [])]
    consolidated = ConsolidatedCompetitionData(
        document_quality=str(data.get("document_quality") or insights.get("document_quality") or "insufficient"),
        quality_report=insights.get("document_audit") or {},
        procedure_identity=procedure,
        prices=prices,
        award_strategy=award,
        required_team=marked(required_team, "required_team"),
        phases_and_deliverables=marked(deliverables, "deliverables"),
        submission_checklist={key: marked(value, f"checklist:{key}") for key, value in checklist.items()},
        technical_constraints=marked(insights.get("technical_constraints"), "technical_constraints"),
        exclusion_risks=marked(insights.get("exclusion_risks") or data.get("risks"), "exclusion_risks"),
        document_alerts=marked(insights.get("document_alerts"), "document_alerts"),
    )
    return consolidated


@router.post("/{analise_id}/presentation")
def criar_apresentacao(analise_id: int, utilizador: UtilizadorAutenticado = Depends(obter_utilizador_atual)):
    resolved = _consolidated_for_analysis(analise_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    consolidated, _ = resolved
    logger.info("analysis_presentation_cache=miss analysis_id=%s ollama=attempt fallback=automatic force=true", analise_id)
    return PRESENTATION_BUILDER.build(consolidated, force=True).model_dump(mode="json")


@router.get("/{analise_id}/presentation")
def obter_apresentacao(analise_id: int, utilizador: UtilizadorAutenticado = Depends(obter_utilizador_atual)):
    resolved = _consolidated_for_analysis(analise_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    consolidated, _ = resolved
    presentation = PRESENTATION_BUILDER.cached(consolidated)
    if presentation is not None:
        logger.info("analysis_presentation_cache=hit analysis_id=%s", analise_id)
        return presentation.model_dump(mode="json")
    logger.info("analysis_presentation_cache=miss analysis_id=%s ollama=attempt fallback=automatic", analise_id)
    presentation = PRESENTATION_BUILDER.build(consolidated)
    return presentation.model_dump(mode="json")


class CriarAnalisePedido(BaseModel):
    concurso_id: int = Field(gt=0)


_STAGE_POR_ESTADO = {
    "aguarda": "queued",
    "extracao": "extracting_documents",
    "processamento": "extracting_documents",
    "geracao": "generating_competition_analysis",
    "concluida": "completed",
    "erro": "failed",
    "cancelada": "cancelled",
}


def _status_job_api(
    job: dict,
    existing_analysis_id: int | None = None,
    refreshing: bool = False,
) -> dict:
    estado = str(job.get("estado") or "")
    status = {
        "aguarda": "queued",
        "extracao": "processing",
        "processamento": "processing",
        "geracao": "processing",
        "concluida": "completed",
        "erro": "failed",
        "cancelada": "cancelled",
    }.get(estado, "processing")
    analysis_id = job.get("analysis_id")
    if status != "completed":
        analysis_id = analysis_id or existing_analysis_id
    return {
        **job,
        "job_id": job.get("id"),
        "status": status,
        "stage": job.get("stage") or _STAGE_POR_ESTADO.get(estado, estado),
        "progress": job.get("progresso", 0),
        "analysis_id": analysis_id,
        "existing_analysis_id": existing_analysis_id,
        "refreshing": refreshing,
        "error": job.get("erro"),
    }


def _empresa_id_utilizador(utilizador: UtilizadorAutenticado) -> int | None:
    empresa = obter_empresa_utilizador(utilizador.id)
    return int(empresa["id"]) if empresa else None


def _current_company_context_hash(company_id: int | None) -> str | None:
    if company_id is None:
        return None
    try:
        company_context = build_company_context(company_id).model_dump()
    except Exception:
        return None
    return hashlib.sha256(
        json.dumps(
            company_context,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _parse_date(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:16], pattern)
        except ValueError:
            continue
    match = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", text)
    if match:
        day, month, year = match.groups()
        try:
            return datetime(int(year), int(month), int(day))
        except ValueError:
            return None
    return None


def _enrich_analysis_item(
    item: dict,
    *,
    company_id: int | None,
    current_company_hash: str | None,
) -> dict:
    raw_json = item.pop("dados_json", None)
    data = {}
    if raw_json:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            data = {}

    source_platform = data.get("source_platform_status") or {}
    recommendation = (
        data.get("decision_summary", {}).get("recommendation")
        or data.get("recomendacao_final", {}).get("decisao")
        or data.get("analise_ai", {}).get("recomendacao")
    )
    schema_version = data.get("analysis_schema_version")
    stored_company_hash = data.get("company_profile_hash")
    stale_reasons: list[str] = []
    if item.get("analysis_scope") == "sistema" and company_id is not None:
        stale_reasons.append(
            "Analise antiga sem company_id; precisa de atualizacao com o perfil da empresa."
        )
    if not schema_version:
        stale_reasons.append("Schema de analise anterior.")
    if (
        current_company_hash
        and stored_company_hash
        and stored_company_hash != current_company_hash
    ):
        stale_reasons.append("Perfil da empresa mudou desde a ultima analise.")

    deadline = _parse_date(item.get("data_limite"))
    item["stale"] = bool(stale_reasons)
    item["stale_reasons"] = stale_reasons
    item["analysis_schema_version"] = schema_version
    item["recommendation"] = recommendation
    item["source_platform"] = source_platform.get("platform")
    item["source_platform_status"] = source_platform.get("status")
    item["source_documents_count"] = len(source_platform.get("documents") or [])
    item["concurso_encerrado"] = bool(deadline and deadline < datetime.now())
    return item


@router.get("")
def listar_analises(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    company_id = _empresa_id_utilizador(utilizador)
    current_hash = _current_company_context_hash(company_id)
    items = listar_analises_utilizador(
        utilizador.id,
        company_id,
    )
    return {
        "analises": [
            _enrich_analysis_item(
                dict(item),
                company_id=company_id,
                current_company_hash=current_hash,
            )
            for item in items
        ]
    }


@router.post("/criar")
def criar_analise(
    pedido: CriarAnalisePedido,
    response: Response,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    if concurso_por_id(pedido.concurso_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concurso não encontrado.",
        )

    company_id = _empresa_id_utilizador(utilizador)
    analise_existente = analise_concluida_por_concurso(
        pedido.concurso_id,
        utilizador.id,
        company_id,
    )
    existing_analysis_id = (
        int(analise_existente["id"]) if analise_existente else None
    )

    job, criado = criar_ou_reiniciar_analise_job(
        utilizador.id,
        pedido.concurso_id,
        company_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED
        if criado
        else status.HTTP_200_OK
    )
    return _status_job_api(
        job,
        existing_analysis_id=existing_analysis_id,
        refreshing=existing_analysis_id is not None,
    )


@router.get("/jobs/{job_id}")
def obter_estado_job(
    job_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    job = obter_estado_analise_job_utilizador(
        utilizador.id,
        job_id,
        _empresa_id_utilizador(utilizador),
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job de anÃ¡lise nÃ£o encontrado.",
        )
    return _status_job_api(job)


def _remover_temporarios_job(job_id: int) -> bool:
    pasta = (JOBS_TEMP_DIR / str(job_id)).resolve()
    if JOBS_TEMP_DIR not in pasta.parents or not pasta.exists():
        return False
    shutil.rmtree(pasta)
    return True


def _id_portal_base(link: str | None) -> str | None:
    if not link:
        return None
    import re

    resultado = re.search(r"[?&]id=(\d+)", link)
    return resultado.group(1) if resultado else None


def _remover_temporarios_concurso(concurso: dict | None) -> list[str]:
    removidos: list[str] = []
    if not concurso:
        return removidos

    identificador = _id_portal_base(concurso.get("link")) or str(concurso["id"])
    candidatos = [
        (ANALISES_DIR / identificador / "temp").resolve(),
    ]
    for pasta in candidatos:
        if ANALISES_DIR in pasta.parents and pasta.exists():
            shutil.rmtree(pasta)
            removidos.append(pasta.relative_to(BASE_DIR).as_posix())
    return removidos


def _remover_ficha_especifica(caminho_relativo: str | None) -> bool:
    if not caminho_relativo:
        return False

    ficheiro = (BASE_DIR / caminho_relativo).resolve()
    if (
        ANALISES_DIR not in ficheiro.parents
        or ficheiro.name != "ficha.json"
        or not ficheiro.is_file()
    ):
        return False

    ficheiro.unlink()
    return True


@router.post("/{job_id}/cancelar")
def cancelar_analise(
    job_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    job = obter_analise_job_utilizador(utilizador.id, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada.",
        )
    if job["estado"] not in {
        "aguarda", "extracao", "processamento", "geracao"
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta análise já não pode ser cancelada.",
        )

    cancelado = cancelar_analise_job(utilizador.id, job_id)
    if cancelado is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O estado da análise foi alterado. Atualiza a página.",
        )

    temporarios_removidos = _remover_temporarios_job(job_id)
    return {
        **cancelado,
        "temporarios_removidos": temporarios_removidos,
    }


@router.post("/{job_id}/repetir")
def repetir_analise(
    job_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    job = obter_analise_job_utilizador(utilizador.id, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada.",
        )
    if job["estado"] != "erro":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível repetir análises em erro.",
        )

    repetido = repetir_analise_job(utilizador.id, job_id)
    if repetido is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O estado da análise foi alterado. Atualiza a página.",
        )

    concurso = concurso_por_id(repetido["concurso_id"])
    temporarios = []
    if _remover_temporarios_job(job_id):
        temporarios.append(f"analise_documentos/.jobs/{job_id}")
    temporarios.extend(_remover_temporarios_concurso(concurso))
    return {
        **repetido,
        "temporarios_removidos": temporarios,
    }


@router.post("/concurso/{concurso_id}/atualizar")
def atualizar_analise_concurso(
    concurso_id: int,
    response: Response,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    concurso = concurso_por_id(concurso_id)
    if concurso is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concurso não encontrado.",
        )

    job, criado = criar_ou_reiniciar_analise_job(
        utilizador.id,
        concurso_id,
        _empresa_id_utilizador(utilizador),
    )
    response.status_code = (
        status.HTTP_201_CREATED if criado else status.HTTP_200_OK
    )
    return {
        **job,
        "mensagem": "Análise colocada na fila de atualização.",
    }


@router.delete("/jobs/{job_id}")
def apagar_analise_job(
    job_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    job = obter_analise_job_utilizador(utilizador.id, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada.",
        )
    if job["estado"] not in {"erro", "cancelada"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível apagar jobs em erro ou cancelados.",
        )

    removido = remover_analise_job_utilizador(utilizador.id, job_id)
    if removido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada ou não pertence ao utilizador atual.",
        )

    concurso = concurso_por_id(removido["concurso_id"])
    temporarios = []
    if _remover_temporarios_job(job_id):
        temporarios.append(f"analise_documentos/.jobs/{job_id}")
    temporarios.extend(_remover_temporarios_concurso(concurso))

    return {
        "apagada": True,
        "tipo": "job",
        "job_id": job_id,
        "concurso_id": removido["concurso_id"],
        "temporarios_removidos": temporarios,
    }


@router.delete("/{analise_id}")
def apagar_analise(
    analise_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    removida = remover_analise_utilizador(
        utilizador.id,
        analise_id,
    )
    if removida is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Análise não encontrada ou não pertence "
                "ao utilizador atual."
            ),
        )

    ficha_removida = False
    if removida["ficheiro_exclusivo"]:
        ficha_removida = _remover_ficha_especifica(
            removida.get("ficheiro_ficha")
        )

    return {
        "apagada": True,
        "analise_id": analise_id,
        "concurso_id": removida["concurso_id"],
        "ficha_removida": ficha_removida,
    }
