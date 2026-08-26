"""Leitor universal de Programa do Concurso / Programa do Procedimento.

Camada de fallback determinística sobre o pipeline existente. Não substitui os
readers atuais: enriquece apenas campos em falta com evidência textual real.

Prioridade:
- Programa do Concurso / Procedimento -> candidatura, critérios, equipa, proposta.
- Caderno de Encargos -> âmbito/execução contratual.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, Mapping

VERSION = "universal-program-reader-v18"


PROGRAM_NAME_PATTERNS = (
    r"\bprograma[_\-\s]+do[_\-\s]+concurso\b",
    r"\bprograma[_\-\s]+concurso\b",
    r"\bprograma[_\-\s]+do[_\-\s]+procedimento\b",
    r"\bprograma[_\-\s]+procedimento\b",
    r"\bprograma[_\-\s]+de[_\-\s]+concurso\b",
)

PROGRAM_TEXT_PATTERNS = (
    r"\bprograma\s+do\s+concurso\b",
    r"\bprograma\s+do\s+procedimento\b",
)

PROGRAM_EXCLUDES = (
    "programa preliminar",
    "programa funcional",
    "programa de intervencao",
    "programa base",
)

CONTRACT_NAME_PATTERNS = (
    r"\bcaderno[_\-\s]+de[_\-\s]+encargos\b",
    r"\bcaderno[_\-\s]+encargos\b",
    r"\bclausulas[_\-\s]+tecnicas\b",
)

ROLE_PATTERNS = (
    r"\bcoordenador(?:a)?(?:\s+geral)?(?:\s+do|\s+de)?\s+projeto\b",
    r"\bcoordenador(?:a)?\s+bim\b",
    r"\bgestor(?:a)?\s+bim\b",
    r"\barquiteto(?:a)?(?:\s+coordenador(?:a)?)?\b",
    r"\barquiteto(?:a)?\s+paisagista\b",
    r"\bengenheiro(?:a)?\s+[a-zà-ÿ0-9 /-]{2,70}",
    r"\bautor(?:a)?\s+do\s+projeto\s+de\s+[a-zà-ÿ0-9 /-]{2,70}",
    r"\btecnico(?:a)?\s+(?:responsavel\s+)?(?:por|de)\s+[a-zà-ÿ0-9 /-]{2,70}",
    r"\bespecialista\s+(?:em|de)\s+[a-zà-ÿ0-9 /-]{2,70}",
)

LIST_PREFIX = re.compile(
    r"^\s*(?:[-•▪◦–—]|[a-z]\)|[a-z]\.|[ivxlcdm]+\)|\d+(?:\.\d+){0,4}[.)-]?)\s+",
    re.I,
)

SUBFACTOR_LINE = re.compile(
    r"(?i)\bsubfator\s*([a-z0-9]+(?:\.[a-z0-9]+)*)\b"
    r"[^%\n]{0,220}?(\d+(?:[.,]\d+)?)\s*%"
)

FACTOR_LINE = re.compile(
    r"(?i)\bfator\s*([a-z0-9]+(?:\.[a-z0-9]+)*)?\s*[:\-–—]?\s*"
    r"([^%\n]{2,160}?)\s*(\d+(?:[.,]\d+)?)\s*%"
)

GENERIC_PERCENT_LINE = re.compile(
    r"(?i)^\s*(?:[-•▪◦–—]|\d+(?:\.\d+){0,4}[.)-]?)?\s*"
    r"(.{3,150}?)\s*[:\-–—]?\s*(\d+(?:[.,]\d+)?)\s*%\s*$"
)

YEARS = re.compile(r"(?i)\b(\d{1,2})\s+anos?\b")
PROJECT_COUNT = re.compile(
    r"(?i)\b(\d{1,2})\s+(?:projetos?|obras?|referencias?)\b"
)
EURO = re.compile(
    r"(?i)(?:€\s*)?(\d{1,3}(?:[ .]\d{3})+(?:,\d+)?|\d+(?:,\d+)?)\s*(?:€|euros?)"
)
AREA = re.compile(
    r"(?i)\b(\d{1,3}(?:[ .]\d{3})*(?:,\d+)?)\s*m(?:2|²)\b"
)
HOURS = re.compile(r"(?i)\b(\d{1,4})\s+horas?\b")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    return re.sub(r"[^a-z0-9%€.,:/+\-\s]+", " ", text)


def _number(value: str) -> float | None:
    raw = _clean(value).replace(" ", "")
    if not raw:
        return None
    raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _lines(text: str) -> list[str]:
    result: list[str] = []
    for raw in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _clean(raw)
        if line:
            result.append(line)
    return result


def _is_program(filename: str, text: str) -> bool:
    name = _fold(filename).replace("\\", " ").replace("/", " ")
    head = _fold(text[:6000])

    if any(excluded in name for excluded in PROGRAM_EXCLUDES):
        return False

    if any(re.search(pattern, name, re.I) for pattern in PROGRAM_NAME_PATTERNS):
        return True

    return any(re.search(pattern, head, re.I) for pattern in PROGRAM_TEXT_PATTERNS)


def _is_contract(filename: str, text: str) -> bool:
    name = _fold(filename).replace("\\", " ").replace("/", " ")
    head = _fold(text[:5000])
    if any(re.search(pattern, name, re.I) for pattern in CONTRACT_NAME_PATTERNS):
        return True
    return "caderno de encargos" in head


def _heading_like(line: str) -> bool:
    plain = _clean(line)
    if len(plain) > 150:
        return False
    folded = _fold(plain)

    if re.match(r"^\d+(?:\.\d+){0,4}\s+", folded):
        return True
    if len(plain) <= 85 and plain == plain.upper() and any(ch.isalpha() for ch in plain):
        return True

    heading_words = (
        "criterio de adjudicacao",
        "criterios de adjudicacao",
        "modelo de avaliacao",
        "fatores de avaliacao",
        "equipa tecnica",
        "equipa projetista",        "equipa de projeto",
        "documentos que instruem",
        "documentos da proposta",
        "conteudo da proposta",
        "apresentacao da proposta",
        "modo de apresentacao",
        "causas de exclusao",
        "exclusao das propostas",
        "documentos de habilitacao",
        "habilitacao do adjudicatario",
        "objeto do contrato",
        "fases do projeto",
        "fases da prestacao",
        "condicoes de pagamento",
        "penalidades",
    )
    return any(word in folded for word in heading_words)


def _section_windows(
    lines: list[str],
    triggers: Iterable[str],
    *,
    max_lines: int = 90,
) -> list[tuple[str, list[str]]]:
    folded_triggers = tuple(_fold(item) for item in triggers)
    result: list[tuple[str, list[str]]] = []

    for index, line in enumerate(lines):
        probe = _fold(line)
        if not any(trigger in probe for trigger in folded_triggers):
            continue

        collected = [line]
        for cursor in range(index + 1, min(len(lines), index + max_lines)):
            candidate = lines[cursor]
            if cursor > index + 3 and _heading_like(candidate):
                break
            collected.append(candidate)

        result.append((line, collected))

    return result


def _context(lines: list[str], index: int, radius: int = 2) -> str:
    start = max(0, index - radius)
    end = min(len(lines), index + radius + 1)
    return _clean(" ".join(lines[start:end]))[:900]

_TEAM_ROLE_START = re.compile(
    r"(?i)^(?:coordenador(?:a)?|gestor(?:a)?|diretor(?:a)?|"
    r"autor(?:a)?|perito|t[ée]cnico(?:a)?|especialista)\b"
)


def _team_submission_context(lines: list[str]) -> bool:
    """Detecta a obrigação de identificar a equipa com a proposta."""
    text = _fold(" ".join(lines))
    has_proposal_documents = (
        "documentos que instruem a proposta" in text
        or "documentos que constituem a proposta" in text
    )
    has_team_reference = (
        ("identifica" in text and "equipa" in text and "proposta" in text)
        or ("equipa tecnica" in text and "proposta" in text)
    )
    return has_proposal_documents and has_team_reference

def _role_title(lines: list[str], index: int) -> str:
    """Retorna o nome completo de uma role tabelada, sem a janela de contexto."""
    title = _clean(lines[index])
    for offset in range(index + 1, min(len(lines), index + 3)):
        candidate = _clean(lines[offset])
        if not candidate or _heading_like(candidate) or _TEAM_ROLE_START.match(candidate):
            break
        if re.match(r"(?i)^p[Ã¡a]gina\s+\d+", candidate):
            break
        if len(title) + len(candidate) > 300:
            break
        title = _clean(f"{title} {candidate}")
    title = re.sub(r"(?i)\s+p[Ã¡a]gina\s+\d+\s+de\s+\d+.*$", "", title)
    return title[:300].strip(" -:;,." )


def _dedupe(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in items:
        role_key = _fold(item.get("role"))
        signature = (
            f"role|{role_key}"
            if role_key
            else _fold(
                "|".join(
                    [
                        _clean(item.get("subfactor_code")),
                        _clean(item.get("title")),
                        _clean(item.get("summary")),
                    ]
                )
            )
        )
        if not signature or signature in seen:
            continue
        seen.add(signature)
        output.append(item)

    return output

def _parameters(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}

    years = [int(match.group(1)) for match in YEARS.finditer(text)]
    if years:
        result["years"] = max(years)

    counts = [int(match.group(1)) for match in PROJECT_COUNT.finditer(text)]
    if counts:
        result["project_count"] = max(counts)

    hours = [int(match.group(1)) for match in HOURS.finditer(text)]
    if hours:
        result["training_hours"] = max(hours)

    euros = [_number(match.group(1)) for match in EURO.finditer(text)]
    euros = [value for value in euros if value is not None]
    if euros:
        result["project_value_eur"] = max(euros)

    areas = [_number(match.group(1)) for match in AREA.finditer(text)]
    areas = [value for value in areas if value is not None]
    if areas:
        result["area_m2"] = max(areas)

    return result


def _extract_roles(
    filename: str,
    lines: list[str],
    *,
    only_scored: bool = False,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    role_regex = re.compile("|".join(f"(?:{pattern})" for pattern in ROLE_PATTERNS), re.I)
    proposal_team_required = _team_submission_context(lines)
    team_region = False

    for index, line in enumerate(lines):
        folded_line = _fold(line)
        if (("ficha de" in folded_line and "identifica" in folded_line and "equipa" in folded_line) or any(marker in folded_line for marker in (
            "ficha de identificacao da equipa",
            "equipa projetista",
            "equipa tecnica a identificar na proposta",
            "composicao da equipa",
        ))):
            team_region = True
        elif team_region and re.match(r"(?i)^anexo\s+[a-z0-9]+", folded_line):
            team_region = False

        explicit_role = bool(_TEAM_ROLE_START.match(_clean(line)))
        match = role_regex.search(folded_line)
        if not match and not explicit_role:
            continue

        context = _context(lines, index, 3)
        context_folded = _fold(context)
        scored = bool(
            "%" in context
            or "pontu" in context_folded
            or "avaliacao" in context_folded
            or "subfator" in context_folded
        )
        if not team_region and not scored:
            continue
        if only_scored and not scored:
            continue

        role = _role_title(lines, index) if explicit_role else _clean(match.group(0)).title()
        if not role or len(role) < 5:
            continue

        nearby = _fold(" ".join(lines[max(0, index - 24): index + 1]))
        post_award = any(
            marker in nearby
            for marker in (
                "habilitacao do adjudicatario",
                "documentos de habilitacao",
                "declaracoes das ordens profissionais",
                "apos adjudicacao",
            )
        )
        required_at_submission = bool(proposal_team_required and team_region and not post_award)
        if post_award:
            phase, stage = "habilitation", "post_award"
        elif required_at_submission:
            phase, stage = "competition", "pre_award"
        else:
            phase, stage = "execution", "post_award"

        source_heading = "Equipa / experiência"
        annex_name = ""
        for previous in reversed(lines[: index + 1]):
            previous_folded = _fold(previous)
            if "anexo" in previous_folded and len(previous) <= 180:
                source_heading = _clean(previous)
                annex_match = re.search(r"(?i)\banexo\s+([a-z0-9]+)", previous_folded)
                annex_name = annex_match.group(1) if annex_match else ""
                break
            if "equipa projetista" in previous_folded or ("ficha de" in previous_folded and "equipa" in previous_folded):
                source_heading = _clean(previous)
        sub_code = ""
        sub_match = re.search(r"(?i)\bsubfator\s*([a-z0-9]+(?:\.[a-z0-9]+)*)", context)
        if sub_match:
            sub_code = sub_match.group(1)

        weight = None
        weight_match = re.search(r"(\d+(?:[.,]\d+)?)\s*%", context)
        if weight_match:
            weight = _number(weight_match.group(1))

        item = {
            "title": role,
            "role": role,
            "summary": context if not explicit_role else role,
            "subfactor_code": sub_code or None,
            "weight_percent": weight,
            "parameters": _parameters(context),
            "source_document": filename,
            "source_heading": source_heading,
            "evidence_excerpt": context,
            "confidence": 0.9 if required_at_submission else (0.86 if scored else 0.78),
            "phase": phase,
            "stage": stage,
            "nature": "team",
            "profile_dependent": required_at_submission,
            "required_at_submission": required_at_submission,
            "mandatory": required_at_submission,
            "evidence_kind": "proposal_document" if required_at_submission else "procedural_role",
        }
        if annex_name:
            item["cross_reference"] = {
                "kind": "annex",
                "name": annex_name,
                "inherited_from": "proposal_team_requirement" if required_at_submission else None,
            }
        result.append(item)

    return _dedupe(result)

def _extract_scoring(filename: str, lines: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    factors: list[dict[str, Any]] = []
    scoring: list[dict[str, Any]] = []

    factor_sections = _section_windows(
        lines,
        (
            "criterio de adjudicacao",
            "criterios de adjudicacao",
            "modelo de avaliacao",
            "fatores de avaliacao",
            "fatores e subfatores",
            "valia tecnica",
        ),
        max_lines=140,
    )

    candidate_lines: list[str] = []
    for _, section in factor_sections:
        candidate_lines.extend(section)

    if not candidate_lines:
        candidate_lines = [
            line
            for line in lines
            if "%" in line and any(
                word in _fold(line)
                for word in ("preco", "fator", "subfator", "qualidade", "experiencia", "equipa", "valia")
            )
        ]

    parent_by_code: dict[str, dict[str, Any]] = {}

    for line in candidate_lines:
        sub = SUBFACTOR_LINE.search(line)
        if sub:
            code = sub.group(1)
            weight = _number(sub.group(2))
            label = re.sub(
                r"(?i)^.*?\bsubfator\s*" + re.escape(code) + r"\b\s*[:\-–—]?\s*",
                "",
                line,
            )
            label = re.sub(r"\s*\d+(?:[.,]\d+)?\s*%\s*$", "", label).strip(" -–—:")
            if label:
                item = {
                    "code": code,
                    "label": label[:240],
                    "title": label[:240],
                    "subfactor_code": code,
                    "weight_percent": weight,
                    "summary": line[:900],
                    "source_document": filename,
                    "source_heading": "Critérios de adjudicação",
                    "evidence_excerpt": line[:900],
                    "parameters": _parameters(line),
                    "profile_dependent": bool(
                        re.search(
                            r"(?i)experi|equipa|coorden|arquit|engenhe|bim|projeto|obra|certifica|formacao",
                            _fold(line),
                        )
                    ),
                }
                scoring.append(item)
            continue

        factor = FACTOR_LINE.search(line)
        if factor:
            code = _clean(factor.group(1))
            label = _clean(factor.group(2)).strip(" -–—:")
            weight = _number(factor.group(3))
            if label:
                item = {
                    "code": code or label[:24],
                    "label": label[:240],
                    "weight_percent": weight,
                    "source_document": filename,
                    "source_heading": "Critérios de adjudicação",
                    "evidence_excerpt": line[:900],
                    "subfactors": [],
                }
                factors.append(item)
                if code:
                    parent_by_code[code.split(".")[0]] = item
            continue

        generic = GENERIC_PERCENT_LINE.search(line)
        if generic:
            label = _clean(generic.group(1)).strip(" -–—:")
            weight = _number(generic.group(2))
            folded = _fold(label)
            if not label or len(label) > 150:
                continue
            if any(word in folded for word in ("preco", "qualidade", "valia", "experiencia", "equipa", "metodologia", "prazo")):
                factors.append(
                    {
                        "code": label[:24],
                        "label": label[:240],
                        "weight_percent": weight,
                        "source_document": filename,
                        "source_heading": "Critérios de adjudicação",
                        "evidence_excerpt": line[:900],
                        "subfactors": [],
                    }
                )

    # Associa subfatores ao fator pai apenas quando o código o permite.
    for sub in scoring:
        code = _clean(sub.get("subfactor_code"))
        parent_code = code.split(".")[0] if "." in code else ""
        parent = parent_by_code.get(parent_code)
        if parent is not None:
            parent.setdefault("subfactors", []).append(
                {
                    "code": code,
                    "label": sub["label"],
                    "weight_percent": sub.get("weight_percent"),
                    "summary": sub.get("summary"),
                    "source_document": filename,
                    "evidence_excerpt": sub.get("evidence_excerpt"),
                }
            )
            sub["factor_code"] = parent.get("code")

    return _dedupe(factors), _dedupe(scoring)


# CNLL_UNIVERSAL_READER_QUALITY_V18_1
def _starts_like_list_item(line: str) -> bool:
    return bool(LIST_PREFIX.match(line))


def _document_item_candidate(line: str) -> bool:
    """Aceita itens documentais explícitos; rejeita prosa narrativa."""
    cleaned = LIST_PREFIX.sub("", _clean(line)).strip(" -–—;:")
    folded = _fold(cleaned)

    if not cleaned or len(cleaned) > 420:
        return False

    if _starts_like_list_item(line):
        return True

    return bool(
        re.match(
            r"(?i)^(?:"
            r"declaracao|certidao|comprovativo|curriculum|curriculo|cv|"
            r"formulario|memoria|relatorio|plano|cronograma|programa de trabalhos|"
            r"termo de responsabilidade|nota justificativa|proposta|"
            r"ficheiro|documento|pecas? escritas?|pecas? desenhadas?|"
            r"seguro|garantia|caucao"
            r")\b",
            folded,
        )
    )


def _list_items(
    filename: str,
    lines: list[str],
    triggers: Iterable[str],
    heading: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for section_heading, section in _section_windows(lines, triggers, max_lines=80):
        for line in section[1:]:
            if not _document_item_candidate(line):
                continue

            cleaned = LIST_PREFIX.sub("", line).strip(" -–—;:")
            if not cleaned:
                continue

            result.append(
                {
                    "title": cleaned[:320],
                    "summary": cleaned[:900],
                    "source_document": filename,
                    "source_heading": section_heading[:240] or heading,
                    "evidence_excerpt": line[:900],
                    "confidence": 0.9 if _starts_like_list_item(line) else 0.82,
                }
            )

    return _dedupe(result)


_PHASE_TERMS = (
    "estudo previo",
    "programa base",
    "anteprojeto",
    "projeto de execucao",
    "projeto execucao",
    "assistencia tecnica",
    "levantamento",
    "sondagens",
    "licenciamento",
    "aprovacao",
    "fase i",
    "fase ii",
    "fase iii",
    "fase iv",
    "etapa i",
    "etapa ii",
    "etapa iii",
    "etapa iv",
)

_DELIVERABLE_TERMS = (
    "pecas escritas",
    "pecas desenhadas",
    "memoria",
    "relatorio",
    "mapa",
    "medicoes",
    "orcamento",
    "caderno de encargos",
    "ficheiro",
    "pdf",
    "dwg",
    "dxf",
    "modelo bim",
    "modelo ifc",
)

_STRONG_RISK_TERMS = (
    "penalidade",
    "multa",
    "sancao",
    "incumprimento",
    "atraso imputavel",
    "responsabilidade civil",
    "seguro de responsabilidade",
    "caucao",
    "garantia bancaria",
    "resolucao do contrato",
)


def _contract_kind(heading: str) -> str:
    probe = _fold(heading)
    if "fase" in probe:
        return "phases"
    if "pagamento" in probe:
        return "payments"
    if "entreg" in probe:
        return "deliverables"
    if "risco" in probe or "penal" in probe:
        return "risks"
    return "scope"


def _explicit_phase(line: str) -> bool:
    probe = _fold(line)

    if re.match(r"^(?:fase|etapa)\s*(?:[ivx]+|\d+)?\b", probe, re.I):
        return True

    if any(term in probe for term in _PHASE_TERMS):
        return _starts_like_list_item(line) or len(_clean(line)) <= 150

    return False


def _explicit_payment(line: str) -> bool:
    probe = _fold(line)

    if not (
        "%" in line
        or "pagamento" in probe
        or "fatura" in probe
        or "prestacao" in probe
        or "honorario" in probe
    ):
        return False

    return _starts_like_list_item(line) or len(_clean(line)) <= 200


def _explicit_deliverable(line: str) -> bool:
    probe = _fold(line)

    if not any(term in probe for term in _DELIVERABLE_TERMS):
        return False

    return _starts_like_list_item(line) or len(_clean(line)) <= 180


def _explicit_risk(line: str) -> bool:
    probe = _fold(line)

    if not any(term in probe for term in _STRONG_RISK_TERMS):
        return False

    return len(_clean(line)) <= 260


def _explicit_scope(line: str) -> bool:
    return _starts_like_list_item(line) and len(_clean(line)) <= 240


def _contract_items(
    filename: str,
    lines: list[str],
    triggers: Iterable[str],
    heading: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    kind = _contract_kind(heading)

    matcher = {
        "phases": _explicit_phase,
        "payments": _explicit_payment,
        "deliverables": _explicit_deliverable,
        "risks": _explicit_risk,
        "scope": _explicit_scope,
    }[kind]

    for section_heading, section in _section_windows(lines, triggers, max_lines=70):
        for line in section[1:]:
            if len(line) < 4 or len(line) > 520:
                continue
            if _heading_like(line):
                continue
            if not matcher(line):
                continue

            cleaned = LIST_PREFIX.sub("", line).strip(" -–—;:")
            if not cleaned:
                continue

            result.append(
                {
                    "title": cleaned[:320],
                    "summary": cleaned[:900],
                    "source_document": filename,
                    "source_heading": section_heading[:240] or heading,
                    "evidence_excerpt": line[:900],
                    "confidence": 0.9,
                }
            )

            if len(result) >= 12:
                break

    return _dedupe(result)

def extract_universal_document_sections(
    textos: Mapping[str, str] | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "version": VERSION,
        "program_documents": [],
        "contract_documents": [],
        "award_criteria": {"factors": [], "scoring_requirements": []},
        "technical_team": [],
        "eligibility": {
            "explicit_exclusions": [],
            "eligibility_requirements": [],
        },
        "submission": {
            "participant_documents": [],
            "proposal_documents": [],
            "formats_and_limits": [],
            "critical_conditions": [],
            "post_selection_documents": [],
        },
        "contract": {
            "scope_services": [],
            "phases": [],
            "payments": [],
            "deliverables": [],
            "risks": [],
        },
    }

    if not isinstance(textos, Mapping):
        return result

    for filename, raw_text in textos.items():
        text = str(raw_text or "")
        if not text.strip():
            continue

        lines = _lines(text)

        if _is_program(filename, text):
            result["program_documents"].append(filename)

            factors, scoring = _extract_scoring(filename, lines)
            result["award_criteria"]["factors"].extend(factors)
            result["award_criteria"]["scoring_requirements"].extend(scoring)

            result["technical_team"].extend(
                _extract_roles(filename, lines, only_scored=False)
            )

            result["submission"]["participant_documents"].extend(
                _list_items(
                    filename,
                    lines,
                    (
                        "documentos que instruem a proposta",
                        "documentos que constituem a proposta",
                        "elementos que instruem a proposta",
                        "elementos que constituem a proposta",
                    ),
                    "Documentos que instruem a proposta",
                )
            )

            result["submission"]["proposal_documents"].extend(
                _list_items(
                    filename,
                    lines,
                    (
                        "conteudo da proposta",
                        "conteudo tecnico da proposta",
                        "elementos tecnicos da proposta",
                        "proposta tecnica",
                    ),
                    "Conteúdo técnico da proposta",
                )
            )

            result["submission"]["formats_and_limits"].extend(
                _list_items(
                    filename,
                    lines,
                    (
                        "apresentacao da proposta",
                        "modo de apresentacao",
                        "formato dos documentos",
                        "formato da proposta",
                        "submissao da proposta",
                    ),
                    "Formatos e submissão",
                )
            )

            exclusions = _list_items(
                filename,
                lines,
                (
                    "causas de exclusao",
                    "exclusao das propostas",
                    "motivos de exclusao",
                    "condicoes de exclusao",
                ),
                "Exclusões",
            )
            result["eligibility"]["explicit_exclusions"].extend(exclusions)
            result["submission"]["critical_conditions"].extend(exclusions)

            result["eligibility"]["eligibility_requirements"].extend(
                _list_items(
                    filename,
                    lines,
                    (
                        "condicoes de participacao",
                        "requisitos de participacao",
                        "requisitos do concorrente",
                        "capacidade tecnica",
                        "habilitacao tecnica",
                    ),
                    "Elegibilidade",
                )
            )

            result["submission"]["post_selection_documents"].extend(
                _list_items(
                    filename,
                    lines,
                    (
                        "habilitacao do adjudicatario",
                        "documentos de habilitacao",
                        "documentos do adjudicatario",
                    ),
                    "Habilitação",
                )
            )

        if _is_contract(filename, text):
            result["contract_documents"].append(filename)

            result["contract"]["scope_services"].extend(
                _contract_items(
                    filename,
                    lines,
                    (
                        "objeto do contrato",
                        "objeto da prestacao",
                        "ambito dos servicos",
                        "servicos a prestar",
                    ),
                    "Âmbito do contrato",
                )
            )

            result["contract"]["phases"].extend(
                _contract_items(
                    filename,
                    lines,
                    (
                        "fases da prestacao",
                        "fases do projeto",
                        "fases dos servicos",
                        "faseamento",
                    ),
                    "Fases",
                )
            )

            result["contract"]["payments"].extend(
                _contract_items(
                    filename,
                    lines,
                    (
                        "condicoes de pagamento",
                        "pagamentos",
                        "preco e pagamento",
                    ),
                    "Pagamentos",
                )
            )

            result["contract"]["deliverables"].extend(
                _contract_items(
                    filename,
                    lines,
                    (
                        "elementos a entregar",
                        "entregaveis",
                        "documentos a entregar",
                    ),
                    "Entregáveis",
                )
            )

            result["contract"]["risks"].extend(
                _contract_items(
                    filename,
                    lines,
                    (
                        "penalidades",
                        "multas",
                        "incumprimento",
                        "responsabilidade civil",
                        "seguros",
                        "caucao",
                    ),
                    "Riscos contratuais",
                )
            )

    result["award_criteria"]["factors"] = _dedupe(
        result["award_criteria"]["factors"]
    )
    result["award_criteria"]["scoring_requirements"] = _dedupe(
        result["award_criteria"]["scoring_requirements"]
    )
    result["technical_team"] = _dedupe(result["technical_team"])

    for key in result["eligibility"]:
        result["eligibility"][key] = _dedupe(result["eligibility"][key])

    for key in result["submission"]:
        result["submission"][key] = _dedupe(result["submission"][key])

    for key in result["contract"]:
        result["contract"][key] = _dedupe(result["contract"][key])

    return result


def _merge_list(existing: Any, extra: Any) -> list[dict[str, Any]]:
    return _dedupe(
        [
            *([item for item in existing if isinstance(item, dict)] if isinstance(existing, list) else []),
            *([item for item in extra if isinstance(item, dict)] if isinstance(extra, list) else []),
        ]
    )


def enrich_procedure_from_documents(
    procedure: dict[str, Any] | None,
    extracted: dict[str, Any],
) -> dict[str, Any]:
    procedure = dict(procedure or {})

    award = dict(procedure.get("award_criteria") or {})
    extracted_award = extracted.get("award_criteria") or {}

    award["factors"] = _merge_list(
        award.get("factors"),
        extracted_award.get("factors"),
    )
    award["scoring_requirements"] = _merge_list(
        award.get("scoring_requirements"),
        extracted_award.get("scoring_requirements"),
    )
    procedure["award_criteria"] = award

    procedure["technical_team"] = _merge_list(
        procedure.get("technical_team"),
        extracted.get("technical_team"),
    )

    eligibility = dict(procedure.get("eligibility") or {})
    extracted_eligibility = extracted.get("eligibility") or {}
    for key in ("explicit_exclusions", "eligibility_requirements"):
        eligibility[key] = _merge_list(
            eligibility.get(key),
            extracted_eligibility.get(key),
        )
    procedure["eligibility"] = eligibility

    submission = dict(procedure.get("submission") or {})
    extracted_submission = extracted.get("submission") or {}
    for key in (
        "participant_documents",
        "proposal_documents",
        "formats_and_limits",
        "critical_conditions",
        "post_selection_documents",
    ):
        submission[key] = _merge_list(
            submission.get(key),
            extracted_submission.get(key),
        )
    procedure["submission"] = submission

    contract = dict(procedure.get("contract") or {})
    extracted_contract = extracted.get("contract") or {}
    for key in (
        "scope_services",
        "phases",
        "payments",
        "deliverables",
        "risks",
    ):
        contract[key] = _merge_list(
            contract.get(key),
            extracted_contract.get(key),
        )
    procedure["contract"] = contract

    procedure["universal_program_reader"] = {
        "version": extracted.get("version"),
        "program_documents": list(extracted.get("program_documents") or []),
        "contract_documents": list(extracted.get("contract_documents") or []),
        "scoring_count": len(award.get("scoring_requirements") or []),
        "team_count": len(procedure.get("technical_team") or []),
        "submission_count": sum(
            len(submission.get(key) or [])
            for key in (
                "participant_documents",
                "proposal_documents",
                "formats_and_limits",
                "critical_conditions",
                "post_selection_documents",
            )
        ),
    }

    return procedure
