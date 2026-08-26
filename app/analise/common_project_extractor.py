"""Núcleo documental comum para concursos de projeto.

Extrai informação administrativa e de submissão antes dos módulos de domínio.
É deliberadamente determinístico e conserva a fonte de cada valor.
"""

from __future__ import annotations

import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zipfile import BadZipFile, ZipFile

from app.analise.submission_requirements import (
    extract_submission_requirements,
)


VERSION = "common-project-extractor-v1"
DOCX_EXTENSIONS = {".docx", ".docm"}

MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

GENERIC_PROCEDURE_TYPES = {
    "",
    "concurso publico",
    "procedimento de contratacao publica",
    "concurso de arquitetura",
}


def _clean(value: object) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").replace("\x00", " "),
    ).strip()


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold()
    return re.sub(r"[^a-z0-9%€.,:/+\-\s]+", " ", text)


def _docx_paragraph_text(root: ET.Element) -> list[str]:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(namespace + "p"):
        fragments: list[str] = []
        for element in paragraph.iter():
            if element.tag == namespace + "t" and element.text:
                fragments.append(element.text)
            elif element.tag in {
                namespace + "tab",
                namespace + "br",
                namespace + "cr",
            }:
                fragments.append("\t" if element.tag.endswith("tab") else "\n")
        text = _clean("".join(fragments))
        if text:
            paragraphs.append(text)
    return paragraphs


def extract_docx_text(path: Path) -> str:
    """Lê DOCX/DOCM sem dependência externa, incluindo tabelas e cabeçalhos."""
    parts: list[str] = []
    wanted = re.compile(
        r"^word/(?:document|header\d+|footer\d+|footnotes|endnotes)\.xml$",
        re.IGNORECASE,
    )
    try:
        with ZipFile(path) as archive:
            names = [
                name
                for name in archive.namelist()
                if wanted.match(name)
            ]
            names.sort(
                key=lambda name: (
                    0 if name.casefold() == "word/document.xml" else 1,
                    name,
                )
            )
            for name in names:
                try:
                    root = ET.fromstring(archive.read(name))
                except (ET.ParseError, KeyError):
                    continue
                parts.extend(_docx_paragraph_text(root))
    except (BadZipFile, OSError):
        return ""
    return "\n".join(parts).strip()


def _document_priority(filename: str) -> int:
    name = _fold(Path(filename).name)
    if "anuncio" in name:
        return 150
    if re.search(r"\bpc\b", name) or "programa do procedimento" in name:
        return 140
    if re.search(r"\bce\b", name) or "caderno de encargos" in name:
        return 130
    if "convite" in name:
        return 125
    if "fator" in name or "pontuacao" in name:
        return 110
    if "eir" in name:
        return 30
    return 80


def _iter_documents(
    textos: dict[str, str],
) -> list[tuple[str, str, str, int]]:
    blocked = {
        "ficha.json",
        "analise.json",
        "textos.json",
        "consolidated.json",
        "dados_concurso.txt",
    }
    output: list[tuple[str, str, str, int]] = []
    for raw_name, raw_text in (textos or {}).items():
        filename = str(raw_name or "documento.txt")
        if Path(filename).name.casefold() in blocked:
            continue
        raw = str(raw_text or "").replace("\x00", " ")
        if not raw.strip():
            continue
        output.append(
            (
                filename,
                raw,
                _fold(raw),
                _document_priority(filename),
            )
        )
    output.sort(key=lambda item: (-item[3], item[0].casefold()))
    return output


def _date_from_text(value: object) -> tuple[str, str] | None:
    raw = _clean(value)
    if not raw:
        return None
    folded = _fold(raw)

    textual = re.search(
        r"\b(\d{1,2})\s+de\s+"
        r"(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|"
        r"setembro|outubro|novembro|dezembro)"
        r"\s+de\s+(\d{4})\b",
        folded,
    )
    hour = re.search(
        r"\b(?:as|às|pelas)?\s*(\d{1,2})[:h.](\d{2})\b",
        folded,
    )
    if textual:
        day = int(textual.group(1))
        month = MONTHS[textual.group(2)]
        year = int(textual.group(3))
    else:
        numeric = re.search(
            r"\b(?:(\d{4})[./-](\d{1,2})[./-](\d{1,2})|"
            r"(\d{1,2})[./-](\d{1,2})[./-](\d{4}))\b",
            raw,
        )
        if not numeric:
            return None
        if numeric.group(1):
            year, month, day = map(
                int,
                (
                    numeric.group(1),
                    numeric.group(2),
                    numeric.group(3),
                ),
            )
        else:
            day, month, year = map(
                int,
                (
                    numeric.group(4),
                    numeric.group(5),
                    numeric.group(6),
                ),
            )

    try:
        parsed = datetime(
            year,
            month,
            day,
            int(hour.group(1)) if hour else 0,
            int(hour.group(2)) if hour else 0,
        )
    except ValueError:
        return None

    publication = parsed.strftime("%d/%m/%Y")
    deadline = parsed.strftime("%d-%m-%Y")
    if hour:
        deadline += parsed.strftime(" %H:%M")
    return publication, deadline


def _window(
    raw: str,
    pattern: str,
    *,
    before: int = 120,
    after: int = 650,
) -> str:
    match = re.search(pattern, raw, re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - before)
    end = min(len(raw), match.end() + after)
    return _clean(raw[start:end])


def _best_labeled_date(
    documents: list[tuple[str, str, str, int]],
    patterns: tuple[str, ...],
) -> dict[str, Any] | None:
    candidates: list[tuple[int, str, str, str, str]] = []
    for filename, raw, _normalized, priority in documents:
        for pattern in patterns:
            for match in re.finditer(pattern, raw, re.IGNORECASE):
                context = raw[
                    match.start():
                    min(len(raw), match.end() + 900)
                ]
                parsed = _date_from_text(context)
                if not parsed:
                    continue
                publication, deadline = parsed
                candidates.append(
                    (
                        priority,
                        filename,
                        _clean(context)[:900],
                        publication,
                        deadline,
                    )
                )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], len(item[2])))
    priority, filename, excerpt, publication, deadline = candidates[0]
    return {
        "publication": publication,
        "deadline": deadline,
        "source_document": filename,
        "excerpt": excerpt,
        "confidence": 0.96 if priority >= 120 else 0.86,
    }


def _format_money(raw: str) -> str:
    compact = re.sub(r"\s+", "", raw)
    if "," in compact and "." in compact:
        if compact.rfind(",") > compact.rfind("."):
            normalized = compact.replace(".", "").replace(",", ".")
        else:
            normalized = compact.replace(",", "")
    elif "," in compact:
        head, tail = compact.rsplit(",", 1)
        normalized = (
            f"{head.replace('.', '')}.{tail}"
            if len(tail) == 2
            else compact.replace(".", "").replace(",", "")
        )
    else:
        parts = compact.split(".")
        normalized = (
            "".join(parts)
            if len(parts) > 2 or (len(parts) == 2 and len(parts[-1]) == 3)
            else compact
        )
    try:
        number = float(normalized)
    except ValueError:
        return _clean(raw) + " €"
    decimals = bool(re.search(r"[,.]\d{2}$", compact))
    formatted = f"{number:,.2f}" if decimals else f"{number:,.0f}"
    formatted = (
        formatted.replace(",", "§")
        .replace(".", ",")
        .replace("§", " ")
    )
    return formatted + " €"


def _extract_base_price(
    documents: list[tuple[str, str, str, int]],
) -> dict[str, Any] | None:
    amount = (
        r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})?"
        r"|\d{4,}(?:[,.]\d{2})?)"
    )
    patterns = (
        r"pre[cç]o\s+base(?:\s+do\s+procedimento)?"
        r".{0,180}?" + amount + r"\s*(?:€|eur)",
        r"valor\s+base(?:\s+do\s+procedimento)?"
        r".{0,180}?" + amount + r"\s*(?:€|eur)",
        r"honor[aá]rios?.{0,180}?" + amount + r"\s*(?:€|eur)",
    )
    candidates: list[tuple[int, str, str, str]] = []
    for filename, raw, normalized, priority in documents:
        for pattern in patterns:
            match = re.search(pattern, normalized, re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            candidates.append(
                (
                    priority,
                    filename,
                    _format_money(match.group(1)),
                    _window(raw, r"pre[cç]o\s+base|valor\s+base|honor[aá]rios?"),
                )
            )
    if not candidates:
        return None
    candidates.sort(key=lambda item: -item[0])
    priority, filename, value, excerpt = candidates[0]
    return {
        "value": value,
        "source_document": filename,
        "excerpt": excerpt,
        "confidence": 0.97 if priority >= 120 else 0.86,
    }


def _criteria_window(
    documents: list[tuple[str, str, str, int]],
) -> tuple[str, str, int]:
    patterns = (
        r"crit[eé]rio(?:s)?\s+de\s+adjudica[cç][aã]o",
        r"modelo\s+de\s+avalia[cç][aã]o",
        r"proposta\s+economicamente\s+mais\s+vantajosa",
        r"fatores?\s+de\s+avalia[cç][aã]o",
    )
    candidates: list[tuple[int, str, str]] = []
    for filename, raw, _normalized, priority in documents:
        for pattern in patterns:
            match = re.search(pattern, raw, re.IGNORECASE)
            if not match:
                continue
            context = _clean(
                raw[
                    match.start():
                    min(len(raw), match.end() + 2500)
                ]
            )
            candidates.append((priority, filename, context))
    if not candidates:
        return "", "", 0
    candidates.sort(key=lambda item: (-item[0], len(item[2])))
    priority, filename, context = candidates[0]
    return filename, context, priority


def _extract_criteria(
    documents: list[tuple[str, str, str, int]],
) -> dict[str, Any] | None:
    filename, context, priority = _criteria_window(documents)
    if not context:
        return None
    folded = _fold(context)

    factors: list[tuple[str, str | None]] = []
    rules = (
        ("Qualidade", r"qualidade|m[eé]rito\s+t[eé]cnico|fator\s*a\b"),
        ("Preço", r"pre[cç]o|fator\s*b\b"),
        ("Prazo", r"prazo"),
        ("Equipa", r"equipa|experi[eê]ncia"),
    )

    for label, pattern in rules:
        if not re.search(pattern, folded, re.IGNORECASE):
            continue
        percentage = None
        grouped_pattern = f"(?:{pattern})"
        forward = re.search(
            grouped_pattern
            + r".{0,140}?(\d{1,3}(?:[,.]\d+)?)\s*%",
            folded,
            re.IGNORECASE | re.DOTALL,
        )
        reverse = re.search(
            r"(\d{1,3}(?:[,.]\d+)?)\s*%.{0,140}?"
            + grouped_pattern,
            folded,
            re.IGNORECASE | re.DOTALL,
        )
        match = forward or reverse
        if match:
            percentage = match.group(1).replace(".", ",") + "%"
        factors.append((label, percentage))

    if not factors:
        return None

    type_value = " + ".join(label for label, _ in factors[:4])
    weighted = [
        f"{label} {percentage}"
        for label, percentage in factors
        if percentage
    ]
    summary = " • ".join(weighted)
    return {
        "type": type_value,
        "summary": summary,
        "detail": context[:1800],
        "percentages": [
            {
                "criterio": label,
                "percentagem": percentage,
            }
            for label, percentage in factors
        ],
        "source_document": filename,
        "excerpt": context[:900],
        "confidence": 0.95 if priority >= 120 else 0.82,
    }


def _list_items_from_section(text: str) -> list[str]:
    items: list[str] = []
    patterns = (
        r"(?m)^\s*(?:[a-z]\)|\d+(?:\.\d+)*[.)-])\s+(.{8,260})$",
        r"(?m)^\s*[•\-–]\s+(.{8,260})$",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = _clean(match.group(1)).strip(" .;:-")
            folded = _fold(value)
            if (
                len(value) < 8
                or len(value) > 240
                or "indice" in folded
                or re.search(r"\.{4,}", value)
            ):
                continue
            items.append(value)
    return list(dict.fromkeys(items))[:24]


def _fallback_deliverables(
    documents: list[tuple[str, str, str, int]],
) -> tuple[list[str], str]:
    heading = re.compile(
        r"(?im)^\s*(?:(?:artigo|cl[aá]usula)\s+\d+(?:\.\d+)?"
        r"\s*[.ºªoa]*\s*[-–—:]?\s*)?"
        r"(?:documentos?|elementos?|pe[cç]as?)"
        r"(?:\s+que\s+constituem)?\s+(?:a|da)\s+proposta[^\n]*$"
    )
    next_heading = re.compile(
        r"(?im)^\s*(?:artigo|cl[aá]usula)\s+\d+(?:\.\d+)?"
    )

    for filename, raw, _normalized, _priority in documents:
        match = heading.search(raw)
        if not match:
            continue
        next_match = next_heading.search(raw, match.end())
        end = next_match.start() if next_match else min(len(raw), match.end() + 12000)
        section = raw[match.start():end]
        items = _list_items_from_section(section)
        if items:
            return items, filename
    return [], ""


def _submission_deliverables(
    textos: dict[str, str],
    documents: list[tuple[str, str, str, int]],
) -> tuple[dict[str, Any], list[str], str]:
    requirements = extract_submission_requirements(textos)
    groups = requirements.get("groups") or {}
    values: list[str] = []
    source = ""

    for group_name in (
        "participant_documents",
        "design_work",
        "complementary_documents",
    ):
        for item in groups.get(group_name) or []:
            if not isinstance(item, dict):
                continue
            title = _clean(item.get("title"))
            if title and title not in values:
                values.append(title)
            source = source or _clean(item.get("source_document"))

    if not values:
        values, source = _fallback_deliverables(documents)
    return requirements, values[:18], source


def infer_procedure_type(
    concurso: dict[str, Any],
    documents: list[tuple[str, str, str, int]],
) -> str:
    title = _fold(concurso.get("titulo"))
    if re.search(r"conce[cç][aã]o\s*[-–—]?\s*constru[cç][aã]o", title):
        return "Conceção-Construção"
    if re.search(r"concurso\s+(?:p[uú]blico\s+)?de?\s*conce[cç][aã]o", title):
        return "Concurso de conceção"
    current = _clean(concurso.get("tipo_procedimento"))
    if _fold(current) not in GENERIC_PROCEDURE_TYPES:
        return current
    for _filename, raw, _normalized, _priority in documents:
        folded = _fold(raw[:7000])
        if "concurso publico internacional" in folded:
            return "Concurso Público Internacional"
        if "concurso publico" in folded:
            return "Concurso Público"
    return current


def extract_common_project_data(
    *,
    textos: dict[str, str],
    concurso: dict[str, Any],
) -> dict[str, Any]:
    documents = _iter_documents(textos)

    publication = _best_labeled_date(
        documents,
        (
            r"data\s+de\s+publica[cç][aã]o",
            r"publica[cç][aã]o\s+do\s+an[uú]ncio",
            r"publicad[oa]\s+em",
            r"data\s+do\s+an[uú]ncio",
        ),
    )
    deadline = _best_labeled_date(
        documents,
        (
            r"prazo\s+para\s+(?:a\s+)?apresenta[cç][aã]o\s+das?\s+propostas",
            r"termo\s+do\s+prazo\s+para\s+(?:a\s+)?apresenta[cç][aã]o",
            r"data\s+limite\s+(?:de|para)\s+(?:a\s+)?entrega",
            r"prazo\s+de\s+entrega\s+das?\s+propostas",
            r"apresenta[cç][aã]o\s+das?\s+propostas\s+at[eé]",
        ),
    )
    price = _extract_base_price(documents)
    criteria = _extract_criteria(documents)
    submission, deliverables, deliverables_source = _submission_deliverables(
        textos,
        documents,
    )
    procedure_type = infer_procedure_type(concurso, documents)

    result = {
        "active": bool(documents),
        "version": VERSION,
        "procedure_type": procedure_type,
        "publication_date": (
            {
                "value": publication["publication"],
                "source_document": publication["source_document"],
                "evidence_excerpt": publication["excerpt"],
                "confidence": publication["confidence"],
            }
            if publication
            else {}
        ),
        "submission_deadline": (
            {
                "value": deadline["deadline"],
                "source_document": deadline["source_document"],
                "evidence_excerpt": deadline["excerpt"],
                "confidence": deadline["confidence"],
            }
            if deadline
            else {}
        ),
        "base_price": price or {},
        "award_criteria": criteria or {},
        "submission_requirements": submission,
        "deliverables": deliverables,
        "deliverables_source": deliverables_source,
        "source_documents": [item[0] for item in documents],
        "counts": {
            "documents": len(documents),
            "deliverables": len(deliverables),
            "submission_groups": sum(
                len(items)
                for items in (submission.get("groups") or {}).values()
                if isinstance(items, list)
            ),
        },
    }
    return result


def _confirmed_entry(
    *,
    type_value: str,
    value: str,
    source_document: str,
    excerpt: str,
) -> dict[str, Any]:
    return {
        "type": type_value,
        "value": value,
        "date": value,
        "confirmed": True,
        "evidence": {
            "value": value,
            "source_document": source_document,
            "page": None,
            "section": type_value,
            "confidence": 0.96,
            "status": "confirmado",
            "evidence_excerpt": excerpt,
        },
    }


def _looks_corrupted_deliverables(value: object) -> bool:
    text = _clean(value)
    folded = _fold(text)
    return (
        text.startswith("{")
        or text.startswith("[")
        or "principais" in folded
        or "entregaveis da fase" in folded
        or "spreadsheet source" in folded
    )


def apply_common_project_extraction(
    *,
    ficha: dict[str, Any],
    textos: dict[str, str],
    concurso: dict[str, Any],
) -> dict[str, Any]:
    result = extract_common_project_data(
        textos=textos,
        concurso=concurso,
    )
    ficha["common_project_extraction"] = result
    ficha["submission_requirements"] = result["submission_requirements"]

    identification = ficha.setdefault("identificacao", {})
    if isinstance(identification, dict):
        if result.get("procedure_type"):
            current = _fold(identification.get("tipo_procedimento"))
            if current in GENERIC_PROCEDURE_TYPES:
                identification["tipo_procedimento"] = result["procedure_type"]
        if result["publication_date"].get("value"):
            identification["data_publicacao"] = result["publication_date"]["value"]
        if result["submission_deadline"].get("value"):
            identification["data_entrega_propostas"] = result["submission_deadline"]["value"]

    criteria = ficha.setdefault("criterios", {})
    if isinstance(criteria, dict) and result["award_criteria"]:
        extracted = result["award_criteria"]
        criteria["criterio_adjudicacao"] = extracted.get("type") or criteria.get(
            "criterio_adjudicacao"
        )
        criteria["resumo"] = extracted.get("summary") or criteria.get("resumo")
        criteria["detalhe"] = extracted.get("detail") or criteria.get("detalhe")
        criteria["percentagens"] = extracted.get("percentages") or criteria.get(
            "percentagens"
        )

    economy = ficha.setdefault("economia", {})
    if isinstance(economy, dict) and result["base_price"].get("value"):
        economy["valor_procedimento"] = result["base_price"]["value"]

    current_deliverables = ficha.get("entregaveis")
    current_principals = (
        current_deliverables.get("principais")
        if isinstance(current_deliverables, dict)
        else current_deliverables
    )
    if result["deliverables"]:
        ficha["entregaveis"] = {"principais": result["deliverables"]}
    elif _looks_corrupted_deliverables(current_principals):
        ficha["entregaveis"] = {"principais": []}

    insights = ficha.setdefault("document_insights", {})
    if isinstance(insights, dict):
        timeline = insights.setdefault("timeline", [])
        if not isinstance(timeline, list):
            timeline = []
            insights["timeline"] = timeline

        def add_timeline(key: str, entry: dict[str, Any]) -> None:
            if not entry.get("value"):
                return
            timeline[:] = [
                item
                for item in timeline
                if not (
                    isinstance(item, dict)
                    and _fold(item.get("type")) == _fold(key)
                )
            ]
            timeline.append(
                _confirmed_entry(
                    type_value=key,
                    value=entry["value"],
                    source_document=entry.get("source_document", ""),
                    excerpt=entry.get("evidence_excerpt", ""),
                )
            )

        add_timeline("Publicação", result["publication_date"])
        add_timeline("Entrega das propostas", result["submission_deadline"])

        procedure_summary = insights.setdefault("procedure_summary", {})
        if isinstance(procedure_summary, dict):
            if result["submission_deadline"].get("value"):
                procedure_summary["submission_deadline"] = {
                    "value": result["submission_deadline"]["value"],
                    "source_document": result["submission_deadline"].get(
                        "source_document",
                        "",
                    ),
                    "confidence": result["submission_deadline"].get(
                        "confidence",
                        0.96,
                    ),
                    "status": "confirmado",
                    "evidence_excerpt": result["submission_deadline"].get(
                        "evidence_excerpt",
                        "",
                    ),
                }
            if result["base_price"].get("value"):
                procedure_summary["base_price"] = {
                    "value": result["base_price"]["value"],
                    "source_document": result["base_price"].get(
                        "source_document",
                        "",
                    ),
                    "confidence": result["base_price"].get("confidence", 0.96),
                    "status": "confirmado",
                    "evidence_excerpt": result["base_price"].get("excerpt", ""),
                }

        if result["award_criteria"]:
            insights["award_criteria"] = [
                {
                    "factor": item["criterio"],
                    "weight": item.get("percentagem"),
                    "confirmed": True,
                    "evidence": {
                        "value": item["criterio"],
                        "source_document": result["award_criteria"].get(
                            "source_document",
                            "",
                        ),
                        "confidence": result["award_criteria"].get(
                            "confidence",
                            0.95,
                        ),
                        "status": "confirmado",
                        "evidence_excerpt": result["award_criteria"].get(
                            "excerpt",
                            "",
                        ),
                    },
                }
                for item in result["award_criteria"].get("percentages", [])
            ]

    extraction = ficha.setdefault("design_competition_extraction", {})
    if isinstance(extraction, dict):
        facts = extraction.setdefault("facts", {})
        if isinstance(facts, dict):
            mapping = {
                "publication_date": result["publication_date"],
                "submission_deadline": result["submission_deadline"],
                "procedure_value": result["base_price"],
            }
            for key, entry in mapping.items():
                if entry.get("value"):
                    facts[key] = {
                        "value": entry["value"],
                        "source_document": entry.get("source_document", ""),
                        "confidence": entry.get("confidence", 0.95),
                    }
        extraction["submission_requirements"] = result["submission_requirements"]
        extraction["common_project"] = result

    return result


__all__ = [
    "DOCX_EXTENSIONS",
    "VERSION",
    "apply_common_project_extraction",
    "extract_common_project_data",
    "extract_docx_text",
    "infer_procedure_type",
]
