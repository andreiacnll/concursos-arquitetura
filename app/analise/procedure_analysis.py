"""Análise condicional por família de procedimento.

Este módulo não cria um segundo pipeline. Reorganiza os factos já extraídos e
faz uma leitura determinística adicional, separando candidatura, pós-seleção,
execução contratual e programa técnico.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.analise.submission_requirements import extract_submission_requirements
from app.analise.project_services_profile import extract_project_services_profile


VERSION = "procedure-analysis-v15.7"

FAMILY_DESIGN_COMPETITION = "design_competition"
FAMILY_PROJECT_SERVICES = "project_services"
FAMILY_DESIGN_BUILD = "design_build"

FAMILY_LABELS = {
    FAMILY_DESIGN_COMPETITION: "Concurso de conceção",
    FAMILY_PROJECT_SERVICES: "Prestação de serviços de projeto",
    FAMILY_DESIGN_BUILD: "Conceção-Construção",
}

ROLE_ANNOUNCEMENT = "announcement"
ROLE_PROCEDURE_PROGRAM = "procedure_program"
ROLE_PROPOSAL_ANNEX = "proposal_annex"
ROLE_TERMS_REFERENCE = "terms_of_reference"
ROLE_CONTRACT_SPECIFICATIONS = "contract_specifications"
ROLE_EIR = "eir"
ROLE_CLARIFICATION = "clarification"
ROLE_OTHER = "other"

SUBMISSION_ROLES = {
    ROLE_ANNOUNCEMENT,
    ROLE_PROCEDURE_PROGRAM,
    ROLE_PROPOSAL_ANNEX,
    ROLE_CLARIFICATION,
}
CONTRACT_ROLES = {
    ROLE_CONTRACT_SPECIFICATIONS,
    ROLE_EIR,
}
TECHNICAL_ROLES = {
    ROLE_TERMS_REFERENCE,
    ROLE_CONTRACT_SPECIFICATIONS,
    ROLE_EIR,
}

BLOCKED_FILENAMES = {
    "ficha.json",
    "analise.json",
    "textos.json",
    "consolidated.json",
    "dados_concurso.txt",
    "presentation.json",
}

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

GENERIC_TYPES = {
    "",
    "concurso publico",
    "concurso publico internacional",
    "procedimento de contratacao publica",
    "concurso de arquitetura",
}


@dataclass(frozen=True)
class Document:
    filename: str
    text: str
    folded: str
    role: str
    confidence: float


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    ).casefold()
    return re.sub(r"[^a-z0-9%€.,:/+\-\s]+", " ", text)


def _unique(values: Iterable[str], limit: int = 30) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = _clean(raw).strip(" .;:-–—")
        signature = _fold(value)
        if not value or len(value) < 4 or signature in seen:
            continue
        if len(value) > 320:
            value = value[:317].rstrip() + "…"
            signature = _fold(value)
        seen.add(signature)
        output.append(value)
        if len(output) >= limit:
            break
    return output


def _iter_source_documents(textos: dict[str, str]) -> Iterable[tuple[str, str]]:
    for raw_name, raw_text in (textos or {}).items():
        filename = str(raw_name or "documento.txt")
        if Path(filename).name.casefold() in BLOCKED_FILENAMES:
            continue
        text = str(raw_text or "").replace("\x00", " ")
        if text.strip():
            yield filename, text


def classify_document_role(filename: str, text: str) -> tuple[str, float]:
    name = _fold(Path(filename).name)
    opening = _fold(text[:12000])
    joined = f"{name} {opening}"

    # A função do documento é decidida primeiro pelo título/ficheiro. Uma
    # ocorrência interna de “esclarecimentos” num Programa do Concurso não o
    # transforma num documento de esclarecimentos.
    if "anexo" in name and any(
        marker in name
        for marker in ("pc", "proposta", "fator", "declaracao", "boletim", "estimativa")
    ):
        return ROLE_PROPOSAL_ANNEX, 0.97
    if (
        re.search(r"(?:^|[_\-\s])pc(?:[_\-\s.]|$)", name)
        or "programa do procedimento" in opening[:2500]
        or "programa de concurso" in opening[:2500]
        or "prorama de concurso" in opening[:2500]
    ):
        return ROLE_PROCEDURE_PROGRAM, 0.99
    if (
        re.search(r"(?:^|[_\-\s])ce(?:[_\-\s.]|$)", name)
        or "caderno de encargos" in opening[:2500]
    ):
        return ROLE_CONTRACT_SPECIFICATIONS, 0.99
    if "eir" in name or "exchange information requirements" in opening[:4000] or "requisitos de troca de informacao" in opening[:4000]:
        return ROLE_EIR, 0.99
    if any(marker in name for marker in ("esclarecimento", "retificacao", "prorrogacao")):
        return ROLE_CLARIFICATION, 0.98
    if any(marker in opening[:1800] for marker in ("anuncio do procedimento", "anuncio de procedimento")):
        return ROLE_ANNOUNCEMENT, 0.98
    if any(marker in joined for marker in ("termos de referencia", "programa preliminar", "programa de intervencao", "programa tecnico")):
        return ROLE_TERMS_REFERENCE, 0.97
    if any(marker in name for marker in ("anexo", "modelo", "fator", "pontuacao", "proposta", "declaracao")):
        return ROLE_PROPOSAL_ANNEX, 0.88
    return ROLE_OTHER, 0.55


def _documents(textos: dict[str, str]) -> list[Document]:
    output: list[Document] = []
    for filename, text in _iter_source_documents(textos):
        role, confidence = classify_document_role(filename, text)
        output.append(
            Document(
                filename=filename,
                text=text,
                folded=_fold(text),
                role=role,
                confidence=confidence,
            )
        )
    priority = {
        ROLE_CLARIFICATION: 100,
        ROLE_ANNOUNCEMENT: 95,
        ROLE_PROCEDURE_PROGRAM: 90,
        ROLE_PROPOSAL_ANNEX: 80,
        ROLE_TERMS_REFERENCE: 70,
        ROLE_CONTRACT_SPECIFICATIONS: 60,
        ROLE_EIR: 50,
        ROLE_OTHER: 10,
    }
    output.sort(key=lambda item: (-priority[item.role], item.filename.casefold()))
    return output


def infer_analysis_family(
    concurso: dict[str, Any],
    documents: Iterable[Document] = (),
) -> dict[str, Any]:
    title = _fold(concurso.get("titulo"))
    procedure = _fold(concurso.get("tipo_procedimento"))
    cpv = _fold(concurso.get("cpv"))
    structured = " ".join((title, procedure, cpv))
    document_opening = " ".join(document.folded[:5000] for document in documents)
    corpus = f"{structured} {document_opening}"

    reasons: list[str] = []
    confidence = 0.72

    design_build_patterns = (
        r"concecao\s*[-–—/]?\s*construcao",
        r"projeto\s+e\s+construcao",
        r"design\s*[-–—/]?\s*build",
        r"empreitada\s+de\s+concecao\s+e\s+construcao",
    )
    if any(re.search(pattern, corpus) for pattern in design_build_patterns):
        reasons.append("Objeto ou tipo estruturado contém Conceção-Construção.")
        return {
            "family": FAMILY_DESIGN_BUILD,
            "label": FAMILY_LABELS[FAMILY_DESIGN_BUILD],
            "confidence": 0.99,
            "reasons": reasons,
        }

    design_competition_patterns = (
        r"concurso\s+(?:publico\s+)?de\s+concecao",
        r"concurso\s+de\s+ideias",
        r"trabalhos?\s+de\s+concecao",
        r"anonimato.{0,100}juri",
    )
    if any(re.search(pattern, corpus) for pattern in design_competition_patterns):
        reasons.append("Procedimento seleciona um trabalho de conceção.")
        return {
            "family": FAMILY_DESIGN_COMPETITION,
            "label": FAMILY_LABELS[FAMILY_DESIGN_COMPETITION],
            "confidence": 0.98,
            "reasons": reasons,
        }

    service_markers = (
        "aquisicao de servicos",
        "prestacao de servicos",
        "elaboracao de projeto",
        "projeto de arquitetura",
        "projeto de arquitectura",
        "projeto de arquitetura paisagista",
        "projeto e especialidades",
        "servicos de arquitetura",
        "servicos de projeto",
        "assistencia tecnica",
    )
    service_hits = [marker for marker in service_markers if marker in corpus]
    if service_hits:
        reasons.append("Objeto corresponde a prestação de serviços de projeto.")
        confidence = 0.97 if any(marker in structured for marker in service_hits) else 0.88
        return {
            "family": FAMILY_PROJECT_SERVICES,
            "label": FAMILY_LABELS[FAMILY_PROJECT_SERVICES],
            "confidence": confidence,
            "reasons": reasons,
        }

    current = _fold(concurso.get("tipo_procedimento"))
    if "concecao" in current:
        reasons.append("Tipo estruturado indica conceção, sem componente de construção.")
        return {
            "family": FAMILY_DESIGN_COMPETITION,
            "label": FAMILY_LABELS[FAMILY_DESIGN_COMPETITION],
            "confidence": 0.8,
            "reasons": reasons,
        }

    reasons.append("Classificação conservadora como serviços de projeto.")
    return {
        "family": FAMILY_PROJECT_SERVICES,
        "label": FAMILY_LABELS[FAMILY_PROJECT_SERVICES],
        "confidence": 0.62,
        "reasons": reasons,
    }


def _heading_level(line: str) -> tuple[int, str]:
    clean = _clean(line)
    folded = _fold(clean)
    article = re.match(
        r"^(?:artigo|clausula)\s+(\d+(?:\.\d+)?)",
        folded,
    )
    if article:
        return len(article.group(1).split(".")), article.group(1)

    numbered = re.match(r"^(\d+(?:\.\d+)*)[.)\s-]+(.+)$", clean)
    if numbered:
        number, title = numbered.groups()
        letters = [char for char in title if char.isalpha()]
        uppercase = sum(char.isupper() for char in letters)
        looks_title = (
            len(title) <= 180
            and len(title.split()) <= 22
            and (not letters or uppercase / max(1, len(letters)) >= 0.55)
        )
        if looks_title:
            return len(number.split(".")), number

    letters = [char for char in clean if char.isalpha()]
    uppercase = sum(char.isupper() for char in letters)
    if (
        4 <= len(clean) <= 150
        and 1 <= len(clean.split()) <= 16
        and letters
        and uppercase / len(letters) >= 0.72
    ):
        return 1, "heading"
    return 99, ""


def _line_entries(text: str) -> list[tuple[int, int, str]]:
    entries: list[tuple[int, int, str]] = []
    cursor = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        start = cursor
        cursor += len(raw)
        entries.append((start, cursor, line))
    if not entries and text:
        entries.append((0, len(text), text))
    return entries


def _section_by_patterns(
    text: str,
    patterns: tuple[str, ...],
    max_chars: int = 18000,
    *,
    strict: bool = False,
) -> tuple[str, str] | None:
    entries = _line_entries(text)
    candidates: list[tuple[int, str, str]] = []

    for index, (start, _end, raw_line) in enumerate(entries):
        heading = _clean(raw_line)
        folded_heading = _fold(heading)
        if not heading or re.search(r"\.{3,}\s*\d+\s*$", heading):
            continue
        if not any(re.search(pattern, folded_heading, re.IGNORECASE) for pattern in patterns):
            continue

        level, marker = _heading_level(heading)
        if strict and level == 99:
            continue
        if re.match(r"^\s*[a-z]\)\s+", heading, re.IGNORECASE):
            continue

        end = min(len(text), start + max_chars)
        for next_start, _next_end, next_raw in entries[index + 1:]:
            next_line = _clean(next_raw)
            if not next_line:
                continue
            next_level, next_marker = _heading_level(next_line)
            if next_level == 99:
                continue
            if next_start <= start + max(20, len(raw_line)):
                continue
            if level == 99 or next_level <= level:
                end = min(end, next_start)
                break
            if marker and next_marker and next_marker != marker and next_level == 1:
                end = min(end, next_start)
                break

        section = text[start:end].strip()
        if len(section) >= 40:
            score = (200 if strict else 100) + min(len(section), max_chars) // 100
            candidates.append((score, heading, section))

    if candidates:
        _score, heading, section = max(candidates, key=lambda item: item[0])
        return heading, section

    if strict:
        return None

    folded = _fold(text)
    for pattern in patterns:
        match = re.search(pattern, folded, re.IGNORECASE)
        if match:
            raw_start = max(0, match.start() - 120)
            return _clean(text[raw_start:raw_start + 220])[:180], text[raw_start:raw_start + max_chars]
    return None

def _list_lines(section: str, limit: int = 40) -> list[str]:
    candidates: list[str] = []
    for raw_line in section.splitlines():
        line = _clean(raw_line)
        if not line:
            continue
        match = re.match(
            r"^(?:[a-z]\)|\d+(?:\.\d+)*[.)-]|[•\-–—])\s+(.+)$",
            line,
            re.IGNORECASE,
        )
        if match:
            candidates.append(match.group(1))

    if not candidates:
        candidates.extend(
            part
            for part in re.split(r"\s*[;\n]\s*", section)
            if 10 <= len(_clean(part)) <= 320
        )

    blocked = (
        "indice",
        "pagina ",
        "pag. ",
        "sumario",
        "caderno de encargos",
        "programa do procedimento",
        "relatorio preliminar",
        "relatorio final",
        "decisao de adjudicacao",
        "nao adjudicacao",
        "legislacao aplicavel",
    )
    output: list[str] = []
    for value in candidates:
        clean = _clean(value).strip(" .;:-–—")
        folded = _fold(clean)
        if len(clean) < 6 or len(clean) > 320:
            continue
        if any(marker in folded for marker in blocked):
            continue
        if _heading_level(clean)[0] != 99:
            continue
        if re.fullmatch(r"[A-Z0-9 ._/-]{3,60}", clean) and len(clean.split()) <= 7:
            continue
        output.append(clean)
    return _unique(output, limit)

def _evidence_item(
    title: str,
    *,
    phase: str,
    source_document: str,
    source_heading: str,
    excerpt: str,
    mandatory: bool | None = True,
    conditional: bool = False,
    category: str = "other",
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "key": re.sub(r"[^a-z0-9]+", "_", _fold(title)).strip("_")[:80],
        "title": _clean(title),
        "phase": phase,
        "category": category,
        "mandatory": mandatory,
        "conditional": conditional,
        "source_document": source_document,
        "source_heading": source_heading,
        "source_article": source_heading,
        "source_excerpt": _clean(excerpt)[:1200],
        "confidence": confidence,
    }


_ADMIN_PATTERNS = (
    "declaracao",
    "deucp",
    "certidao",
    "procuracao",
    "identificacao do concorrente",
    "documento europeu unico",
    "registo criminal",
    "situacao contributiva",
    "situacao tributaria",
    "pacto social",
    "certificado",
    "comprovativo de inscricao",
)

_PROPOSAL_PATTERNS = (
    "proposta de preco",
    "preco contratual",
    "memoria",
    "metodologia",
    "plano de trabalhos",
    "cronograma",
    "boletim de identificacao da equipa",
    "equipa tecnica",
    "curriculo",
    "portfolio",
    "portefolio",
    "referencias",
    "experiencia",
    "plano de execucao bim",
    "bep",
    "estimativa de custo",
    "mapa de quantidades",
    "programa de trabalhos",
    "nota justificativa",
)

_SUBMISSION_DOCUMENT_MARKERS = _ADMIN_PATTERNS + _PROPOSAL_PATTERNS + (
    "anexo i",
    "anexo ii",
    "anexo iii",
    "formulario",
    "modelo de declaracao",
    "ficha",
    "termo de responsabilidade",
)

_GENERAL_PROCEDURE_SENTENCES = (
    "qualquer classificacao de documentos",
    "os documentos que constituem a proposta devem ser apresentados",
    "todos os documentos da proposta tem de ser redigidos",
    "nao e admitida a apresentacao",
    "abertura eletronica das propostas",
    "esclarecimentos e suprimento",
    "disponibilizacao e acesso as pecas",
    "o processo de concurso esta disponivel",
    "logo apos a assinatura do contrato",
    "inscricao na plataforma de faturacao",
    "mao de obra e equipamentos de apoio",
)


def _classify_submission_item(value: str) -> str:
    folded = _fold(value)
    if any(marker in folded for marker in _ADMIN_PATTERNS):
        return "participant"
    return "proposal"


def _submission_document_title(value: str) -> str:
    clean = _clean(value).strip(" .;:-–—")
    clean = re.sub(r"^(?:[a-z]\)|\d+(?:\.\d+)*[.)-])\s+", "", clean, flags=re.I)
    folded = _fold(clean)
    if not clean or any(marker in folded for marker in _GENERAL_PROCEDURE_SENTENCES):
        return ""
    if not any(marker in folded for marker in _SUBMISSION_DOCUMENT_MARKERS):
        return ""

    rules = (
        ("Declaração do Anexo I", r"declaracao.{0,80}anexo\s+i\b"),
        ("Boletim de identificação da equipa", r"boletim.{0,80}identificacao.{0,40}equipa"),
        ("Proposta de preço", r"proposta.{0,30}preco|preco\s+contratual"),
        ("Memória metodológica", r"memoria.{0,40}metodolog|metodologia"),
        ("Plano de trabalhos", r"plano\s+de\s+trabalhos|programa\s+de\s+trabalhos"),
        ("Cronograma", r"cronograma"),
        ("Currículos da equipa", r"curricul"),
        ("Portefólio e referências", r"portfolio|portefolio|referencias?"),
        ("Declarações de experiência", r"declaracao.{0,80}experiencia"),
        ("Plano de Execução BIM", r"plano.{0,40}execucao.{0,20}bim|\bbep\b"),
        ("Mapa de quantidades", r"mapa\s+de\s+quantidades"),
        ("Estimativa orçamental", r"estimativa.{0,30}(?:custo|orcament)"),
        ("Termo de responsabilidade", r"termo\s+de\s+responsabilidade"),
        ("DEUCP", r"deucp|documento\s+europeu\s+unico"),
        ("Procuração", r"procuracao"),
        ("Certificado ou comprovativo profissional", r"certificado|comprovativo.{0,50}inscricao"),
    )
    for title, pattern in rules:
        if re.search(pattern, folded, re.I):
            return title

    first = re.split(r"[.;](?:\s|$)", clean, maxsplit=1)[0]
    first = re.sub(r"^(?:o|a|os|as)\s+", "", first, flags=re.I)
    if len(first) > 145:
        first = first[:142].rstrip(" ,;:-") + "…"
    return first


def _format_rule_items(section: str, document: Document, heading: str) -> list[dict[str, Any]]:
    folded = _fold(section)
    rules: list[tuple[str, str]] = []
    if "plataforma" in folded or "anogov" in folded:
        rules.append(("Submissão na plataforma eletrónica", r"plataforma|anogov"))
    if "assinatura eletronica" in folded:
        rules.append(("Assinatura eletrónica qualificada", r"assinatura\s+eletronica"))
    if "lingua portuguesa" in folded or "idioma portugues" in folded:
        rules.append(("Documentos redigidos em português", r"lingua\s+portuguesa|idioma\s+portugues"))
    formats = sorted(set(re.findall(r"\.(?:pdf|docx?|xlsx?|ifc|dwg|dxf|rvt)\b", section, re.I)))
    if formats:
        rules.append(("Formatos aceites: " + ", ".join(item.upper() for item in formats), r"formato|ficheiro"))
    page = re.search(r"(?:maximo|max\.?|limite\s+de)\s*(\d{1,3})\s+paginas", folded)
    if page:
        rules.append((f"Limite de {page.group(1)} páginas", r"paginas"))
    size = re.search(r"(?:maximo|max\.?|limite\s+de)\s*(\d{1,4})\s*mb", folded)
    if size:
        rules.append((f"Limite de {size.group(1)} MB por ficheiro", r"mb"))

    return [
        _evidence_item(
            title,
            phase="submission",
            source_document=document.filename,
            source_heading=heading,
            excerpt=section,
            category="format_and_limit",
            confidence=0.94,
        )
        for title, _pattern in rules
    ]


def _critical_condition_title(value: str) -> str:
    folded = _fold(value)
    if re.search(r"prazo|data\s+e\s+hora", folded) and "exclu" in folded:
        return "Entrega depois do prazo"
    if "assinatura" in folded and "exclu" in folded:
        return "Falta de assinatura exigida"
    if re.search(r"falta|ausencia|nao\s+apresent", folded) and "document" in folded:
        return "Falta de documento obrigatório"
    if "alteracao" in folded and ("modelo" in folded or "anexo" in folded):
        return "Alteração de modelo obrigatório"
    if "equipa" in folded and re.search(r"formacao|minim|experiencia|identific", folded):
        return "Equipa sem os requisitos exigidos"
    if "preco" in folded and ("anormalmente baixo" in folded or "exclu" in folded):
        return "Proposta financeira não admissível"
    return ""


def _submission_extraction(documents: list[Document], family: str) -> dict[str, Any]:
    filtered_texts = {
        document.filename: document.text
        for document in documents
        if document.role in SUBMISSION_ROLES
    }
    legacy = extract_submission_requirements(filtered_texts)
    legacy_groups = legacy.get("groups") or {}

    participant: list[dict[str, Any]] = [
        dict(item)
        for item in legacy_groups.get("participant_documents") or []
        if isinstance(item, dict)
    ]
    proposal: list[dict[str, Any]] = [
        dict(item)
        for group in ("design_work", "complementary_documents")
        for item in legacy_groups.get(group) or []
        if isinstance(item, dict)
    ]
    post_selection: list[dict[str, Any]] = [
        dict(item)
        for item in legacy_groups.get("post_selection_documents") or []
        if isinstance(item, dict)
    ]
    formats: list[dict[str, Any]] = []
    critical: list[dict[str, Any]] = []

    if family in {FAMILY_PROJECT_SERVICES, FAMILY_DESIGN_BUILD}:
        participant = []
        proposal = []
        post_selection = []

        for document in documents:
            if document.role not in SUBMISSION_ROLES:
                continue

            proposal_section = _section_by_patterns(
                document.text,
                (
                    r"documentos?.{0,40}(?:constituem|integram|instruem).{0,40}proposta",
                    r"elementos?.{0,40}(?:constituem|integram|instruem).{0,40}proposta",
                    r"documentos?\s+da\s+proposta",
                    r"conteudo\s+da\s+proposta",
                ),
                max_chars=12000,
                strict=True,
            )
            if proposal_section:
                heading, section = proposal_section
                for value in _list_lines(section, 40):
                    title = _submission_document_title(value)
                    if not title:
                        continue
                    group = _classify_submission_item(value)
                    item = _evidence_item(
                        title,
                        phase="submission",
                        source_document=document.filename,
                        source_heading=heading,
                        excerpt=value,
                        category="administrative_submission_document" if group == "participant" else "technical_proposal_document",
                        confidence=0.98,
                    )
                    (participant if group == "participant" else proposal).append(item)

            explicit_participant = _section_by_patterns(
                document.text,
                (
                    r"documentos?\s+do\s+concorrente",
                    r"documentos?\s+administrativos?",
                    r"identificacao\s+do\s+concorrente",
                    r"documentos?\s+de\s+candidatura",
                ),
                max_chars=8000,
                strict=True,
            )
            if explicit_participant:
                heading, section = explicit_participant
                for value in _list_lines(section, 24):
                    title = _submission_document_title(value)
                    if not title:
                        continue
                    participant.append(
                        _evidence_item(
                            title,
                            phase="submission",
                            source_document=document.filename,
                            source_heading=heading,
                            excerpt=value,
                            category="administrative_submission_document",
                            confidence=0.97,
                        )
                    )

            habilitation = _section_by_patterns(
                document.text,
                (
                    r"documentos?\s+de\s+habilitacao",
                    r"habilitacao\s+do\s+adjudicatario",
                    r"documentos?\s+do\s+adjudicatario",
                ),
                max_chars=9000,
                strict=True,
            )
            if habilitation:
                heading, section = habilitation
                for value in _list_lines(section, 24):
                    title = _submission_document_title(value)
                    if not title:
                        first = re.split(r"[.;]", _clean(value), maxsplit=1)[0]
                        title = first if 8 <= len(first) <= 140 else ""
                    if title:
                        post_selection.append(
                            _evidence_item(
                                title,
                                phase="post_selection",
                                source_document=document.filename,
                                source_heading=heading,
                                excerpt=value,
                                category="habilitation",
                                confidence=0.96,
                            )
                        )

            presentation = _section_by_patterns(
                document.text,
                (
                    r"modo\s+de\s+apresentacao\s+das?\s+propostas",
                    r"apresentacao\s+das\s+propostas",
                    r"submissao\s+das\s+propostas",
                    r"formato\s+dos\s+ficheiros",
                ),
                max_chars=9000,
                strict=True,
            )
            if presentation:
                heading, section = presentation
                formats.extend(_format_rule_items(section, document, heading))

            exclusion = _section_by_patterns(
                document.text,
                (r"exclusao\s+das\s+propostas", r"causas?\s+de\s+exclusao"),
                max_chars=12000,
                strict=True,
            )
            if exclusion:
                heading, section = exclusion
                chunks = _list_lines(section, 40)
                chunks.extend(
                    _clean(match.group(0))
                    for match in re.finditer(
                        r"(?is)(?:sob\s+pena\s+de\s+exclusao|excluidas?\s+as\s+propostas|determina\s+a\s+exclusao).{0,360}",
                        section,
                    )
                )
                for value in chunks:
                    title = _critical_condition_title(value)
                    if not title:
                        continue
                    critical.append(
                        _evidence_item(
                            title,
                            phase="submission",
                            source_document=document.filename,
                            source_heading=heading,
                            excerpt=value,
                            category="exclusion_risk",
                            confidence=0.96,
                        )
                    )

    def dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            title = _clean(item.get("title"))
            signature = _fold(title)
            if not title or signature in seen:
                continue
            seen.add(signature)
            item["title"] = title
            output.append(item)
        return output

    participant = dedupe(participant)[:16]
    proposal = dedupe(proposal)[:20]
    post_selection = dedupe(post_selection)[:16]
    formats = dedupe(formats)[:8]
    critical = dedupe(critical)[:8]

    return {
        "participant_documents": participant,
        "proposal_documents": proposal,
        "formats_and_limits": formats,
        "critical_conditions": critical,
        "post_selection_documents": post_selection,
        "legacy": legacy,
    }

def _criteria_section(documents: list[Document]) -> tuple[Document, str, str] | None:
    candidates: list[tuple[int, Document, str, str]] = []
    for document in documents:
        if document.role not in SUBMISSION_ROLES:
            continue
        result = _section_by_patterns(
            document.text,
            (
                r"criterio(?:s)?\s+de\s+adjudicacao",
                r"modelo\s+de\s+avaliacao",
                r"fatores?\s+de\s+avaliacao",
                r"proposta\s+economicamente\s+mais\s+vantajosa",
            ),
            max_chars=22000,
            strict=True,
        )
        if not result:
            continue
        heading, section = result
        role_priority = 130 if document.role == ROLE_PROCEDURE_PROGRAM else 80
        candidates.append((role_priority + min(len(section) // 1000, 15), document, heading, section))
    if not candidates:
        return None
    _, document, heading, section = max(candidates, key=lambda item: item[0])
    return document, heading, section


def _percentage(value: str) -> float | None:
    try:
        number = float(value.replace(" ", "").replace(",", "."))
    except ValueError:
        return None
    if not (0 < number <= 100):
        return None
    return round(number, 3)


def _factor_label(raw: str, code: str = "") -> str:
    clean = _clean(raw).strip(" .;:-–—()[]")
    clean = re.sub(r"(?i)^(?:fator|subfator)\s+[A-Z0-9.]+\s*[-–—:]?\s*", "", clean)
    clean = re.sub(r"(?i)^(?:ponderacao|peso)\s*[-–—:]?\s*", "", clean)
    clean = re.sub(r"\s+", " ", clean)
    if not clean or len(clean) > 120:
        return f"Fator {code}" if code else "Fator de avaliação"
    folded = _fold(clean)
    aliases = (
        ("Preço", ("preco", "valor da proposta", "honorarios")),
        ("Qualidade técnica", ("qualidade tecnica", "merito tecnico", "qualidade da proposta")),
        ("Metodologia", ("metodologia", "memoria metodologica", "abordagem")),
        ("Equipa técnica", ("equipa tecnica", "curriculo da equipa")),
        ("Experiência da equipa", ("experiencia da equipa", "experiencia dos tecnicos")),
        ("Prazo", ("prazo", "tempo de execucao")),
        ("Sustentabilidade", ("sustentabilidade", "desempenho ambiental")),
        ("Plano de trabalhos", ("plano de trabalhos", "programa de trabalhos")),
    )
    for label, markers in aliases:
        if any(marker in folded for marker in markers):
            return label
    return clean[0].upper() + clean[1:]


def _extract_criteria(documents: list[Document]) -> dict[str, Any]:
    located = _criteria_section(documents)
    if not located:
        return {}
    document, heading, section = located
    folded = _fold(section)

    factor_names: dict[str, str] = {}
    for match in re.finditer(
        r"(?im)^\s*fator\s+([A-Z])\s*[-–—:]?\s*([^\n%]{3,140})$",
        section,
    ):
        code = match.group(1).upper()
        factor_names[code] = _factor_label(match.group(2), code)

    formula_text = ""
    formula_weights: dict[str, float] = {}
    for match in re.finditer(
        r"(?im)^\s*([A-Z]{1,4})\s*=\s*((?:\d+[,.]\d+\s*(?:\*|x)?\s*[A-Z](?:\s*[+\-]\s*)?){2,})\s*$",
        section,
    ):
        formula_text = _clean(match.group(0))
        for coefficient, code in re.findall(r"(0[,.]\d+|1[,.]0+)\s*(?:\*|x)?\s*([A-Z])", match.group(2)):
            value = round(float(coefficient.replace(",", ".")) * 100, 3)
            if 0 < value <= 100:
                formula_weights[code.upper()] = value
        if formula_weights:
            break

    explicit_weights: dict[str, float] = {}
    for match in re.finditer(
        r"(?im)^\s*fator\s+([A-Z])(?:\s*[-–—:]\s*([^\n%]{3,120}?))?\s*(?:[-–—:(]|\s)\s*(\d{1,3}(?:[,.]\d+)?)\s*%",
        section,
    ):
        code = match.group(1).upper()
        weight = _percentage(match.group(3))
        if weight is not None:
            explicit_weights[code] = weight
        if match.group(2):
            factor_names[code] = _factor_label(match.group(2), code)

    weights = formula_weights or explicit_weights
    generic_factors: list[tuple[str, float]] = []
    if not weights:
        for match in re.finditer(
            r"(?im)^\s*([^\n%]{3,100}?)\s*[-–—:]\s*(\d{1,3}(?:[,.]\d+)?)\s*%\s*$",
            section,
        ):
            raw_name = _clean(match.group(1))
            folded_name = _fold(raw_name)
            if re.match(r"^(?:subfator\s+)?[A-Z]\d+(?:\.\d+)?\b", raw_name, re.I):
                continue
            if any(marker in folded_name for marker in ("iva", "taxa", "pagina", "limite")):
                continue
            weight = _percentage(match.group(2))
            if weight is not None:
                generic_factors.append((_factor_label(raw_name), weight))
        if generic_factors and abs(sum(weight for _name, weight in generic_factors) - 100) > 2:
            generic_factors = []

    factors: list[dict[str, Any]] = []
    if weights and abs(sum(weights.values()) - 100) <= 2:
        for code, weight in sorted(weights.items()):
            factors.append({
                "code": code,
                "name": factor_names.get(code) or f"Fator {code}",
                "weight": weight,
                "source_document": document.filename,
                "source_heading": heading,
                "evidence_excerpt": formula_text or f"Fator {code}: {weight:g}%",
                "confidence": 0.98 if formula_weights else 0.95,
                "subfactors": [],
            })
    elif generic_factors:
        for name, weight in generic_factors:
            factors.append({
                "code": "",
                "name": name,
                "weight": weight,
                "source_document": document.filename,
                "source_heading": heading,
                "evidence_excerpt": f"{name}: {weight:g}%",
                "confidence": 0.96,
                "subfactors": [],
            })

    subfactors: list[dict[str, Any]] = []
    for match in re.finditer(
        r"(?im)^\s*([A-Z]\d+(?:\.\d+)?)\s*[-–—:]\s*([^\n%]{3,150}?)\s*(?:[-–—:(]|\s)\s*(\d{1,3}(?:[,.]\d+)?)\s*%",
        section,
    ):
        code = match.group(1).upper()
        weight = _percentage(match.group(3))
        if weight is None:
            continue
        sub = {
            "code": code,
            "name": _factor_label(match.group(2), code),
            "weight": weight,
            "source_document": document.filename,
            "source_heading": heading,
            "evidence_excerpt": _clean(match.group(0)),
            "confidence": 0.94,
        }
        subfactors.append(sub)
        parent = code[0]
        for factor in factors:
            if factor.get("code") == parent:
                factor["subfactors"].append(sub)
                break

    summary = " • ".join(f"{item['name']} {item['weight']:g}%" for item in factors)
    if not summary:
        detected = []
        for label, marker in (
            ("Preço", "preco"),
            ("Qualidade", "qualidade"),
            ("Metodologia", "metodologia"),
            ("Equipa", "equipa"),
        ):
            if marker in folded:
                detected.append(label)
        summary = " + ".join(detected)
        if summary:
            summary += " · Ponderações principais por confirmar"

    interpretation = "Não determinado"
    if factors:
        price_weight = sum(item["weight"] for item in factors if "preco" in _fold(item["name"]))
        team_weight = sum(item["weight"] for item in factors if any(marker in _fold(item["name"]) for marker in ("equipa", "experiencia", "curriculo")))
        method_weight = sum(item["weight"] for item in factors if "metod" in _fold(item["name"]))
        if price_weight >= 50:
            interpretation = "Dominado pelo preço"
        elif team_weight >= 50:
            interpretation = "Dominado pelo currículo"
        elif method_weight >= 45:
            interpretation = "Dominado pela metodologia"
        else:
            interpretation = "Equilibrado"

    tie_breakers = []
    for match in re.finditer(r"(?is)(?:desempate|em\s+caso\s+de\s+empate).{0,500}", section):
        sentence = re.split(r"(?<=[.;])\s+", _clean(match.group(0)), maxsplit=1)[0]
        if 20 <= len(sentence) <= 260:
            tie_breakers.append(sentence)

    return {
        "type": " + ".join(item["name"] for item in factors) or summary,
        "summary": summary,
        "factors": factors,
        "subfactors": subfactors,
        "formula": formula_text,
        "tie_breakers": _unique(tie_breakers, 4),
        "interpretation": interpretation,
        "source_document": document.filename,
        "source_heading": heading,
        "evidence_excerpt": _clean(section[:1800]),
        "confidence": 0.98 if factors else 0.64,
        "verified_top_level_weights": bool(factors),
    }

def _scope_and_contract(documents: list[Document]) -> dict[str, Any]:
    scope: list[dict[str, Any]] = []
    deliverables: list[dict[str, Any]] = []
    phases: list[dict[str, Any]] = []
    payments: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []

    scope_rules = (
        ("Estudo prévio", r"estudo\s+previo"),
        ("Anteprojeto", r"anteprojeto"),
        ("Projeto de licenciamento", r"projeto\s+de\s+licenciamento"),
        ("Projeto de execução", r"projeto\s+de\s+execucao"),
        ("Especialidades", r"especialidades"),
        ("Levantamento", r"levantamento(?:s)?\s+(?:topografico|arquitetonico|cadastral)"),
        ("Medições", r"medicoes"),
        ("Mapa de quantidades", r"mapa\s+de\s+quantidades"),
        ("Estimativa orçamental", r"estimativa\s+(?:orcamental|de\s+custo)"),
        ("Coordenação de projeto", r"coordenacao\s+(?:geral\s+)?do\s+projeto"),
        ("Assistência técnica", r"assistencia\s+tecnica"),
        ("Acompanhamento de obra", r"acompanhamento\s+(?:tecnico\s+)?da\s+obra"),
        ("Modelos BIM", r"modelos?\s+bim|building\s+information\s+model"),
        ("Telas finais", r"telas\s+finais|as[- ]built"),
    )

    risk_rules = (
        ("Penalizações por atraso", "high", r"pena(?:lidade|lizacao)s?.{0,250}(?:atraso|mora)|multa.{0,250}atraso"),
        ("Correções sem remuneração adicional", "medium", r"corrig.{0,250}sem\s+(?:qualquer\s+)?remuneracao|sem\s+encargos\s+adicionais"),
        ("Responsabilidade por erros e omissões", "high", r"erros?\s+e\s+omissoes|responsabilidade.{0,200}erro"),
        ("Propriedade intelectual e direitos", "medium", r"propriedade\s+intelectual|cedencia\s+de\s+direitos|direitos\s+de\s+autor"),
        ("Caução", "medium", r"caucao"),
        ("Seguros", "medium", r"seguro(?:s)?\s+(?:obrigatorio|de\s+responsabilidade)"),
        ("Resolução do contrato", "high", r"resolucao\s+do\s+contrato"),
        ("Alterações unilaterais", "medium", r"alteracao\s+unilateral|modificacao\s+unilateral"),
    )

    for document in documents:
        if document.role not in TECHNICAL_ROLES:
            continue
        for title, pattern in scope_rules:
            match = re.search(pattern, document.folded, re.IGNORECASE)
            if not match:
                continue
            excerpt = _clean(document.text[max(0, match.start() - 120):match.end() + 380])
            item = _evidence_item(
                title,
                phase="contract_execution",
                source_document=document.filename,
                source_heading="Âmbito dos serviços",
                excerpt=excerpt,
                category="scope_service",
                confidence=0.9,
            )
            scope.append(item)
            if title in {"Estudo prévio", "Anteprojeto", "Projeto de licenciamento", "Projeto de execução"}:
                phases.append(dict(item))
            if title in {"Projeto de execução", "Medições", "Mapa de quantidades", "Estimativa orçamental", "Modelos BIM", "Telas finais"}:
                deliverables.append(dict(item))

        payment_section = _section_by_patterns(
            document.text,
            (r"condicoes\s+de\s+pagamento", r"pagamentos?", r"preco\s+contratual"),
            max_chars=8000,
        )
        if payment_section:
            heading, section = payment_section
            for value in _list_lines(section, 16):
                if any(marker in _fold(value) for marker in ("pagamento", "%", "fatura", "dias", "fase", "retencao")):
                    payments.append(
                        _evidence_item(
                            value,
                            phase="contract_execution",
                            source_document=document.filename,
                            source_heading=heading,
                            excerpt=section,
                            category="payment",
                            confidence=0.88,
                        )
                    )

        if document.role in CONTRACT_ROLES:
            for title, level, pattern in risk_rules:
                match = re.search(pattern, document.folded, re.IGNORECASE | re.DOTALL)
                if not match:
                    continue
                excerpt = _clean(document.text[max(0, match.start() - 100):match.end() + 500])
                risks.append(
                    {
                        **_evidence_item(
                            title,
                            phase="contract_execution",
                            source_document=document.filename,
                            source_heading="Riscos contratuais",
                            excerpt=excerpt,
                            category="contract_risk",
                            confidence=0.9,
                        ),
                        "level": level,
                        "summary": excerpt[:420],
                    }
                )

    def dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            signature = _fold(item.get("title"))
            if not signature or signature in seen:
                continue
            seen.add(signature)
            result.append(item)
        return result

    return {
        "scope_services": dedupe(scope)[:24],
        "deliverables": dedupe(deliverables)[:24],
        "phases": dedupe(phases)[:12],
        "payments": dedupe(payments)[:16],
        "risks": dedupe(risks)[:16],
    }


def _eligibility_and_team(documents: list[Document]) -> dict[str, Any]:
    eligibility: list[dict[str, Any]] = []
    team: list[dict[str, Any]] = []

    team_rules = (
        ("Coordenador", r"coordenador(?:\s+geral|\s+de\s+projeto)?"),
        ("Arquitetura", r"arquiteto|arquitecto|arquitetura"),
        ("Arquitetura paisagista", r"arquiteto\s+paisagista|arquitecto\s+paisagista|arquitetura\s+paisagista"),
        ("Estruturas", r"estruturas"),
        ("Águas e esgotos", r"aguas\s+e\s+esgotos|abastecimento\s+de\s+agua|drenagem\s+de\s+aguas"),
        ("Eletricidade", r"eletricidade|instalacoes\s+eletricas"),
        ("AVAC", r"avac|climatizacao"),
        ("Acústica", r"acustica"),
        ("Térmica", r"termica"),
        ("Segurança contra incêndios", r"seguranca\s+contra\s+incendios|scie"),
        ("Sustentabilidade", r"sustentabilidade"),
        ("BIM", r"gestor\s+bim|coordenador\s+bim|bim\s+manager"),
        ("Segurança", r"coordenacao\s+de\s+seguranca|plano\s+de\s+seguranca"),
    )

    for document in documents:
        if document.role not in SUBMISSION_ROLES:
            continue

        eligibility_section = _section_by_patterns(
            document.text,
            (
                r"requisitos?\s+(?:minimos?\s+)?de\s+capacidade\s+tecnica",
                r"requisitos?\s+de\s+participacao",
                r"experiencia\s+minima\s+exigida",
                r"habilitacoes?\s+profissionais?",
                r"composicao\s+minima\s+da\s+equipa",
            ),
            max_chars=12000,
            strict=True,
        )
        if eligibility_section:
            heading, section = eligibility_section
            for value in _list_lines(section, 28):
                folded = _fold(value)
                mandatory = any(marker in folded for marker in ("minimo", "obrigatorio", "deve", "exigido", "exclusao"))
                if not mandatory:
                    continue
                title = re.split(r"[.;]", _clean(value), maxsplit=1)[0]
                if len(title) > 150:
                    title = title[:147].rstrip(" ,;:-") + "…"
                if len(title) < 12:
                    continue
                eligibility.append(
                    _evidence_item(
                        title,
                        phase="submission",
                        source_document=document.filename,
                        source_heading=heading,
                        excerpt=value,
                        category="eligibility",
                        confidence=0.94,
                    )
                )

        team_section = _section_by_patterns(
            document.text,
            (
                r"equipa\s+tecnica\s+(?:obrigatoria|minima)",
                r"composicao\s+(?:minima\s+)?da\s+equipa",
                r"tecnicos?\s+(?:a\s+afetar|responsaveis)",
                r"qualificacoes?\s+da\s+equipa",
            ),
            max_chars=16000,
            strict=True,
        )
        if not team_section:
            continue
        heading, section = team_section
        folded_section = _fold(section)
        for title, pattern in team_rules:
            match = re.search(pattern, folded_section, re.IGNORECASE)
            if not match:
                continue
            excerpt = _clean(section[max(0, match.start() - 100):match.end() + 420])
            years_match = re.search(r"(\d{1,2})\s+anos?\s+de\s+experiencia", excerpt, re.IGNORECASE)
            qualification = ""
            qualification_match = re.search(r"(?:inscrito|membro|habilitado).{0,100}", excerpt, re.IGNORECASE)
            if qualification_match:
                qualification = _clean(qualification_match.group(0))[:140]
            team.append({
                **_evidence_item(
                    title,
                    phase="submission",
                    source_document=document.filename,
                    source_heading=heading,
                    excerpt=excerpt,
                    category="technical_team",
                    confidence=0.92,
                ),
                "role": title,
                "minimum_years": int(years_match.group(1)) if years_match else None,
                "qualification": qualification,
                "specific_experience": "",
                "proof_documents": [],
            })

    def dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            signature = _fold(item.get("title"))
            if not signature or signature in seen:
                continue
            seen.add(signature)
            output.append(item)
        return output

    eligibility = dedupe(eligibility)[:12]
    team = dedupe(team)[:16]
    status = "Não determinado"
    risk = "Não determinado"
    if eligibility:
        status = "Requisitos mínimos identificados"
        risk = "Médio" if len(eligibility) >= 3 else "Baixo"

    return {
        "requirements": eligibility,
        "status": status,
        "exclusion_risk": risk,
        "team": team,
    }


PROJECT_EXPERIENCE_MARKERS = (
    "experiencia",
    "curriculo",
    "referencia",
    "projeto semelhante",
    "projetos semelhantes",
    "obra semelhante",
    "obras semelhantes",
    "equipa tecnica",
)

PROJECT_TARGET_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Parques urbanos",
        (
            "parque urbano",
            "parques urbanos",
            "jardim publico",
            "jardins publicos",
            "espaco verde urbano",
            "paisagismo urbano",
        ),
    ),
    (
        "Obras de urbanização pública",
        (
            "obra de urbanizacao",
            "obras de urbanizacao",
            "urbanizacao publica",
            "urbanizacoes publicas",
            "arruamento",
            "infraestrutura urbana",
            "espaco publico",
        ),
    ),
    (
        "Remodelação/modelação de terrenos",
        (
            "remodelacao de terreno",
            "remodelacao de terrenos",
            "modelacao do terreno",
            "movimento de terras",
            "movimentos de terras",
            "terraplenagem",
            "topografia",
        ),
    ),
    (
        "Arquitetura paisagista",
        (
            "arquitetura paisagista",
            "arquitectura paisagista",
            "projeto paisagistico",
            "projecto paisagistico",
            "paisagismo",
        ),
    ),
    (
        "Projeto de edifícios",
        (
            "projeto de edificio",
            "projetos de edificios",
            "arquitetura de edificios",
            "reabilitacao de edificio",
            "equipamento publico",
        ),
    ),
)


def _nested_texts(value: object) -> list[str]:
    output: list[str] = []
    if isinstance(value, dict):
        for nested in value.values():
            output.extend(_nested_texts(nested))
    elif isinstance(value, (list, tuple, set)):
        for nested in value:
            output.extend(_nested_texts(nested))
    elif value is not None:
        cleaned = _clean(value)
        if cleaned:
            output.append(cleaned)
    return output


def _company_project_records(company_profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Devolve apenas registos de projeto, sem misturar serviços/competências.

    O matching de experiência pontuada nunca pode ser satisfeito por a empresa
    dizer que presta urbanismo, BIM ou paisagismo. Tem de existir uma referência
    de projeto compatível no perfil documental.
    """
    raw = company_profile.get("project_experience") or []
    if not isinstance(raw, list):
        return []
    output: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("name") or item.get("title"))
        typology = _clean(item.get("typology") or item.get("category") or item.get("project_type"))
        if not name and not typology:
            continue
        text = _fold(" ".join(_nested_texts({
            "name": name,
            "typology": typology,
            "description": item.get("description"),
            "skills": item.get("skills_demonstrated"),
            "role": item.get("role"),
            "location": item.get("location"),
            "year": item.get("year") or item.get("date"),
            "value": item.get("value") or item.get("budget") or item.get("construction_cost"),
            "volume": item.get("earthworks_volume") or item.get("volume"),
        })))
        output.append({
            "name": name or typology or "Projeto",
            "typology": typology,
            "text": text,
            "raw": item,
        })
    return output


def _criterion_targets(value: object) -> list[dict[str, Any]]:
    folded = _fold(value)
    targets: list[dict[str, Any]] = []
    for label, aliases in PROJECT_TARGET_GROUPS:
        if any(alias in folded for alias in aliases):
            targets.append({"label": label, "aliases": aliases})
    return targets


def _project_matches_target(project: dict[str, Any], target: dict[str, Any]) -> bool:
    text = project.get("text") or ""
    return any(alias in text for alias in target.get("aliases") or ())


def _project_typology_labels(projects: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for project in projects:
        label = _clean(project.get("typology"))
        key = _fold(label)
        if not label or not key or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels[:12]


def _bim_training_demonstrated(company_profile: dict[str, Any], team_context: dict[str, Any]) -> bool:
    corpus = _fold(" ".join(_nested_texts({
        "company": company_profile,
        "team": team_context,
    })))
    # A competência "BIM" isolada não comprova a formação específica exigida.
    return bool(
        "bim" in corpus
        and "80" in corpus
        and any(marker in corpus for marker in ("formacao", "curso", "certificado", "horas"))
    )


def assess_company_award_fit(
    procedure_analysis: dict[str, Any],
    company_profile: dict[str, Any],
    team_context: dict[str, Any],
) -> dict[str, Any]:
    """Avalia currículo apenas contra os critérios concretos do concurso.

    Projetos de Habitação, Educação, Cultura, etc. não contam para um fator que
    pontua Parques Urbanos, Urbanização Pública ou Remodelação de Terrenos.
    A ausência de prova no perfil é reportada como "não demonstrado", não como
    afirmação de inexistência da experiência real da equipa.
    """
    criteria = procedure_analysis.get("award_criteria") or {}
    factors = criteria.get("factors") or []
    projects = _company_project_records(company_profile)
    project_typologies = _project_typology_labels(projects)

    assessed: list[dict[str, Any]] = []
    relevant_weight = 0.0
    covered_weight = 0.0
    criterion_aliases: set[str] = set()

    for factor in factors:
        if not isinstance(factor, dict):
            continue
        factor_weight = float(factor.get("weight") or 0)
        if factor_weight <= 0:
            continue
        subfactors = [item for item in (factor.get("subfactors") or []) if isinstance(item, dict)]
        candidates = subfactors or [factor]
        sub_total = sum(float(item.get("weight") or 0) for item in subfactors)

        factor_source = " ".join(
            _clean(factor.get(key))
            for key in ("name", "evidence_excerpt", "title")
        )
        folded_factor_source = _fold(factor_source)
        factor_is_experience = any(
            marker in folded_factor_source
            for marker in PROJECT_EXPERIENCE_MARKERS
        )

        for candidate in candidates:
            source = " ".join(
                _clean(candidate.get(key))
                for key in ("name", "evidence_excerpt", "title")
            )
            folded_source = _fold(source)

            # Subfatores como "Projetos de parques urbanos" não repetem
            # necessariamente a palavra "experiência", mas herdam a natureza
            # do fator principal "Experiência da equipa técnica".
            targets = _criterion_targets(source)
            is_experience = (
                any(marker in folded_source for marker in PROJECT_EXPERIENCE_MARKERS)
                or (factor_is_experience and bool(targets))
            )
            is_bim_training = "bim" in folded_source and any(
                marker in folded_source for marker in ("formacao", "curso", "horas")
            )
            if not is_experience and not is_bim_training:
                continue

            explicit_absolute = float(candidate.get("absolute_weight") or 0)
            candidate_weight = float(candidate.get("weight") or 0)
            if explicit_absolute > 0:
                absolute_weight = explicit_absolute
            elif subfactors and sub_total > 0:
                absolute_weight = factor_weight * candidate_weight / sub_total
            else:
                absolute_weight = factor_weight

            for target in targets:
                criterion_aliases.update(target.get("aliases") or ())

            matched_projects: list[dict[str, str]] = []
            matched_target_labels: list[str] = []
            if targets:
                for project in projects:
                    target_labels = [
                        target["label"] for target in targets
                        if _project_matches_target(project, target)
                    ]
                    if not target_labels:
                        continue
                    matched_projects.append({
                        "name": _clean(project.get("name")) or "Projeto",
                        "typology": _clean(project.get("typology")),
                    })
                    for label in target_labels:
                        if label not in matched_target_labels:
                            matched_target_labels.append(label)
                coverage = 1.0 if matched_projects else 0.0
                status = "confirmed" if matched_projects else "not_demonstrated"
                status_label = "Comprovado no perfil" if matched_projects else "Não demonstrado no perfil"
            elif is_bim_training:
                demonstrated = _bim_training_demonstrated(company_profile, team_context)
                coverage = 1.0 if demonstrated else 0.0
                status = "confirmed" if demonstrated else "not_demonstrated"
                status_label = "Formação comprovada" if demonstrated else "Formação por confirmar"
            else:
                # Critério genérico de experiência sem tipologia explícita:
                # não atribuir crédito automático por existirem projetos quaisquer.
                coverage = 0.0
                status = "not_demonstrated"
                status_label = "Não demonstrado no perfil"

            display_name = (
                targets[0]["label"]
                if len(targets) == 1
                else (_clean(candidate.get("name")) or "Experiência avaliada")
            )
            relevant_weight += absolute_weight
            covered_weight += absolute_weight * coverage
            assessed.append({
                "name": _clean(candidate.get("name")) or "Experiência avaliada",
                "display_name": display_name,
                "absolute_weight": round(absolute_weight, 2),
                "coverage": round(coverage, 2),
                "status": status,
                "status_label": status_label,
                "targets": [target["label"] for target in targets],
                "matched_targets": matched_target_labels,
                "matched_projects": matched_projects[:8],
                "source_document": _clean(candidate.get("source_document")),
                "evidence_excerpt": _clean(candidate.get("evidence_excerpt"))[:420],
            })

    if relevant_weight <= 0:
        return {
            "active": False,
            "penalty": 0,
            "coverage_percent": None,
            "relevant_weight": 0,
            "documented_weight": 0,
            "pending_weight": 0,
            "assessed_requirements": [],
            "missing_requirements": [],
            "matched_requirements": [],
            "unrelated_project_typologies": [],
            "explanation": "Não foram identificados critérios de currículo ou experiência com ponderação verificável.",
        }

    ratio = max(0.0, min(1.0, covered_weight / relevant_weight))
    penalty = round(min(35.0, relevant_weight * (1.0 - ratio) * 0.55))
    missing = [item for item in assessed if item["status"] != "confirmed"]
    matched = [item for item in assessed if item["status"] == "confirmed"]
    coverage_percent = round(ratio * 100)

    # Tipologias existentes no portefólio mas que não respondem a nenhum dos
    # critérios deste concurso. Servem apenas para explicar por que não contam.
    unrelated: list[str] = []
    for label in project_typologies:
        folded = _fold(label)
        if criterion_aliases and any(alias in folded for alias in criterion_aliases):
            continue
        unrelated.append(label)

    explanation = (
        f"A experiência/currículo representa {relevant_weight:g}% da avaliação. "
        f"O perfil documental comprova {covered_weight:g} pontos desse peso e deixa "
        f"{max(0.0, relevant_weight - covered_weight):g} pontos por demonstrar. "
        "Projetos só contam quando correspondem à tipologia efetivamente pontuada."
    )
    if unrelated:
        explanation += " Projetos noutras tipologias do portefólio não são usados para estes critérios."
    if penalty:
        explanation += f" A pontuação documentada foi reduzida em {penalty} pontos."

    return {
        "active": True,
        "penalty": penalty,
        "coverage_percent": coverage_percent,
        "relevant_weight": round(relevant_weight, 2),
        "documented_weight": round(covered_weight, 2),
        "pending_weight": round(max(0.0, relevant_weight - covered_weight), 2),
        "assessed_requirements": assessed,
        "missing_requirements": missing,
        "matched_requirements": matched,
        "unrelated_project_typologies": unrelated[:8],
        "explanation": explanation,
    }

def _date_value(entry: object) -> str:
    if isinstance(entry, dict):
        return _clean(entry.get("value"))
    return _clean(entry)


def _top_metrics(
    *,
    ficha: dict[str, Any],
    concurso: dict[str, Any],
    family: str,
    criteria: dict[str, Any],
    submission: dict[str, Any],
) -> list[dict[str, Any]]:
    common = ficha.get("common_project_extraction") or {}
    extraction = ficha.get("design_competition_extraction") or {}
    facts = extraction.get("facts") or {}
    financial = extraction.get("financial") or {}
    intervention = ficha.get("intervention_program") or extraction.get("intervention_program") or {}

    def fact(key: str) -> str:
        value = facts.get(key)
        return _date_value(value)

    procedure_value = (
        _date_value(common.get("base_price"))
        or _clean(concurso.get("preco_base"))
        or fact("procedure_value")
    )
    construction_cost = fact("estimated_construction_cost")
    proposal_titles = " ".join(
        _fold(item.get("title"))
        for item in (submission.get("proposal_documents") or [])
        if isinstance(item, dict)
    )
    construction_cost_required = any(
        marker in proposal_titles
        for marker in (
            "estimativa orcamental",
            "estimativa de custo",
            "estimativa do custo",
            "orcamento da obra",
        )
    )
    construction_cost_status = "confirmed" if construction_cost else "pending"
    construction_cost_status_label = "Confirmado" if construction_cost else "Por confirmar"
    if not construction_cost and construction_cost_required:
        construction_cost = "A entregar na proposta"
        construction_cost_status = "required"
        construction_cost_status_label = "Exigido"
    services_value = (
        _clean(financial.get("design_services_value_display"))
        or fact("design_services_value")
    )
    area = (
        _date_value((intervention.get("area_intervencao") or {}))
        or _clean(intervention.get("total_area"))
        or fact("area_intervencao")
        or fact("total_area")
    )
    deadline = (
        _clean(concurso.get("data_entrega_propostas"))
        or _date_value(common.get("submission_deadline"))
        or fact("submission_deadline")
    )
    publication = (
        _clean(concurso.get("data"))
        or _date_value(common.get("publication_date"))
        or fact("publication_date")
    )
    criteria_summary = _clean(criteria.get("summary")) or _clean(concurso.get("criterio_resumo")) or _clean(concurso.get("criterio_tipo"))
    if criteria_summary and "%" not in criteria_summary:
        criteria_summary = f"{criteria_summary} · Ponderações por confirmar"
    procedure_type = _clean(concurso.get("tipo_procedimento")) or _clean((ficha.get("identificacao") or {}).get("tipo_procedimento"))
    document_status = _clean((ficha.get("document_insights") or {}).get("document_status"))

    first_financial_label = "Valor do procedimento"
    if family == FAMILY_PROJECT_SERVICES:
        first_financial_label = "Preço base / honorários"
    elif family == FAMILY_DESIGN_BUILD:
        first_financial_label = "Preço base projeto + obra"

    def metric(
        key: str,
        label: str,
        value: object,
        *,
        status: str | None = None,
        status_label: str | None = None,
    ) -> dict[str, Any]:
        clean_value = _clean(value)
        resolved_status = status or ("confirmed" if clean_value else "pending")
        resolved_label = status_label or ("Confirmado" if clean_value else "Por confirmar")
        return {
            "key": key,
            "label": label,
            "value": clean_value,
            "status": resolved_status,
            "status_label": resolved_label,
        }

    return [
        metric("procedure_value", first_financial_label, procedure_value),
        metric(
            "construction_cost",
            "Estimativa de custo da obra",
            construction_cost,
            status=construction_cost_status,
            status_label=construction_cost_status_label,
        ),
        metric("services_value", "Honorários de projeto", services_value),
        metric("intervention_area", "Área de intervenção", area),
        metric("publication_date", "Publicação", publication),
        metric("submission_deadline", "Entrega das propostas", deadline),
        metric("award_criteria", "Critérios de adjudicação", criteria_summary),
        metric("procedure_type", "Tipo de procedimento", procedure_type),
        metric("document_status", "Estado da documentação", document_status),
    ]


def extract_procedure_analysis(
    *,
    ficha: dict[str, Any],
    textos: dict[str, str],
    concurso: dict[str, Any],
) -> dict[str, Any]:
    documents = _documents(textos)
    classification = infer_analysis_family(concurso, documents)
    family = classification["family"]

    criteria = _extract_criteria(documents)
    common = ficha.get("common_project_extraction") or {}
    if not criteria:
        existing = common.get("award_criteria") or {}
        if existing:
            criteria = {
                "type": _clean(existing.get("type")),
                "summary": _clean(existing.get("summary")),
                "factors": [
                    {
                        "name": _clean(item.get("criterio")),
                        "weight": _percentage(str(item.get("percentagem") or "").replace("%", "")),
                        "subfactors": [],
                        "source_document": _clean(existing.get("source_document")),
                        "evidence_excerpt": _clean(existing.get("excerpt")),
                        "confidence": existing.get("confidence", 0.8),
                    }
                    for item in existing.get("percentages") or []
                    if isinstance(item, dict)
                ],
                "formula": "",
                "tie_breakers": [],
                "interpretation": "Não determinado",
                "source_document": _clean(existing.get("source_document")),
                "source_heading": "Critério de adjudicação",
                "evidence_excerpt": _clean(existing.get("excerpt")),
                "confidence": existing.get("confidence", 0.8),
            }

    submission = _submission_extraction(documents, family)
    eligibility = _eligibility_and_team(documents)
    contract = _scope_and_contract(documents)
    project_profile: dict[str, Any] = {}

    if family == FAMILY_PROJECT_SERVICES:
        project_profile = extract_project_services_profile(
            [
                {
                    "filename": document.filename,
                    "text": document.text,
                    "role": document.role,
                }
                for document in documents
            ]
        )
        if project_profile:
            profile_criteria = project_profile.get("award_criteria") or {}
            if profile_criteria:
                criteria = profile_criteria

            profile_submission = project_profile.get("submission") or {}
            if profile_submission:
                profile_submission["legacy"] = submission.get("legacy") or {}
                submission = profile_submission

            profile_eligibility = project_profile.get("eligibility") or {}
            if profile_eligibility:
                eligibility = {
                    **profile_eligibility,
                    "team": project_profile.get("technical_team") or [],
                }

            profile_contract = project_profile.get("contract") or {}
            if profile_contract:
                contract = profile_contract

    timeline: list[dict[str, Any]] = []
    for key, label in (
        ("publication_date", "Publicação"),
        ("submission_deadline", "Entrega das propostas"),
    ):
        entry = common.get(key) or {}
        value = _date_value(entry)
        if value:
            timeline.append(
                {
                    "key": key,
                    "label": label,
                    "value": value,
                    "phase": "submission",
                    "source_document": _clean(entry.get("source_document")) if isinstance(entry, dict) else "",
                    "confidence": entry.get("confidence", 0.9) if isinstance(entry, dict) else 0.9,
                }
            )

    if project_profile:
        for key, label in (
            ("submission_deadline", "Entrega das propostas"),
            ("proposal_validity", "Validade da proposta"),
            ("opening", "Abertura das propostas"),
        ):
            entry = (project_profile.get("deadlines") or {}).get(key) or {}
            value = _clean(entry.get("value"))
            if value and not any(existing.get("key") == key for existing in timeline):
                timeline.append({
                    "key": key,
                    "label": label,
                    "value": value,
                    "phase": "submission",
                    "source_document": _clean(entry.get("source_document")),
                    "confidence": entry.get("confidence", 0.98),
                })

    for item in contract.get("phases") or []:
        timeline.append(
            {
                "key": item.get("key"),
                "label": item.get("title"),
                "value": _clean(item.get("duration_label")) or "Previsto no contrato",
                "phase": "contract_execution",
                "source_document": item.get("source_document"),
                "confidence": item.get("confidence", 0.85),
            }
        )

    result = {
        "version": VERSION,
        "family": family,
        "family_label": classification["label"],
        "classification": classification,
        "documents": [
            {
                "filename": document.filename,
                "role": document.role,
                "role_confidence": document.confidence,
            }
            for document in documents
        ],
        "award_criteria": criteria,
        "submission": submission,
        "eligibility": eligibility,
        "technical_team": project_profile.get("technical_team") or eligibility.get("team") or [],
        "contract": contract,
        "timeline": timeline,
        "features": project_profile.get("features") or {},
        "design_submission": (project_profile.get("submission") or {}).get("proposal_documents") or [],
        "document_gaps": project_profile.get("document_gaps") or [],
        "inconsistencies": project_profile.get("inconsistencies") or [],
        "formal_risks": (project_profile.get("submission") or {}).get("formal_risks") or [],
        "counts": {
            "documents": len(documents),
            "participant_documents": len(submission["participant_documents"]),
            "proposal_documents": len(submission["proposal_documents"]),
            "formats_and_limits": len(submission["formats_and_limits"]),
            "critical_conditions": len(submission["critical_conditions"]),
            "post_selection_documents": len(submission["post_selection_documents"]),
            "scope_services": len(contract["scope_services"]),
            "contract_deliverables": len(contract["deliverables"]),
            "contract_risks": len(contract["risks"]),
            "technical_team": len(project_profile.get("technical_team") or eligibility.get("team") or []),
            "explicit_exclusions": len(submission.get("critical_conditions") or []),
            "document_gaps": len(project_profile.get("document_gaps") or []),
            "inconsistencies": len(project_profile.get("inconsistencies") or []),
        },
    }
    top_metrics = _top_metrics(
        ficha=ficha,
        concurso=concurso,
        family=family,
        criteria=criteria,
        submission=submission,
    )
    overrides = project_profile.get("top_metric_overrides") or {}
    if overrides:
        metric_map = {str(item.get("key")): item for item in top_metrics}
        for key, override in overrides.items():
            if not isinstance(override, dict) or not _clean(override.get("value")):
                continue
            current = metric_map.get(key)
            payload = {
                "key": key,
                "label": {
                    "procedure_value": "Preço base dos serviços",
                    "construction_cost": "Estimativa de custo da obra",
                    "submission_deadline": "Entrega das propostas",
                    "proposal_validity": "Validade da proposta",
                    "contract_duration": "Prazo máximo do contrato",
                    "award_criteria": "Critérios de adjudicação",
                    "procedure_type": "Tipo de procedimento",
                }.get(key, key.replace("_", " ").title()),
                "value": _clean(override.get("value")),
                "status": _clean(override.get("status")) or "confirmed",
                "status_label": _clean(override.get("status_label")) or "Confirmado",
                "source_document": _clean(override.get("source_document")),
                "source_heading": _clean(override.get("source_heading")),
            }
            if current:
                current.update(payload)
            else:
                top_metrics.append(payload)
                metric_map[key] = payload
    result["top_metrics"] = top_metrics
    return result


def _legacy_requirement_item(item: dict[str, Any], group: str, label: str) -> dict[str, Any]:
    copied = dict(item)
    copied["group"] = group
    copied["group_label"] = label
    copied["phase"] = copied.get("phase") or (
        "submission" if group in {"participant_documents", "design_work", "complementary_documents"}
        else "post_selection" if group == "post_selection_documents"
        else "contract_execution"
    )
    return copied


def apply_procedure_analysis(
    *,
    ficha: dict[str, Any],
    textos: dict[str, str],
    concurso: dict[str, Any],
) -> dict[str, Any]:
    result = extract_procedure_analysis(
        ficha=ficha,
        textos=textos,
        concurso=concurso,
    )
    ficha["procedure_analysis"] = result
    ficha["analysis_family"] = result["family"]

    identification = ficha.setdefault("identificacao", {})
    if isinstance(identification, dict):
        identification["analysis_family"] = result["family"]
        current_type = _fold(identification.get("tipo_procedimento") or concurso.get("tipo_procedimento"))
        if result["family"] == FAMILY_DESIGN_BUILD:
            identification["tipo_procedimento"] = "Conceção-Construção"
        elif result["family"] == FAMILY_DESIGN_COMPETITION and current_type in GENERIC_TYPES:
            identification["tipo_procedimento"] = "Concurso de conceção"
        elif result["family"] == FAMILY_PROJECT_SERVICES and current_type in GENERIC_TYPES:
            identification["tipo_procedimento"] = "Prestação de serviços de projeto"

    criteria = result.get("award_criteria") or {}
    if criteria:
        target = ficha.setdefault("criterios", {})
        if isinstance(target, dict):
            target["criterio_adjudicacao"] = criteria.get("type") or target.get("criterio_adjudicacao")
            target["resumo"] = criteria.get("summary") or target.get("resumo")
            target["detalhe"] = criteria.get("evidence_excerpt") or target.get("detalhe")
            target["percentagens"] = [
                {
                    "criterio": item.get("name"),
                    "percentagem": f"{item.get('weight'):g}%" if isinstance(item.get("weight"), (int, float)) else "",
                }
                for item in criteria.get("factors") or []
            ]
            target["fatores"] = criteria.get("factors") or []
            target["formula"] = criteria.get("formula") or ""
            target["desempate"] = criteria.get("tie_breakers") or []
            target["leitura"] = criteria.get("interpretation") or "Não determinado"

    ficha["project_services_profile"] = {
        "features": result.get("features") or {},
        "document_gaps": result.get("document_gaps") or [],
        "inconsistencies": result.get("inconsistencies") or [],
        "formal_risks": result.get("formal_risks") or [],
    }

    submission = result["submission"]
    if result["family"] == FAMILY_DESIGN_COMPETITION:
        legacy = submission.get("legacy") or ficha.get("submission_requirements") or {}
        ficha["submission_requirements"] = legacy
    else:
        groups = {
            "participant_documents": [
                _legacy_requirement_item(item, "participant_documents", "Documentos que instruem a proposta")
                for item in submission["participant_documents"]
            ],
            "design_work": [
                _legacy_requirement_item(item, "design_work", "Conteúdo técnico da proposta")
                for item in submission["proposal_documents"]
            ],
            "complementary_documents": [],
            "post_selection_documents": [
                _legacy_requirement_item(item, "post_selection_documents", "Após seleção")
                for item in submission["post_selection_documents"]
            ],
            "contract_deliverables": [
                _legacy_requirement_item(item, "contract_deliverables", "Entregáveis do contrato")
                for item in result["contract"]["deliverables"]
            ],
        }
        ficha["submission_requirements"] = {
            "version": VERSION,
            "analysis_family": result["family"],
            "source_documents_used": [item["filename"] for item in result["documents"] if item["role"] in SUBMISSION_ROLES],
            "groups": groups,
            "formats_and_limits": submission["formats_and_limits"],
            "critical_conditions": submission["critical_conditions"],
            "counts": {
                "participant_documents": len(groups["participant_documents"]),
                "design_work": len(groups["design_work"]),
                "complementary_documents": 0,
                "post_selection_documents": len(groups["post_selection_documents"]),
                "contract_deliverables": len(groups["contract_deliverables"]),
                "competition_delivery_types": len(groups["design_work"]),
                "competition_submission_total": len(groups["participant_documents"]) + len(groups["design_work"]),
                "mandatory_confirmed": sum(item.get("mandatory") is True for item in groups["participant_documents"] + groups["design_work"]),
                "conditional": sum(item.get("conditional") is True for item in groups["participant_documents"] + groups["design_work"]),
                "physical_units": 0,
                "digital_files": len(groups["design_work"]),
            },
        }
        ficha["entregaveis"] = {
            "principais": [item["title"] for item in submission["proposal_documents"]]
        }

    extraction = ficha.setdefault("design_competition_extraction", {})
    if isinstance(extraction, dict):
        extraction["procedure_analysis"] = result
        extraction["submission_requirements"] = ficha.get("submission_requirements")
        extraction.setdefault("counts", {})["procedure_documents"] = len(result["documents"])

    insights = ficha.setdefault("document_insights", {})
    if isinstance(insights, dict):
        insights["procedure_analysis"] = result
        if result.get("timeline"):
            existing = insights.get("timeline")
            if not isinstance(existing, list):
                existing = []
            by_key = {
                _fold(item.get("type") or item.get("label") or item.get("key")): item
                for item in existing
                if isinstance(item, dict)
            }
            for item in result["timeline"]:
                by_key[_fold(item.get("label") or item.get("key"))] = {
                    "type": item.get("label"),
                    "value": item.get("value"),
                    "date": item.get("value"),
                    "confirmed": True,
                    "phase": item.get("phase"),
                    "evidence": {
                        "source_document": item.get("source_document"),
                        "confidence": item.get("confidence"),
                        "status": "confirmado",
                    },
                }
            insights["timeline"] = list(by_key.values())

    return result


__all__ = [
    "FAMILY_DESIGN_BUILD",
    "FAMILY_DESIGN_COMPETITION",
    "FAMILY_LABELS",
    "FAMILY_PROJECT_SERVICES",
    "VERSION",
    "apply_procedure_analysis",
    "assess_company_award_fit",
    "classify_document_role",
    "extract_procedure_analysis",
    "infer_analysis_family",
]

# CNLL_CANONICAL_ANALYSIS_V16
# O motor documental legado continua a extrair os factos. Esta camada final
# normaliza a apresentação, a hierarquia dos pesos e as perguntas de perfil.
_apply_procedure_analysis_before_canonical_v16 = apply_procedure_analysis


def apply_procedure_analysis(*, ficha, textos, concurso):
    procedure = _apply_procedure_analysis_before_canonical_v16(
        ficha=ficha,
        textos=textos,
        concurso=concurso,
    )
    from app.analise.canonical_analysis import apply_canonical_analysis
    apply_canonical_analysis(
        ficha=ficha,
        procedure=procedure if isinstance(procedure, dict) else {},
        textos=textos,
        concurso=concurso,
    )
    return procedure

# CNLL_UNIVERSAL_PROGRAM_READER_V18
# Fallback universal inspirado na metodologia documental que funcionou no
# Lumiar: lê o texto real das peças, prioriza Programa do Concurso para
# candidatura e Caderno de Encargos para execução, e só acrescenta factos com
# evidência documental.
_apply_procedure_analysis_before_universal_program_v18 = apply_procedure_analysis


def apply_procedure_analysis(*, ficha, textos, concurso):
    procedure = _apply_procedure_analysis_before_universal_program_v18(
        ficha=ficha,
        textos=textos,
        concurso=concurso,
    )

    from app.analise.universal_document_sections import (
        enrich_procedure_from_documents,
        extract_universal_document_sections,
    )

    extracted = extract_universal_document_sections(textos)
    enriched = enrich_procedure_from_documents(
        procedure if isinstance(procedure, dict) else {},
        extracted,
    )

    ficha["procedure_analysis"] = enriched

    design_extraction = ficha.get("design_competition_extraction")
    if isinstance(design_extraction, dict):
        design_extraction["procedure_analysis"] = enriched

    # Compatibilidade com os cards/estruturas já existentes.
    team = enriched.get("technical_team") or []
    if team:
        ficha["equipa"] = team

    criteria = enriched.get("award_criteria") or {}
    if criteria:
        target = ficha.setdefault("criterios", {})
        if isinstance(target, dict):
            if criteria.get("factors"):
                target["fatores"] = criteria.get("factors")
            if criteria.get("scoring_requirements"):
                target["requisitos_pontuacao"] = criteria.get(
                    "scoring_requirements"
                )

    submission = enriched.get("submission") or {}
    if any(submission.get(key) for key in submission):
        ficha["submission_requirements_v18"] = submission

    # O wrapper V16 já pode ter construído canonical antes deste fallback.
    # Reconstituímos canonical com o procedimento enriquecido.
    from app.analise.canonical_analysis import apply_canonical_analysis

    apply_canonical_analysis(
        ficha=ficha,
        procedure=enriched,
        textos=textos,
        concurso=concurso,
    )

    ficha["universal_program_reader"] = enriched.get(
        "universal_program_reader"
    )

    return enriched
