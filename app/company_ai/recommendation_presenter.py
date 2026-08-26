from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .competition_context import CompetitionContext
from .compatibility_score import (
    CompatibilityScoreBreakdownItem,
    calculate_compatibility_score,
)
from .recommendation_engine import CompanyRecommendation


class RecommendationCardData(BaseModel):
    competition_id: int | None = None
    title: str = ""
    entity: str = ""
    location: str = ""
    link: str = ""
    published_at: str = ""
    deadline: str = ""
    base_price: str = ""
    procedure_type: str = ""
    award_criteria_type: str = ""
    award_criteria_summary: str = ""
    status: str = "unknown"
    compatibility_score: int | None = None
    compatibility_label: str = "Sem dados suficientes"
    confidence_label: str = "Baixa"
    score_breakdown: list[CompatibilityScoreBreakdownItem] = Field(default_factory=list)
    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    attention_points: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    action_label: str = "Ver detalhe"


def _texto_limpo(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split())


def _normalizar_contexto(
    competition_context,
) -> CompetitionContext:
    if isinstance(competition_context, CompetitionContext):
        return competition_context
    if hasattr(competition_context, "model_dump"):
        return CompetitionContext.model_validate(
            competition_context.model_dump()
        )
    if isinstance(competition_context, dict):
        return CompetitionContext.model_validate(competition_context)
    return CompetitionContext()


def _normalizar_recomendacao(
    recommendation,
) -> CompanyRecommendation:
    if isinstance(recommendation, CompanyRecommendation):
        return recommendation
    if hasattr(recommendation, "model_dump"):
        return CompanyRecommendation.model_validate(
            recommendation.model_dump()
        )
    if isinstance(recommendation, dict):
        return CompanyRecommendation.model_validate(recommendation)
    return CompanyRecommendation()


def _formatar_match(match: dict[str, Any]) -> str:
    field = _texto_limpo(match.get("field"))
    company_values = ", ".join(map(str, match.get("company_values") or []))
    competition_values = ", ".join(
        map(str, match.get("competition_values") or [])
    )

    if company_values and competition_values:
        return f"{field}: {company_values} -> {competition_values}"
    if company_values:
        return f"{field}: {company_values}"
    if competition_values:
        return f"{field}: {competition_values}"
    return field or "Compatibilidade identificada"


def _formatar_fator(factor: dict[str, Any]) -> str:
    return (
        _texto_limpo(factor.get("explanation"))
        or _texto_limpo(factor.get("name"))
        or "Compatibilidade identificada"
    )


def _formatar_risco(risk: dict[str, Any]) -> str:
    name = _texto_limpo(risk.get("name"))
    level = _texto_limpo(risk.get("level"))
    if name and level:
        return f"{name}: risco {level}"
    return _texto_limpo(risk.get("explanation")) or name or "Risco a validar"


def _formatar_gap(gap: dict[str, Any]) -> str:
    field = _texto_limpo(gap.get("field"))
    competition_values = ", ".join(
        map(str, gap.get("competition_values") or [])
    )
    if competition_values:
        return f"{field}: falta evidencia para {competition_values}"
    return f"{field}: requer validacao"


def _gerar_summary(
    recommendation: CompanyRecommendation,
    competition_context: CompetitionContext,
) -> str:
    title = _texto_limpo(competition_context.title) or "este concurso"
    if recommendation.status == "suggested":
        return (
            f"Ha compatibilidade relevante com {title}. "
            "Existem sinais positivos suficientes para analise detalhada."
        )
    if recommendation.status == "needs_validation":
        return (
            f"{title} pode ser relevante, mas ainda ha pontos a validar "
            "antes de avancar."
        )
    return (
        f"Nao ha evidencia suficiente para avaliar {title} com confianca."
    )


def _valor_competicao(
    competition_context: CompetitionContext,
    raw_competition: dict[str, Any],
    *keys: str,
) -> str:
    source_data = competition_context.source_data or {}
    for key in keys:
        valor = raw_competition.get(key)
        if valor not in (None, ""):
            return _texto_limpo(valor)
        valor = source_data.get(key)
        if valor not in (None, ""):
            return _texto_limpo(valor)
    return ""


def _valor_aninhado(
    competition_context: CompetitionContext,
    raw_competition: dict[str, Any],
    section: str,
    *keys: str,
) -> str:
    source_data = competition_context.source_data or {}
    for candidate in (raw_competition.get(section), source_data.get(section)):
        if not isinstance(candidate, dict):
            continue
        for key in keys:
            valor = candidate.get(key)
            if valor not in (None, ""):
                return _texto_limpo(valor)
    return ""


def build_recommendation_card(
    recommendation,
    competition_context,
    raw_competition: dict[str, Any] | None = None,
) -> RecommendationCardData:
    """
    Converte uma recommendation interna numa estrutura preparada para UI.

    O score e deterministico e deriva apenas dos matches, gaps e unknowns
    calculados pelo motor de compatibilidade existente.
    """
    recommendation_model = _normalizar_recomendacao(recommendation)
    competition_model = _normalizar_contexto(competition_context)
    raw = raw_competition if isinstance(raw_competition, dict) else {}

    match_items = [
        match
        for match in recommendation_model.matches
        if isinstance(match, dict)
    ]
    gap_items = [
        gap
        for gap in recommendation_model.gaps
        if isinstance(gap, dict)
    ]

    strengths = [_formatar_match(match) for match in match_items]
    attention_points = [_formatar_gap(gap) for gap in gap_items]
    enriched_strengths = [
        _formatar_fator(factor)
        for factor in recommendation_model.positive_factors
        if isinstance(factor, dict)
    ]
    enriched_risks = [
        _formatar_risco(risk)
        for risk in recommendation_model.risks
        if isinstance(risk, dict)
    ]
    missing_information = [
        _texto_limpo(item)
        for item in recommendation_model.unknowns
        if _texto_limpo(item)
    ]

    summary = _gerar_summary(recommendation_model, competition_model)
    score_result = calculate_compatibility_score(
        matches=match_items,
        gaps=gap_items,
        unknowns=list(recommendation_model.unknowns),
    )

    action_label = (
        "Analisar oportunidade"
        if recommendation_model.status == "suggested"
        else "Validar informacao"
        if recommendation_model.status == "needs_validation"
        else "Ver detalhe"
    )

    return RecommendationCardData(
        competition_id=competition_model.competition_id
        or recommendation_model.competition_id,
        title=competition_model.title,
        entity=_valor_competicao(competition_model, raw, "entidade"),
        location=competition_model.location
        or _valor_competicao(competition_model, raw, "municipio", "distrito"),
        link=_valor_competicao(competition_model, raw, "link"),
        published_at=_valor_competicao(
            competition_model,
            raw,
            "data",
            "data_publicacao_iso",
        ),
        deadline=_valor_competicao(
            competition_model,
            raw,
            "data_fim_calculada",
            "data_entrega_propostas",
            "data_limite",
        ),
        base_price=_valor_competicao(
            competition_model,
            raw,
            "preco_base",
            "valor_procedimento",
            "valor_obra",
        )
        or _valor_aninhado(
            competition_model,
            raw,
            "economia",
            "valor_procedimento",
            "valor_estimado_obra",
        ),
        procedure_type=_valor_competicao(
            competition_model,
            raw,
            "tipo_procedimento",
        ),
        award_criteria_type=_valor_competicao(
            competition_model,
            raw,
            "criterio_tipo",
        )
        or _valor_aninhado(
            competition_model,
            raw,
            "criterios",
            "tipo",
            "criterio_tipo",
        ),
        award_criteria_summary=_valor_competicao(
            competition_model,
            raw,
            "criterio_resumo",
            "criterio_detalhe",
        )
        or _valor_aninhado(
            competition_model,
            raw,
            "criterios",
            "resumo",
            "criterio_resumo",
            "detalhe",
        ),
        status=recommendation_model.status,
        compatibility_score=recommendation_model.score
        if recommendation_model.score is not None
        else score_result.score,
        compatibility_label=recommendation_model.score_explanation.get("label")
        or score_result.label,
        confidence_label=recommendation_model.confidence,
        score_breakdown=list(score_result.breakdown),
        summary=summary,
        strengths=(enriched_strengths or strengths)[:3],
        attention_points=(enriched_risks or attention_points)[:3],
        missing_information=missing_information,
        evidence=list(recommendation_model.evidence),
        action_label=action_label,
    )
