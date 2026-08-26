from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import BaseModel, Field


class InterpretedAnswer(BaseModel):
    field: str
    value: Any
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = "deterministic_rule_engine"


_SERVICE_KEYWORDS = (
    ("arquitetura", "arquitetura"),
    ("urbanismo", "urbanismo"),
    ("reabilitacao", "reabilitação"),
    ("interiores", "interiores"),
    ("consultoria", "consultoria"),
)

_STRATEGY_KEYWORDS = (
    ("cultura", "cultura"),
    ("educacao", "educação"),
    ("saude", "saúde"),
    ("habitacao", "habitação"),
    ("espaco publico", "espaço público"),
)

_COMPETENCE_KEYWORDS = (
    ("bim", "BIM"),
    ("revit", "Revit"),
    ("autocad", "AutoCAD"),
    ("sketchup", "SketchUp"),
    ("coordena", "coordenação"),
    ("reabilitacao", "reabilitação"),
    ("visualiza", "visualização"),
    ("gestao", "gestão"),
    ("arquitetura", "arquitetura"),
    ("urbanismo", "urbanismo"),
    ("interiores", "interiores"),
    ("consultoria", "consultoria"),
    ("modelacao", "modelação"),
    ("projeto", "projeto"),
)

_VERBOS_INICIAIS = (
    "fazemos",
    "prestamos",
    "apostamos em",
    "apostamos",
    "queremos apostar em",
    "temos",
    "somos",
    "atuamos em",
    "atuamos",
)


def _remover_acentos(texto: str) -> str:
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caractere)
    )


def _normalizar_texto(texto: Any) -> str:
    return _remover_acentos(str(texto or "").strip().lower())


def _texto_limpo(texto: Any) -> str:
    return re.sub(r"\s+", " ", str(texto or "").strip())


def _desembrulhar_answer(answer: Any) -> Any:
    if isinstance(answer, dict):
        for chave in ("value", "answer", "text", "description"):
            if chave in answer:
                return answer[chave]
    return answer


def _segmentar_texto(texto: str) -> list[str]:
    texto = _texto_limpo(texto)
    if not texto:
        return []

    bruto = re.split(
        r"\s*(?:,|;|/|\||\+|\be\b|\band\b)\s*",
        texto,
        flags=re.IGNORECASE,
    )

    segmentos: list[str] = []
    for segmento in bruto:
        limpo = _texto_limpo(segmento)
        if limpo:
            segmentos.append(limpo)

    if segmentos:
        return segmentos

    return [texto]


def _remover_verbos_iniciais(texto: str) -> str:
    resultado = texto.strip()
    normalizado = _normalizar_texto(resultado)

    for verbo in sorted(_VERBOS_INICIAIS, key=len, reverse=True):
        verbo_norm = _normalizar_texto(verbo)
        if normalizado.startswith(verbo_norm):
            resultado = resultado[len(verbo):].strip()
            break

    return resultado


def _extrair_por_palavras_chave(
    answer: Any,
    palavras_chave: tuple[tuple[str, str], ...],
) -> list[str]:
    texto_base = _normalizar_texto(answer)
    valores: list[str] = []

    for termo_normalizado, valor_canonico in palavras_chave:
        if termo_normalizado in texto_base:
            valores.append(valor_canonico)

    if valores:
        return list(dict.fromkeys(valores))

    if isinstance(answer, list):
        return [
            _texto_limpo(item)
            for item in answer
            if _texto_limpo(item)
        ]

    if isinstance(answer, dict):
        return [
            _texto_limpo(item)
            for item in answer.values()
            if _texto_limpo(item)
        ]

    segmentos = [
        _remover_verbos_iniciais(segmento)
        for segmento in _segmentar_texto(str(answer))
    ]
    return [
        segmento
        for segmento in segmentos
        if segmento
    ]


def _interpretar_company_services(answer: Any) -> list[str]:
    valores = _extrair_por_palavras_chave(answer, _SERVICE_KEYWORDS)
    return valores


def _interpretar_company_strategy(answer: Any) -> list[str]:
    valores = _extrair_por_palavras_chave(answer, _STRATEGY_KEYWORDS)
    return valores


def _interpretar_team_competences(answer: Any) -> list[str]:
    valores = _extrair_por_palavras_chave(answer, _COMPETENCE_KEYWORDS)
    if valores:
        return valores

    if isinstance(answer, list):
        return [
            _texto_limpo(item)
            for item in answer
            if _texto_limpo(item)
        ]

    if isinstance(answer, dict):
        return [
            _texto_limpo(item)
            for item in answer.values()
            if _texto_limpo(item)
        ]

    segmentos = [
        _remover_verbos_iniciais(segmento)
        for segmento in _segmentar_texto(str(answer))
    ]
    return [segmento for segmento in segmentos if segmento]


def _interpretar_company_identity(answer: Any) -> Any:
    if isinstance(answer, dict):
        resultado: dict[str, str] = {}
        for chave in ("company_name", "description", "location", "website"):
            valor = _texto_limpo(answer.get(chave))
            if valor:
                resultado[chave] = valor

        if resultado:
            return resultado

        texto = " ".join(
            _texto_limpo(valor)
            for valor in answer.values()
            if _texto_limpo(valor)
        ).strip()
        return texto

    return _texto_limpo(answer)


def interpret_answer(
    field: str,
    answer: Any,
) -> InterpretedAnswer:
    """
    Interpreta respostas livres de entrevistas em dados estruturados.

    A camada é determinística e serve como ponto de entrada para uma
    futura integração LLM sem alterar o contrato do updater.
    """
    raw_answer = _desembrulhar_answer(answer)

    if field == "company.services":
        value = _interpretar_company_services(raw_answer)
        confidence = 0.95 if value else 0.0
    elif field == "company.strategy":
        value = _interpretar_company_strategy(raw_answer)
        confidence = 0.95 if value else 0.0
    elif field == "company.identity":
        value = _interpretar_company_identity(raw_answer)
        confidence = 0.9 if _texto_limpo(value) else 0.0
    elif field == "team.competences":
        value = _interpretar_team_competences(raw_answer)
        confidence = 0.9 if value else 0.0
    else:
        value = raw_answer
        confidence = 0.0

    return InterpretedAnswer(
        field=field,
        value=value,
        confidence=confidence,
        source="deterministic_rule_engine",
    )
