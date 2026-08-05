from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import BaseModel, Field


class ExtractedFact(BaseModel):
    field: str
    value: Any
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = ""
    url: str = ""
    section: str = ""
    evidence_text: str = ""
    status: str = "confirmed"


class CompanyExtractionResult(BaseModel):
    facts: list[ExtractedFact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: str = ""


_SERVICE_RULES: tuple[tuple[str, str], ...] = (
    ("arquitetura", "arquitetura"),
    ("urbanismo", "urbanismo"),
    ("reabilitacao", "reabilitação"),
    ("reabilitação", "reabilitação"),
    ("interiores", "interiores"),
    ("consultoria", "consultoria"),
    ("paisagismo", "paisagismo"),
)

_COMPETENCE_RULES: tuple[tuple[str, str], ...] = (
    ("bim", "BIM"),
    ("revit", "Revit"),
    ("autocad", "AutoCAD"),
    ("sketchup", "SketchUp"),
    ("coordenacao", "coordenação"),
    ("coordenação", "coordenação"),
    ("reabilitacao", "reabilitação"),
    ("reabilitação", "reabilitação"),
    ("visualizacao", "visualização"),
    ("visualização", "visualização"),
    ("gestao", "gestão"),
    ("gestão", "gestão"),
    ("arquitetura", "arquitetura"),
    ("urbanismo", "urbanismo"),
    ("interiores", "interiores"),
    ("consultoria", "consultoria"),
    ("modelacao", "modelação"),
    ("modelação", "modelação"),
)

_IDENTITY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("ateli", "atelier"),
    ("estudio", "estúdio"),
    ("estúdio", "estúdio"),
    ("gabinete", "gabinete"),
    ("escritório", "escritório"),
    ("escritorio", "escritório"),
)

_PROJECT_TYPOLOGY_RULES: tuple[tuple[str, str], ...] = (
    ("habitacao", "habitação"),
    ("habitação", "habitação"),
    ("escola", "educação"),
    ("educacao", "educação"),
    ("educação", "educação"),
    ("saude", "saúde"),
    ("saúde", "saúde"),
    ("cultura", "cultura"),
    ("patrimonio", "património"),
    ("património", "património"),
    ("espaco publico", "espaço público"),
    ("espaço publico", "espaço público"),
    ("espaco público", "espaço público"),
    ("turismo", "turismo"),
    ("reabilitacao", "reabilitação"),
    ("reabilitação", "reabilitação"),
)


def _texto_limpo(valor: Any) -> str:
    if valor is None:
        return ""
    return " ".join(str(valor).strip().split())


def _sem_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(
        caractere
        for caractere in normalizado
        if not unicodedata.combining(caractere)
    )


def _normalizar(texto: Any) -> str:
    return _sem_acentos(_texto_limpo(texto).lower())


def _lista_unica(valores: list[str]) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []

    for valor in valores:
        texto = _texto_limpo(valor)
        if not texto:
            continue
        chave = _normalizar(texto)
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(texto)

    return resultado


def _extrair_por_regras(
    texto: str,
    regras: tuple[tuple[str, str], ...],
) -> list[str]:
    base = _normalizar(texto)
    encontrados: list[str] = []

    for termo, valor in regras:
        if _normalizar(termo) in base:
            encontrados.append(valor)

    return _lista_unica(encontrados)


def _extrair_services(texto: str) -> list[str]:
    return _extrair_por_regras(texto, _SERVICE_RULES)


def _extrair_competences(texto: str) -> list[str]:
    return _extrair_por_regras(texto, _COMPETENCE_RULES)


def _extrair_identity(texto: str) -> str:
    texto_limpo = _texto_limpo(texto)
    if not texto_limpo:
        return ""

    base = _normalizar(texto_limpo)
    marcadores = [valor for termo, valor in _IDENTITY_PATTERNS if _normalizar(termo) in base]
    if marcadores:
        return texto_limpo[:900]

    if len(texto_limpo) >= 40 and re.search(r"\b(atelier|est[úu]dio|gabinete|escrit[óo]rio)\b", base):
        return texto_limpo[:900]

    return ""


def _extrair_project_typologies(texto: str) -> list[str]:
    return _extrair_por_regras(texto, _PROJECT_TYPOLOGY_RULES)


def _extrair_secao(texto: str, etiqueta: str) -> str:
    padrao = rf"{re.escape(etiqueta)}\n(.*?)(?=\n[A-ZÃÁÉÍÓÚÇ ]{{4,}}\n|\Z)"
    match = re.search(padrao, texto, re.S)
    return _texto_limpo(match.group(1)) if match else ""


def _facto(
    field: str,
    value: Any,
    *,
    confidence: float,
    source: str,
    url: str = "",
    section: str = "",
    evidence_text: str = "",
    status: str = "confirmed",
) -> ExtractedFact:
    return ExtractedFact(
        field=field,
        value=value,
        confidence=confidence,
        source=source,
        url=url,
        section=section,
        evidence_text=evidence_text,
        status=status,
    )


def extract_company_information(
    text: str,
    source: str = "",
    project_names: list[str] | None = None,
    section_urls: dict[str, str] | None = None,
    section_evidence: dict[str, str] | None = None,
) -> CompanyExtractionResult:
    """
    Camada determinística de extração empresarial.

    Esta função serve como base para futuras integrações com:
    - parser documental;
    - extractor de website;
    - LLM extraction.
    """
    texto = _texto_limpo(text)
    origem = _texto_limpo(source)
    urls = section_urls or {}
    evidence = section_evidence or {}
    warnings: list[str] = []
    facts: list[ExtractedFact] = []

    if not texto:
        warnings.append("empty_text")
        return CompanyExtractionResult(
            facts=facts,
            warnings=warnings,
            source=origem,
        )

    identity_text = _extrair_secao(texto, "IDENTIDADE") or texto
    services_text = _extrair_secao(texto, "SERVICOS") or texto
    competences_text = _extrair_secao(texto, "COMPETENCIAS") or texto
    typologies_text = _extrair_secao(texto, "TIPOLOGIAS") or texto

    services = _extrair_services(services_text)
    if services:
        facts.append(
            _facto(
                "company.services",
                services,
                confidence=0.86,
                source=origem,
                url=urls.get("services", ""),
                section="services",
                evidence_text=evidence.get("services", ""),
            )
        )

    competences = _extrair_competences(competences_text)
    if competences:
        facts.append(
            _facto(
                "company.competences",
                competences,
                confidence=0.82,
                source=origem,
                url=urls.get("competences", ""),
                section="competences",
                evidence_text=evidence.get("competences", ""),
            )
        )

    identity = _extrair_identity(identity_text)
    if identity:
        facts.append(
            _facto(
                "company.identity",
                identity,
                confidence=0.78,
                source=origem,
                url=urls.get("identity", ""),
                section="identity",
                evidence_text=evidence.get("identity", identity),
            )
        )

    typologies = _extrair_project_typologies(typologies_text)
    if typologies:
        facts.append(
            _facto(
                "projects.typologies",
                typologies,
                confidence=0.82,
                source=origem,
                url=urls.get("typologies", ""),
                section="typologies",
                evidence_text=evidence.get("typologies", ""),
            )
        )

    nomes_projeto = _lista_unica(
        [
            _texto_limpo(item)
            for item in (project_names or [])
            if _texto_limpo(item)
        ]
    )
    if nomes_projeto:
        facts.append(
            _facto(
                "projects.items",
                nomes_projeto,
                confidence=0.9,
                source=origem,
                url=urls.get("projects", ""),
                section="projects",
                evidence_text=evidence.get("projects", ""),
            )
        )

    if not facts:
        warnings.append("no_structured_information_detected")

    return CompanyExtractionResult(
        facts=facts,
        warnings=warnings,
        source=origem,
    )
