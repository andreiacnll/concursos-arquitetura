"""Canonical normalization for award criteria collected from any source."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any


def _text(value: object) -> str | None:
    value = str(value or "").strip()
    return value or None


def _fold(value: object) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", str(value or "").casefold())
        if unicodedata.category(char) != "Mn"
    )


def _clean_factor_name(value: object) -> str:
    text = " ".join(str(value or "").split()).strip()
    text = re.sub(r"^(?:outros?\s+)?outro\s+nome\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.rstrip(" :").strip()


def _factor_type(name: str) -> str:
    folded = _fold(name)
    if "preco" in folded:
        return "preco"
    if "qualidade" in folded:
        return "qualidade"
    return "outro"


def _factor(name: object, weight: object) -> dict[str, Any] | None:
    cleaned_name = _clean_factor_name(name)
    if not cleaned_name:
        return None
    try:
        cleaned_weight = float(str(weight).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if cleaned_weight < 0:
        return None
    return {
        "nome": cleaned_name,
        "peso": int(cleaned_weight) if cleaned_weight.is_integer() else cleaned_weight,
        "tipo": _factor_type(cleaned_name),
    }


def _split_factor_lines(value: str) -> list[str]:
    return [
        line.strip()
        for line in re.split(r"\n|\s*[\u2022\u00b7]\s*|\s+\ufffd\s+", value)
        if line.strip()
    ]


def _factors_from_text(value: object) -> list[dict[str, Any]]:
    text = _text(value)
    if not text:
        return []

    factors: list[dict[str, Any]] = []
    for line in _split_factor_lines(text):
        match = re.match(r"^(.*?)(?:\s*:?)\s*(\d+(?:[,.]\d+)?)\s*%\s*$", line)
        if not match:
            continue
        factor = _factor(match.group(1), match.group(2))
        if factor and factor not in factors:
            factors.append(factor)
    return factors


def _factors_from_value(value: object) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return _factors_from_text(value)

    if not isinstance(value, list):
        return []

    factors: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        factor = _factor(
            item.get("nome") or item.get("name") or item.get("label") or item.get("factor"),
            item.get("peso", item.get("weight", item.get("percentagem", item.get("percentage")))),
        )
        if factor and factor not in factors:
            factors.append(factor)
    return factors


def _criterion_type(value: object, factors: list[dict[str, Any]]) -> str | None:
    text = _text(value)
    if text:
        folded = _fold(text)
        if "multi" in folded:
            return "Multifator"
        if "mono" in folded:
            return "Monofator"
        return text
    if len(factors) > 1:
        return "Multifator"
    if len(factors) == 1:
        return "Monofator"
    return None


def _short_legal_summary(value: object) -> str | None:
    text = _text(value)
    if not text:
        return None
    folded = _fold(text)
    if "melhor relacao qualidade-preco" in folded or ("melhor rela" in folded and "qualidade" in folded and "pre" in folded):
        return "Melhor relação qualidade-preço"
    if "proposta economicamente mais vantajosa" in folded:
        return "Proposta economicamente mais vantajosa"
    return None


def _summary(value: object, detail: object, factors: list[dict[str, Any]]) -> str | None:
    if factors:
        return " · ".join(f"{factor['nome']} {factor['peso']}%" for factor in factors)

    text = _text(value)
    if text:
        return _short_legal_summary(text) or text
    return _short_legal_summary(detail)


def normalizar_criterio_adjudicacao(
    criterio_tipo: object = None,
    criterio_resumo: object = None,
    criterio_detalhe: object = None,
    criterio_fatores: object = None,
) -> dict[str, str | None]:
    """Returns display-safe fields while preserving the original legal detail."""

    detail = _text(criterio_detalhe)
    factors = (
        _factors_from_value(criterio_fatores)
        or _factors_from_text(criterio_resumo)
        or _factors_from_text(detail)
    )
    return {
        "criterio_tipo": _criterion_type(criterio_tipo, factors),
        "criterio_resumo": _summary(criterio_resumo, detail, factors),
        "criterio_detalhe": detail,
        "criterio_fatores": json.dumps(factors, ensure_ascii=False) if factors else None,
    }