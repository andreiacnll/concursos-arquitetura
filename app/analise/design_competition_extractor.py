from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

from app.analise.design_competition_enrichment import enrich_design_competition

from app.architecture_intelligence.schemas import (
    ConsolidatedCompetitionData,
)

from app.analise.submission_requirements import (
    extract_submission_requirements,
)


TARGET_FIELDS = {
    "competition_prize_first",
    "competition_prize_second",
    "competition_prize_third",
    "competition_prize_mentions",
    "competition_prize_total",
    "procedure_value",
    "estimated_construction_cost",
    "design_services_value",
    "submission_panel_quantity",
    "submission_panel_format",
    "descriptive_memory",
    "digital_files",
    "anonymity_requirement",
    "submission_platform",
    "submission_deadline",
    "site_visit",
    "clarification_deadline",
    "execution_project",
    "technical_assistance",
    "final_drawings",
    "measurements",
    "quantity_schedule",
    "approval_requirement",
    "specialties",
    "project_phases",
    "payment_conditions",
    "program_summary",
    "intervention_type",
    "total_area",
    "functional_areas",
    "main_spaces",
    "functional_requirements",
    "constraints",
}

NUMBER_WORDS = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
}


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = text.lower()
    text = re.sub(r"[^a-z0-9.,%€\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _source_id(filename: str) -> str:
    digest = hashlib.sha256(
        filename.encode("utf-8")
    ).hexdigest()[:16]
    return f"worker-source-{digest}"


def _documents(
    textos: dict[str, str],
) -> list[tuple[str, str, str]]:
    blocked = {
        "ficha.json",
        "analise.json",
        "textos.json",
        "analise_ai.json",
        "consolidated.json",
    }
    output: list[tuple[str, str, str]] = []

    for raw_filename, raw_text in (textos or {}).items():
        filename = Path(
            str(raw_filename or "documento.txt")
        ).name
        if filename.casefold() in blocked:
            continue

        raw = str(raw_text or "").replace("\x00", " ")
        if not raw.strip():
            continue

        output.append((filename, raw, _normalize(raw)))

    return output


def _parse_number(raw: str) -> float | None:
    compact = str(raw or "").replace(" ", "")
    if not compact:
        return None

    if "," in compact and "." in compact:
        if compact.rfind(",") > compact.rfind("."):
            normalized = (
                compact.replace(".", "")
                .replace(",", ".")
            )
        else:
            normalized = compact.replace(",", "")
    elif "," in compact:
        head, tail = compact.rsplit(",", 1)
        normalized = (
            f"{head.replace(',', '')}.{tail}"
            if len(tail) == 2
            else compact.replace(",", "")
        )
    elif "." in compact:
        parts = compact.split(".")
        if len(parts) > 2:
            normalized = (
                "".join(parts[:-1]) + "." + parts[-1]
                if len(parts[-1]) == 2
                else "".join(parts)
            )
        else:
            head, tail = parts
            normalized = (
                f"{head}.{tail}"
                if len(tail) == 2
                else head + tail
            )
    else:
        normalized = compact

    try:
        return float(normalized)
    except ValueError:
        return None


def _format_money(raw: str) -> str:
    number = _parse_number(raw)
    if number is None:
        clean = " ".join(str(raw or "").split())
        return f"{clean} EUR"

    has_decimals = bool(
        re.search(r"[,.]\d{2}$", str(raw or "").strip())
    )
    formatted = (
        f"{number:,.2f}"
        if has_decimals
        else f"{number:,.0f}"
    )
    formatted = (
        formatted.replace(",", "§")
        .replace(".", ",")
        .replace("§", " ")
    )
    return f"{formatted} EUR"


AMOUNT = (
    r"(\d{1,3}(?:[.\s]\d{3})+(?:[,.]\d{2})?"
    r"|\d{4,}(?:[,.]\d{2})?)"
)


def _first_match(
    normalized: str,
    patterns: list[str],
) -> str:
    for pattern in patterns:
        match = re.search(
            pattern,
            normalized,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1).strip()
    return ""


def _sentence(
    raw: str,
    needle: str,
    limit: int = 240,
) -> str:
    match = re.search(needle, raw, re.IGNORECASE)
    if not match:
        return ""

    start = max(
        raw.rfind(".", 0, match.start()) + 1,
        raw.rfind("\n", 0, match.start()) + 1,
    )
    end_candidates = [
        value
        for value in (
            raw.find(".", match.end()),
            raw.find("\n", match.end()),
        )
        if value >= 0
    ]
    end = (
        min(end_candidates) + 1
        if end_candidates
        else min(len(raw), match.end() + limit)
    )
    value = " ".join(raw[start:end].split()).strip()
    return value[:limit].strip()


def _item(
    field_name: str,
    value: str,
    *,
    filename: str,
    phase: str,
    block: str,
    confidence: float = 0.98,
) -> dict[str, Any]:
    return {
        "field_name": field_name,
        "value": value,
        "normalized_value": value,
        "knowledge_block": block,
        "phase": phase,
        "purpose": "display",
        "source_document": filename,
        "source_document_id": _source_id(filename),
        "document_category": "design_competition_source",
        "confidence": confidence,
        "evidence_ids": [],
        "document_priority": 100,
        "reader_name": "design_competition_extractor",
        "section": "explicit_document_fact",
    }


def _fact(
    facts: dict[str, dict[str, Any]],
    field_name: str,
    value: str,
    filename: str,
    *,
    phase: str,
    block: str,
    confidence: float = 0.98,
) -> None:
    clean = " ".join(str(value or "").split()).strip()
    if not clean:
        return
    facts[field_name] = _item(
        field_name,
        clean,
        filename=filename,
        phase=phase,
        block=block,
        confidence=confidence,
    )


def _financial_facts(
    documents: list[tuple[str, str, str]],
    facts: dict[str, dict[str, Any]],
) -> None:
    for filename, _raw, normalized in documents:
        procedure = _first_match(
            normalized,
            [
                (
                    r"valor do preco base do procedimento"
                    r".{0,120}?" + AMOUNT
                ),
                (
                    r"preco base do procedimento"
                    r".{0,120}?" + AMOUNT
                ),
            ],
        )
        if procedure:
            _fact(
                facts,
                "procedure_value",
                _format_money(procedure),
                filename,
                phase="administrative",
                block="financials",
            )

        construction = _first_match(
            normalized,
            [
                (
                    r"preco base da empreitada"
                    r".{0,220}?(?:estima se em|e de|de)"
                    r".{0,60}?" + AMOUNT
                ),
                (
                    r"valor de obra"
                    r".{0,180}?" + AMOUNT
                ),
                (
                    r"custo estimado da obra"
                    r".{0,180}?" + AMOUNT
                ),
            ],
        )
        if construction:
            _fact(
                facts,
                "estimated_construction_cost",
                _format_money(construction),
                filename,
                phase="administrative",
                block="financials",
            )

        services = _first_match(
            normalized,
            [
                (
                    r"clausula 30.{0,120}?preco contratual"
                    r".{0,900}?pagara.{0,240}?montante de"
                    r".{0,60}?" + AMOUNT
                ),
                (
                    r"pela aquisicao dos servicos objeto do contrato"
                    r".{0,500}?montante de.{0,60}?" + AMOUNT
                ),
                (
                    r"valor maximo dos servicos de projeto"
                    r".{0,160}?" + AMOUNT
                ),
                (
                    r"honorarios?.{0,160}?" + AMOUNT
                ),
            ],
        )
        if services:
            _fact(
                facts,
                "design_services_value",
                _format_money(services),
                filename,
                phase="administrative",
                block="financials",
            )

        prize_rules = [
            (
                "competition_prize_first",
                [
                    r"primeiro lugar.{0,220}?" + AMOUNT,
                    r"1 o premio.{0,220}?" + AMOUNT,
                ],
            ),
            (
                "competition_prize_second",
                [
                    r"segundo lugar.{0,220}?" + AMOUNT,
                    r"2 o premio.{0,220}?" + AMOUNT,
                ],
            ),
            (
                "competition_prize_third",
                [
                    r"terceiro lugar.{0,220}?" + AMOUNT,
                    r"3 o premio.{0,220}?" + AMOUNT,
                ],
            ),
            (
                "competition_prize_total",
                [
                    (
                        r"montante global dos premios"
                        r".{0,160}?" + AMOUNT
                    ),
                    r"total dos premios.{0,160}?" + AMOUNT,
                ],
            ),
        ]

        for field_name, patterns in prize_rules:
            amount = _first_match(normalized, patterns)
            if amount:
                _fact(
                    facts,
                    field_name,
                    _format_money(amount),
                    filename,
                    phase="administrative",
                    block="financials",
                )


def _submission_facts(
    documents: list[tuple[str, str, str]],
    facts: dict[str, dict[str, Any]],
) -> None:
    for filename, raw, normalized in documents:
        quantity_match = re.search(
            r"\b(\d+|um|uma|dois|duas|tres|quatro|cinco|seis)"
            r"\s*(?:\([^)]*\)\s*)?paineis?\b",
            normalized,
            re.IGNORECASE,
        )
        if quantity_match:
            token = quantity_match.group(1).lower()
            quantity = (
                int(token)
                if token.isdigit()
                else NUMBER_WORDS.get(token)
            )
            if quantity:
                _fact(
                    facts,
                    "submission_panel_quantity",
                    str(quantity),
                    filename,
                    phase="submission",
                    block="submission_deliverables",
                )

        if re.search(
            r"\bpaineis?\s+a1\b|\bformato\s+a1\b",
            normalized,
        ):
            orientation = ""
            if "horizontal" in normalized:
                orientation = " horizontal"
            elif "vertical" in normalized:
                orientation = " vertical"

            support = (
                " · formato físico"
                if "formato fisico" in normalized
                else ""
            )
            _fact(
                facts,
                "submission_panel_format",
                f"A1{orientation}{support}",
                filename,
                phase="submission",
                block="submission_deliverables",
            )

        sentence_rules = [
            (
                "descriptive_memory",
                r"mem[oó]ria\s+descritiva",
                "submission_deliverables",
            ),
            (
                "digital_files",
                (
                    r"ficheiros?\s+(?:pdf|jpg|digitais?)"
                    r"|formato\s+digital"
                    r"|suporte\s+digital"
                ),
                "submission_deliverables",
            ),
            (
                "anonymity_requirement",
                r"anonim",
                "submission_deliverables",
            ),
            (
                "submission_platform",
                (
                    r"acingov"
                    r"|plataforma\s+eletr[oó]nica"
                    r"|edelivery"
                ),
                "submission_deliverables",
            ),
            (
                "submission_deadline",
                (
                    r"prazo\s+para\s+apresenta[cç][aã]o"
                    r"|data\s+limite\s+de\s+entrega"
                ),
                "schedule",
            ),
            (
                "site_visit",
                r"visita\s+ao\s+local",
                "schedule",
            ),
            (
                "clarification_deadline",
                (
                    r"pedidos?\s+de\s+esclarecimento"
                    r"|prazo\s+para\s+esclarecimentos"
                ),
                "schedule",
            ),
        ]

        for field_name, needle, block in sentence_rules:
            value = _sentence(raw, needle)
            if value:
                _fact(
                    facts,
                    field_name,
                    value,
                    filename,
                    phase="submission",
                    block=block,
                    confidence=0.93,
                )


def _contract_facts(
    documents: list[tuple[str, str, str]],
    facts: dict[str, dict[str, Any]],
) -> None:
    specialty_map = [
        ("Arquitetura", r"projeto de arquitetura"),
        ("Demolições", r"projeto de demolicoes"),
        ("Estruturas", r"fundacoes e estruturas|estruturas"),
        ("Águas", r"sistemas de aguas"),
        ("Esgotos", r"sistemas de esgotos"),
        ("Instalações elétricas", r"sistemas eletricos|instalacoes eletricas"),
        ("Comunicações", r"sistemas de comunicacoes"),
        ("Gás", r"sistemas de gas"),
        ("AVAC", r"aquecimento ventilacao ar condicionado|\bavac\b"),
        ("Elevadores", r"transporte pessoas e cargas"),
        ("SCIE", r"seguranca contra incendios|\bscie\b"),
        ("Acústica", r"condicionamento acustico"),
        ("Térmica", r"comportamento termico"),
        ("Fotovoltaico", r"energia eletrica fotovoltaica"),
        ("Paisagismo", r"arquitetura paisagista"),
        ("Cozinhas e lavandarias", r"cozinhas e lavandarias"),
        ("Mobiliário", r"projeto de mobiliario"),
        ("Sinalética", r"projeto de sinaletica"),
    ]

    all_specialties: list[str] = []
    specialty_source = ""

    for filename, raw, normalized in documents:
        rules = [
            (
                "execution_project",
                r"\bprojeto(?:\s+geral)?\s+de\s+execucao\b",
                "Projeto de execução incluído",
            ),
            (
                "technical_assistance",
                r"\bassistencia\s+tecnica\b",
                "Assistência técnica incluída",
            ),
            (
                "final_drawings",
                r"\btelas\s+finais\b",
                "Telas finais incluídas",
            ),
            (
                "measurements",
                r"\bmapa\s+de\s+medicoes\b",
                "Mapa de medições incluído",
            ),
            (
                "quantity_schedule",
                r"\bmapa\s+de\s+quantidades\b",
                "Mapa de quantidades incluído",
            ),
            (
                "approval_requirement",
                (
                    r"apreciacao e aprovacao por entidades externas"
                    r"|pareceres finais das entidades"
                    r"|certificacoes obrigatorias"
                ),
                "Aprovação por entidades externas prevista",
            ),
        ]

        for field_name, pattern, value in rules:
            if re.search(pattern, normalized):
                _fact(
                    facts,
                    field_name,
                    value,
                    filename,
                    phase="contract_execution",
                    block="contract_deliverables",
                )

        phases = []
        phase_map = [
            ("Estudo prévio", r"fase 1 elaboracao do estudo previo"),
            ("Anteprojeto", r"fase 2 elaboracao do anteprojeto"),
            ("Projeto de execução", r"fase 3 elaboracao e entrega do projeto"),
            ("Versão final", r"fase 4 entrega da versao final"),
            ("Assistência técnica e telas finais", r"fase 5 assistencia tecnica"),
        ]
        for label, pattern in phase_map:
            if re.search(pattern, normalized):
                phases.append(label)
        if phases:
            _fact(
                facts,
                "project_phases",
                " · ".join(phases),
                filename,
                phase="contract_execution",
                block="contract_deliverables",
            )

        payment_lines = []
        for match in re.finditer(
            (
                r"fase\s+[1-5][^.;\n]{0,120}?"
                r"\d+(?:[,.]\d+)?\s*%\s+do\s+preco\s+contratual"
            ),
            normalized,
        ):
            payment_lines.append(
                " ".join(match.group(0).split())
            )
        if payment_lines:
            _fact(
                facts,
                "payment_conditions",
                " · ".join(payment_lines[:8]),
                filename,
                phase="contract_execution",
                block="financials",
                confidence=0.94,
            )

        for label, pattern in specialty_map:
            if re.search(pattern, normalized):
                all_specialties.append(label)
                specialty_source = filename

    if all_specialties and specialty_source:
        ordered = list(dict.fromkeys(all_specialties))
        _fact(
            facts,
            "specialties",
            " · ".join(ordered),
            specialty_source,
            phase="contract_execution",
            block="team",
            confidence=0.95,
        )


def _program_facts(
    documents: list[tuple[str, str, str]],
    facts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    program: dict[str, Any] = {
        "summary": "",
        "intervention_type": "",
        "total_area": "",
        "area_total": {},
        "area_bruta": {},
        "area_intervencao": {},
        "area_util": {},
        "areas": [],
        "main_spaces": [],
        "requirements": [],
        "constraints": [],
    }

    def compact(value: str, limit: int = 520) -> str:
        text = " ".join(str(value or "").split()).strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip(" ,;:-") + "…"

    def format_area(number: float) -> str:
        decimals = 2 if abs(number - round(number)) > 0.001 else 0
        formatted = f"{number:,.{decimals}f}"
        return (
            formatted.replace(",", "§")
            .replace(".", ",")
            .replace("§", " ")
            + " m²"
        )

    def looks_like_index(text: str) -> bool:
        normalized = _normalize(text)
        return bool(
            not normalized
            or re.search(r"\.{4,}\s*\d+\s*$", text)
            or re.search(r"^\s*\d+(?:\.\d+)+\s+", text)
            or "indice" in normalized
            or "sumario" in normalized
        )

    def clean_label(value: str) -> str:
        label = " ".join(str(value or "").split()).strip(" -:;|.")
        label = re.sub(
            r"^(?:m\s*2|m²|area|área)\s+(?=[A-Za-zÀ-ÿ])",
            "",
            label,
            flags=re.IGNORECASE,
        )
        label = re.sub(r"^\d+(?:\.\d+)*\s+", "", label)
        return label.strip(" -:;|.")

    def valid_label(label: str) -> bool:
        normalized = _normalize(label)
        if len(normalized) < 3:
            return False
        if normalized in {
            "m", "m2", "area", "area 1", "area 2", "total",
        }:
            return False
        return not any(
            token in normalized
            for token in (
                "pagina", "escala", "artigo", "clausula",
                "concurso", "numero", "indice", "sumario",
            )
        )

    global_candidates: dict[str, dict[str, Any]] = {}
    functional_areas: list[dict[str, Any]] = []
    area_signatures: set[tuple[str, str]] = set()
    summary_candidates: list[tuple[float, str, str]] = []

    global_rules = {
        "area_total": (
            "Área total",
            [
                (r"\barea total de construcao\b", 125),
                (r"\barea total do programa\b", 120),
                (r"\barea global\b", 115),
                (r"\barea total do edificio\b", 115),
                (r"\barea total de intervencao\b", 108),
                (r"\barea total\b", 72),
            ],
        ),
        "area_bruta": (
            "Área bruta",
            [
                (r"\barea bruta de construcao\b", 122),
                (r"\barea bruta total\b", 115),
                (r"\barea bruta\b", 82),
            ],
        ),
        "area_intervencao": (
            "Área de intervenção",
            [
                (r"\barea total de intervencao\b", 118),
                (r"\barea de intervencao\b", 108),
                (r"\barea da intervencao\b", 102),
            ],
        ),
        "area_util": (
            "Área útil",
            [
                (r"\barea util total\b", 118),
                (r"\barea util de construcao\b", 112),
                (r"\barea util\b", 82),
            ],
        ),
    }

    space_map = [
        ("Salas de aula", r"\bsalas? de aula\b"),
        ("Laboratórios", r"\blaboratorios?\b"),
        ("Biblioteca / centro de recursos", r"\bbiblioteca\b|\bcentro de recursos\b"),
        ("Auditório", r"\bauditorio\b"),
        ("Refeitório", r"\brefeitorio\b"),
        ("Cozinha", r"\bcozinha\b"),
        ("Ginásio / desporto", r"\bginasio\b|\binstalacoes desportivas\b"),
        ("Administração", r"\bespacos? administrativos?\b|\badministracao\b"),
        ("Espaços exteriores", r"\bespacos? exteriores\b|\blogradouro\b"),
        ("Escola provisória", r"\bescola provisoria\b"),
    ]

    requirement_map = [
        ("Conforto e funcionalidade interior e exterior", r"conforto e funcionalidade"),
        ("Articulação funcional dos espaços", r"articulacao dos espacos"),
        ("Arquitetura ecológica e sustentável", r"arquitetura ecologica e sustentavel"),
        ("Acessibilidade universal", r"acessibilidades|plano de acessibilidades"),
        ("Integração urbana e paisagística", r"enquadramento urbano|integracao paisagistica"),
    ]

    constraint_map = [
        ("Intervenção limitada ao perímetro da escola", r"intervencao esta limitada ao perimetro"),
        ("Preservar e potenciar a envolvente verde", r"envolvente verde existente.*preservada"),
        ("Considerar vulnerabilidade e reforço sísmico", r"vulnerabilidade sismica|reforco estrutural e sismico"),
        ("Necessidade de aumento da área de construção", r"aumento da area de construcao"),
        ("Cumprimento do PDM aplicável", r"regulamento do plano diretor municipal"),
        ("Manter funcionamento e articulação escolar", r"funcionamento escolar|ideal pedagogico"),
    ]

    for filename, raw, normalized in documents:
        lines = [
            " ".join(line.split()).strip()
            for line in raw.splitlines()
            if " ".join(line.split()).strip()
        ]
        paragraphs = [
            " ".join(part.split()).strip()
            for part in re.split(r"\n\s*\n+", raw)
            if " ".join(part.split()).strip()
        ]

        for paragraph in paragraphs:
            normalized_paragraph = _normalize(paragraph)
            if len(paragraph) < 110 or looks_like_index(paragraph):
                continue
            score = 0.0
            if "consideracoes gerais sobre a intervencao" in normalized_paragraph:
                score += 70
            if "objeto da intervencao" in normalized_paragraph:
                score += 60
            if "programa preliminar" in normalized_paragraph:
                score += 35
            for token in (
                "reabilitacao", "requalificacao", "modernizacao",
                "ampliacao", "edificio", "escola", "espacos", "funcional",
            ):
                if token in normalized_paragraph:
                    score += 5
            if score >= 25:
                cleaned = re.sub(
                    r"^(?:\d+(?:\.\d+)*\s*)?"
                    r"(?:considerações gerais sobre a intervenção|"
                    r"objeto da intervenção|programa preliminar)"
                    r"\s*[:.\-]?\s*",
                    "",
                    paragraph,
                    flags=re.IGNORECASE,
                )
                summary_candidates.append(
                    (score, compact(cleaned, 620), filename)
                )

        if not program["intervention_type"]:
            if "requalificacao modernizacao" in normalized:
                value = "Requalificação / modernização"
            elif "reabilitacao" in normalized and "ampliacao" in normalized:
                value = "Reabilitação / ampliação"
            elif "reabilitacao" in normalized:
                value = "Reabilitação"
            elif "ampliacao" in normalized:
                value = "Ampliação"
            else:
                value = ""
            if value:
                program["intervention_type"] = value
                _fact(
                    facts,
                    "intervention_type",
                    value,
                    filename,
                    phase="administrative",
                    block="program_functional",
                )

        chunks = lines + [
            compact(part, 360)
            for part in paragraphs
            if len(part) <= 420
        ]

        for chunk in chunks:
            if looks_like_index(chunk):
                continue
            normalized_chunk = _normalize(chunk)

            for key, (label, rules) in global_rules.items():
                for phrase_pattern, base_score in rules:
                    phrase = re.search(phrase_pattern, normalized_chunk)
                    if not phrase:
                        continue
                    after = normalized_chunk[phrase.end(): phrase.end() + 90]
                    amount_match = re.search(
                        r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?"
                        r"|\d{1,6}(?:[,.]\d{1,2})?)\s*m(?:2|²)?",
                        after,
                    )
                    if not amount_match:
                        continue
                    number = _parse_number(amount_match.group(1))
                    if number is None or number <= 0:
                        continue

                    score = float(base_score)
                    if number >= 500:
                        score += 18
                    if number >= 2000:
                        score += 12
                    if any(
                        token in normalized_chunk
                        for token in (
                            "programa", "edificio", "intervencao",
                            "construcao", "empreendimento", "recinto",
                        )
                    ):
                        score += 12
                    if any(
                        token in normalized_chunk
                        for token in (
                            "sala", "gabinete", "laboratorio",
                            "preparacao", "arrumos", "2 x", "2x", "+",
                        )
                    ):
                        score -= 80
                    if re.search(r"\b\d+\s*[x×]\s*\d", normalized_chunk):
                        score -= 90

                    current = global_candidates.get(key)
                    if current is None or score > current["score"]:
                        global_candidates[key] = {
                            "label": label,
                            "value": format_area(number),
                            "number": number,
                            "filename": filename,
                            "confidence": min(0.99, max(0.70, score / 130)),
                            "score": score,
                            "excerpt": compact(chunk, 260),
                        }

        for line in lines:
            if looks_like_index(line) or len(line) > 220:
                continue
            normalized_line = _normalize(line)
            if any(
                phrase in normalized_line
                for phrase in (
                    "area total", "area bruta",
                    "area de intervencao", "area da intervencao",
                    "area util",
                )
            ):
                continue

            quantity_match = re.search(
                r"\b(\d+)\s*[x×]\s*"
                r"(\d{1,5}(?:[,.]\d{1,2})?)\s*m(?:2|²)?",
                line,
                re.IGNORECASE,
            )
            area_match = re.search(
                r"(\d{1,5}(?:[,.]\d{1,2})?)\s*m(?:2|²)?",
                line,
                re.IGNORECASE,
            )
            if not area_match:
                continue

            label_end = (
                quantity_match.start()
                if quantity_match
                else area_match.start()
            )
            label = clean_label(line[:label_end])
            if not valid_label(label):
                continue

            unit_number = _parse_number(area_match.group(1))
            if unit_number is None or unit_number <= 0:
                continue

            quantity = None
            total_number = unit_number
            if quantity_match:
                quantity = int(quantity_match.group(1))
                unit_number = _parse_number(quantity_match.group(2)) or unit_number
                total_number = quantity * unit_number

            value = (
                f"{quantity} × {format_area(unit_number)} = {format_area(total_number)}"
                if quantity and quantity > 1
                else format_area(unit_number)
            )
            signature = (_normalize(label), value)
            if signature in area_signatures:
                continue
            area_signatures.add(signature)

            functional_areas.append(
                {
                    "label": label,
                    "value": value,
                    "kind": "functional_area",
                    "quantity": quantity,
                    "unit_area_m2": unit_number,
                    "total_area_m2": total_number,
                    "source_document": filename,
                    "confidence": 0.91,
                }
            )

        for label, pattern in space_map:
            if re.search(pattern, normalized) and label not in program["main_spaces"]:
                program["main_spaces"].append(label)
        for label, pattern in requirement_map:
            if re.search(pattern, normalized) and label not in program["requirements"]:
                program["requirements"].append(label)
        for label, pattern in constraint_map:
            if re.search(pattern, normalized) and label not in program["constraints"]:
                program["constraints"].append(label)

    if summary_candidates:
        summary_candidates.sort(
            key=lambda item: (item[0], len(item[1])),
            reverse=True,
        )
        program["summary"] = summary_candidates[0][1]
        _fact(
            facts,
            "program_summary",
            program["summary"],
            summary_candidates[0][2],
            phase="administrative",
            block="program_functional",
            confidence=0.96,
        )

    for key in (
        "area_total", "area_bruta",
        "area_intervencao", "area_util",
    ):
        candidate = global_candidates.get(key)
        if not candidate:
            continue
        entry = {
            "label": candidate["label"],
            "value": candidate["value"],
            "kind": "global_area",
            "total_area_m2": candidate["number"],
            "source_document": candidate["filename"],
            "confidence": candidate["confidence"],
            "evidence_excerpt": candidate["excerpt"],
        }
        program[key] = entry
        _fact(
            facts,
            key,
            candidate["value"],
            candidate["filename"],
            phase="administrative",
            block="program_functional",
            confidence=candidate["confidence"],
        )

    globals_first = [
        program[key]
        for key in (
            "area_total", "area_bruta",
            "area_intervencao", "area_util",
        )
        if program[key]
    ]
    program["areas"] = globals_first + functional_areas[:20]

    if program["area_total"]:
        program["total_area"] = program["area_total"]["value"]
        _fact(
            facts,
            "total_area",
            program["total_area"],
            program["area_total"]["source_document"],
            phase="administrative",
            block="program_functional",
            confidence=program["area_total"]["confidence"],
        )

    if functional_areas:
        _fact(
            facts,
            "functional_areas",
            compact(
                " · ".join(
                    f"{item['label']}: {item['value']}"
                    for item in functional_areas[:12]
                ),
                520,
            ),
            functional_areas[0]["source_document"],
            phase="administrative",
            block="program_functional",
            confidence=0.91,
        )

    if program["main_spaces"] and documents:
        _fact(
            facts,
            "main_spaces",
            compact(" · ".join(program["main_spaces"]), 360),
            documents[0][0],
            phase="administrative",
            block="program_functional",
            confidence=0.90,
        )
    if program["requirements"] and documents:
        _fact(
            facts,
            "functional_requirements",
            compact(" · ".join(program["requirements"]), 420),
            documents[0][0],
            phase="administrative",
            block="program_functional",
            confidence=0.90,
        )
    if program["constraints"] and documents:
        _fact(
            facts,
            "constraints",
            compact(" · ".join(program["constraints"]), 420),
            documents[0][0],
            phase="administrative",
            block="program_functional",
            confidence=0.90,
        )

    functional_program = {
        "summary": program["summary"],
        "intervention_type": program["intervention_type"],
        "total_area": program["total_area"],
        "area_total": program["area_total"],
        "area_bruta": program["area_bruta"],
        "area_intervencao": program["area_intervencao"],
        "area_util": program["area_util"],
        "areas": program["areas"],
        "main_spaces": program["main_spaces"],
        "requirements": program["requirements"],
        "constraints": program["constraints"],
    }
    program["functional_program"] = functional_program
    program["global_areas"] = {
        "area_total": program["area_total"],
        "area_bruta": program["area_bruta"],
        "area_intervencao": program["area_intervencao"],
        "area_util": program["area_util"],
    }
    return program


def apply_design_competition_extraction(
    ficha: dict[str, Any],
    consolidated: ConsolidatedCompetitionData,
    textos: dict[str, str],
) -> ConsolidatedCompetitionData:
    documents = _documents(textos)
    submission_requirements = extract_submission_requirements(textos)
    facts: dict[str, dict[str, Any]] = {}

    _financial_facts(documents, facts)
    _submission_facts(documents, facts)
    _contract_facts(documents, facts)
    program = _program_facts(documents, facts)
    enrichment_payload = enrich_design_competition(
        documents=documents,
        facts=facts,
        program=program,
        ficha=ficha,
    )
    program["functional_program"] = enrichment_payload["functional_program"]

    # Keep the information model consistent with the validated program.
    # Rejected cell-level values must not survive as frontend fallbacks.
    for global_key in (
        "area_total", "area_bruta", "area_intervencao", "area_util",
    ):
        validated = program["functional_program"].get(global_key) or {}
        if validated.get("value"):
            if global_key in facts:
                facts[global_key]["value"] = validated["value"]
                facts[global_key]["source_document"] = validated.get(
                    "source_document", facts[global_key].get("source_document", "")
                )
        else:
            facts.pop(global_key, None)
    if program["functional_program"].get("total_area"):
        if "total_area" in facts:
            facts["total_area"]["value"] = program["functional_program"]["total_area"]
    else:
        facts.pop("total_area", None)

    payload = consolidated.model_dump(mode="json")
    current_items = [
        item
        for item in (payload.get("information_model") or [])
        if isinstance(item, dict)
        and str(item.get("field_name") or "")
        not in TARGET_FIELDS
    ]
    current_items.extend(facts.values())
    payload["information_model"] = current_items

    result = ConsolidatedCompetitionData.model_validate(
        payload
    )

    extraction = {
        "version": "design-competition-extractor-v4",
        "facts": {
            key: {
                "value": item["value"],
                "source_document": item["source_document"],
                "confidence": item["confidence"],
            }
            for key, item in facts.items()
        },
        "program_functional": program["functional_program"],
        "functional_program": program["functional_program"],
        "submission": enrichment_payload["submission"],
        "financial": enrichment_payload["financial"],
        "contract": enrichment_payload["contract"],
        "counts": {
            "facts": len(facts),
            "areas": len((program["functional_program"].get("area_schedule") or {}).get("rows") or []),
            "spaces": len(program.get("main_spaces") or []),
            "requirements": len(program.get("requirements") or []),
            "constraints": len(program.get("constraints") or []),
        },
    }

    extraction["submission_requirements"] = submission_requirements
    ficha["submission_requirements"] = submission_requirements

    ficha["design_competition_extraction"] = extraction
    ficha["programa_funcional"] = program["functional_program"]
    ficha["functional_program"] = program["functional_program"]

    return result
