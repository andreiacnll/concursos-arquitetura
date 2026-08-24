"""Extração determinística de programas de intervenção territorial.

O módulo é genérico para concursos de arquitetura paisagista, urbanismo,
espaço público e obras de urbanização com componente de projeto. Não depende
da Lisboa SRU nem de um concurso específico.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable


VERSION = "intervention-program-v3.1"


@dataclass(frozen=True)
class ThemeRule:
    key: str
    label: str
    patterns: tuple[str, ...]


THEMES = (
    ThemeRule(
        "program_intervention",
        "Programa de intervenção",
        (
            r"programa\s+de\s+intervencao",
            r"objeto\s+da\s+intervencao",
            r"ambito\s+da\s+intervencao",
            r"objetivos?\s+da\s+intervencao",
            r"area\s+de\s+intervencao",
            r"\bintervencao\b",
        ),
    ),
    ThemeRule(
        "landscape_public_space",
        "Arquitetura paisagista e espaço público",
        (
            r"arquitetura\s+paisagista",
            r"paisagismo",
            r"espaco\s+publico",
            r"parque\s+urbano",
            r"arranjos?\s+exteriores?",
            r"espacos?\s+verdes?",
        ),
    ),
    ThemeRule(
        "terrain_modeling",
        "Modelação do terreno",
        (
            r"modelacao\s+do\s+terreno",
            r"movimentos?\s+de\s+terras",
            r"terraplenagem",
            r"topografia",
            r"cotas?\s+altimetricas?",
            r"taludes?",
        ),
    ),
    ThemeRule(
        "mobility_access",
        "Mobilidade e acessos",
        (
            r"mobilidade",
            r"acessos?",
            r"circulacao\s+pedonal",
            r"ciclovia",
            r"estacionamento",
            r"acessibilidade",
            r"rede\s+viaria",
        ),
    ),
    ThemeRule(
        "green_system",
        "Sistema verde",
        (
            r"sistema\s+verde",
            r"estrutura\s+verde",
            r"arborizacao",
            r"vegetacao",
            r"plantacao",
            r"especies\s+vegetais",
            r"coberto\s+vegetal",
        ),
    ),
    ThemeRule(
        "drainage",
        "Drenagem",
        (
            r"drenagem",
            r"aguas?\s+pluviais?",
            r"bacia\s+de\s+retencao",
            r"sistema\s+de\s+retencao",
            r"infiltracao",
            r"suds",
        ),
    ),
    ThemeRule(
        "infrastructure_specialties",
        "Infraestruturas e especialidades",
        (
            r"infraestruturas?",
            r"especialidades",
            r"rede\s+de\s+abastecimento",
            r"saneamento",
            r"iluminacao\s+publica",
            r"telecomunicacoes",
            r"eletricidade",
            r"gas",
        ),
    ),
    ThemeRule(
        "bim_requirements",
        "Requisitos BIM",
        (
            r"\bbim\b",
            r"building\s+information\s+modelling",
            r"modelo\s+federado",
            r"modelo\s+de\s+informacao",
            r"cde\b",
            r"common\s+data\s+environment",
        ),
    ),
    ThemeRule(
        "technical_team",
        "Equipa técnica",
        (
            r"equipa\s+tecnica",
            r"coordenador\s+de\s+projeto",
            r"arquiteto\s+paisagista",
            r"engenheiro",
            r"tecnico\s+responsavel",
            r"qualificacoes?\s+da\s+equipa",
        ),
    ),
    ThemeRule(
        "phases_deadlines",
        "Fases e prazos",
        (
            r"fases?\s+do\s+projeto",
            r"estudo\s+previo",
            r"anteprojeto",
            r"projeto\s+de\s+execucao",
            r"prazo\s+de\s+execucao",
            r"cronograma",
            r"assistencia\s+tecnica",
        ),
    ),
)

LANDSCAPE_SIGNALS = (
    (r"arquitetura\s+paisagista", 8),
    (r"parque\s+urbano", 7),
    (r"obras?\s+de\s+urbanizacao", 6),
    (r"espaco\s+publico", 5),
    (r"arranjos?\s+exteriores?", 4),
    (r"urbanismo", 4),
    (r"sistema\s+verde", 3),
    (r"drenagem", 2),
    (r"mobilidade", 2),
    (r"modelacao\s+do\s+terreno", 2),
)

BUILDING_SIGNALS = (
    r"escola\s+(?:basica|secundaria)",
    r"edificio\s+escolar",
    r"programa\s+funcional",
    r"salas?\s+de\s+aula",
)


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    ).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def compact(value: object, limit: int = 760) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" ,;:-") + "…"


def _source_priority(filename: str) -> int:
    name = normalize(filename)
    if "programa procedimento" in name or re.search(r"\bpc\b", name):
        return 130
    if "caderno encargos" in name or re.search(r"\bce\b", name):
        return 120
    if "termos referencia" in name:
        return 110
    if "eir" in name:
        return 35
    return 80




def _source_role(filename: str) -> str:
    name = normalize(filename)
    if "eir" in name or "bim" in name:
        return "eir"
    if "termos referencia" in name or "programa tecnico" in name or "programa preliminar" in name:
        return "terms_reference"
    if "caderno encargos" in name or re.search(r"\bce\b", name):
        return "contract_specifications"
    if "programa procedimento" in name or re.search(r"\bpc\b", name):
        return "procedure_program"
    return "other"


_ADMIN_MARKERS = (
    "concorrente",
    "proposta",
    "procedimento",
    "juri",
    "pontuacao",
    "fator",
    "subfator",
    "anexo",
    "plataforma",
    "anogov",
    "exclusao",
    "adjudicacao",
    "experiencia da equipa",
    "declaracao",
    "publicidade no jornal",
    "audiencia previa",
    "relatorio preliminar",
)


def _theme_accepts_source(theme_key: str, filename: str) -> bool:
    role = _source_role(filename)
    if theme_key == "bim_requirements":
        return role == "eir"
    if theme_key == "phases_deadlines":
        return role == "contract_specifications"
    if theme_key == "technical_team":
        return False

    # O Programa do Procedimento pode conter uma síntese curta e válida do
    # objeto/âmbito técnico. É aceite apenas no cartão geral do programa de
    # intervenção; nunca alimenta automaticamente os temas especializados.
    if theme_key == "program_intervention":
        return role in {
            "procedure_program",
            "terms_reference",
            "contract_specifications",
            "other",
        }

    if theme_key in {
        "landscape_public_space",
        "terrain_modeling",
        "mobility_access",
        "green_system",
        "drainage",
        "infrastructure_specialties",
    }:
        return role in {"terms_reference", "contract_specifications", "other"}
    return True


def _low_quality_sentence(sentence: str) -> bool:
    raw = compact(sentence, 900)
    normalized = normalize(raw)

    if not raw or len(raw) < 45:
        return True
    if re.search(r"\.{4,}", raw):
        return True
    if re.search(r"\b\d+\s*\|\s*\d+\b", raw):
        return True
    if len(re.findall(r"\.(?:pdf|dwg|dxf|ifc|rvt|xlsx?)\b", raw, re.I)) >= 2:
        return True
    if any(
        marker in normalized
        for marker in (
            "codigos 3 caracteres",
            "codigos 2 caracteres",
            "especialidade codigos",
            "spreadsheet source",
            "content types xml",
            "printersettings",
        )
    ):
        return True

    tokens = re.findall(r"\b[A-Za-zÀ-ÿ0-9]+\b", raw)
    if not tokens:
        return True

    short_codes = sum(
        1
        for token in tokens
        if token.isupper() and 2 <= len(token) <= 4
    )
    if len(tokens) >= 12 and short_codes / len(tokens) > 0.28:
        return True

    words = [
        token
        for token in tokens
        if re.search(r"[A-Za-zÀ-ÿ]", token)
    ]
    if len(words) < 7:
        return True

    return False


def _identity_text(ficha: dict[str, Any]) -> str:
    identificacao = ficha.get("identificacao") or {}
    values = (
        identificacao.get("titulo"),
        identificacao.get("objeto"),
        identificacao.get("tipo_procedimento"),
        ficha.get("objeto"),
        ficha.get("resumo"),
    )
    return " ".join(compact(value, 2000) for value in values if value)


def _document_entries(textos: dict[str, str]) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for filename, raw in (textos or {}).items():
        if not isinstance(raw, str) or not raw.strip():
            continue
        entries.append((str(filename), raw, normalize(raw)))
    entries.sort(
        key=lambda item: (
            -_source_priority(item[0]),
            item[0].casefold(),
        )
    )
    return entries


def _variant_score(ficha: dict[str, Any], documentos: list[tuple[str, str, str]]) -> int:
    title_text = normalize(_identity_text(ficha))
    source = title_text + " " + " ".join(item[2][:12000] for item in documentos[:12])
    score = sum(weight for pattern, weight in LANDSCAPE_SIGNALS if re.search(pattern, source))
    if any(re.search(pattern, title_text) for pattern, _ in LANDSCAPE_SIGNALS):
        score += 3
    if any(re.search(pattern, title_text) for pattern in BUILDING_SIGNALS):
        score -= 5
    return score


def _sentences(raw: str) -> Iterable[str]:
    for paragraph in re.split(r"\n\s*\n+|(?<=\n)\s*(?=\d+\.\d+)", raw):
        cleaned = compact(paragraph, 1800)
        if not cleaned:
            continue
        for sentence in re.split(r"(?<=[.!?;:])\s+|\n+", cleaned):
            sentence = compact(sentence, 520)
            if 45 <= len(sentence) <= 520 and not _low_quality_sentence(
                sentence
            ):
                yield sentence


def _theme_items(
    documentos: list[tuple[str, str, str]],
    rule: ThemeRule,
    *,
    limit: int = 3,
) -> tuple[list[str], list[str]]:
    items: list[str] = []
    sources: list[str] = []
    seen: set[str] = set()

    for filename, raw, _ in documentos:
        if not _theme_accepts_source(rule.key, filename):
            continue
        for sentence in _sentences(raw):
            normalized = normalize(sentence)
            if any(marker in normalized for marker in _ADMIN_MARKERS):
                continue
            if not any(re.search(pattern, normalized) for pattern in rule.patterns):
                continue

            if rule.key == "program_intervention" and not any(
                marker in normalized
                for marker in (
                    "objetivo",
                    "ambito",
                    "intervencao",
                    "pretende",
                    "visa",
                    "compreende",
                    "inclui",
                )
            ):
                continue

            if rule.key == "mobility_access" and not any(
                marker in normalized
                for marker in ("circulacao", "acessibilidade", "rede viaria", "pedonal", "ciclovia", "estacionamento", "acesso viario")
            ):
                continue
            if rule.key == "terrain_modeling" and not any(
                marker in normalized
                for marker in ("terreno", "terras", "topografia", "cotas", "talude", "terraplenagem")
            ):
                continue

            concise = sentence
            if len(concise) > 260:
                concise = concise[:257].rstrip(" ,;:-") + "…"
            signature = normalize(concise)[:220]
            if signature in seen:
                continue
            seen.add(signature)
            items.append(concise)
            if filename not in sources:
                sources.append(filename)
            if len(items) >= limit:
                return items, sources
    return items, sources


def _summary(
    ficha: dict[str, Any],
    documentos: list[tuple[str, str, str]],
) -> tuple[str, str]:
    candidates: list[tuple[int, str, str]] = []
    for filename, raw, _ in documentos:
        if _source_role(filename) not in {"terms_reference", "contract_specifications", "other"}:
            continue
        for sentence in _sentences(raw):
            normalized = normalize(sentence)
            if any(marker in normalized for marker in _ADMIN_MARKERS):
                continue
            score = 0
            for pattern, weight in LANDSCAPE_SIGNALS:
                if re.search(pattern, normalized):
                    score += weight
            if "objeto" in normalized or "intervencao" in normalized:
                score += 3
            if "pretende" in normalized or "visa" in normalized:
                score += 2
            if score >= 6:
                candidates.append(
                    (
                        score + (_source_priority(filename) / 20),
                        sentence,
                        filename,
                    )
                )

    if candidates:
        candidates.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
        best = candidates[0]
        return compact(best[1], 900), best[2]

    fallback = (
        (ficha.get("programa") or {}).get("resumo_intervencao")
        or ficha.get("resumo")
        or _identity_text(ficha)
    )
    return compact(fallback, 900), ""


def _inconsistencies(ficha: dict[str, Any]) -> list[str]:
    values: list[str] = []
    sources = (
        (ficha.get("document_audit") or {}).get("warnings"),
        (ficha.get("document_insights") or {}).get("warnings"),
        ficha.get("avisos"),
        ficha.get("inconsistencias_documentais"),
    )
    for source in sources:
        if isinstance(source, str):
            source = [source]
        if not isinstance(source, list):
            continue
        for item in source:
            text = compact(item, 320)
            if text and text not in values:
                values.append(text)
    return values[:8]


def extract_intervention_program(
    *,
    ficha: dict[str, Any],
    textos: dict[str, str],
) -> dict[str, Any]:
    documentos = _document_entries(textos)
    score = _variant_score(ficha, documentos)
    if score < 7:
        return {
            "active": False,
            "version": VERSION,
            "score": score,
        }

    themes: dict[str, Any] = {}
    source_documents: list[str] = []
    for rule in THEMES:
        items, sources = _theme_items(documentos, rule)
        themes[rule.key] = {
            "label": rule.label,
            "items": items,
            "source_documents": sources,
            "confirmed": bool(items),
        }
        for source in sources:
            if source not in source_documents:
                source_documents.append(source)

    summary, summary_source = _summary(ficha, documentos)
    if summary_source and summary_source not in source_documents:
        source_documents.insert(0, summary_source)

    area = ""
    extraction = ficha.get("design_competition_extraction") or {}
    functional = (
        extraction.get("functional_program")
        or extraction.get("program_functional")
        or ficha.get("functional_program")
        or ficha.get("programa_funcional")
        or {}
    )
    area = compact(
        ((functional.get("area_intervencao") or {}).get("value"))
        or functional.get("total_area"),
        80,
    )

    return {
        "active": True,
        "version": VERSION,
        "score": score,
        "kind": "landscape_public_space",
        "label": "Programa de intervenção",
        "summary": summary,
        "intervention_type": "Arquitetura paisagista, urbanismo e espaço público",
        "area_intervencao": {"value": area} if area else {},
        "themes": themes,
        "inconsistencies": _inconsistencies(ficha),
        "source_documents": source_documents,
        "counts": {
            "themes": len(themes),
            "confirmed_themes": sum(1 for theme in themes.values() if theme["confirmed"]),
            "source_documents": len(source_documents),
        },
    }


def apply_intervention_program(
    *,
    ficha: dict[str, Any],
    textos: dict[str, str],
) -> dict[str, Any]:
    result = extract_intervention_program(ficha=ficha, textos=textos)
    if result.get("active"):
        ficha["analysis_variant"] = "intervention_program"
        ficha["intervention_program"] = result
        extraction = ficha.setdefault("design_competition_extraction", {})
        if isinstance(extraction, dict):
            extraction["intervention_program"] = result
    return result
