from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from typing import Any

MARKER = "CNLL_LEGACY_PROCEDURE_RECOVERY_V17_4_2"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def fold(value: Any) -> str:
    text = unicodedata.normalize("NFD", clean(value))
    text = "".join(
        char for char in text if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = clean(value)
    if not text:
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def analysis_body(root: Any) -> dict[str, Any]:
    """
    Algumas análises antigas usam `analise` como wrapper; outras usam-no
    apenas para um pequeno bloco de decisão. Só desembrulha quando há sinais
    reais de que é a análise completa.
    """
    if not isinstance(root, dict):
        return {}

    nested = root.get("analise")
    if not isinstance(nested, dict):
        return root

    wrapper_markers = {
        "analysis_canonical",
        "procedure_analysis",
        "design_competition_extraction",
        "criterios",
        "equipa",
        "requirements",
        "requisitos",
        "document_insights",
    }
    if wrapper_markers.intersection(nested.keys()):
        return nested

    return root


def _team_items(ficha: dict[str, Any]) -> list[dict[str, Any]]:
    value = ficha.get("equipa")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _subfactor_code(title: str) -> str:
    text = clean(title)
    patterns = (
        r"\b(?:subfator|subfactor)\s*([A-Z]?\d+(?:[.\-]\d+)?)",
        r"\bS\s*([A-Z]?\d+)\s*[,.;]\s*\d",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).upper().replace("-", ".")
    return ""



def _team_description(item: dict[str, Any]) -> str:
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    return clean(
        item.get("descricao")
        or item.get("description")
        or item.get("summary")
        or item.get("text")
        or item.get("requirement")
        or item.get("evidence_excerpt")
        or evidence.get("evidence_excerpt")
        or evidence.get("value")
    )


def _weight_value(item: dict[str, Any]) -> float | None:
    for key in ("weight_percent", "percentage", "percent", "weight"):
        value = number(item.get(key))
        if value is not None:
            return value
    return None


def _weights_by_subfactor(team: list[dict[str, Any]]) -> dict[str, float]:
    weights: dict[str, float] = {}
    pattern = re.compile(
        r"\b([A-Z]\d+)\s*[\-–—]\s*[^;\n]{3,180}?"
        r"(?:pondera[cç][aã]o|peso\s+parcial)\s+de\s+"
        r"(\d+(?:[.,]\d+)?)\s*%",
        flags=re.I,
    )
    for item in team:
        text = " ".join(
            clean(part)
            for part in (
                item.get("title"),
                item.get("titulo"),
                item.get("role"),
                _team_description(item),
            )
            if clean(part)
        )
        for match in pattern.finditer(text):
            value = number(match.group(2))
            code = clean(match.group(1)).upper()
            if code and value is not None:
                weights[code] = value
    return weights
def _weight_from_title(title: str) -> float | None:
    matches = re.findall(r"\((\d+(?:[.,]\d+)?)\s*%\)", title)
    if not matches:
        return None
    return number(matches[-1])


def _strip_subfactor_prefix(title: str) -> str:
    value = re.sub(
        r"^\s*(?:subfator|subfactor)\s*[0-9]+(?:[.\-][0-9]+)?\s*[-–—:]?\s*",
        "",
        clean(title),
        flags=re.I,
    )
    value = re.sub(r"\s*\(\d+(?:[.,]\d+)?\s*%\)\s*$", "", value)
    return clean(value)


def _percentages(ficha: dict[str, Any]) -> list[tuple[str, float]]:
    criterios = ficha.get("criterios")
    if not isinstance(criterios, dict):
        return []

    output: list[tuple[str, float]] = []
    rows = criterios.get("percentagens")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            label = clean(
                row.get("criterio")
                or row.get("label")
                or row.get("nome")
            )
            value = number(
                row.get("percentagem")
                or row.get("percentage")
                or row.get("weight")
            )
            if label and value is not None:
                output.append((label, value))
    return output


def _price_weight(ficha: dict[str, Any]) -> float | None:
    for label, value in _percentages(ficha):
        if "preco" in fold(label) or "price" in fold(label):
            return value

    criterios = ficha.get("criterios")
    if isinstance(criterios, dict):
        hay = " ".join(
            clean(criterios.get(key))
            for key in ("resumo", "detalhe", "criterio_adjudicacao")
        )
        match = re.search(
            r"(?:pre[cç]o|price)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*%",
            hay,
            flags=re.I,
        )
        if match:
            return number(match.group(1))
    return None


def _quality_weight(ficha: dict[str, Any]) -> float | None:
    rows = _percentages(ficha)
    for label, value in rows:
        normalized = fold(label)
        if any(
            token in normalized
            for token in (
                "qualidade",
                "tecnica",
                "valia",
                "equipa",
                "quality",
            )
        ):
            return value

    price = _price_weight(ficha)
    if price is not None and 0 <= price <= 100:
        return 100.0 - price

    criterios = ficha.get("criterios")
    if isinstance(criterios, dict):
        hay = " ".join(
            clean(criterios.get(key))
            for key in ("resumo", "detalhe")
        )
        # Ex.: "FATOR 2: Valia Técnica da Equipa de Projeto (60%)"
        match = re.search(
            r"(?:fator|factor)\s*\d+\s*:\s*[^()]{3,160}\((\d+(?:[.,]\d+)?)\s*%\)",
            hay,
            flags=re.I,
        )
        if match:
            return number(match.group(1))
    return None


def _factor_label(ficha: dict[str, Any]) -> str:
    criterios = ficha.get("criterios")
    if isinstance(criterios, dict):
        hay = " ".join(
            clean(criterios.get(key))
            for key in ("resumo", "detalhe")
        )
        match = re.search(
            r"(?:fator|factor)\s*\d+\s*:\s*([^()]{3,180})"
            r"(?:\(\s*\d+(?:[.,]\d+)?\s*%\))?",
            hay,
            flags=re.I,
        )
        if match:
            candidate = clean(match.group(1))
            candidate = re.sub(
                r"\s+\d+(?:[.,]\d+)?\s*%\s*$",
                "",
                candidate,
            )
            if candidate:
                return candidate
    return "Valia Técnica da Equipa de Projeto"


def procedural_richness(ficha: dict[str, Any]) -> int:
    """
    Mede só riqueza PROCEDIMENTAL. Não usa score, matching ou perfil da empresa.
    Serve para escolher uma análise irmã como fonte de critérios.
    """
    score = 0
    team = _team_items(ficha)

    seen_codes: set[str] = set()
    for item in team:
        title = clean(item.get("titulo") or item.get("title"))
        description = clean(
            item.get("descricao")
            or item.get("description")
            or item.get("text")
        )
        code = _subfactor_code(title)
        if code:
            seen_codes.add(code)
            score += 4
        if _weight_from_title(title) is not None:
            score += 3
        if len(description) >= 120:
            score += 12
        elif len(description) >= 30:
            score += 4

        normalized = fold(f"{title} {description}")
        if "pontuacao" in normalized or "descritor" in normalized:
            score += 4
        if "projeto" in normalized and "experiencia" in normalized:
            score += 4

    score += len(seen_codes) * 3

    criterios = ficha.get("criterios")
    if isinstance(criterios, dict):
        if clean(criterios.get("resumo")):
            score += 5
        if clean(criterios.get("detalhe")):
            score += 5
        score += len(_percentages(ficha)) * 2

    procedure = ficha.get("procedure_analysis")
    if isinstance(procedure, dict):
        award = procedure.get("award_criteria")
        if isinstance(award, dict):
            factors = award.get("factors")
            if isinstance(factors, list) and factors:
                score += 40 + 5 * len(factors)

    return score


def _legacy_team_is_material(ficha: dict[str, Any]) -> bool:
    """Reconhece uma lista procedural completa, sem aceitar uma role isolada."""
    candidates = [ficha.get("procedure_analysis")]
    extraction = ficha.get("design_competition_extraction")
    if isinstance(extraction, dict):
        candidates.append(extraction.get("procedure_analysis"))

    for procedure in candidates:
        if not isinstance(procedure, dict):
            continue
        team = procedure.get("technical_team")
        if not isinstance(team, list):
            continue
        roles = {
            fold(clean(item.get("role") or item.get("title") or item.get("label")))
            for item in team
            if isinstance(item, dict)
            and clean(item.get("role") or item.get("title") or item.get("label"))
        }
        if not roles:
            continue
        if any(item.get("required_at_submission") is True for item in team if isinstance(item, dict)):
            return True
        source_documents = " ".join(
            clean(item.get("source_document"))
            for item in team
            if isinstance(item, dict)
        )
        headings = " ".join(
            clean(item.get("source_heading"))
            for item in team
            if isinstance(item, dict)
        )
        if len(roles) >= 3 and "programa" in fold(source_documents) and (
            "equipa" in fold(headings) or "anexo" in fold(headings)
        ):
            return True
    return False


def _existing_material_procedure(
    ficha: dict[str, Any],
) -> dict[str, Any] | None:
    candidates: list[Any] = [ficha.get("procedure_analysis")]

    extraction = ficha.get("design_competition_extraction")
    if isinstance(extraction, dict):
        candidates.append(extraction.get("procedure_analysis"))

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        award = candidate.get("award_criteria")
        if isinstance(award, dict):
            factors = award.get("factors")
            if isinstance(factors, list) and factors:
                return deepcopy(candidate)
        if _legacy_team_is_material({"procedure_analysis": candidate}):
            return deepcopy(candidate)

    return None

def recover_procedure_from_legacy(
    ficha: dict[str, Any],
    *,
    base_procedure: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """
    Reconstrói apenas a camada procedimental a partir de informação já extraída.
    Nunca copia matching, score ou dados da empresa.
    """
    material = _existing_material_procedure(ficha)
    if material is not None:
        return material, {
            "mode": "existing_procedure_analysis",
            "subfactor_details": {},
        }

    team = _team_items(ficha)
    if not team:
        return None, {
            "mode": "no_legacy_team",
            "subfactor_details": {},
        }

    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    weights = _weights_by_subfactor(team)

    for item in team:
        title = clean(
            item.get("titulo")
            or item.get("title")
            or item.get("role")
            or item.get("name")
        )
        description = _team_description(item)
        explicit_code = clean(item.get("subfactor_code") or item.get("criterion_code")).upper()
        code = explicit_code or _subfactor_code(title) or _subfactor_code(description)
        if not code:
            continue

        key = f"{code}|{fold(title)}" if title else code
        if key not in grouped:
            grouped[key] = {
                "code": code,
                "header_title": title,
                "detail_title": title,
                "weight": weights.get(code),
                "description": "",
            }
            order.append(key)

        current = grouped[key]
        weight = _weight_value(item) or _weight_from_title(title) or weights.get(code)
        if weight is not None and current["weight"] is None:
            current["weight"] = weight
            current["header_title"] = title

        if description and len(description) > len(current["description"]):
            current["description"] = description
            current["detail_title"] = title

        if not current["header_title"] and title:
            current["header_title"] = title

    usable = [
        grouped[key]
        for key in order
        if len(clean(grouped[key].get("description"))) >= 40
    ]
    if not usable:
        return None, {
            "mode": "legacy_team_without_descriptors",
            "subfactor_details": {},
        }

    quality_weight = _quality_weight(ficha)
    price_weight = _price_weight(ficha)

    subfactors: list[dict[str, Any]] = []
    scoring_rows: list[dict[str, Any]] = []
    details: dict[str, str] = {}

    for row in usable:
        code = clean(row["code"])
        title = clean(
            row.get("detail_title")
            or row.get("header_title")
            or f"Subfator {code}"
        )
        label = _strip_subfactor_prefix(title) or f"Subfator {code}"
        description = clean(row.get("description"))
        weight = row.get("weight")

        subfactor: dict[str, Any] = {
            "code": code,
            "label": label,
            "summary": description,
            "source_document": "Análise procedural existente",
            "source_heading": title,
            "evidence_excerpt": description[:1200],
        }
        if weight is not None:
            subfactor["weight_percent"] = weight

        scoring = {
            "criterion_code": code,
            "subfactor_code": code,
            "label": label,
            "description": description,
            "source_document": "Análise procedural existente",
            "source_heading": title,
            "evidence_excerpt": description[:1200],
        }
        subfactor["scoring_requirements"] = [scoring]
        subfactors.append(subfactor)
        scoring_rows.append(scoring)
        details[code] = description

    factor_code = clean(usable[0]["code"]).split(".")[0] or "Q"
    factor: dict[str, Any] = {
        "code": factor_code,
        "label": _factor_label(ficha),
        "subfactors": subfactors,
        "source_document": "Análise procedural existente",
    }
    if quality_weight is not None:
        factor["weight_percent"] = quality_weight

    factors: list[dict[str, Any]] = [factor]
    if price_weight is not None:
        factors.append(
            {
                "code": "P",
                "label": "Preço",
                "weight_percent": price_weight,
                "source_document": "Análise procedural existente",
            }
        )

    criteria: dict[str, Any] = {
        "model": clean(
            (ficha.get("criterios") or {}).get("criterio_adjudicacao")
            if isinstance(ficha.get("criterios"), dict)
            else ""
        )
        or "Multifator",
        "factors": factors,
        "scoring_requirements": scoring_rows,
        "verified_top_level_weights": bool(
            quality_weight is not None and price_weight is not None
        ),
    }

    procedure = deepcopy(base_procedure) if isinstance(base_procedure, dict) else {}
    procedure["award_criteria"] = criteria

    # CNLL_RECOVERED_TECHNICAL_TEAM_V17_5_3B
    existing_team = procedure.get("technical_team")
    if not isinstance(existing_team, list) or not existing_team:
        procedure["technical_team"] = [
            {
                "title": subfactor.get("label") or f"Subfator {subfactor.get('code')}",
                "role": subfactor.get("label") or "",
                "summary": subfactor.get("summary") or "",
                "description": subfactor.get("summary") or "",
                "subfactor_code": subfactor.get("code"),
                "weight_percent": subfactor.get("weight_percent"),
                "source_document": subfactor.get("source_document"),
                "source_heading": subfactor.get("source_heading"),
                "evidence_excerpt": subfactor.get("evidence_excerpt"),
            }
            for subfactor in subfactors
            if isinstance(subfactor, dict)
        ]

    if not clean(procedure.get("family")):
        procedure["family"] = clean(
            (ficha.get("identificacao") or {}).get("analysis_family")
            if isinstance(ficha.get("identificacao"), dict)
            else ""
        ) or "project_services"

    if not clean(procedure.get("family_label")):
        procedure["family_label"] = "Prestação de serviços de projeto"

    return procedure, {
        "mode": "legacy_team_descriptors",
        "quality_weight": quality_weight,
        "price_weight": price_weight,
        "subfactor_count": len(subfactors),
        "subfactor_details": details,
    }
