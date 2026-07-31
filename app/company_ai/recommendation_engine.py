from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .compatibility_analysis import CompatibilityResult


class CompanyRecommendation(BaseModel):
    competition_id: int | None = None
    company_id: int | None = None
    status: str = "unknown"
    matches: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


def _texto_limpo(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split())


def _normalizar_resultado(
    compatibility_result,
) -> CompatibilityResult:
    if isinstance(compatibility_result, CompatibilityResult):
        return compatibility_result
    if hasattr(compatibility_result, "model_dump"):
        return CompatibilityResult.model_validate(
            compatibility_result.model_dump()
        )
    if isinstance(compatibility_result, dict):
        return CompatibilityResult.model_validate(compatibility_result)
    return CompatibilityResult()


def _gerar_reasons(
    matches: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    unknowns: list[str],
) -> list[str]:
    reasons: list[str] = []

    for match in matches:
        field = _texto_limpo(match.get("field"))
        company_values = match.get("company_values") or []
        competition_values = match.get("competition_values") or []
        reasons.append(
            f"Compatibilidade encontrada em {field}: "
            f"{', '.join(map(str, company_values))} "
            f"vs {', '.join(map(str, competition_values))}."
        )

    for gap in gaps:
        field = _texto_limpo(gap.get("field"))
        reasons.append(
            f"Existe diferença em {field} e pode exigir validação."
        )

    for unknown in unknowns:
        reasons.append(f"Informação em falta para {unknown}.")

    return reasons


def generate_recommendation(
    company_id,
    competition_id,
    compatibility_result,
) -> CompanyRecommendation:
    """
    Transforma a análise de compatibilidade numa recomendação explicável.

    Futuro:
    - ranking;
    - scoring;
    - user feedback;
    - conversion to favorite.
    """
    compatibility = _normalizar_resultado(compatibility_result)

    has_matches = bool(compatibility.matches)
    has_gaps_or_unknowns = bool(compatibility.gaps or compatibility.unknowns)

    if has_matches:
        status = "suggested"
    elif has_gaps_or_unknowns:
        status = "needs_validation"
    else:
        status = "unknown"

    reasons = _gerar_reasons(
        compatibility.matches,
        compatibility.gaps,
        compatibility.unknowns,
    )

    if has_gaps_or_unknowns and not has_matches:
        reasons.append(
            "A recomendação permanece em revisão até haver mais evidência."
        )

    return CompanyRecommendation(
        competition_id=int(competition_id) if competition_id is not None else None,
        company_id=int(company_id) if company_id is not None else None,
        status=status,
        matches=list(compatibility.matches),
        gaps=list(compatibility.gaps),
        unknowns=list(compatibility.unknowns),
        reasons=reasons,
        evidence=list(compatibility.evidence),
    )
