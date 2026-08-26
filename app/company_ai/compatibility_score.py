from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CompatibilityScoreBreakdownItem(BaseModel):
    label: str
    impact: str
    value: int | None = None


class CompatibilityScoreResult(BaseModel):
    score: int | None = None
    label: str = "Sem dados suficientes"
    breakdown: list[CompatibilityScoreBreakdownItem] = Field(default_factory=list)


SCORE_LABELS: tuple[tuple[int, str], ...] = (
    (90, "Muito elevada"),
    (75, "Elevada"),
    (60, "Moderada"),
    (40, "Baixa"),
    (0, "Muito baixa"),
)

FIELD_WEIGHTS = {
    "competences": 24,
    "preferences.typologies": 24,
    "project_experience.typologies": 22,
    "location": 10,
}

DEFAULT_MATCH_WEIGHT = 12
DEFAULT_GAP_PENALTY = 7
DEFAULT_UNKNOWN_PENALTY = 4


def classify_compatibility_score(score: int | None) -> str:
    if score is None:
        return "Sem dados suficientes"
    for threshold, label in SCORE_LABELS:
        if score >= threshold:
            return label
    return "Muito baixa"


def _field_weight(field: Any) -> int:
    key = str(field or "").strip()
    return FIELD_WEIGHTS.get(key, DEFAULT_MATCH_WEIGHT)


def _impact_for_value(value: int) -> str:
    if value >= 20:
        return "impacto muito positivo"
    if value > 0:
        return "impacto positivo"
    if value == 0:
        return "neutro"
    return "impacto negativo"


def calculate_compatibility_score(
    *,
    matches: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    unknowns: list[str],
) -> CompatibilityScoreResult:
    """
    Calcula um score deterministico a partir dos fatores ja produzidos pelo
    motor de compatibilidade. Nao cria uma segunda logica de recomendacao.
    """
    usable_signals = len(matches) + len(gaps) + len(unknowns)
    if usable_signals == 0:
        return CompatibilityScoreResult()

    raw_score = 50
    breakdown: list[CompatibilityScoreBreakdownItem] = []

    for match in matches:
        value = _field_weight(match.get("field"))
        raw_score += value
        breakdown.append(
            CompatibilityScoreBreakdownItem(
                label=str(match.get("field") or "Compatibilidade identificada"),
                impact=_impact_for_value(value),
                value=value,
            )
        )

    for gap in gaps:
        value = -min(DEFAULT_GAP_PENALTY, max(4, _field_weight(gap.get("field")) // 3))
        raw_score += value
        breakdown.append(
            CompatibilityScoreBreakdownItem(
                label=str(gap.get("field") or "Ponto a validar"),
                impact=_impact_for_value(value),
                value=value,
            )
        )

    for unknown in unknowns:
        value = -DEFAULT_UNKNOWN_PENALTY
        raw_score += value
        breakdown.append(
            CompatibilityScoreBreakdownItem(
                label=str(unknown or "Informacao em falta"),
                impact=_impact_for_value(value),
                value=value,
            )
        )

    score = max(0, min(100, raw_score))
    return CompatibilityScoreResult(
        score=score,
        label=classify_compatibility_score(score),
        breakdown=breakdown,
    )
