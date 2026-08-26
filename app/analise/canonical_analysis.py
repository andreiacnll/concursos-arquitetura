from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Iterable

SCHEMA_VERSION = "cnll-analysis-v16-hierarchical"
MARKER = "CNLL_CANONICAL_ANALYSIS_V16"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFD", _clean(value))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _fold(value)).strip("_") or "item"


def _float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = _clean(value)
    if not text:
        return None
    text = text.replace("\xa0", " ").replace("€", "")
    match = re.search(r"-?\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|-?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    token = match.group(0).replace(" ", "")
    if "," in token:
        token = token.replace(".", "").replace(",", ".")
    elif token.count(".") > 1:
        token = token.replace(".", "")
    try:
        return float(token)
    except ValueError:
        return None


def _percent(value: Any) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if -0.001 <= number <= 1.001 and isinstance(value, float):
        return number * 100
    return number


def _first(mapping: dict[str, Any] | None, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _dicts(value: Any, depth: int = 0) -> Iterable[dict[str, Any]]:
    if depth > 12:
        return
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _dicts(nested, depth + 1)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _dicts(nested, depth + 1)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in (None, "", {}):
        return []
    return [value]


def _source(item: dict[str, Any] | None) -> dict[str, Any]:
    item = item if isinstance(item, dict) else {}
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    return {
        "document": _clean(
            _first(
                item,
                "source_document",
                "document",
                "filename",
                "source",
            )
            or _first(evidence, "source_document", "document", "filename", "source")
        ),
        "section": _clean(
            _first(item, "source_heading", "heading", "section")
            or _first(evidence, "section", "heading")
        ),
        "page": _first(item, "page") or _first(evidence, "page"),
        "excerpt": _clean(
            _first(
                item,
                "evidence_excerpt",
                "excerpt",
                "text",
                "description",
                "summary",
            )
            or _first(evidence, "evidence_excerpt", "excerpt", "value")
        )[:1200],
    }


def _phase_from_source(source: dict[str, Any], *, scored: bool = False) -> str:
    if scored:
        return "competition"
    haystack = _fold(
        " ".join(
            [
                _clean(source.get("document")),
                _clean(source.get("section")),
                _clean(source.get("excerpt"))[:500],
            ]
        )
    )
    competition = (
        "programa do procedimento",
        "programa do concurso",
        "regulamento",
        "convite",
        "criterio de adjudicacao",
        "criterios de adjudicacao",
        "modelo de avaliacao",
        "avaliacao das propostas",
        "fatores de avaliacao",
        "factores de avaliacao",
        "documentos da proposta",
        "documentos que instruem",
        "candidatura",
    )
    execution = (
        "caderno de encargos",
        "contrato",
        "execucao do contrato",
        "fase contratual",
        "obrigacoes do adjudicatario",
    )
    if any(token in haystack for token in competition):
        return "competition"
    if any(token in haystack for token in execution):
        return "execution"
    return "competition"


def _nature(text: Any) -> str:
    hay = _fold(text)
    if any(x in hay for x in ("exclusao", "excluido", "admissao", "habilitacao", "capacidade tecnica", "requisito minimo")):
        return "eligibility"
    if any(x in hay for x in ("equipa", "coordenador", "gestor bim", "autor", "tecnico", "tecnica", "curriculo", "experiencia profissional")):
        return "team"
    if any(x in hay for x in ("painel", "memoria", "ficheiro", "entrega", "submissao", "proposta deve", "documento")):
        return "submission"
    if any(x in hay for x in ("habilitacao", "adjudicatario")):
        return "habilitation"
    return "evaluation"



def _semantic_stage(text: Any, source: dict[str, Any] | None = None, nature: str = "") -> str:
    hay = _fold(text)
    source_phase = _phase_from_source(source or {}, scored=nature == "evaluation")

    pre_markers = (
        "criterio de adjudicacao",
        "avaliacao",
        "pontuacao",
        "proposta",
        "documentos que instruem",
        "documentos da proposta",
        "equipa",
        "experiencia",
        "coordenador",
        "gestor bim",
        "autor",
        "exclusao",
        "admissao",
        "concorrente",
    )
    post_markers = (
        "adjudicatario",
        "apos adjudicacao",
        "apos selecao",
        "celebracao do contrato",
        "contrato",
        "caucao",
        "seguro",
        "fase de execucao",
        "execucao do contrato",
        "assistencia tecnica",
        "pagamento",
    )

    has_pre = any(marker in hay for marker in pre_markers)
    has_post = any(marker in hay for marker in post_markers)

    if has_pre and has_post:
        return "both"
    if has_post and not has_pre:
        return "post_award"
    if source_phase == "execution" and not has_pre:
        return "post_award"
    if nature in {"eligibility", "team", "evaluation", "submission"}:
        return "pre_award"
    return "informational"


def _structured_constraints(text: Any, spec: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = _clean(text)
    folded = _fold(raw)
    constraints: dict[str, Any] = {}

    period = re.search(r"(?:ultimos|últimos)\s+(\d+(?:[.,]\d+)?)\s+anos", raw, flags=re.I)
    if period:
        value = _float(period.group(1))
        if value is not None:
            constraints["period"] = value
            constraints["period_unit"] = "years"
            constraints["lookback_years"] = value

    if "uniao europeia" in folded or re.search(r"\bUE\b", raw):
        constraints["location"] = "EU"

    if "concluid" in folded:
        constraints["completed"] = True

    if "obra publica" in folded or "obras publicas" in folded:
        constraints["public_private"] = "public"
    elif "privad" in folded:
        constraints["public_private"] = "private"

    if "autor" in folded or "autoria" in folded:
        constraints["authorship"] = True

    if "comprov" in folded or "declaracao" in folded or "anexo" in folded:
        constraints["evidence_required"] = True

    if spec:
        metric = _clean(spec.get("metric"))
        value = spec.get("value")
        if metric == "project_count":
            constraints["project_count"] = value
        elif metric == "years":
            constraints.setdefault("period", value)
            constraints.setdefault("period_unit", "years")
        elif metric == "project_value_eur":
            constraints["work_value"] = value
            constraints["work_value_unit"] = "EUR"
        elif metric == "volume_m3":
            constraints["volume"] = value
            constraints["volume_unit"] = "m3"
        elif metric == "training_hours":
            constraints["training_hours"] = value

    return constraints
def _weight_from(item: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in item and item.get(key) not in (None, ""):
            value = _percent(item.get(key))
            if value is not None:
                return value
    return None


def _label(item: dict[str, Any], fallback: str = "") -> str:
    return _clean(
        _first(
            item,
            "label",
            "name",
            "title",
            "factor",
            "criterion",
            "criterio",
            "description",
        )
        or fallback
    )


def _code(item: dict[str, Any], fallback: str = "") -> str:
    return _clean(_first(item, "code", "id", "key", "criterion_code", "factor_code") or fallback)


def _raw_factors(criteria: dict[str, Any]) -> list[dict[str, Any]]:
    factors = criteria.get("factors")
    if isinstance(factors, list) and factors:
        return [item for item in factors if isinstance(item, dict)]
    factors = criteria.get("criteria")
    if isinstance(factors, list) and factors:
        return [item for item in factors if isinstance(item, dict)]
    return []


def _find_criteria(procedure: dict[str, Any], ficha: dict[str, Any]) -> dict[str, Any]:
    candidates: list[Any] = [
        procedure.get("award_criteria"),
        procedure.get("evaluation"),
        procedure.get("criteria"),
        ficha.get("award_criteria"),
        ficha.get("criterios"),
        ficha.get("avaliacao"),
    ]
    extraction = ficha.get("design_competition_extraction")
    if isinstance(extraction, dict):
        candidates.extend(
            [
                extraction.get("award_criteria"),
                extraction.get("evaluation"),
            ]
        )
    for candidate in candidates:
        if isinstance(candidate, dict) and (
            _raw_factors(candidate)
            or candidate.get("subfactors")
            or candidate.get("scoring_requirements")
            or candidate.get("experience_rules")
        ):
            return candidate
    if isinstance(ficha.get("award_criteria"), list):
        return {"factors": ficha["award_criteria"]}
    return {}


def _subfactor_rows(factor: dict[str, Any], criteria: dict[str, Any], factor_code: str) -> list[dict[str, Any]]:
    embedded = _first(factor, "subfactors", "subcriteria", "subcriteria_items", "children")
    rows = [item for item in _as_list(embedded) if isinstance(item, dict)]
    if rows:
        return rows
    flat = criteria.get("subfactors")
    if not isinstance(flat, list):
        return []
    result = []
    factor_key = _fold(factor_code or _label(factor))
    for item in flat:
        if not isinstance(item, dict):
            continue
        parent = _clean(_first(item, "factor_code", "parent_code", "parent", "factor"))
        if parent and (_fold(parent) == factor_key or _fold(parent).startswith(factor_key + " ")):
            result.append(item)
            continue
        code = _code(item)
        if factor_code and code.upper().startswith(factor_code.upper()):
            result.append(item)
    return result


def build_criteria_hierarchy(procedure: dict[str, Any], ficha: dict[str, Any]) -> dict[str, Any]:
    criteria = _find_criteria(procedure, ficha)
    factors_raw = _raw_factors(criteria)
    factors: list[dict[str, Any]] = []

    for index, raw in enumerate(factors_raw, start=1):
        code = _code(raw, chr(64 + index) if index <= 26 else str(index))
        label = _label(raw, f"Fator {code}")
        parent_weight = _weight_from(
            raw,
            "weight_percent",
            "published_weight_percent",
            "weight",
            "percentage",
            "ponderacao",
        )
        if parent_weight is None:
            parent_weight = _weight_from(raw, "effective_weight_percent", "absolute_weight")

        subs_raw = _subfactor_rows(raw, criteria, code)
        probe: list[tuple[dict[str, Any], float | None, float | None, float | None]] = []
        for sub in subs_raw:
            internal = _weight_from(
                sub,
                "internal_weight_percent",
                "published_weight_percent",
                "display_weight_percent",
            )
            effective = _weight_from(
                sub,
                "effective_weight_percent",
                "absolute_weight",
                "global_weight_percent",
            )
            ambiguous = _weight_from(
                sub,
                "weight_percent",
                "weight",
                "percentage",
                "ponderacao",
            )
            probe.append((sub, internal, effective, ambiguous))

        ambiguous_values = [v for _, i, e, v in probe if i is None and e is None and v is not None]
        ambiguous_sum = sum(ambiguous_values)
        treat_ambiguous_as_internal = bool(
            ambiguous_values
            and (
                abs(ambiguous_sum - 100) <= 2.0
                or parent_weight in (None, 0)
                or ambiguous_sum > (parent_weight or 0) + 2
            )
        )

        subfactors: list[dict[str, Any]] = []
        for sub_index, (sub, internal, effective, ambiguous) in enumerate(probe, start=1):
            if internal is None and effective is None and ambiguous is not None:
                if treat_ambiguous_as_internal:
                    internal = ambiguous
                else:
                    effective = ambiguous

            if internal is None and effective is not None and parent_weight not in (None, 0):
                internal = (effective / float(parent_weight)) * 100.0
            if effective is None and internal is not None and parent_weight is not None:
                effective = (float(parent_weight) * internal) / 100.0

            # If there is no parent weight, a subfactor percentage is necessarily displayed as published.
            if internal is None:
                internal = effective
            display = internal

            sub_code = _code(sub, f"{code}{sub_index}")
            sub_label = _label(sub, f"Subfator {sub_code}")
            src = _source(sub)
            subfactors.append(
                {
                    "id": _slug(f"{code}-{sub_code}-{sub_label}"),
                    "code": sub_code,
                    "label": sub_label,
                    "published_weight_percent": round(internal, 4) if internal is not None else None,
                    "internal_weight_percent": round(internal, 4) if internal is not None else None,
                    "parent_factor_weight_percent": round(parent_weight, 4) if parent_weight is not None else None,
                    "effective_weight_percent": round(effective, 4) if effective is not None else None,
                    "display_weight_percent": round(display, 4) if display is not None else None,
                    "weight_context": "do fator" if parent_weight is not None else "global",
                    "source": src,
                    "summary": _clean(
                        _first(
                            sub,
                            "summary",
                            "description",
                            "rule",
                            "text",
                            "evidence_excerpt",
                        )
                    ),
                }
            )

        factors.append(
            {
                "id": _slug(f"{code}-{label}"),
                "code": code,
                "label": label,
                "published_weight_percent": round(parent_weight, 4) if parent_weight is not None else None,
                "display_weight_percent": round(parent_weight, 4) if parent_weight is not None else None,
                "source": _source(raw),
                "subfactors": subfactors,
            }
        )

    model = _clean(_first(criteria, "model", "type", "award_model", "summary"))
    return {
        "model": model,
        "verified_top_level_weights": bool(criteria.get("verified_top_level_weights")),
        "factors": factors,
        "source": _source(criteria),
    }


def _money_from_text(text: str) -> list[float]:
    results: list[float] = []
    patterns = (
        r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?)\s*(?:€|euros?|eur)\b",
        r"(?:€|eur)\s*(\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*(?:milh(?:ao|oes)|milhões?|milhao)\s*(?:de\s*)?(?:€|euros?|eur)",
    )
    for idx, pattern in enumerate(patterns):
        for match in re.finditer(pattern, text, flags=re.I):
            number = _float(match.group(1))
            if number is None:
                continue
            if idx == 2:
                number *= 1_000_000
            if number >= 1000:
                results.append(number)
    return results


def _metric_specs(text: str) -> list[dict[str, Any]]:
    raw = _clean(text)
    folded = _fold(raw)
    specs: list[dict[str, Any]] = []

    for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:anos?|years?)\b", raw, flags=re.I):
        value = _float(match.group(1))
        if value is not None:
            specs.append({"metric": "years", "value": value, "unit": "anos", "operator": ">="})

    for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:horas?|h)\b", raw, flags=re.I):
        value = _float(match.group(1))
        if value is not None:
            specs.append({"metric": "training_hours", "value": value, "unit": "horas", "operator": ">="})

    for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:m3|m³|metros?\s+cubicos?)\b", raw, flags=re.I):
        value = _float(match.group(1))
        if value is not None:
            specs.append({"metric": "volume_m3", "value": value, "unit": "m³", "operator": ">="})

    for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:m2|m²|metros?\s+quadrados?)\b", raw, flags=re.I):
        value = _float(match.group(1))
        if value is not None:
            specs.append({"metric": "area_m2", "value": value, "unit": "m²", "operator": ">="})

    project_matches = re.findall(r"(\d+)\s+projetos?\b", raw, flags=re.I)
    for token in project_matches:
        value = _float(token)
        if value is not None:
            specs.append({"metric": "project_count", "value": value, "unit": "projetos", "operator": "actual"})

    for money in _money_from_text(raw):
        specs.append({"metric": "project_value_eur", "value": money, "unit": "€", "operator": ">="})

    # Deduplicate same metric/value.
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, float, str]] = set()
    for spec in specs:
        key = (str(spec["metric"]), float(spec["value"]), str(spec["operator"]))
        if key not in seen:
            seen.add(key)
            unique.append(spec)
    return unique


def _profile_dependent(text: str, parent_label: str = "") -> bool:
    hay = _fold(f"{parent_label} {text}")
    markers = (
        "experiencia",
        "curriculo",
        "equipa",
        "coordenador",
        "gestor bim",
        "formacao",
        "projeto de",
        "projetos de",
        "autoria",
        "autor",
        "anos",
        "horas",
        "valor da empreitada",
        "valor de obra",
        "urbanizacao",
        "parque urbano",
        "modelacao de terreno",
        "remodelacao de terreno",
        "movimento de terras",
        "obra concluida",
        "obras concluidas",
    )
    return any(marker in hay for marker in markers)


def _scope(text: str) -> tuple[str, str]:
    hay = _fold(text)
    role = ""
    for marker, role_name in (
        ("coordenador", "coordenador"),
        ("gestor bim", "gestor_bim"),
        ("fundacoes", "fundacoes_estruturas"),
        ("estruturas", "fundacoes_estruturas"),
        ("arquitetura paisagista", "arquitetura_paisagista"),
        ("paisagista", "arquitetura_paisagista"),
        ("autor", "autor_projeto"),
    ):
        if marker in hay:
            role = role_name
            break

    if any(x in hay for x in ("coordenador", "gestor bim", "formacao", "anos de experiencia", "experiencia profissional", "tecnico", "tecnica")):
        return "person", role or "membro_equipa"
    if any(x in hay for x in ("projeto", "obra", "empreitada", "parque", "urbanizacao", "terreno", "movimento de terras")):
        return "project", role
    return "company", role


def _reuse_key(label: str, metric: str | None, scope: str, role: str) -> str:
    hay = _fold(label)
    domain = "generic"
    domains = (
        ("parque urbano", "urban_park"),
        ("urbanizacao", "public_urbanization"),
        ("modelacao", "earthworks"),
        ("remodelacao", "earthworks"),
        ("movimento de terras", "earthworks"),
        ("bim", "bim"),
        ("escola", "education"),
        ("escolar", "education"),
        ("educacao", "education"),
        ("hospital", "health"),
        ("saude", "health"),
        ("reabilitacao", "rehabilitation"),
    )
    for token, normalized in domains:
        if token in hay:
            domain = normalized
            break
    metric_name = metric or "qualification"
    pieces = [scope, role or domain, domain if role else "", metric_name]
    return ".".join(piece for piece in pieces if piece and piece != "generic")


def _prompt_for(label: str, spec: dict[str, Any] | None, scope: str, role: str) -> str:
    target = label.strip() or "este requisito"
    if spec is None:
        if scope == "person":
            return f"Tem alguém na equipa que cumpra «{target}»?"
        if scope == "project":
            return f"Tem projetos que cumpram «{target}»?"
        return f"A empresa cumpre «{target}»?"

    metric = spec.get("metric")
    value = spec.get("value")
    unit = spec.get("unit")
    op = spec.get("operator")
    if metric == "years":
        return f"Tem alguém na função relevante com pelo menos {value:g} anos de experiência?"
    if metric == "training_hours":
        return f"Tem algum elemento da equipa com pelo menos {value:g} horas da formação exigida?"
    if metric == "project_value_eur":
        return f"Tem projeto elegível com valor de obra/empreitada de pelo menos {value:,.0f} €?".replace(",", " ")
    if metric == "volume_m3":
        return f"Tem projeto elegível com pelo menos {value:,.0f} m³ na métrica exigida?".replace(",", " ")
    if metric == "area_m2":
        return f"Tem projeto elegível com pelo menos {value:,.0f} m² na métrica exigida?".replace(",", " ")
    if metric == "project_count" and op == "actual":
        return f"Tem projetos elegíveis para «{target}»?"
    return f"Cumpre o valor exigido para «{target}»?"


def _followups(label: str, spec: dict[str, Any] | None, scope: str) -> list[dict[str, Any]]:
    followups: list[dict[str, Any]] = []
    if scope == "person":
        followups.append(
            {
                "id": "person",
                "type": "person",
                "label": "Quem?",
                "required_when": ["yes"],
                "placeholder": "Selecionar ou indicar a pessoa",
            }
        )
    if scope == "project":
        followups.append(
            {
                "id": "project",
                "type": "project",
                "label": "Que projeto?",
                "required_when": ["yes"],
                "placeholder": "Selecionar ou indicar o projeto",
            }
        )
    if spec is not None:
        metric = str(spec.get("metric") or "")
        labels = {
            "years": "Quantos anos de experiência tem?",
            "training_hours": "Quantas horas de formação tem?",
            "project_count": "Quantos projetos elegíveis existem?",
            "project_value_eur": "Qual é o maior valor de obra/empreitada comprovável?",
            "volume_m3": "Qual é o maior volume comprovável?",
            "area_m2": "Qual é a maior área comprovável?",
        }
        if metric in labels:
            followups.append(
                {
                    "id": "value",
                    "type": "number",
                    "label": labels[metric],
                    # Numeric values remain useful even when the first answer is 'no':
                    # they let the system calculate partial bands instead of losing the fact.
                    "required_when": ["yes", "no"],
                    "unit": spec.get("unit"),
                    "metric": metric,
                    "placeholder": "0",
                }
            )
    return followups


def _requirement(
    *,
    label: str,
    parent_factor: dict[str, Any] | None,
    subfactor: dict[str, Any] | None,
    source: dict[str, Any],
    spec: dict[str, Any] | None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    factor_label = _clean((parent_factor or {}).get("label"))
    combined = _clean(" ".join(x for x in (factor_label, label, source.get("excerpt")) if x))
    scope, role = _scope(combined)
    metric = str(spec.get("metric")) if spec else None
    key = _reuse_key(combined, metric, scope, role)
    threshold = spec.get("value") if spec else None
    operator = spec.get("operator") if spec else None
    unit = spec.get("unit") if spec else None
    req_id = hashlib.sha1(
        f"{factor_label}|{label}|{metric}|{threshold}|{key}".encode("utf-8")
    ).hexdigest()[:14]

    required_text = _clean(
        _first(raw, "requirement", "rule", "description", "summary", "text", "evidence_excerpt")
        or source.get("excerpt")
        or label
    )
    nature = _nature(combined)
    semantic_text = _clean(" ".join([combined, required_text]))
    stage = _semantic_stage(semantic_text, source, nature)
    constraints = _structured_constraints(semantic_text, spec)
    return {
        "id": req_id,
        "factor_code": _clean((parent_factor or {}).get("code")),
        "factor_label": factor_label,
        "subfactor_code": _clean((subfactor or {}).get("code")),
        "subfactor_label": _clean((subfactor or {}).get("label")),
        "label": label,
        "phase": "competition",
        "stage": stage,
        "nature": nature,
        "profile_dependent": _profile_dependent(combined, factor_label),
        "required": {
            "text": required_text or label,
            "metric": metric,
            "operator": operator,
            "threshold": threshold,
            "unit": unit,
        },
        "constraints": constraints,
        "profile_target": {
            "scope": scope,
            "role": role,
            "reuse_key": key,
        },
        "profile": {
            "status": "missing",
            "summary": "Não demonstrado no perfil.",
            "evidence": [],
        },
        "result": {
            "status": "pending",
            "label": "Por confirmar",
            "estimated_score": None,
        },
        "source": source,
        "question": {
            "id": f"q_{req_id}",
            "type": "yes_no",
            "text": _prompt_for(label, spec, scope, role),
            "reason": "Este dado é necessário para confirmar elegibilidade ou estimar a pontuação.",
            "profile_target": {
                "scope": scope,
                "role": role,
                "reuse_key": key,
            },
            "followups": _followups(label, spec, scope),
        },
    }


def _criterion_lookup(hierarchy: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any] | None]]:
    lookup: dict[str, tuple[dict[str, Any], dict[str, Any] | None]] = {}
    for factor in hierarchy.get("factors") or []:
        keys = {_fold(factor.get("code")), _fold(factor.get("label"))}
        for key in keys:
            if key:
                lookup[key] = (factor, None)
        for sub in factor.get("subfactors") or []:
            keys = {_fold(sub.get("code")), _fold(sub.get("label"))}
            for key in keys:
                if key:
                    lookup[key] = (factor, sub)
    return lookup


def _match_criterion(
    raw: dict[str, Any],
    hierarchy: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    lookup = _criterion_lookup(hierarchy)
    code = _clean(_first(raw, "criterion_code", "subfactor_code", "code", "factor_code"))
    label = _label(raw)
    for candidate in (_fold(code), _fold(label)):
        if candidate in lookup:
            return lookup[candidate]
    if code:
        for factor in hierarchy.get("factors") or []:
            for sub in factor.get("subfactors") or []:
                if _fold(sub.get("code")) and _fold(code).startswith(_fold(sub.get("code"))):
                    return factor, sub
        for factor in hierarchy.get("factors") or []:
            if _fold(factor.get("code")) and _fold(code).startswith(_fold(factor.get("code"))):
                return factor, None
    return None, None


def _scoring_requirement_rows(criteria: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for key in ("scoring_requirements", "requirements", "evaluation_requirements"):
        for item in _as_list(criteria.get(key)):
            if isinstance(item, dict) and id(item) not in seen:
                seen.add(id(item))
                rows.append(item)
    for factor in _raw_factors(criteria):
        for container in (factor, *[x for x in _as_list(_first(factor, "subfactors", "children")) if isinstance(x, dict)]):
            for key in ("scoring_requirements", "requirements", "rules", "descriptors", "score_bands"):
                for item in _as_list(container.get(key)):
                    if isinstance(item, dict) and id(item) not in seen:
                        seen.add(id(item))
                        rows.append(item)
    return rows


def _experience_rules(criteria: dict[str, Any], procedure: dict[str, Any]) -> dict[str, Any]:
    for candidate in (
        criteria.get("experience_rules"),
        procedure.get("experience_rules"),
        (procedure.get("award_criteria") or {}).get("experience_rules") if isinstance(procedure.get("award_criteria"), dict) else None,
    ):
        if isinstance(candidate, dict):
            return candidate
    return {}


def _rules_requirements(
    rules: dict[str, Any],
    hierarchy: dict[str, Any],
) -> list[dict[str, Any]]:
    if not rules:
        return []
    factors = hierarchy.get("factors") or []
    experience_factor = next(
        (
            factor
            for factor in factors
            if _profile_dependent(_clean(factor.get("label")))
        ),
        factors[0] if factors else None,
    )
    subs = experience_factor.get("subfactors") if isinstance(experience_factor, dict) else []
    subs = subs or []

    def sub_for(*markers: str) -> dict[str, Any] | None:
        for sub in subs:
            hay = _fold(sub.get("label"))
            if any(marker in hay for marker in markers):
                return sub
        return None

    common_qualifiers = []
    geography = _clean(_first(rules, "geography", "territory", "location"))
    period = _clean(_first(rules, "period", "time_period", "lookback"))
    if geography:
        common_qualifiers.append(f"Localização elegível: {geography}.")
    if period:
        common_qualifiers.append(f"Período elegível: {period}.")
    qualifier = " ".join(common_qualifiers)

    generated: list[dict[str, Any]] = []

    # Project count: actual amount matters for scoring. The published maximum is not
    # treated as a minimum; the question stores the real count.
    max_projects = _float(
        _first(
            rules,
            "maximum_projects_per_specialty",
            "max_projects",
            "maximum_projects",
        )
    )
    if max_projects is not None:
        for sub in [s for s in subs if _profile_dependent(_clean(s.get("label")), _clean((experience_factor or {}).get("label")))]:
            if "bim" in _fold(sub.get("label")):
                continue
            label = _clean(sub.get("label"))
            src = sub.get("source") if isinstance(sub.get("source"), dict) else {}
            req = _requirement(
                label=label,
                parent_factor=experience_factor,
                subfactor=sub,
                source=src,
                spec={"metric": "project_count", "value": max_projects, "unit": "projetos", "operator": "actual"},
            )
            req["required"]["text"] = (
                f"{label}. Podem ser considerados até {max_projects:g} projetos por especialidade. {qualifier}"
            ).strip()
            generated.append(req)

    min_value = _float(
        _first(
            rules,
            "minimum_updated_construction_value_eur",
            "minimum_construction_value_eur",
            "min_construction_value_eur",
            "minimum_project_value_eur",
        )
    )
    if min_value is not None:
        targets = [
            sub_for("parques urbanos", "parque urbano"),
            sub_for("urbanizacao", "urbanização"),
        ]
        targets = [target for target in targets if target is not None]
        if not targets and subs:
            targets = subs[:2]
        for sub in targets:
            label = _clean(sub.get("label"))
            src = sub.get("source") if isinstance(sub.get("source"), dict) else {}
            req = _requirement(
                label=label,
                parent_factor=experience_factor,
                subfactor=sub,
                source=src,
                spec={"metric": "project_value_eur", "value": min_value, "unit": "€", "operator": ">="},
            )
            req["required"]["text"] = (
                f"{label}: projeto elegível com valor atualizado de obra/empreitada ≥ {min_value:,.0f} €. {qualifier}"
            ).replace(",", " ").strip()
            generated.append(req)

    earthworks = _float(
        _first(
            rules,
            "minimum_earthworks_volume_m3",
            "earthworks_min_volume_m3",
            "minimum_terrain_remodelling_volume_m3",
            "minimum_terrain_modeling_volume_m3",
        )
    )
    if earthworks is not None:
        sub = sub_for("modelacao", "remodelacao", "terrenos", "earthworks")
        if sub is not None:
            label = _clean(sub.get("label"))
            src = sub.get("source") if isinstance(sub.get("source"), dict) else {}
            req = _requirement(
                label=label,
                parent_factor=experience_factor,
                subfactor=sub,
                source=src,
                spec={"metric": "volume_m3", "value": earthworks, "unit": "m³", "operator": ">="},
            )
            req["required"]["text"] = (
                f"{label}: experiência elegível com volume ≥ {earthworks:,.0f} m³. {qualifier}"
            ).replace(",", " ").strip()
            generated.append(req)

    bim_hours = _float(
        _first(
            rules,
            "minimum_bim_training_hours",
            "bim_training_min_hours",
            "minimum_training_hours",
            "bim_training_hours",
        )
    )
    if bim_hours is not None:
        sub = sub_for("bim")
        if sub is not None:
            label = _clean(sub.get("label"))
            src = sub.get("source") if isinstance(sub.get("source"), dict) else {}
            req = _requirement(
                label=label,
                parent_factor=experience_factor,
                subfactor=sub,
                source=src,
                spec={"metric": "training_hours", "value": bim_hours, "unit": "horas", "operator": ">="},
            )
            req["required"]["text"] = f"{label}: formação do elemento indicado com pelo menos {bim_hours:g} horas."
            generated.append(req)

    return generated


def _subfactor_default_requirements(hierarchy: dict[str, Any]) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    for factor in hierarchy.get("factors") or []:
        for sub in factor.get("subfactors") or []:
            combined = _clean(f"{factor.get('label')} {sub.get('label')} {sub.get('summary')}")
            if not _profile_dependent(combined):
                continue
            src = sub.get("source") if isinstance(sub.get("source"), dict) else {}
            specs = _metric_specs(_clean(f"{sub.get('summary')} {src.get('excerpt')}"))
            if not specs:
                generated.append(
                    _requirement(
                        label=_clean(sub.get("label")),
                        parent_factor=factor,
                        subfactor=sub,
                        source=src,
                        spec=None,
                    )
                )
            else:
                for spec in specs:
                    generated.append(
                        _requirement(
                            label=_clean(sub.get("label")),
                            parent_factor=factor,
                            subfactor=sub,
                            source=src,
                            spec=spec,
                        )
                    )
    return generated


def _award_requirements(
    criteria: dict[str, Any],
    hierarchy: dict[str, Any],
) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    for raw in _scoring_requirement_rows(criteria):
        factor, sub = _match_criterion(raw, hierarchy)
        label = _label(raw, _clean((sub or factor or {}).get("label")) or "Requisito de avaliação")
        src = _source(raw)
        text = _clean(
            " ".join(
                [
                    label,
                    _clean(_first(raw, "requirement", "rule", "summary", "description", "text")),
                    src.get("excerpt", ""),
                ]
            )
        )
        specs = _metric_specs(text)
        if specs:
            for spec in specs:
                generated.append(
                    _requirement(
                        label=label,
                        parent_factor=factor,
                        subfactor=sub,
                        source=src,
                        spec=spec,
                        raw=raw,
                    )
                )
        elif _profile_dependent(text, _clean((factor or {}).get("label"))):
            generated.append(
                _requirement(
                    label=label,
                    parent_factor=factor,
                    subfactor=sub,
                    source=src,
                    spec=None,
                    raw=raw,
                )
            )
    return generated


def _team_is_submission_required(item: dict[str, Any], procedure: dict[str, Any]) -> bool:
    explicit = item.get("required_at_submission")
    if explicit is not None:
        return explicit is True
    if _fold(item.get("stage")) == "post_award" or _fold(item.get("phase")) == "execution":
        return False

    source = _source(item)
    source_text = " ".join(_clean(value) for value in source.values())
    hay = _fold(" ".join([source_text, " ".join(_clean(item.get(key)) for key in ("role", "title", "summary"))]))
    if "proposta" in hay and any(marker in hay for marker in ("equipa", "coordenador", "autor", "tecnico")):
        return True

    team = procedure.get("technical_team") if isinstance(procedure, dict) else None
    team_items = [entry for entry in _as_list(team) if isinstance(entry, dict)]
    unique_roles = {
        _fold(_first(entry, "role", "title", "label", "name"))
        for entry in team_items
        if _clean(_first(entry, "role", "title", "label", "name"))
    }
    source_document = _fold(source.get("document"))
    family = _fold(procedure.get("family")).replace(" ", "_")
    # Compatibilidade com análises antigas: uma lista de roles completa,
    # extraída do Programa, é evidência procedural quando o procedimento é
    # de conceção-construção. Não basta existir uma única role isolada.
    return (
        len(unique_roles) >= 3
        and "programa" in source_document
        and family == "design_build"
    )


def _team_requirements(procedure: dict[str, Any]) -> list[dict[str, Any]]:
    """Converte roles documentais explicitamente exigidas com a proposta."""
    generated: list[dict[str, Any]] = []
    team = procedure.get("technical_team") if isinstance(procedure, dict) else None
    for item in _as_list(team):
        if not isinstance(item, dict) or not _team_is_submission_required(item, procedure):
            continue
        label = _clean(_first(item, "role", "title", "label", "name"))
        if not label:
            continue
        req = _requirement(
            label=label,
            parent_factor=None,
            subfactor=None,
            source=_source(item),
            spec=None,
            raw=item,
        )
        req["nature"] = "team"
        req["phase"] = "competition"
        req["stage"] = "pre_award"
        req["profile_dependent"] = True
        req["required_at_submission"] = True
        req["mandatory"] = bool(item.get("mandatory", True))
        req["required"]["text"] = (
            f"Identificar {label} na equipa técnica apresentada com a proposta."
        )
        target = req.setdefault("profile_target", {})
        target["scope"] = "person"
        target["role"] = _clean(item.get("role") or label)
        target["reuse_key"] = f"team.role.{_fold(label)}"
        question = req.setdefault("question", {})
        question["type"] = "yes_no"
        question["text"] = f"Consegue apresentar {label} para esta proposta?"
        question["reason"] = "A resposta é necessária para validar a equipa exigida com a proposta."
        question["profile_target"] = dict(target)
        question["followups"] = []
        generated.append(req)
    return generated

def _procedural_noise(text: str) -> bool:
    """Rejeita índices e formalidades que não são factos da empresa."""
    folded = _fold(text)
    if text.count(".") >= 8:
        return True
    return any(
        marker in folded
        for marker in (
            "audiencia",
            "relatorio preliminar",
            "relatorio final",
            "nao adjudicacao",
            "prestacao de caucao",
        )
    )

def _competition_gate_requirements(procedure: dict[str, Any]) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    containers: list[tuple[str, Any]] = [
        ("eligibility", procedure.get("eligibility")),
        ("submission", procedure.get("submission")),
        ("participation", procedure.get("participation")),
    ]
    for container_name, container in containers:
        if not isinstance(container, dict):
            continue
        for key in (
            "critical_conditions",
            "eligibility_requirements",
            "minimum_requirements",
            "team_requirements",
            "explicit_exclusions",
            "scoring_requirements",
        ):
            for raw_value in _as_list(container.get(key)):
                if isinstance(raw_value, dict):
                    raw = raw_value
                    text = _clean(
                        _first(
                            raw,
                            "requirement",
                            "title",
                            "label",
                            "summary",
                            "description",
                            "text",
                        )
                    )
                    src = _source(raw)
                else:
                    raw = {}
                    text = _clean(raw_value)
                    src = {}
                if not text:
                    continue
                if _procedural_noise(text):
                    continue
                src_phase = _phase_from_source(src, scored=False)
                if src_phase == "execution":
                    continue
                if not _profile_dependent(text) and container_name != "eligibility":
                    continue
                specs = _metric_specs(text)
                if not specs:
                    specs = [None]
                for spec in specs:
                    req = _requirement(
                        label=text[:180],
                        parent_factor=None,
                        subfactor=None,
                        source=src,
                        spec=spec,
                        raw=raw,
                    )
                    req["nature"] = "eligibility" if container_name == "eligibility" else _nature(text)
                    generated.append(req)
    return generated


def _dedupe_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove apenas duplicados reais, sem apagar bandas de pontuação distintas."""
    by_key: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

    for req in requirements:
        target = req.get("profile_target") or {}
        required = req.get("required") or {}
        threshold = required.get("threshold")
        threshold_key = (
            f"{threshold:.8g}"
            if isinstance(threshold, float)
            else _clean(threshold)
        )

        key = (
            _clean(
                req.get("subfactor_code")
                or req.get("factor_code")
                or req.get("label")
            ),
            _clean(target.get("reuse_key")),
            _clean(required.get("metric")),
            _clean(required.get("operator")),
            threshold_key,
        )

        current = by_key.get(key)
        if current is None:
            by_key[key] = req
            continue

        current_text = _clean((current.get("required") or {}).get("text"))
        new_text = _clean(required.get("text"))
        current_source = current.get("source") or {}
        new_source = req.get("source") or {}

        current_quality = (
            bool(_clean(current_source.get("document"))),
            bool(_clean(current_source.get("excerpt"))),
            len(current_text),
        )
        new_quality = (
            bool(_clean(new_source.get("document"))),
            bool(_clean(new_source.get("excerpt"))),
            len(new_text),
        )

        if new_quality > current_quality:
            by_key[key] = req

    return list(by_key.values())

def _matching_candidates(ficha: dict[str, Any]) -> list[dict[str, Any]]:
    matching = ficha.get("company_matching")
    if not isinstance(matching, dict):
        return []
    candidates: list[dict[str, Any]] = []
    for item in _dicts(matching):
        status = _fold(_first(item, "status", "state", "result", "coverage_status"))
        if status or any(key in item for key in ("criterion_code", "subfactor_code", "requirement", "documented")):
            candidates.append(item)
    return candidates


def _apply_existing_profile_matches(ficha: dict[str, Any], requirements: list[dict[str, Any]]) -> None:
    candidates = _matching_candidates(ficha)
    for req in requirements:
        req_tokens = {
            _fold(req.get("factor_code")),
            _fold(req.get("subfactor_code")),
            _fold(req.get("label")),
            _fold((req.get("profile_target") or {}).get("reuse_key")),
        }
        req_tokens.discard("")
        best: dict[str, Any] | None = None
        best_score = 0
        for item in candidates:
            hay_parts = [
                _first(item, "criterion_code", "subfactor_code", "factor_code", "code"),
                _first(item, "label", "name", "requirement", "title"),
                _first(item, "reuse_key", "field"),
            ]
            hay = _fold(" ".join(_clean(x) for x in hay_parts if x))
            score = sum(1 for token in req_tokens if token and (token == hay or token in hay or hay in token))
            if score > best_score:
                best_score = score
                best = item
        if not best or best_score == 0:
            continue
        status = _fold(_first(best, "status", "state", "coverage_status"))
        documented = best.get("documented")
        if documented is True or status in {"confirmed", "confirmado", "documented", "comprovado", "met", "cumpre"}:
            req["profile"] = {
                "status": "confirmed",
                "summary": _clean(
                    _first(best, "summary", "justification", "explanation", "value", "result")
                    or "Informação já demonstrada no perfil."
                ),
                "evidence": _as_list(best.get("evidence")),
            }
            req["result"] = {
                "status": "met",
                "label": "Cumpre",
                "estimated_score": _first(best, "score", "points", "estimated_score"),
            }


def _attach_requirements(hierarchy: dict[str, Any], requirements: list[dict[str, Any]]) -> None:
    by_sub: dict[str, list[dict[str, Any]]] = {}
    by_factor: dict[str, list[dict[str, Any]]] = {}
    for req in requirements:
        sub_code = _fold(req.get("subfactor_code"))
        factor_code = _fold(req.get("factor_code"))
        if sub_code:
            by_sub.setdefault(sub_code, []).append(req)
        elif factor_code:
            by_factor.setdefault(factor_code, []).append(req)

    for factor in hierarchy.get("factors") or []:
        factor["requirements"] = by_factor.get(_fold(factor.get("code")), [])
        for sub in factor.get("subfactors") or []:
            sub["requirements"] = by_sub.get(_fold(sub.get("code")), [])


def _decision(ficha: dict[str, Any], requirements: list[dict[str, Any]], hierarchy: dict[str, Any]) -> dict[str, Any]:
    matching = ficha.get("company_matching") if isinstance(ficha.get("company_matching"), dict) else {}
    recommendation = ficha.get("recomendacao_final") if isinstance(ficha.get("recomendacao_final"), dict) else {}
    ai = ficha.get("analise_ai") if isinstance(ficha.get("analise_ai"), dict) else {}

    score = _first(matching, "score_compatibilidade", "score")
    if score is None:
        score = _first(ai, "score")
    score_num = _float(score)

    missing = [req for req in requirements if req.get("profile_dependent") and (req.get("profile") or {}).get("status") != "confirmed"]
    confirmed = [req for req in requirements if req.get("profile_dependent") and (req.get("profile") or {}).get("status") == "confirmed"]

    sub_weight: dict[str, float] = {}
    for factor in hierarchy.get("factors") or []:
        for sub in factor.get("subfactors") or []:
            value = _float(sub.get("effective_weight_percent"))
            if value is not None:
                sub_weight[_fold(sub.get("code"))] = value

    def driver_weight(req: dict[str, Any]) -> float:
        return sub_weight.get(_fold(req.get("subfactor_code")), 0.0)

    drivers = sorted(
        [req for req in requirements if req.get("profile_dependent")],
        key=lambda req: (-driver_weight(req), _clean(req.get("label"))),
    )[:8]

    if missing:
        eligibility = "Por confirmar"
        risk = "Médio" if any(req.get("nature") == "eligibility" for req in missing) else "Por confirmar"
    else:
        eligibility = "Compatível" if requirements else "Por confirmar"
        risk = "Baixo" if requirements else "Por confirmar"

    confidence_obj = matching.get("confidence") if isinstance(matching.get("confidence"), dict) else {}
    confidence = _clean(_first(confidence_obj, "level") or _first(recommendation, "confianca") or "Por confirmar")

    return {
        "score": score_num,
        "classification": _clean(
            _first(recommendation, "decisao")
            or _first(ai.get("vale_a_pena_concorrer") if isinstance(ai.get("vale_a_pena_concorrer"), dict) else {}, "veredito")
            or ("Avaliar" if missing else "Compatível")
        ),
        "eligibility": eligibility,
        "risk": risk,
        "confidence": confidence,
        "missing_profile_facts": len(missing),
        "confirmed_profile_facts": len(confirmed),
        "explanation": _clean(
            _first(recommendation, "explicacao")
            or (
                f"Faltam {len(missing)} dados do perfil com impacto potencial na elegibilidade ou pontuação."
                if missing
                else "Os requisitos de perfil identificados estão demonstrados com os dados disponíveis."
            )
        ),
        "drivers": [
            {
                "requirement_id": req.get("id"),
                "label": req.get("label"),
                "factor_code": req.get("factor_code"),
                "subfactor_code": req.get("subfactor_code"),
                "status": (req.get("result") or {}).get("status"),
                "effective_weight_percent": driver_weight(req),
                "profile_status": (req.get("profile") or {}).get("status"),
            }
            for req in drivers
        ],
    }


def build_canonical_analysis(
    *,
    ficha: dict[str, Any],
    procedure: dict[str, Any],
    textos: Any = None,
    concurso: dict[str, Any] | None = None,
) -> dict[str, Any]:
    criteria = _find_criteria(procedure, ficha)
    hierarchy = build_criteria_hierarchy(procedure, ficha)

    requirements: list[dict[str, Any]] = []
    requirements.extend(_award_requirements(criteria, hierarchy))
    requirements.extend(_rules_requirements(_experience_rules(criteria, procedure), hierarchy))
    requirements.extend(_subfactor_default_requirements(hierarchy))
    requirements.extend(_team_requirements(procedure))
    requirements.extend(_competition_gate_requirements(procedure))
    requirements = _dedupe_requirements(requirements)
    _apply_existing_profile_matches(ficha, requirements)
    _attach_requirements(hierarchy, requirements)
    for requirement in requirements:
        if isinstance(requirement, dict):
            requirement["impact_weight_percent"] = _requirement_weight(
                requirement,
                hierarchy,
            )

    questions = _build_deduplicated_questions(requirements, hierarchy)

    result = {
        "schema_version": SCHEMA_VERSION,
        "template": {
            "name": "CNLL Canonical Analysis",
            "references": ["Lumiar", "Parque Urbano do Vale de Santo António"],
            "hierarchical_weights": True,
            "three_question_metric": [
                "O que é exigido?",
                "O que temos no perfil?",
                "Qual é o resultado?",
            ],
        },
        "competition_id": _first(concurso or {}, "id", "concurso_id"),
        "procedure_family": _clean(procedure.get("family")),
        "procedure_family_label": _clean(procedure.get("family_label")),
        "criteria": hierarchy,
        "requirements": requirements,
        "questions": questions,
        "question_policy_version": "decision-facts-v17.3",
        "decision": _decision(ficha, requirements, hierarchy),
        "phase_policy": {
            "decision_phase": "competition",
            "competition_natures": [
                "eligibility",
                "team",
                "evaluation",
                "submission",
                "habilitation",
            ],
            "execution_is_separate": True,
            "document_priority": [
                "Programa do Procedimento / Programa do Concurso / Regulamento",
                "Convite e matrizes/anexos de avaliação",
                "Peças de candidatura e submissão",
                "Caderno de Encargos apenas quando a regra afeta explicitamente a candidatura",
            ],
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return result


def apply_canonical_analysis(
    *,
    ficha: dict[str, Any],
    procedure: dict[str, Any],
    textos: Any = None,
    concurso: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(ficha, dict):
        raise TypeError("ficha deve ser um dicionário")
    if not isinstance(procedure, dict):
        procedure = {}
    result = build_canonical_analysis(
        ficha=ficha,
        procedure=procedure,
        textos=textos,
        concurso=concurso,
    )
    ficha["analysis_template_version"] = SCHEMA_VERSION
    ficha["analysis_canonical"] = result
    return result

# CNLL_CANONICAL_PROFILE_RECALC_V17_2
def _question_reuse_key(req: dict[str, Any]) -> str:
    target = req.get("profile_target") if isinstance(req.get("profile_target"), dict) else {}
    question = req.get("question") if isinstance(req.get("question"), dict) else {}
    question_target = (
        question.get("profile_target")
        if isinstance(question.get("profile_target"), dict)
        else {}
    )
    return _clean(
        target.get("reuse_key")
        or question_target.get("reuse_key")
        or (req.get("required") or {}).get("reuse_key")
    )


# CNLL_QUESTION_POLICY_V17_3
def _requirement_weight(
    requirement: dict[str, Any],
    hierarchy: dict[str, Any] | None,
) -> float:
    hierarchy = hierarchy if isinstance(hierarchy, dict) else {}
    sub_code = _fold(requirement.get("subfactor_code"))
    factor_code = _fold(requirement.get("factor_code"))

    for factor in hierarchy.get("factors") or []:
        if not isinstance(factor, dict):
            continue

        for sub in factor.get("subfactors") or []:
            if not isinstance(sub, dict):
                continue
            if sub_code and _fold(sub.get("code")) == sub_code:
                value = (
                    sub.get("effective_weight_percent")
                    if sub.get("effective_weight_percent") is not None
                    else sub.get("display_weight_percent")
                )
                return float(_float(value) or 0)

        if factor_code and _fold(factor.get("code")) == factor_code:
            return float(_float(factor.get("display_weight_percent")) or 0)

    return 0.0


def _question_group_key(
    requirement: dict[str, Any],
) -> tuple[str, str, str, str]:
    target = requirement.get("profile_target") or {}
    return (
        _fold(
            requirement.get("subfactor_code")
            or requirement.get("factor_code")
            or requirement.get("label")
        ),
        _clean(target.get("scope")),
        _clean(target.get("role")),
        _fold(requirement.get("nature")),
    )


def _mandatory_language(requirement: dict[str, Any]) -> bool:
    required = requirement.get("required") or {}
    source = requirement.get("source") or {}
    hay = _fold(
        " ".join(
            [
                _clean(requirement.get("label")),
                _clean(required.get("text")),
                _clean(source.get("excerpt")),
            ]
        )
    )
    return any(
        marker in hay
        for marker in (
            "obrigatorio",
            "obrigatoria",
            "deve",
            "devera",
            "minimo",
            "minima",
            "pelo menos",
            "requisito",
            "exigido",
            "exigida",
            "condicao de admissao",
            "condicao de participacao",
        )
    )


def _material_question_requirement(
    requirement: dict[str, Any],
    hierarchy: dict[str, Any] | None,
) -> bool:
    """
    Só pergunta factos que podem alterar a decisão de concorrer:
    elegibilidade, equipa obrigatória ou pontuação.
    """
    if not isinstance(requirement, dict):
        return False
    if not requirement.get("profile_dependent"):
        return False
    if (requirement.get("profile") or {}).get("status") == "confirmed":
        return False

    stage = _fold(requirement.get("stage"))
    if stage == "post_award":
        return False
    if _fold(requirement.get("phase")) == "execution":
        return False

    source = requirement.get("source") or {}
    if _phase_from_source(source, scored=False) == "execution":
        return False

    nature = _fold(requirement.get("nature"))
    if nature in {"submission", "habilitation"}:
        return False

    required = requirement.get("required") or {}
    metric = _clean(required.get("metric"))
    weight = _requirement_weight(requirement, hierarchy)

    if nature == "eligibility":
        return True

    if nature == "team":
        return bool(
            metric
            or weight > 0
            or requirement.get("required_at_submission") is True
            or requirement.get("mandatory") is True
            or _mandatory_language(requirement)
        )
    if nature == "evaluation":
        # Frases soltas de experiência não devem virar perguntas de CV.
        # Para avaliação, exigimos ligação a um fator/subfator realmente pontuado.
        return weight > 0

    return False


def _question_priority(
    requirement: dict[str, Any],
    hierarchy: dict[str, Any] | None,
) -> tuple[int, float]:
    nature = _fold(requirement.get("nature"))
    weight = _requirement_weight(requirement, hierarchy)

    if nature == "eligibility":
        return (0, -weight)
    if nature == "team":
        return (1, -weight)
    return (2, -weight)


def _priority_label(requirement: dict[str, Any]) -> str:
    nature = _fold(requirement.get("nature"))
    if nature == "eligibility":
        return "Elegibilidade"
    if nature == "team":
        return "Equipa"
    return "Pontuação"


def _format_threshold(value: Any) -> str:
    number = _float(value)
    if number is None:
        return _clean(value)
    if float(number).is_integer():
        return f"{int(number):,}".replace(",", " ")
    return f"{number:g}".replace(".", ",")


def _neutral_question_text(
    *,
    label: str,
    metric: str,
    scope: str,
    fallback: str,
    threshold: Any = None,
    unit: str = "",
) -> str:
    """
    Mostra o limiar documental na pergunta, mas guarda depois o valor REAL.

    Exemplo: se o patamar máximo é 80 h e a resposta é Não, o follow-up pode
    guardar 60 h e essa informação continua útil noutro concurso/patamar.
    """
    quoted = f"«{label}»" if label else "este critério"
    threshold_text = _format_threshold(threshold)
    unit_text = _clean(unit)

    if metric == "years":
        if threshold_text:
            return (
                "Existe alguém na equipa com pelo menos "
                f"{threshold_text} {unit_text or 'anos'} de experiência "
                f"relevante para {quoted}?"
            )
        return f"Existe alguém na equipa com experiência relevante para {quoted}?"

    if metric == "training_hours":
        if threshold_text:
            return (
                "Existe algum elemento da equipa com pelo menos "
                f"{threshold_text} {unit_text or 'horas'} de formação "
                f"relevante para {quoted}?"
            )
        return (
            "Existe algum elemento da equipa com formação relevante para "
            f"{quoted}?"
        )

    if metric == "project_count":
        if threshold_text:
            return (
                f"A empresa tem pelo menos {threshold_text} projetos "
                f"que possam ser considerados em {quoted}?"
            )
        return f"A empresa tem projetos que possam ser considerados em {quoted}?"

    if metric == "project_value_eur":
        if threshold_text:
            return (
                "A empresa tem algum projeto que possa ser considerado em "
                f"{quoted} com valor de obra atualizado de pelo menos "
                f"{threshold_text} {unit_text or '€'}?"
            )
        return f"A empresa tem algum projeto que possa ser considerado em {quoted}?"

    if metric == "volume_m3":
        if threshold_text:
            return (
                "A empresa tem algum projeto que possa ser considerado em "
                f"{quoted} com pelo menos {threshold_text} "
                f"{unit_text or 'm³'}?"
            )
        return f"A empresa tem algum projeto que possa ser considerado em {quoted}?"

    if metric == "area_m2":
        if threshold_text:
            return (
                "A empresa tem algum projeto que possa ser considerado em "
                f"{quoted} com pelo menos {threshold_text} "
                f"{unit_text or 'm²'}?"
            )
        return f"A empresa tem algum projeto que possa ser considerado em {quoted}?"

    if scope == "person":
        return f"Existe alguém na equipa que cumpra {quoted}?"
    if scope == "project":
        return f"A empresa tem projetos que cumpram {quoted}?"
    return fallback or f"A empresa cumpre {quoted}?"


def _build_deduplicated_questions(
    requirements: list[dict[str, Any]],
    hierarchy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Uma pergunta por facto reutilizável.

    `hierarchy is None` mantém compatibilidade com chamadas/testes V17.2.
    Quando a hierarquia é fornecida, ativa a política criteriosa V17.3.
    """
    strict = hierarchy is not None
    hierarchy_data = hierarchy if isinstance(hierarchy, dict) else {}

    candidates: list[dict[str, Any]] = []
    for req in requirements:
        if not isinstance(req, dict):
            continue
        if not req.get("profile_dependent"):
            continue
        if (req.get("profile") or {}).get("status") == "confirmed":
            continue
        if not isinstance(req.get("question"), dict):
            continue
        if strict and not _material_question_requirement(req, hierarchy_data):
            continue
        candidates.append(req)

    if strict:
        groups_with_metric = {
            _question_group_key(req)
            for req in candidates
            if _clean((req.get("required") or {}).get("metric"))
        }
        filtered: list[dict[str, Any]] = []
        for req in candidates:
            metric = _clean((req.get("required") or {}).get("metric"))
            if not metric and _question_group_key(req) in groups_with_metric:
                # Evita "Tem experiência?" + "Qual é o valor/anos?" para o mesmo
                # critério. O valor real é o facto reutilizável que interessa.
                continue
            filtered.append(req)
        candidates = filtered

        candidates.sort(
            key=lambda req: (
                *_question_priority(req, hierarchy_data),
                _clean(req.get("factor_code")),
                _clean(req.get("subfactor_code")),
                _clean(req.get("label")),
            )
        )

    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for req in candidates:
        source_question = req.get("question") or {}
        reuse_key = _question_reuse_key(req)
        if not reuse_key:
            reuse_key = f"requirement:{_clean(req.get('id'))}"

        required = req.get("required") or {}
        target = (
            req.get("profile_target")
            if isinstance(req.get("profile_target"), dict)
            else source_question.get("profile_target") or {}
        )

        if reuse_key not in grouped:
            question = dict(source_question)
            question["requirement_id"] = req.get("id")
            question["requirement_ids"] = (
                [req.get("id")] if req.get("id") else []
            )
            question["factor_code"] = req.get("factor_code")
            question["subfactor_code"] = req.get("subfactor_code")
            question["required"] = dict(required)
            question["profile_target"] = target
            question["contexts"] = [
                {
                    "factor_code": req.get("factor_code"),
                    "subfactor_code": req.get("subfactor_code"),
                    "label": req.get("label"),
                    "required": required,
                    "nature": req.get("nature"),
                    "stage": req.get("stage"),
                }
            ]

            if strict:
                metric = _clean(required.get("metric"))
                scope = _clean(target.get("scope"))
                question["nature"] = req.get("nature")
                question["phase"] = req.get("phase")
                question["stage"] = req.get("stage")
                question["priority_label"] = _priority_label(req)
                question["impact_weight_percent"] = _requirement_weight(
                    req, hierarchy_data
                )
                question["text"] = _neutral_question_text(
                    label=_clean(req.get("label")),
                    metric=metric,
                    scope=scope,
                    fallback=_clean(source_question.get("text")),
                    threshold=required.get("threshold"),
                    unit=_clean(required.get("unit")),
                )
                question["reason"] = (
                    "A resposta altera a elegibilidade."
                    if _fold(req.get("nature")) == "eligibility"
                    else (
                        "A resposta é necessária para validar a equipa exigida."
                        if _fold(req.get("nature")) == "team"
                        else "A resposta altera a pontuação estimada deste concurso."
                    )
                )

            threshold = required.get("threshold")
            if threshold is not None:
                question["required"]["thresholds"] = [threshold]

            grouped[reuse_key] = question
            order.append(reuse_key)
            continue

        question = grouped[reuse_key]

        req_id = req.get("id")
        ids = question.setdefault("requirement_ids", [])
        if req_id and req_id not in ids:
            ids.append(req_id)

        question.setdefault("contexts", []).append(
            {
                "factor_code": req.get("factor_code"),
                "subfactor_code": req.get("subfactor_code"),
                "label": req.get("label"),
                "required": required,
                "nature": req.get("nature"),
                "stage": req.get("stage"),
            }
        )

        if strict:
            question["impact_weight_percent"] = max(
                float(question.get("impact_weight_percent") or 0),
                _requirement_weight(req, hierarchy_data),
            )

        threshold = required.get("threshold")
        if threshold is not None:
            thresholds = question.setdefault("required", {}).setdefault(
                "thresholds", []
            )
            if threshold not in thresholds:
                thresholds.append(threshold)

        existing_followups = (
            question.get("followups")
            if isinstance(question.get("followups"), list)
            else []
        )
        incoming_followups = (
            source_question.get("followups")
            if isinstance(source_question.get("followups"), list)
            else []
        )
        seen = {
            (
                _clean(item.get("type")),
                _clean(item.get("metric")),
                _clean(item.get("label")),
            )
            for item in existing_followups
            if isinstance(item, dict)
        }
        for item in incoming_followups:
            if not isinstance(item, dict):
                continue
            signature = (
                _clean(item.get("type")),
                _clean(item.get("metric")),
                _clean(item.get("label")),
            )
            if signature not in seen:
                existing_followups.append(item)
                seen.add(signature)
        question["followups"] = existing_followups

    for question in grouped.values():
        required = question.get("required") or {}
        thresholds = required.get("thresholds")
        if isinstance(thresholds, list):
            numeric: list[float] = []
            for value in thresholds:
                number = _float(value)
                if number is not None:
                    numeric.append(number)
            if numeric:
                required["thresholds"] = sorted(set(numeric))
                # Compatibilidade com o frontend/API V17.2:
                # `threshold` continua a existir, mas os patamares completos
                # ficam preservados em `thresholds`.
                required["threshold"] = max(numeric)

        if strict:
            contexts = (
                question.get("contexts")
                if isinstance(question.get("contexts"), list)
                else []
            )
            first_context = (
                contexts[0]
                if contexts and isinstance(contexts[0], dict)
                else {}
            )
            target = (
                question.get("profile_target")
                if isinstance(question.get("profile_target"), dict)
                else {}
            )
            question["text"] = _neutral_question_text(
                label=_clean(first_context.get("label")),
                metric=_clean(required.get("metric")),
                scope=_clean(target.get("scope")),
                fallback=_clean(question.get("text")),
                threshold=required.get("threshold"),
                unit=_clean(required.get("unit")),
            )

    return [grouped[key] for key in order]

def _fact_mapping(facts: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if isinstance(facts, dict):
        for key, value in facts.items():
            if not isinstance(value, dict):
                continue
            reuse_key = _clean(value.get("reuse_key") or key)
            if reuse_key:
                result[reuse_key] = value
        return result

    if isinstance(facts, list):
        for value in facts:
            if not isinstance(value, dict):
                continue
            reuse_key = _clean(value.get("reuse_key"))
            if reuse_key:
                result[reuse_key] = value
    return result


def _fact_result(
    requirement: dict[str, Any],
    fact: dict[str, Any],
) -> dict[str, Any]:
    required = requirement.get("required") or {}
    answer = _fold(fact.get("answer"))
    actual = _float(fact.get("numeric_value"))
    threshold = _float(required.get("threshold"))
    operator = _clean(required.get("operator"))

    status = "pending"
    label = "Por confirmar"

    if actual is not None and threshold is not None and operator != "actual":
        if operator == ">=":
            status = "met" if actual >= threshold else "not_met"
        elif operator == "<=":
            status = "met" if actual <= threshold else "not_met"
        elif operator == ">":
            status = "met" if actual > threshold else "not_met"
        elif operator == "<":
            status = "met" if actual < threshold else "not_met"
        elif operator in {"=", "=="}:
            status = "met" if actual == threshold else "not_met"

        if status == "met":
            label = "Cumpre"
        elif status == "not_met":
            label = "Não cumpre"

    if status == "pending":
        if answer in {"yes", "sim", "true", "1"}:
            status, label = "met", "Cumpre"
        elif answer in {"no", "nao", "não", "false", "0"}:
            if actual is not None and operator == "actual":
                if actual > 0:
                    status, label = "partial", "Cumpre parcialmente / pontuação a calcular"
                else:
                    status, label = "not_met", "Não demonstrado"
            else:
                status, label = "not_met", "Não demonstrado"

    return {
        "status": status,
        "label": label,
        "estimated_score": (requirement.get("result") or {}).get("estimated_score"),
    }


def _fact_summary(fact: dict[str, Any]) -> str:
    parts: list[str] = []
    person = _clean(fact.get("person"))
    project = _clean(fact.get("project"))
    numeric = fact.get("numeric_value")
    unit = _clean(fact.get("unit"))
    answer = _fold(fact.get("answer"))

    if person:
        parts.append(person)
    if project:
        parts.append(project)
    if numeric not in (None, ""):
        parts.append(f"{numeric}{(' ' + unit) if unit else ''}")
    if not parts and answer:
        parts.append("Sim" if answer in {"yes", "sim", "true", "1"} else "Não")
    return " · ".join(parts) or "Dado confirmado pelo utilizador."


def apply_profile_facts_to_canonical(
    ficha: dict[str, Any],
    facts: Any,
) -> dict[str, Any]:
    canonical = ficha.get("analysis_canonical")
    if not isinstance(canonical, dict):
        raise ValueError("A análise ainda não tem analysis_canonical.")

    requirements = canonical.get("requirements")
    if not isinstance(requirements, list):
        requirements = []

    by_key = _fact_mapping(facts)

    for req in requirements:
        if not isinstance(req, dict) or not req.get("profile_dependent"):
            continue
        reuse_key = _question_reuse_key(req)
        fact = by_key.get(reuse_key)
        if not fact:
            continue

        req["profile"] = {
            "status": "confirmed",
            "summary": _fact_summary(fact),
            "evidence": [],
            "reuse_key": reuse_key,
            "source": _clean(fact.get("source")) or "company_cv",
        }
        req["result"] = _fact_result(req, fact)

    hierarchy = canonical.get("criteria")
    if not isinstance(hierarchy, dict):
        hierarchy = {"factors": []}
        canonical["criteria"] = hierarchy

    _attach_requirements(hierarchy, requirements)
    for requirement in requirements:
        if isinstance(requirement, dict):
            requirement["impact_weight_percent"] = _requirement_weight(
                requirement,
                hierarchy,
            )
    canonical["questions"] = _build_deduplicated_questions(requirements, hierarchy)
    decision = _decision(ficha, requirements, hierarchy)

    failed_eligibility = [
        req
        for req in requirements
        if isinstance(req, dict)
        and req.get("nature") == "eligibility"
        and (req.get("result") or {}).get("status") == "not_met"
    ]
    if failed_eligibility:
        decision["eligibility"] = "Não cumpre"
        decision["risk"] = "Alto"
        decision["classification"] = "Não elegível"
        decision["explanation"] = (
            f"{len(failed_eligibility)} requisito(s) eliminatório(s) "
            "não são cumpridos com os dados atuais do CV."
        )

    canonical["decision"] = decision
    canonical["requirements"] = requirements
    canonical["profile_recalculated_at"] = datetime.now(timezone.utc).isoformat()
    ficha["analysis_canonical"] = canonical
    return canonical
