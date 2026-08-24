from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


VERSION = "submission-requirements-v2"

GROUPS = (
    "participant_documents",
    "design_work",
    "complementary_documents",
    "post_selection_documents",
    "contract_deliverables",
)

GROUP_LABELS = {
    "participant_documents": "Documentos do concorrente",
    "design_work": "Trabalho de conceção",
    "complementary_documents": "Documentos complementares da entrega",
    "post_selection_documents": "Após seleção",
    "contract_deliverables": "Entregáveis do contrato",
}

BLOCKED_FILENAMES = {
    "ficha.json",
    "analise.json",
    "textos.json",
    "analise_ai.json",
    "consolidated.json",
    "presentation.json",
}

HEADING_RE = re.compile(
    r"(?im)^[ \t]*(?:artigo|cl[aá]usula)\s+"
    r"\d+(?:\.\d+)?\s*[.ººªoa]*\s*[-–—:]\s*[^\n]+"
)

SECTION_TITLES = {
    "participant": (
        r"documentos?\s+do\s+concorrente",
        r"documentos?\s+de\s+participa[cç][aã]o",
        r"documentos?\s+administrativos?\s+do\s+concorrente",
        r"documentos?\s+que\s+constituem\s+a\s+proposta",
        r"documentos?\s+da\s+proposta",
        r"elementos?\s+que\s+constituem\s+a\s+proposta",
    ),
    "design": (
        r"documentos?\s+que\s+materializam\s+os\s+trabalhos?\s+de\s+conce[cç][aã]o",
        r"elementos?\s+que\s+constituem\s+os\s+trabalhos?\s+de\s+conce[cç][aã]o",
        r"pe[cç]as\s+a\s+apresentar",
        r"elementos?\s+da\s+proposta\s+de\s+conce[cç][aã]o",
    ),
    "presentation": (
        r"modo\s+de\s+apresenta[cç][aã]o\s+dos\s+ficheiros",
        r"apresenta[cç][aã]o\s+dos\s+ficheiros",
        r"modo\s+de\s+submiss[aã]o",
    ),
    "physical": (
        r"modo\s+de\s+apresenta[cç][aã]o\s+dos\s+pain[eé]is",
        r"entrega\s+f[ií]sica\s+dos\s+pain[eé]is",
        r"apresenta[cç][aã]o\s+f[ií]sica",
    ),
    "post_selection": (
        r"habilita[cç][oõ]es",
        r"documentos?\s+de\s+habilita[cç][aã]o",
        r"documentos?\s+ap[oó]s\s+sele[cç][aã]o",
    ),
    "complementary": (
        r"documentos?\s+complementares?\s+da\s+entrega",
        r"outros\s+documentos?\s+da\s+proposta",
        r"elementos?\s+complementares?",
    ),
}


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    ).casefold()


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()


def _iter_documents(
    textos: dict[str, str],
) -> Iterable[tuple[str, str]]:
    for raw_name, raw_text in (textos or {}).items():
        name = str(raw_name or "documento.txt")
        if Path(name).name.casefold() in BLOCKED_FILENAMES:
            continue
        text = str(raw_text or "").replace("\x00", " ")
        if text.strip():
            yield name, text


def _section_heading_pattern(title_pattern: str) -> re.Pattern[str]:
    return re.compile(
        r"(?im)^[ \t]*(?:artigo|cl[aá]usula)\s+"
        r"\d+(?:\.\d+)?\s*[.ººªoa]*\s*[-–—:]\s*"
        + title_pattern
        + r"[^\n]*"
    )


def _extract_longest_section(
    text: str,
    title_patterns: tuple[str, ...],
) -> tuple[str, str] | None:
    candidates: list[tuple[str, str]] = []

    for title_pattern in title_patterns:
        heading_pattern = _section_heading_pattern(title_pattern)

        for match in heading_pattern.finditer(text):
            next_heading = HEADING_RE.search(text, match.end())
            end = next_heading.start() if next_heading else len(text)
            section = text[match.start():end].strip()

            # Exclui entradas muito curtas do índice, mas aceita
            # artigos breves de habilitações com listas pequenas.
            if len(section) < 80:
                continue

            heading = _clean(match.group(0))
            candidates.append((heading, section))

    if not candidates:
        return None

    return max(candidates, key=lambda item: len(item[1]))


def _excerpt(
    text: str,
    match: re.Match[str],
    radius_before: int = 80,
    radius_after: int = 420,
) -> str:
    start = max(0, match.start() - radius_before)
    end = min(len(text), match.end() + radius_after)
    return _clean(text[start:end])[:1000]


def _local(
    text: str,
    match: re.Match[str],
    before: int = 80,
    after: int = 500,
) -> str:
    return text[
        max(0, match.start() - before):
        min(len(text), match.end() + after)
    ]


def _subsection_text(
    section: str,
    match: re.Match[str],
    max_characters: int = 5000,
) -> str:
    """Recorta apenas o item numerado atual.

    Evita que atributos do item seguinte contaminem o atual, por exemplo
    "A3 horizontal" do Caderno a alterar a orientação dos painéis A1.
    """
    start = match.start()
    search_from = match.end()

    next_heading = re.search(
        r"(?im)^[ \t]*\d+(?:\.\d+)+[ \t]+"
        r"(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])",
        section[search_from:],
    )

    if next_heading:
        end = search_from + next_heading.start()
    else:
        end = min(len(section), start + max_characters)

    return section[start:end]


def _first_int(
    text: str,
    patterns: tuple[str, ...],
) -> int | None:
    folded = _fold(text)

    for pattern in patterns:
        match = re.search(pattern, folded, re.IGNORECASE)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if 0 < value <= 10000:
            return value

    return None


def _detect_format(text: str) -> str | None:
    folded = _fold(text)
    values: list[str] = []

    for label, pattern in (
        ("PDF", r"\bpdf\b"),
        ("JPG", r"\bjpe?g\b"),
        ("PNG", r"\bpng\b"),
        ("XLSX", r"\bxlsx?\b"),
        ("DWG", r"\bdwg\b"),
        ("DXF", r"\bdxf\b"),
        ("IFC", r"\bifc\b"),
        ("RVT", r"\brvt\b"),
        ("MP4", r"\bmp4\b"),
    ):
        if re.search(pattern, folded):
            values.append(label)

    return " + ".join(values) if values else None


def _detect_page_size(text: str) -> str | None:
    match = re.search(
        r"\b(?:din\s+)?(a[0-4])\b",
        _fold(text),
        re.IGNORECASE,
    )
    return match.group(1).upper() if match else None


def _detect_orientation(text: str) -> str | None:
    folded = _fold(text)

    if "horizontal" in folded:
        return "horizontal"
    if "vertical" in folded:
        return "vertical"

    return None


def _detect_max_pages(text: str) -> int | None:
    return _first_int(
        text,
        (
            r"(?:numero\s+)?maximo\s+de\s+(\d{1,3})"
            r"(?:\s*\([^)]*\))?\s+paginas?",
            r"nao\s+pode\s+exceder\s+(\d{1,3})"
            r"(?:\s*\([^)]*\))?\s+paginas?",
            r"limite\s+de\s+(\d{1,3})"
            r"(?:\s*\([^)]*\))?\s+paginas?",
        ),
    )


def _detect_max_size_mb(text: str) -> int | None:
    return _first_int(
        text,
        (
            r"ultrapassar\s+(\d{1,4})\s*mb\b",
            r"maximo\s+de\s+(\d{1,4})\s*mb\b",
            r"nao\s+pode\s+exceder\s+(\d{1,4})\s*mb\b",
        ),
    )


def _detect_quantity(
    text: str,
    noun_patterns: tuple[str, ...],
) -> int | None:
    folded = _fold(text)

    for noun in noun_patterns:
        patterns = (
            rf"(?<![\d.])(?:[a-zçãõáéíóúêô]+\s*)?\((\d{{1,3}})\)\s*{noun}\b",
            rf"(?<![\d.])(\d{{1,3}})\s*(?:\([^)]*\)\s*)?{noun}\b",
            rf"\b{noun}\b.{{0,100}}\b(\d{{1,3}})\s*"
            rf"(?:ficheiros?|unidades?)?\b",
        )
        value = _first_int(folded, patterns)
        if value is not None:
            return value

    return None


def _detect_filename(text: str) -> str | None:
    match = re.search(
        r"\b[A-Za-z0-9_ -]{1,90}\."
        r"(?:pdf|jpe?g|png|xlsx?|dwg|dxf|ifc|rvt|mp4)\b",
        text,
        re.IGNORECASE,
    )
    return _clean(match.group(0)) if match else None


def _detect_filename_pattern(
    text: str,
    prefix: str,
) -> str | None:
    names = re.findall(
        rf"\b{re.escape(prefix)}[A-Za-z0-9_-]*\."
        r"(?:pdf|jpe?g|png|xlsx?)\b",
        text,
        re.IGNORECASE,
    )
    unique = list(dict.fromkeys(_clean(name) for name in names))

    if not unique:
        return None
    if len(unique) == 1:
        return unique[0]

    return f"{unique[0]} … {unique[-1]}"


def _detect_scales(text: str) -> list[str]:
    values = re.findall(
        r"\b1\s*[:/]\s*(\d{2,5})\b",
        text,
    )
    return list(
        dict.fromkeys(f"1:{value}" for value in values)
    )[:10]


def _has_signature_requirement(*texts: str) -> bool | None:
    folded = _fold(" ".join(texts))

    if any(
        marker in folded
        for marker in (
            "nao devem ser assinados",
            "nao deve ser assinado",
            "sem assinatura",
        )
    ):
        return False

    if any(
        marker in folded
        for marker in (
            "assinados digitalmente",
            "assinatura digital",
            "assinatura eletronica qualificada",
            "assinatura digital qualificada",
        )
    ):
        return True

    return None


def _has_anonymity_requirement(*texts: str) -> bool | None:
    folded = _fold(" ".join(texts))

    if any(
        marker in folded
        for marker in (
            "anonimato",
            "anonimo",
            "nao podendo conter qualquer elemento que permita",
        )
    ):
        return True

    return None


def _source_article(heading: str) -> str:
    match = re.match(
        r"(?i)\s*(artigo|cl[aá]usula)\s+"
        r"(\d+(?:\.\d+)?)\s*[.ººªoa]*",
        heading,
    )
    if not match:
        return heading

    kind = "Artigo" if _fold(match.group(1)).startswith("artigo") else "Cláusula"
    return f"{kind} {match.group(2)}.º"


def _item(
    *,
    key: str,
    title: str,
    group: str,
    category: str,
    source_document: str,
    source_heading: str,
    source_excerpt: str,
    mandatory: bool | None = True,
    conditional: bool = False,
    prohibited: bool = False,
    delivery_mode: str | None = None,
    format_value: str | None = None,
    page_size: str | None = None,
    orientation: str | None = None,
    quantity: int | None = None,
    maximum_pages: int | None = None,
    maximum_size_mb: int | None = None,
    filename: str | None = None,
    template_provided: bool | None = None,
    signature_required: bool | None = None,
    anonymity_required: bool | None = None,
    evaluated_by_jury: bool = False,
    scales: list[str] | None = None,
    contents: list[str] | None = None,
    confidence: float = 0.96,
) -> dict[str, Any]:
    phase_by_group = {
        "participant_documents": "competition_submission",
        "design_work": "competition_submission",
        "complementary_documents": "competition_submission",
        "post_selection_documents": "post_selection",
        "contract_deliverables": "contract_execution",
    }

    return {
        "key": key,
        "title": title,
        "phase": phase_by_group[group],
        "group": group,
        "group_label": GROUP_LABELS[group],
        "category": category,
        "mandatory": mandatory,
        "conditional": conditional,
        "prohibited": prohibited,
        "delivery_mode": delivery_mode,
        "format": format_value,
        "page_size": page_size,
        "orientation": orientation,
        "quantity": quantity,
        "maximum_pages": maximum_pages,
        "maximum_size_mb": maximum_size_mb,
        "filename": filename,
        "template_provided": template_provided,
        "signature_required": signature_required,
        "anonymity_required": anonymity_required,
        "evaluated_by_jury": evaluated_by_jury,
        "scales": scales or [],
        "contents": contents or [],
        "source_document": source_document,
        "source_article": _source_article(source_heading),
        "source_heading": source_heading,
        "source_excerpt": source_excerpt,
        "confidence": confidence,
    }


def _find_first(
    section: str,
    patterns: tuple[str, ...],
) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(
            pattern,
            section,
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        if match:
            return match
    return None


def _extract_contents(
    text: str,
    rules: tuple[tuple[str, tuple[str, ...]], ...],
) -> list[str]:
    values: list[str] = []

    for label, patterns in rules:
        if _find_first(text, patterns):
            values.append(label)

    return values


PARTICIPANT_RULES = (
    (
        "identification_form",
        "Boletim ou ficha de identificação",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*"
            r"(?:boletim|ficha)\s+de\s+identifica[cç][aã]o\b[^\n]*",
        ),
    ),
    (
        "commitment_declaration",
        "Declaração de compromisso",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*"
            r"declara[cç][aã]o\s+de\s+compromisso\b[^\n]*",
        ),
    ),
    (
        "ccp_declaration",
        "Declaração segundo modelo do CCP",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*declara[cç][aã]o\b"
            r"[^\n]*(?:ccp|c[oó]digo\s+dos\s+contratos\s+p[uú]blicos)"
            r"[^\n]*",
        ),
    ),
    (
        "representation_powers",
        "Poderes de representação ou procuração",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*"
            r"(?:procura[cç][aã]o|documento[^\n]*poderes?\s+de\s+representa[cç][aã]o)"
            r"[^\n]*",
        ),
    ),
    (
        "consortium_declaration",
        "Declaração de constituição de agrupamento",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*declara[cç][aã]o\b"
            r"[^\n]*(?:agrupamento|cons[oó]rcio)[^\n]*",
        ),
    ),
    (
        "authorship_declaration",
        "Declaração de autoria ou originalidade",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*declara[cç][aã]o\b"
            r"[^\n]*(?:autoria|originalidade)[^\n]*",
        ),
    ),
    (
        "conflict_declaration",
        "Declaração de inexistência de conflitos",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*declara[cç][aã]o\b"
            r"[^\n]*(?:conflitos?\s+de\s+interesse|incompatibilidades)"
            r"[^\n]*",
        ),
    ),
    (
        "professional_registration",
        "Comprovativo de inscrição profissional",
        "team",
        (
            r"(?im)^[ \t]*[a-z]\)\s*"
            r"(?:declara[cç][aã]o|comprovativo|certid[aã]o)"
            r"[^\n]*(?:ordem\s+dos\s+arquitetos|ordem\s+profissional|"
            r"inscri[cç][aã]o\s+profissional)[^\n]*",
        ),
    ),
    (
        "team_identification",
        "Identificação da equipa projetista",
        "team",
        (
            r"(?im)^[ \t]*[a-z]\)\s*"
            r"(?:identifica[cç][aã]o|ficha)[^\n]*"
            r"equipa\s+projetista[^\n]*",
        ),
    ),
    (
        "curricula",
        "Currículos da equipa",
        "team",
        (
            r"(?im)^[ \t]*[a-z]\)\s*"
            r"(?:curr[ií]culos?|curriculum\s+vitae)[^\n]*",
        ),
    ),
    (
        "portfolio",
        "Portefólio ou fichas de experiência",
        "team",
        (
            r"(?im)^[ \t]*[a-z]\)\s*"
            r"(?:portef[oó]lio|portfolio|fichas?\s+de\s+experi[eê]ncia)"
            r"[^\n]*",
        ),
    ),
)


DESIGN_TOP_LEVEL_RULES = (
    (
        "panels",
        "Painéis",
        "drawing",
        (
            r"(?im)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"pain[eé]is?\b[^\n]*",
        ),
    ),
    (
        "digital_booklet",
        "Caderno digital",
        "written_report",
        (
            r"(?im)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"caderno\b[^\n]*",
        ),
    ),
    (
        "area_schedule",
        "Quadro de áreas",
        "area_schedule",
        (
            r"(?im)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"[^\n]{0,140}?(?:quadro|mapa)\s+de\s+[aá]reas\b[^\n]*",
        ),
    ),
    (
        "publication_images",
        "Imagens para divulgação",
        "publication",
        (
            r"(?ims)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"(?:cinco\s*(?:\(\s*5\s*\))?|\d+\s*(?:\(\d+\))?)\s+ficheiros?"
            r".{0,180}?(?:divulga[cç][aã]o|publica[cç][aã]o)"
            r".{0,120}?(?:jpg|jpeg)",
        ),
    ),
    (
        "panel_reproductions",
        "Reprodução digital dos painéis",
        "publication",
        (
            r"(?ims)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"(?:tr[eê]s\s*(?:\(\s*3\s*\))?|\d+\s*(?:\(\d+\))?)\s+ficheiros?"
            r".{0,160}?(?:cada\s+painel|pain[eé]is?\s+a1)"
            r".{0,160}?(?:jpg|jpeg)",
        ),
    ),
    (
        "standalone_memory",
        "Memória descritiva",
        "written_report",
        (
            r"(?im)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"mem[oó]ria\s+(?:descritiva|justificativa)\b[^\n]*",
        ),
    ),
    (
        "cost_estimate",
        "Estimativa do custo da obra",
        "cost_estimate",
        (
            r"(?im)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"(?:estimativa\s+do\s+custo|estimativa\s+or[cç]amental|"
            r"or[cç]amento\s+estimativo)\b[^\n]*",
        ),
    ),
    (
        "schedule",
        "Cronograma ou faseamento",
        "schedule",
        (
            r"(?im)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"(?:cronograma|plano\s+de\s+trabalhos|faseamento)\b[^\n]*",
        ),
    ),
    (
        "bim_model",
        "Modelo BIM / IFC",
        "digital_model",
        (
            r"(?im)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"(?:modelo\s+bim|ficheiro\s+ifc)\b[^\n]*",
        ),
    ),
    (
        "video",
        "Vídeo ou animação",
        "video",
        (
            r"(?im)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"(?:v[ií]deo|anima[cç][aã]o)\b[^\n]*",
        ),
    ),
    (
        "physical_model",
        "Maqueta física",
        "physical_model",
        (
            r"(?im)^[ \t]*\d+(?:\.\d+)+[ \t]+"
            r"(?:maqueta|modelo\s+f[ií]sico)\b[^\n]*",
        ),
    ),
)


COMPLEMENTARY_RULES = (
    (
        "fees_proposal",
        "Proposta de honorários",
        "financial",
        (
            r"(?im)^[ \t]*(?:\d+(?:\.\d+)+|[a-z]\))[ \t]+"
            r"proposta\s+de\s+honor[aá]rios\b[^\n]*",
        ),
    ),
    (
        "financial_proposal",
        "Proposta financeira",
        "financial",
        (
            r"(?im)^[ \t]*(?:\d+(?:\.\d+)+|[a-z]\))[ \t]+"
            r"proposta\s+financeira\b[^\n]*",
        ),
    ),
    (
        "service_schedule",
        "Calendário ou plano de trabalhos",
        "schedule",
        (
            r"(?im)^[ \t]*(?:\d+(?:\.\d+)+|[a-z]\))[ \t]+"
            r"(?:calend[aá]rio\s+dos\s+servi[cç]os|plano\s+de\s+trabalhos)"
            r"\b[^\n]*",
        ),
    ),
    (
        "team_methodology",
        "Metodologia e organização da equipa",
        "team",
        (
            r"(?im)^[ \t]*(?:\d+(?:\.\d+)+|[a-z]\))[ \t]+"
            r"(?:metodologia\s+da\s+equipa|organograma\s+da\s+equipa|"
            r"distribui[cç][aã]o\s+de\s+tarefas)\b[^\n]*",
        ),
    ),
    (
        "requirements_matrix",
        "Matriz de cumprimento dos requisitos",
        "compliance",
        (
            r"(?im)^[ \t]*(?:\d+(?:\.\d+)+|[a-z]\))[ \t]+"
            r"(?:matriz\s+de\s+cumprimento|matriz\s+de\s+conformidade)"
            r"\b[^\n]*",
        ),
    ),
    (
        "file_index",
        "Índice ou lista dos ficheiros",
        "administrative",
        (
            r"(?im)^[ \t]*(?:\d+(?:\.\d+)+|[a-z]\))[ \t]+"
            r"(?:lista\s+dos\s+ficheiros|[ií]ndice\s+das\s+pe[cç]as|"
            r"[ií]ndice\s+dos\s+documentos)\b[^\n]*",
        ),
    ),
    (
        "responsibility_term",
        "Termo de responsabilidade",
        "administrative",
        (
            r"(?im)^[ \t]*(?:\d+(?:\.\d+)+|[a-z]\))[ \t]+"
            r"termo\s+de\s+responsabilidade\b[^\n]*",
        ),
    ),
)


POST_SELECTION_RULES = (
    (
        "professional_order_declaration",
        "Declaração da ordem profissional",
        "team",
        (
            r"(?im)^[ \t]*[a-z]\)\s*declara[cç][aã]o\b"
            r"[^\n]*(?:ordem\s+dos\s+arquitetos|ordem\s+profissional)"
            r"[^\n]*",
        ),
    ),
    (
        "commercial_registry",
        "Certidão comercial",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*certid[aã]o\s+comercial\b[^\n]*",
        ),
    ),
    (
        "ccp_qualification_declaration",
        "Declaração de habilitação segundo o CCP",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*declara[cç][aã]o\b"
            r"[^\n]*(?:anexo\s+ii|artigo\s+81|ccp)[^\n]*",
        ),
    ),
    (
        "tax_clearance",
        "Comprovativo de situação tributária regularizada",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*"
            r"(?:certid[aã]o|declara[cç][aã]o|comprovativo)"
            r"[^\n]*(?:situa[cç][aã]o\s+tribut[aá]ria|finan[cç]as)"
            r"[^\n]*",
        ),
    ),
    (
        "social_security_clearance",
        "Comprovativo de situação contributiva regularizada",
        "administrative",
        (
            r"(?im)^[ \t]*[a-z]\)\s*"
            r"(?:certid[aã]o|declara[cç][aã]o|comprovativo)"
            r"[^\n]*seguran[cç]a\s+social[^\n]*",
        ),
    ),
)


CONTRACT_RULES = (
    (
        "preliminary_design",
        "Estudo prévio",
        "project_phase",
        r"\bestudo\s+pr[eé]vio\b",
    ),
    (
        "anteproject",
        "Anteprojeto",
        "project_phase",
        r"\banteprojeto\b",
    ),
    (
        "execution_project",
        "Projeto de execução",
        "project_phase",
        r"\bprojeto\s+(?:geral\s+)?de\s+execu[cç][aã]o\b",
    ),
    (
        "technical_assistance",
        "Assistência técnica",
        "service",
        r"\bassist[eê]ncia\s+t[eé]cnica\b",
    ),
    (
        "final_drawings",
        "Telas finais",
        "drawing",
        r"\btelas\s+finais\b",
    ),
    (
        "specialties",
        "Projetos de especialidades",
        "specialties",
        r"\bprojetos?\s+de\s+especialidades\b",
    ),
    (
        "measurements_quantities",
        "Medições e mapa de quantidades",
        "cost_estimate",
        r"\b(?:mapa\s+de\s+medi[cç][oõ]es|mapa\s+de\s+quantidades)\b",
    ),
    (
        "budget",
        "Orçamento",
        "cost_estimate",
        r"\bor[cç]amento\b",
    ),
)


PANEL_CONTENT_RULES = (
    (
        "Implantação ou fotografia aérea",
        (
            r"planta\s+ou\s+fotografia\s+a[eé]rea\s+de\s+implanta[cç][aã]o",
            r"planta\s+de\s+implanta[cç][aã]o",
        ),
    ),
    (
        "Plantas, cortes e alçados",
        (
            r"plantas?,\s*cortes?\s+e\s+al[cç]ados?",
        ),
    ),
    (
        "Elementos a manter, demolir, construir ou ampliar",
        (
            r"elementos?\s+a\s+manter.{0,120}"
            r"(?:demolir|demolidos?).{0,120}"
            r"(?:construir|ampliar)",
        ),
    ),
    (
        "Organograma funcional",
        (
            r"organograma\s+funcional",
        ),
    ),
    (
        "Representações tridimensionais",
        (
            r"representa[cç][oõ]es?\s+tridimensionais?",
            r"perspetivas?",
            r"axonometrias?",
        ),
    ),
    (
        "Diagramas e esquemas complementares",
        (
            r"organogramas?,\s*diagramas?",
            r"diagramas?",
            r"esquemas?",
        ),
    ),
)


BOOKLET_CONTENT_RULES = (
    (
        "Conceito geral da proposta",
        (
            r"conceito\s+geral\s+da\s+proposta",
        ),
    ),
    (
        "Acessibilidade e espaços exteriores",
        (
            r"acessibilidade\s+e\s+espa[cç]os\s+exteriores",
        ),
    ),
    (
        "Organização interna e cumprimento do programa",
        (
            r"organiza[cç][aã]o\s+interna\s+e\s+cumprimento",
            r"cumprimento\s+do\s+programa\s+preliminar",
        ),
    ),
    (
        "Materialidade e viabilidade técnica e financeira",
        (
            r"materialidade\s+e\s+viabilidade",
            r"viabilidade\s+t[eé]cnica\s+e\s+financeira",
        ),
    ),
    (
        "Eficiência e sustentabilidade energética",
        (
            r"efici[eê]ncia\s+e\s+sustentabilidade\s+energ[eé]tica",
            r"estrat[eé]gia\s+e\s+conceito\s+energ[eé]tico",
        ),
    ),
    (
        "Escola provisória e faseamento da obra",
        (
            r"escola\s+provis[oó]ria",
            r"faseamento\s+(?:construtivo|da\s+obra)",
        ),
    ),
)


def _merge_item(
    existing: dict[str, Any],
    incoming: dict[str, Any],
) -> dict[str, Any]:
    result = dict(existing)

    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue

        current = result.get(key)

        if key in {"contents", "scales"}:
            result[key] = list(
                dict.fromkeys(
                    list(current or []) + list(value or [])
                )
            )
        elif key == "confidence":
            result[key] = max(
                float(current or 0),
                float(value or 0),
            )
        elif key == "source_excerpt":
            if len(str(value)) > len(str(current or "")):
                result[key] = value
        elif current in (None, "", [], {}):
            result[key] = value

    return result


def _dedupe(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    for item in items:
        signature = (
            str(item.get("group") or ""),
            str(item.get("key") or ""),
        )

        if signature in merged:
            merged[signature] = _merge_item(
                merged[signature],
                item,
            )
        else:
            merged[signature] = item

    return sorted(
        merged.values(),
        key=lambda item: (
            GROUPS.index(str(item.get("group")))
            if str(item.get("group")) in GROUPS
            else 99,
            str(item.get("title") or ""),
        ),
    )


def _extract_participant_items(
    *,
    source_document: str,
    heading: str,
    section: str,
    presentation_section: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for key, title, category, patterns in PARTICIPANT_RULES:
        match = _find_first(section, patterns)
        if not match:
            continue

        local = _local(section, match)
        conditional = bool(
            re.search(
                r"(?i)\b(?:se|quando|caso)\s+"
                r"(?:aplic[aá]vel|necess[aá]rio|o\s+concorrente)",
                local,
            )
        )

        items.append(
            _item(
                key=key,
                title=title,
                group="participant_documents",
                category=category,
                source_document=source_document,
                source_heading=heading,
                source_excerpt=_excerpt(section, match),
                mandatory=not conditional,
                conditional=conditional,
                delivery_mode="digital",
                format_value=_detect_format(local),
                quantity=1,
                filename=_detect_filename(local),
                template_provided=bool(
                    re.search(r"(?i)\banexo\s+[ivxlcdm]+\b", local)
                ),
                signature_required=_has_signature_requirement(
                    section,
                    presentation_section,
                ),
                anonymity_required=_has_anonymity_requirement(
                    presentation_section,
                ),
                confidence=0.98,
            )
        )

    return items


def _extract_design_items(
    *,
    source_document: str,
    heading: str,
    section: str,
    presentation_section: str,
    physical_section: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for key, title, category, patterns in DESIGN_TOP_LEVEL_RULES:
        match = _find_first(section, patterns)
        if not match:
            continue

        local = _subsection_text(
            section,
            match,
        )

        delivery_mode = "digital"
        evaluated = True
        prohibited = False
        contents: list[str] = []
        filename = _detect_filename(local)
        quantity: int | None = 1

        if key == "panels":
            delivery_mode = "physical_and_digital"
            quantity = _detect_quantity(
                local,
                (r"pain[eé]is?",),
            )
            contents = _extract_contents(
                local,
                PANEL_CONTENT_RULES,
            )
        elif key == "digital_booklet":
            quantity = 1
            contents = _extract_contents(
                local,
                BOOKLET_CONTENT_RULES,
            )
        elif key == "area_schedule":
            quantity = 1
            filename = (
                _detect_filename_pattern(local, "B_")
                or filename
            )
        elif key == "publication_images":
            quantity = _detect_quantity(
                local,
                (r"ficheiros?", r"imagens?"),
            )
            filename = (
                _detect_filename_pattern(local, "C_")
                or filename
            )
        elif key == "panel_reproductions":
            quantity = _detect_quantity(
                local,
                (r"ficheiros?",),
            )
            filename = (
                _detect_filename_pattern(local, "D_")
                or filename
            )
        elif key == "physical_model":
            delivery_mode = "physical"
            prohibited = bool(
                re.search(
                    r"(?i)\bn[aã]o\s+(?:[ée]\s+)?"
                    r"(?:permitida|permitido|admitida|admitido)",
                    local,
                )
            )

        items.append(
            _item(
                key=key,
                title=title,
                group="design_work",
                category=category,
                source_document=source_document,
                source_heading=heading,
                source_excerpt=_excerpt(
                    section,
                    match,
                    radius_after=850,
                ),
                mandatory=False if prohibited else True,
                prohibited=prohibited,
                delivery_mode=delivery_mode,
                format_value=_detect_format(local),
                page_size=_detect_page_size(local),
                orientation=_detect_orientation(local),
                quantity=quantity,
                maximum_pages=_detect_max_pages(local),
                maximum_size_mb=_detect_max_size_mb(local),
                filename=filename,
                template_provided=bool(
                    re.search(
                        r"(?i)\b(?:anexo|modelo\s+fornecido|"
                        r"modelo\s+disponibilizado)\b",
                        local,
                    )
                ),
                signature_required=_has_signature_requirement(
                    presentation_section,
                ),
                anonymity_required=_has_anonymity_requirement(
                    presentation_section,
                    physical_section,
                ),
                evaluated_by_jury=evaluated,
                scales=_detect_scales(local),
                contents=contents,
                confidence=0.99,
            )
        )

    return items


def _extract_complementary_items(
    *,
    source_document: str,
    heading: str,
    section: str,
    presentation_section: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for key, title, category, patterns in COMPLEMENTARY_RULES:
        match = _find_first(section, patterns)
        if not match:
            continue

        local = _local(section, match)

        items.append(
            _item(
                key=key,
                title=title,
                group="complementary_documents",
                category=category,
                source_document=source_document,
                source_heading=heading,
                source_excerpt=_excerpt(section, match),
                delivery_mode="digital",
                format_value=_detect_format(local),
                quantity=1,
                maximum_pages=_detect_max_pages(local),
                maximum_size_mb=_detect_max_size_mb(local),
                filename=_detect_filename(local),
                signature_required=_has_signature_requirement(
                    local,
                    presentation_section,
                ),
                anonymity_required=_has_anonymity_requirement(
                    presentation_section,
                ),
                confidence=0.96,
            )
        )

    return items


def _extract_post_selection_items(
    *,
    source_document: str,
    heading: str,
    section: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    deadline_days = _first_int(
        section,
        (
            r"prazo\s+de\s+(\d{1,3})\s+"
            r"(?:dias?\s+[uú]teis|dias?)",
        ),
    )

    for key, title, category, patterns in POST_SELECTION_RULES:
        match = _find_first(section, patterns)
        if not match:
            continue

        local = _local(section, match)

        item = _item(
            key=key,
            title=title,
            group="post_selection_documents",
            category=category,
            source_document=source_document,
            source_heading=heading,
            source_excerpt=_excerpt(section, match),
            delivery_mode="digital",
            format_value=_detect_format(local),
            quantity=1,
            signature_required=_has_signature_requirement(local),
            confidence=0.98,
        )
        item["deadline_days"] = deadline_days
        item["deadline_type"] = (
            "business_days" if deadline_days else None
        )
        items.append(item)

    return items


def _extract_contract_items(
    source_document: str,
    text: str,
) -> list[dict[str, Any]]:
    folded_name = _fold(source_document)
    folded_text = _fold(text[:8000])

    if (
        "caderno de encargos" not in folded_name
        and "caderno de encargos" not in folded_text
    ):
        return []

    items: list[dict[str, Any]] = []

    for key, title, category, pattern in CONTRACT_RULES:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )
        if not match:
            continue

        items.append(
            _item(
                key=key,
                title=title,
                group="contract_deliverables",
                category=category,
                source_document=source_document,
                source_heading="Caderno de Encargos",
                source_excerpt=_excerpt(text, match),
                mandatory=True,
                delivery_mode=(
                    "service"
                    if key == "technical_assistance"
                    else "digital"
                ),
                confidence=0.92,
            )
        )

    return items


def _group_items(
    items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped = {group: [] for group in GROUPS}

    for item in items:
        group = str(item.get("group") or "")
        if group in grouped:
            grouped[group].append(item)

    return grouped


def _sum_quantities(
    items: list[dict[str, Any]],
    *,
    modes: set[str],
    exclude_keys: set[str] | None = None,
) -> int:
    excluded = exclude_keys or set()
    total = 0

    for item in items:
        if str(item.get("key")) in excluded:
            continue
        if str(item.get("delivery_mode")) not in modes:
            continue
        quantity = item.get("quantity")
        total += int(quantity) if isinstance(quantity, int) else 1

    return total


def _summary(
    grouped: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    participant = grouped["participant_documents"]
    design = grouped["design_work"]
    complementary = grouped["complementary_documents"]
    post_selection = grouped["post_selection_documents"]
    contract = grouped["contract_deliverables"]
    competition = design + complementary

    return {
        "participant_documents": len(participant),
        "design_work": len(design),
        "complementary_documents": len(complementary),
        "post_selection_documents": len(post_selection),
        "contract_deliverables": len(contract),
        "competition_delivery_types": len(competition),
        "competition_submission_total": (
            len(participant) + len(competition)
        ),
        "mandatory_confirmed": sum(
            item.get("mandatory") is True
            for item in participant + competition
        ),
        "conditional": sum(
            item.get("conditional") is True
            for item in participant + competition
        ),
        "physical_units": _sum_quantities(
            competition,
            modes={"physical", "physical_and_digital"},
        ),
        # A reprodução digital dos painéis já é um ficheiro autónomo.
        # O item "painéis" não volta a ser contado como ficheiro digital.
        "digital_files": _sum_quantities(
            competition,
            modes={"digital", "physical_and_digital"},
            exclude_keys={"panels"},
        ),
    }


def extract_submission_requirements(
    textos: dict[str, str],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    documents_read = 0
    source_documents_used: list[str] = []
    section_audit: list[dict[str, Any]] = []

    for source_document, text in _iter_documents(textos):
        documents_read += 1

        participant = _extract_longest_section(
            text,
            SECTION_TITLES["participant"],
        )
        design = _extract_longest_section(
            text,
            SECTION_TITLES["design"],
        )
        presentation = _extract_longest_section(
            text,
            SECTION_TITLES["presentation"],
        )
        physical = _extract_longest_section(
            text,
            SECTION_TITLES["physical"],
        )
        post_selection = _extract_longest_section(
            text,
            SECTION_TITLES["post_selection"],
        )
        complementary = _extract_longest_section(
            text,
            SECTION_TITLES["complementary"],
        )

        presentation_text = presentation[1] if presentation else ""
        physical_text = physical[1] if physical else ""

        used_here = False

        if participant:
            heading, section = participant
            items.extend(
                _extract_participant_items(
                    source_document=source_document,
                    heading=heading,
                    section=section,
                    presentation_section=presentation_text,
                )
            )
            section_audit.append({
                "source_document": source_document,
                "kind": "participant",
                "heading": heading,
                "characters": len(section),
            })
            used_here = True

        if design:
            heading, section = design
            items.extend(
                _extract_design_items(
                    source_document=source_document,
                    heading=heading,
                    section=section,
                    presentation_section=presentation_text,
                    physical_section=physical_text,
                )
            )
            items.extend(
                _extract_complementary_items(
                    source_document=source_document,
                    heading=heading,
                    section=section,
                    presentation_section=presentation_text,
                )
            )
            section_audit.append({
                "source_document": source_document,
                "kind": "design",
                "heading": heading,
                "characters": len(section),
            })
            used_here = True

        if complementary:
            heading, section = complementary
            items.extend(
                _extract_complementary_items(
                    source_document=source_document,
                    heading=heading,
                    section=section,
                    presentation_section=presentation_text,
                )
            )
            section_audit.append({
                "source_document": source_document,
                "kind": "complementary",
                "heading": heading,
                "characters": len(section),
            })
            used_here = True

        if post_selection:
            heading, section = post_selection
            items.extend(
                _extract_post_selection_items(
                    source_document=source_document,
                    heading=heading,
                    section=section,
                )
            )
            section_audit.append({
                "source_document": source_document,
                "kind": "post_selection",
                "heading": heading,
                "characters": len(section),
            })
            used_here = True

        contract_items = _extract_contract_items(
            source_document,
            text,
        )
        if contract_items:
            items.extend(contract_items)
            used_here = True

        if used_here:
            source_documents_used.append(source_document)

    deduped = _dedupe(items)
    grouped = _group_items(deduped)

    return {
        "version": VERSION,
        "documents_read": documents_read,
        "source_documents_used": list(
            dict.fromkeys(source_documents_used)
        ),
        "sections": section_audit,
        "groups": grouped,
        "counts": _summary(grouped),
        "warnings": [],
    }


__all__ = [
    "GROUP_LABELS",
    "GROUPS",
    "VERSION",
    "extract_submission_requirements",
]
