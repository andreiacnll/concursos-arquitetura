from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field


class CompatibilityResult(BaseModel):
    score: int | None = None
    confidence: str = "Baixa"
    confidence_reasons: list[str] = Field(default_factory=list)
    compatibility_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    matched_projects: list[dict[str, Any]] = Field(default_factory=list)
    matched_services: list[str] = Field(default_factory=list)
    matched_competences: list[str] = Field(default_factory=list)
    matched_specializations: list[str] = Field(default_factory=list)
    strengths: list[dict[str, Any]] = Field(default_factory=list)
    weaknesses: list[dict[str, Any]] = Field(default_factory=list)
    strategic_fit: dict[str, Any] = Field(default_factory=dict)
    score_explanation: dict[str, Any] = Field(default_factory=dict)
    recommendation: dict[str, Any] = Field(default_factory=dict)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    positive_factors: list[dict[str, Any]] = Field(default_factory=list)
    negative_factors: list[dict[str, Any]] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    experience_summary: list[dict[str, Any]] = Field(default_factory=list)


TYPOLOGY_ALIASES: dict[str, tuple[str, ...]] = {
    "Educacao": (
        "educacao",
        "escola",
        "escolar",
        "school",
        "campus",
        "secondary school",
        "primary school",
        "university",
    ),
    "Saude": (
        "saude",
        "hospital",
        "clinic",
        "health",
        "centro de saude",
    ),
    "Habitacao": (
        "habitacao",
        "housing",
        "residential",
        "moradia",
        "apartamento",
    ),
    "Mercados": (
        "mercado",
        "market",
        "municipal market",
    ),
    "Mobiliario": (
        "mobiliario",
        "furniture",
        "chair",
        "cadeira",
    ),
    "Escritorios": (
        "escritorio",
        "office",
        "office building",
        "workplace",
    ),
    "Industria": (
        "industria",
        "industrial",
        "factory",
        "warehousing",
    ),
    "Paisagismo": (
        "paisagismo",
        "landscape",
        "jardim",
    ),
    "Espaco Publico": (
        "espaco publico",
        "public space",
        "square",
        "plaza",
    ),
    "Urbanismo": (
        "urbanismo",
        "urban planning",
        "planeamento urbano",
        "urban design",
    ),
    "Comercio": (
        "comercio",
        "retail",
        "shop",
        "store",
    ),
    "Turismo": (
        "turismo",
        "hotel",
        "hospitality",
        "lodging",
    ),
    "Cultura": (
        "cultura",
        "museum",
        "theatre",
        "biblioteca",
        "auditorio",
    ),
    "Desporto": (
        "desporto",
        "sport",
        "stadium",
        "pavilhao",
    ),
    "Infraestruturas": (
        "infraestrutura",
        "infrastructure",
        "roads",
        "utilities",
    ),
    "Reabilitacao": (
        "reabilitacao",
        "requalificacao",
        "rehabilitation",
        "refurbishment",
    ),
}

SERVICE_ALIASES: dict[str, tuple[str, ...]] = {
    "Arquitetura": (
        "arquitetura",
        "architecture",
        "projecto de arquitetura",
        "projeto de arquitetura",
        "concecao",
        "concepcao",
    ),
    "Coordenacao": (
        "coordenacao",
        "coordination",
        "coordenacao tecnica",
        "coordenacao de projeto",
    ),
    "Fiscalizacao": (
        "fiscalizacao",
        "supervisao",
        "inspection",
    ),
    "BIM": (
        "bim",
        "building information modeling",
        "building information management",
        "modelacao da informacao",
    ),
    "Planeamento": (
        "planeamento",
        "planning",
        "urban planning",
        "planeamento urbano",
    ),
    "Reabilitacao": (
        "reabilitacao",
        "requalificacao",
        "rehabilitation",
        "refurbishment",
    ),
    "Paisagismo": (
        "paisagismo",
        "landscape",
    ),
    "Especialidades": (
        "especialidades",
        "engineering",
        "structures",
        "instalacoes",
    ),
    "Gestao de Projeto": (
        "gestao de projeto",
        "project management",
    ),
    "Estudo Previo": (
        "estudo previo",
        "preliminary study",
    ),
}

TEAM_CONCEPTS = tuple(
    sorted(
        {
            "Arquitetura",
            "Coordenacao",
            "Fiscalizacao",
            "BIM",
            "Planeamento",
            "Reabilitacao",
            "Paisagismo",
            "Especialidades",
            "Gestao de Projeto",
            "Estudo Previo",
        }
    )
)

FIELD_MAX = {
    "experience": 35,
    "team": 20,
    "services": 15,
    "specializations": 10,
    "criteria": 10,
    "price": 5,
    "location": 5,
}


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return dict(value)
    return {}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _norm(value: Any) -> str:
    text = _clean(value).casefold()
    return text


def _tokenize(value: Any) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    parts = [part.strip() for part in text.replace("/", " ").split()]
    return [part for part in parts if part]


def _unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _clean(value)
        if not text:
            continue
        key = _norm(text)
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[Any] = []
        for item in value:
            if isinstance(item, dict):
                items.extend(item.values())
            else:
                items.append(item)
        return _unique(items)
    if isinstance(value, dict):
        items: list[Any] = []
        for sub in value.values():
            if isinstance(sub, list):
                items.extend(sub)
            elif sub not in (None, ""):
                items.append(sub)
        return _unique(items)
    text = _clean(value)
    return [text] if text else []


def _company_profile(company_context: dict[str, Any]) -> dict[str, Any]:
    company = company_context.get("company") or {}
    if isinstance(company, dict) and "profile" in company:
        profile = company.get("profile") or {}
        return profile if isinstance(profile, dict) else {}
    return company if isinstance(company, dict) else {}


def _competition_source(competition_data: dict[str, Any]) -> dict[str, Any]:
    source_data = competition_data.get("source_data")
    return source_data if isinstance(source_data, dict) else {}


def _catalog_match(value: Any, catalog: dict[str, tuple[str, ...]]) -> str:
    text = _norm(value)
    if not text:
        return ""
    for canonical, aliases in catalog.items():
        for alias in aliases:
            if _norm(alias) in text or text in _norm(alias):
                return canonical
    return _clean(value)


def _catalog_matches(
    values: list[str],
    catalog: dict[str, tuple[str, ...]],
) -> list[str]:
    return _unique([_catalog_match(value, catalog) for value in values])


def _extract_competition_blocks(
    competition_data: dict[str, Any],
) -> dict[str, list[str]]:
    source = _competition_source(competition_data)
    typology_sources = _list(competition_data.get("typologies"))
    typology_sources.extend(_list(source.get("typologies")))
    typology_sources.extend(_list(source.get("programa")))
    typology_sources.extend(_list(source.get("programa_funcional")))
    typology_sources.extend(_list(source.get("especialidades")))
    typology_sources.extend(_list(source.get("entregaveis")))

    requirement_sources = _list(competition_data.get("requirements"))
    requirement_sources.extend(_list(competition_data.get("competences")))
    requirement_sources.extend(_list(competition_data.get("specializations")))
    requirement_sources.extend(_list(competition_data.get("constraints")))
    requirement_sources.extend(_list(source.get("requisitos")))
    requirement_sources.extend(_list(source.get("documentos")))
    requirement_sources.extend(_list(source.get("drawings")))
    requirement_sources.extend(_list(source.get("financial_conditions")))
    requirement_sources.extend(_list(source.get("technical_constraints")))
    requirement_sources.extend(_list(source.get("exclusion_risks")))
    requirement_sources.extend(_list(source.get("drawing_rules")))
    requirement_sources.extend(_list(source.get("submission_checklist")))

    team_sources = _list(source.get("required_team"))
    team_sources.extend(_list(source.get("equipa")))
    team_sources.extend(_list(source.get("team")))

    service_sources = _list(source.get("award_strategy"))
    service_sources.extend(_list(source.get("technical_constraints")))
    service_sources.extend(_list(source.get("phases_and_deliverables")))
    service_sources.extend(_list(source.get("submission_checklist")))

    price_sources = _list(source.get("financial_conditions"))
    location_sources = _list([competition_data.get("location"), source.get("location")])

    return {
        "typologies": _catalog_matches(typology_sources, TYPOLOGY_ALIASES),
        "requirements": _unique(requirement_sources),
        "team": _unique(team_sources),
        "services": _unique(service_sources),
        "price": _unique(price_sources),
        "location": _unique(location_sources),
        "alerts": _list(source.get("document_alerts")) + _list(competition_data.get("document_alerts")),
    }


def _extract_company_projects(
    company_context: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    profile = _company_profile(company_context)
    projects = []
    counts: dict[str, int] = defaultdict(int)
    summary = []

    profile_projects = profile.get("project_experience") or []
    summary_source = company_context.get("project_experience_summary") or []
    counts_source = company_context.get("project_counts_by_typology") or {}

    for index, project in enumerate(profile_projects):
        if not isinstance(project, dict):
            project = project.model_dump() if hasattr(project, "model_dump") else {}
        typology = _catalog_match(project.get("typology"), TYPOLOGY_ALIASES)
        name = _clean(project.get("name"))
        location = _clean(project.get("location"))
        skills = _unique(_list(project.get("skills_demonstrated")))
        if typology and typology != _clean(project.get("typology")):
            counts[_norm(typology)] += 1
        elif typology:
            counts[_norm(typology)] += 1
        if typology or name:
            projects.append(
                {
                    "name": name or "Not Found",
                    "typology": typology or "Not Found",
                    "normalized_typology": typology or "Not Found",
                    "location": location or "Not Found",
                    "skills_demonstrated": skills,
                    "source": "company_profile",
                    "index": index,
                }
            )

    for item in summary_source:
        if not isinstance(item, dict):
            continue
        typology = _catalog_match(item.get("typology"), TYPOLOGY_ALIASES)
        count = int(item.get("project_count") or 0)
        if typology:
            counts[_norm(typology)] = max(counts[_norm(typology)], count)
        summary.append(
            {
                "typology": typology or _clean(item.get("typology")) or "Not Found",
                "project_count": count,
                "experience_level": _clean(item.get("experience_level")) or "Not Found",
                "experience_level_score": int(item.get("experience_level_score") or 0),
                "origins": _unique(_list(item.get("origins"))),
                "confidence": float(item.get("confidence") or 0.0),
                "projects": [p for p in _list(item.get("projects"))][:5],
            }
        )

    for typology, count in counts_source.items():
        text = _catalog_match(typology, TYPOLOGY_ALIASES)
        if text:
            counts[_norm(text)] = max(counts[_norm(text)], int(count or 0))

    return projects, dict(counts), summary


def _build_project_summary(
    project_counts: dict[str, int],
    project_items: list[dict[str, Any]],
    company_context: dict[str, Any],
    competition_typologies: list[str],
) -> list[dict[str, Any]]:
    profile = _company_profile(company_context)
    competition_norms = {_norm(item) for item in competition_typologies if _clean(item)}
    explicit = company_context.get("project_experience_summary") or []
    if explicit:
        # Keep explicit summaries, but normalize typologies for the matcher.
        result: list[dict[str, Any]] = []
        for item in explicit:
            if not isinstance(item, dict):
                continue
            typology = _catalog_match(item.get("typology"), TYPOLOGY_ALIASES)
            count = int(item.get("project_count") or 0)
            level = _clean(item.get("experience_level")) or "Not Found"
            level_score = int(item.get("experience_level_score") or 0)
            projects = [
                p
                for p in item.get("projects") or []
                if isinstance(p, dict)
            ]
            if typology:
                result.append(
                    {
                        "typology": typology,
                        "project_count": count,
                        "experience_level": level,
                        "experience_level_score": level_score,
                        "origins": _unique(_list(item.get("origins"))),
                        "confidence": float(item.get("confidence") or 0.0),
                        "projects": projects[:5],
                    }
                )
        if result:
            if competition_norms:
                result = [
                    item
                    for item in result
                    if _norm(item.get("typology")) in competition_norms
                ]
                if not result:
                    return []
            return sorted(
                result,
                key=lambda item: (
                    item.get("project_count") or 0,
                    item.get("experience_level_score") or 0,
                ),
                reverse=True,
            )

    grouped: dict[str, dict[str, Any]] = {}
    for project in project_items:
        typology = _clean(project.get("normalized_typology") or project.get("typology"))
        if not typology or typology == "Not Found":
            continue
        key = _norm(typology)
        grouped.setdefault(
            key,
            {
                "typology": typology,
                "project_count": 0,
                "experience_level": "Not Found",
                "experience_level_score": 0,
                "origins": ["company_profile"],
                "confidence": 0.55,
                "projects": [],
            },
        )
        grouped[key]["project_count"] += 1
        if len(grouped[key]["projects"]) < 5:
            grouped[key]["projects"].append(
                {
                    "name": project.get("name") or "Not Found",
                    "location": project.get("location") or "Not Found",
                    "source": project.get("source") or "company_profile",
                    "skills_demonstrated": list(project.get("skills_demonstrated") or []),
                }
            )

    for key, item in grouped.items():
        count = int(item["project_count"])
        if count >= 20:
            item["experience_level"] = "Especialista"
            item["experience_level_score"] = 5
        elif count >= 10:
            item["experience_level"] = "Forte"
            item["experience_level_score"] = 4
        elif count >= 4:
            item["experience_level"] = "Consistente"
            item["experience_level_score"] = 3
        elif count >= 1:
            item["experience_level"] = "Pontual"
            item["experience_level_score"] = 2

    result = list(grouped.values())
    if not result and project_counts:
        for typology, count in project_counts.items():
            if count <= 0:
                continue
            result.append(
                {
                    "typology": typology,
                    "project_count": count,
                    "experience_level": "Not Found",
                    "experience_level_score": 0,
                    "origins": ["project_counts_by_typology"],
                    "confidence": 0.5,
                    "projects": [],
                }
            )

    competition_norms = {_norm(item) for item in competition_typologies}
    result = [
        item
        for item in result
        if _norm(item["typology"]) in competition_norms or not competition_norms
    ]
    return sorted(
        result,
        key=lambda item: (
            item.get("project_count") or 0,
            item.get("experience_level_score") or 0,
        ),
        reverse=True,
    )


def _concept_set(values: list[str], catalog: dict[str, tuple[str, ...]]) -> set[str]:
    return {item for item in _catalog_matches(values, catalog) if item}


def _service_values(profile: dict[str, Any]) -> list[str]:
    values = _list(profile.get("services"))
    values.extend(_list(profile.get("competences")))
    values.extend(_list(profile.get("specializations")))
    return _unique(values)


def _team_values(company_context: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    values = _service_values(profile)
    team = company_context.get("team") or {}
    if isinstance(team, dict):
        values.extend(_list(team.get("competences")))
        values.extend(_list(team.get("specializations")))
        for member in team.get("members") or []:
            if not isinstance(member, dict):
                continue
            member_profile = member.get("profile") or {}
            if not isinstance(member_profile, dict):
                continue
            comp = member_profile.get("competences") or {}
            if isinstance(comp, dict):
                values.extend(_list(comp.get("technical")))
                values.extend(_list(comp.get("software")))
                values.extend(_list(comp.get("methodologies")))
    return _unique(values)


def _company_location(profile: dict[str, Any]) -> str:
    identity = profile.get("identity") or {}
    if isinstance(identity, dict):
        return _clean(identity.get("location"))
    return ""


def _money(value: Any) -> float | None:
    text = _clean(value)
    if not text:
        return None
    raw = ""
    for token in text.replace("€", " ").replace("EUR", " ").split():
        if any(char.isdigit() for char in token):
            raw = token
            break
    if not raw:
        return None
    raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _competition_money(competition_data: dict[str, Any]) -> float | None:
    source = _competition_source(competition_data)
    candidates = [
        source.get("base_price"),
        source.get("financial_conditions"),
        source.get("economia"),
        competition_data.get("base_price"),
        competition_data.get("price"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key in (
                "value_procedimento",
                "value_estimado_obra",
                "base_price",
                "price",
            ):
                money = _money(candidate.get(key))
                if money is not None:
                    return money
        else:
            money = _money(candidate)
            if money is not None:
                return money
    return None


def _location_fit(company_location: str, preferred_locations: list[str], competition_location: str) -> tuple[bool, str]:
    if not competition_location:
        return False, "Not Found"
    if not company_location and not preferred_locations:
        return False, "Not Found"
    company_norm = _norm(company_location)
    competition_norm = _norm(competition_location)
    if company_norm and (company_norm in competition_norm or competition_norm in company_norm):
        return True, competition_location
    for preferred in preferred_locations:
        pref_norm = _norm(preferred)
        if pref_norm and (pref_norm in competition_norm or competition_norm in pref_norm):
            return True, competition_location
    return False, competition_location


def _requirement_rows(
    competition_requirements: list[str],
    company_values: list[str],
    company_sources: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    company_concepts = _concept_set(company_values, SERVICE_ALIASES)
    rows: list[dict[str, Any]] = []
    for requirement in competition_requirements:
        requirement_concept = _catalog_match(requirement, SERVICE_ALIASES)
        if requirement_concept in company_concepts:
            rows.append(
                {
                    "requirement": requirement,
                    "matched_with": requirement_concept,
                    "status": "encontrado",
                    "match_status": "confirmed",
                    "evidence": [
                        {
                            "source": "company_profile",
                            "value": requirement_concept,
                            "requirement": requirement,
                        }
                    ],
                }
            )
            continue
        if requirement_concept != _clean(requirement) and company_concepts:
            rows.append(
                {
                    "requirement": requirement,
                    "matched_with": requirement_concept,
                    "status": "parcial",
                    "match_status": "partial",
                    "evidence": [
                        {
                            "source": "company_profile",
                            "value": requirement_concept,
                            "requirement": requirement,
                        }
                    ],
                }
            )
            continue
        rows.append(
            {
                "requirement": requirement,
                "matched_with": "Not Found",
                "status": "missing",
                "match_status": "missing",
                "evidence": company_sources or [],
            }
        )
    return rows


def _score_from_ratio(
    value: int,
    maximum: int,
    ratio: float,
    *,
    label: str,
    justification: str,
    evidence: list[dict[str, Any]] | None = None,
    status: str = "confirmed",
) -> dict[str, Any]:
    return {
        "name": label,
        "value": max(0, min(maximum, int(round(value)))),
        "maximum": maximum,
        "justification": justification,
        "evidence": list(evidence or []),
        "status": status,
        "ratio": max(0.0, min(1.0, float(ratio))),
    }


def _confidence(result: CompatibilityResult) -> tuple[str, list[str]]:
    signals = 0
    if result.matched_projects:
        signals += 2
    signals += len(result.matched_services)
    signals += len(result.matched_competences)
    signals += len(result.matched_specializations)
    signals += len(
        [
            item
            for item in result.requirements
            if item.get("status") in {"confirmed", "encontrado"}
            or item.get("match_status") == "confirmed"
        ]
    )
    signals += len(result.strengths)
    missing = len(result.missing_information)

    reasons = [
        f"{len(result.matched_projects)} projetos semelhantes localizados.",
        f"{len(result.requirements)} requisitos avaliados.",
    ]
    if missing:
        reasons.append(f"{missing} campos ainda estao em falta.")

    score = signals * 8 - missing * 4
    if score >= 50:
        return "Muito elevada", reasons
    if score >= 35:
        return "Elevada", reasons
    if score >= 18:
        return "Media", reasons
    return "Baixa", reasons


def _final_recommendation(result: CompatibilityResult) -> dict[str, Any]:
    if result.score is None:
        decision = "dados insuficientes"
    elif result.score >= 75 and result.confidence in {"Elevada", "Muito elevada"}:
        decision = "avancar"
    elif result.score >= 55 or result.strengths:
        decision = "avaliar"
    elif result.missing_information:
        decision = "dados insuficientes"
    else:
        decision = "nao prioritario"

    explanations = {
        "avancar": "A empresa mostra compatibilidade forte e evidencias consistentes para avancar.",
        "avaliar": "Ha compatibilidade relevante, mas convem validar lacunas e o peso da estrategia.",
        "nao prioritario": "A evidencia disponivel nao mostra alinhamento suficiente com o perfil empresarial.",
        "dados insuficientes": "Nao ha informacao suficiente para produzir uma recomendacao segura.",
    }
    return {
        "decision": decision,
        "confidence": result.confidence,
        "explanation": explanations[decision],
        "main_risks": result.weaknesses[:3],
        "missing_information": result.missing_information,
    }


def _build_breakdown(
    *,
    experience_value: int,
    team_value: int,
    services_value: int,
    specializations_value: int,
    criteria_value: int,
    price_value: int,
    location_value: int,
) -> list[dict[str, Any]]:
    return [
        _score_from_ratio(
            experience_value,
            FIELD_MAX["experience"],
            experience_value / FIELD_MAX["experience"] if FIELD_MAX["experience"] else 0,
            label="Experiencia",
            justification="Peso principal atribuido ao historial em tipologias semelhantes.",
        ),
        _score_from_ratio(
            team_value,
            FIELD_MAX["team"],
            team_value / FIELD_MAX["team"] if FIELD_MAX["team"] else 0,
            label="Equipa",
            justification="Cobertura da equipa exigida no concurso.",
        ),
        _score_from_ratio(
            services_value,
            FIELD_MAX["services"],
            services_value / FIELD_MAX["services"] if FIELD_MAX["services"] else 0,
            label="Servicos",
            justification="Servicos da empresa alinhados com o objeto do concurso.",
        ),
        _score_from_ratio(
            specializations_value,
            FIELD_MAX["specializations"],
            specializations_value / FIELD_MAX["specializations"] if FIELD_MAX["specializations"] else 0,
            label="Especializacoes",
            justification="Especializacoes e capacidades tecnicas relevantes para o concurso.",
        ),
        _score_from_ratio(
            criteria_value,
            FIELD_MAX["criteria"],
            criteria_value / FIELD_MAX["criteria"] if FIELD_MAX["criteria"] else 0,
            label="Criterios",
            justification="Adequacao da empresa ao peso dos criterios de adjudicacao.",
        ),
        _score_from_ratio(
            price_value,
            FIELD_MAX["price"],
            price_value / FIELD_MAX["price"] if FIELD_MAX["price"] else 0,
            label="Preco",
            justification="Adequacao da escala economica ao perfil habitual da empresa.",
        ),
        _score_from_ratio(
            location_value,
            FIELD_MAX["location"],
            location_value / FIELD_MAX["location"] if FIELD_MAX["location"] else 0,
            label="Localizacao",
            justification="Compatibilidade geografica e preferencia territorial.",
        ),
    ]


def analyze_compatibility(company_context, competition_context) -> CompatibilityResult:
    company_data = _as_dict(company_context)
    competition_data = _as_dict(competition_context)
    profile = _company_profile(company_data)
    competition_blocks = _extract_competition_blocks(competition_data)

    result = CompatibilityResult()

    company_projects, project_counts_by_typology, project_summary = _extract_company_projects(company_data)
    competition_typologies = competition_blocks["typologies"]
    project_summary = _build_project_summary(
        project_counts_by_typology,
        company_projects,
        company_data,
        competition_typologies,
    )

    company_services = _service_values(profile)
    company_concepts = _concept_set(company_services, SERVICE_ALIASES)
    company_competences = _unique(_list(profile.get("competences")))
    company_competence_concepts = _concept_set(company_competences, SERVICE_ALIASES)
    company_specializations = _unique(_list(profile.get("specializations")))
    company_specialization_concepts = _concept_set(company_specializations, TYPOLOGY_ALIASES)
    company_team_values = _team_values(company_data, profile)
    company_location = _company_location(profile)
    preferred_locations = _list((profile.get("preferences") or {}).get("locations"))
    preferred_typologies = _catalog_matches(
        _list((profile.get("preferences") or {}).get("typologies")),
        TYPOLOGY_ALIASES,
    )
    strategy = profile.get("strategy") or {}
    strategy_fit = {
        "priority_areas": _list(strategy.get("priority_areas")),
        "secondary_areas": _list(strategy.get("secondary_areas")),
        "avoid_areas": _list(strategy.get("avoid_areas")),
        "future_goals": _list(strategy.get("future_goals")),
    }

    competition_location = _clean(competition_data.get("location"))
    competition_money = _competition_money(competition_data)
    competition_services = _concept_set(competition_blocks["services"] + competition_blocks["requirements"], SERVICE_ALIASES)
    competition_team = _concept_set(competition_blocks["team"] + competition_blocks["requirements"], SERVICE_ALIASES)
    competition_specializations = _catalog_matches(
        competition_blocks["typologies"] + competition_blocks["requirements"] + competition_blocks["services"],
        TYPOLOGY_ALIASES,
    )

    relevant_typologies = [
        item
        for item in project_summary
        if _norm(item.get("typology")) in {_norm(t) for t in competition_typologies}
        or _norm(item.get("typology")) in {_norm(t) for t in competition_specializations}
    ]
    if not relevant_typologies and project_summary and competition_typologies:
        # Keep nearby categories such as "Escola Secundaria" -> "Educacao".
        relevant_typologies = [
            item
            for item in project_summary
            if _catalog_match(item.get("typology"), TYPOLOGY_ALIASES) in competition_typologies
        ]

    matched_projects: list[dict[str, Any]] = []
    for item in relevant_typologies:
        for project in item.get("projects") or []:
            if not isinstance(project, dict):
                continue
            matched_projects.append(
                {
                    "name": project.get("name") or "Not Found",
                    "typology": item.get("typology") or "Not Found",
                    "normalized_typology": item.get("typology") or "Not Found",
                    "location": project.get("location") or "Not Found",
                    "source": project.get("source") or "company_profile",
                    "confidence": item.get("confidence") or 0.5,
                }
            )
    matched_projects = matched_projects[:8]

    experience_value = 0
    experience_evidence: list[dict[str, Any]] = []
    if relevant_typologies:
        strongest = max(
            relevant_typologies,
            key=lambda item: int(item.get("project_count") or 0),
        )
        count = int(strongest.get("project_count") or 0)
        level_score = int(strongest.get("experience_level_score") or 0)
        experience_value = min(
            FIELD_MAX["experience"],
            min(24, count) + min(11, level_score * 2),
        )
        experience_evidence = matched_projects[:5]
        result.experience_summary = relevant_typologies
    elif project_summary:
        count = sum(int(item.get("project_count") or 0) for item in project_summary)
        level_score = max(int(item.get("experience_level_score") or 0) for item in project_summary)
        experience_value = min(
            FIELD_MAX["experience"],
            min(20, count // 2) + min(11, level_score * 2),
        )
        experience_evidence = [
            {
                "name": item.get("typology") or "Not Found",
                "project_count": item.get("project_count") or 0,
                "source": "project_experience_summary",
            }
            for item in project_summary[:5]
        ]
        result.experience_summary = project_summary
    else:
        result.experience_summary = []

    team_requirements = competition_blocks["team"]
    team_rows: list[dict[str, Any]] = []
    if team_requirements:
        team_concepts = _concept_set(company_team_values, SERVICE_ALIASES)
        for requirement in team_requirements:
            requirement_concept = _catalog_match(requirement, SERVICE_ALIASES)
            if requirement_concept in team_concepts:
                status = "confirmed"
                matched_with = requirement_concept
                ratio = 1.0
            elif team_concepts:
                status = "partial"
                matched_with = requirement_concept if requirement_concept else "Not Found"
                ratio = 0.5
            else:
                status = "missing"
                matched_with = "Not Found"
                ratio = 0.0
            team_rows.append(
                {
                    "requirement": requirement,
                    "matched_with": matched_with,
                    "status": status,
                    "evidence": [
                        {
                            "source": "company_profile.team",
                            "value": matched_with,
                            "requirement": requirement,
                        }
                    ] if matched_with != "Not Found" else [],
                }
            )
        confirmed = sum(1 for row in team_rows if row["status"] == "confirmed")
        partial = sum(1 for row in team_rows if row["status"] == "partial")
        total = len(team_rows)
        team_value = min(
            FIELD_MAX["team"],
            round((confirmed * 1.0 + partial * 0.5) * (FIELD_MAX["team"] / max(total, 1))),
        )
    else:
        team_value = 0
        team_rows = []

    service_matches = sorted(company_concepts & competition_services)
    if not service_matches and company_concepts:
        service_matches = sorted(company_concepts & _concept_set(competition_blocks["typologies"], SERVICE_ALIASES))
    matched_services = _unique(service_matches)
    services_value = min(
        FIELD_MAX["services"],
        round(
            len(matched_services)
            * (FIELD_MAX["services"] / max(len(competition_services or matched_services or [1]), 1))
            * 1.3
        ),
    ) if matched_services else 0

    matched_competences = _unique(sorted(company_competence_concepts & competition_team))
    competence_value = 0
    if matched_competences:
        competence_value = min(
            FIELD_MAX["specializations"],
            round(len(matched_competences) * 2),
        )

    matched_specializations = _unique(sorted(company_specialization_concepts & set(competition_specializations)))
    specializations_value = 0
    if matched_specializations:
        specializations_value = min(
            FIELD_MAX["specializations"],
            round(len(matched_specializations) * 2.5),
        )

    award_strategy = competition_data.get("award_strategy") or {}
    criteria_weights = _list(award_strategy.get("criteria"))
    if not criteria_weights:
        criteria_weights = _list(_competition_source(competition_data).get("award_strategy"))
    quality_bias = 0.5
    for item in criteria_weights:
        if "%" in item and ("qualidade" in _norm(item) or "tecnica" in _norm(item)):
            quality_bias = 0.7
            break
    criteria_value = min(
        FIELD_MAX["criteria"],
        round(
            FIELD_MAX["criteria"]
            * quality_bias
            * (
                0.35
                + (experience_value / FIELD_MAX["experience"]) * 0.35
                + (team_value / FIELD_MAX["team"]) * 0.3
            )
        ),
    )

    price_value = 0
    competition_scale = _competition_money(competition_data)
    project_scale = _clean((profile.get("preferences") or {}).get("project_scale"))
    if competition_scale is not None:
        if project_scale:
            scale_norm = _norm(project_scale)
            if any(token in scale_norm for token in ("grande", "medium", "media", "pequena", "small")):
                price_value = 3
        elif competition_scale <= 250000:
            price_value = 3
        else:
            price_value = 2
        if competition_scale >= 500000 and experience_value >= 20:
            price_value = FIELD_MAX["price"]

    location_value = 0
    location_fit, location_value_text = _location_fit(company_location, preferred_locations, competition_location)
    if location_fit:
        location_value = FIELD_MAX["location"]
    elif competition_location and preferred_locations:
        location_value = 3

    breakdown = _build_breakdown(
        experience_value=experience_value,
        team_value=team_value,
        services_value=services_value,
        specializations_value=max(specializations_value, competence_value),
        criteria_value=criteria_value,
        price_value=price_value,
        location_value=location_value,
    )
    score = sum(item["value"] for item in breakdown)
    score = max(0, min(100, int(score)))

    # Core compatibility fields used by the legacy presenter/router.
    if relevant_typologies:
        competition_typology_values = [item["typology"] for item in relevant_typologies[:5]]
    else:
        competition_typology_values = competition_typologies or competition_specializations

    if relevant_typologies:
        result.matches.append(
            {
                "field": "project_experience.typologies",
                "company_values": [item["typology"] for item in relevant_typologies[:5]],
                "competition_values": competition_typology_values,
                "status": "compatible",
            }
        )
    else:
        result.gaps.append(
            {
                "field": "project_experience.typologies",
                "company_values": ["Not Found"],
                "competition_values": competition_typology_values or ["Not Found"],
                "status": "no_evidence",
            }
        )

    if matched_services:
        result.matches.append(
            {
                "field": "services",
                "company_values": matched_services,
                "competition_values": sorted(competition_services),
                "status": "compatible",
            }
        )
    elif company_services:
        result.gaps.append(
            {
                "field": "services",
                "company_values": company_services[:5],
                "competition_values": sorted(competition_services) or ["Not Found"],
                "status": "no_evidence",
            }
        )

    if matched_competences:
        result.matches.append(
            {
                "field": "competences",
                "company_values": matched_competences,
                "competition_values": sorted(competition_team) or matched_competences,
                "status": "compatible",
            }
        )
    elif company_competences:
        result.gaps.append(
            {
                "field": "competences",
                "company_values": company_competences[:5],
                "competition_values": sorted(competition_team) or ["Not Found"],
                "status": "no_evidence",
            }
        )

    if matched_specializations:
        result.matches.append(
            {
                "field": "specializations",
                "company_values": matched_specializations,
                "competition_values": competition_specializations or matched_specializations,
                "status": "compatible",
            }
        )
    elif company_specializations:
        result.gaps.append(
            {
                "field": "specializations",
                "company_values": company_specializations[:5],
                "competition_values": competition_specializations or ["Not Found"],
                "status": "no_evidence",
            }
        )

    if team_rows:
        for row in team_rows:
            if row["status"] == "confirmed":
                result.matches.append(
                    {
                        "field": "required_team",
                        "company_values": [row["matched_with"]],
                        "competition_values": [row["requirement"]],
                        "status": "compatible",
                    }
                )
            else:
                result.gaps.append(
                    {
                        "field": "required_team",
                        "company_values": ["Not Found"],
                        "competition_values": [row["requirement"]],
                        "status": row["status"],
                    }
                )
    else:
        result.unknowns.append("competition.required_team")

    if location_fit:
        result.matches.append(
            {
                "field": "location",
                "company_values": [company_location or "Not Found"] + preferred_locations,
                "competition_values": [location_value_text],
                "status": "compatible",
            }
        )
    elif competition_location:
        result.gaps.append(
            {
                "field": "location",
                "company_values": [company_location or "Not Found"] + preferred_locations,
                "competition_values": [competition_location],
                "status": "outside_usual_area",
            }
        )
    else:
        result.unknowns.append("competition.location")

    result.matched_projects = matched_projects
    result.matched_services = matched_services
    result.matched_competences = matched_competences
    result.matched_specializations = matched_specializations
    result.strategic_fit = {
        "location": {
            "company": company_location or "Not Found",
            "preferred_locations": preferred_locations,
            "competition": competition_location or "Not Found",
            "status": "confirmed" if location_fit else "partial" if competition_location else "Not Found",
        },
        "scale": {
            "company": _clean(project_scale) or "Not Found",
            "competition_base_price": competition_money if competition_money is not None else "Not Found",
        },
        "strategy": strategy_fit,
        "competition_typologies": competition_typologies,
    }

    result.requirements = _requirement_rows(
        competition_blocks["requirements"][:12],
        _service_values(profile),
        company_sources=[{"source": "company_profile", "value": "Not Found"}],
    )

    result.missing_information = _unique(
        [
            item.get("field") if isinstance(item, dict) else str(item)
            for item in result.gaps
        ]
        + list(competition_blocks["alerts"] or [])
    )
    if not result.matched_projects:
        result.missing_information.append("experience.summary")
    if not result.matched_services:
        result.missing_information.append("services")
    if not result.matched_competences:
        result.missing_information.append("competences")
    if not result.matched_specializations:
        result.missing_information.append("specializations")

    result.opportunities = [
        {
            "name": "Experiencia semelhante",
            "explanation": (
                f"{item.get('project_count', 0)} projetos em {item.get('typology')}"
                if item.get("project_count")
                else "Not Found"
            ),
            "origin": "company_profile.project_experience",
            "confidence": float(item.get("confidence") or 0.0),
        }
        for item in result.experience_summary[:3]
    ]

    result.strengths = [
        {
            "name": "Experiencia",
            "value": experience_value,
            "maximum": FIELD_MAX["experience"],
            "justification": "Tipologias de projeto alinhadas com o concurso.",
            "evidence": experience_evidence,
        },
        {
            "name": "Equipa",
            "value": team_value,
            "maximum": FIELD_MAX["team"],
            "justification": "Competencias e especializacoes da equipa respondem aos requisitos.",
            "evidence": [row for row in team_rows if row["status"] == "confirmed"],
        },
    ]

    result.weaknesses = []
    if not result.matched_services:
        result.weaknesses.append(
            {
                "name": "Servicos",
                "value": 0,
                "maximum": FIELD_MAX["services"],
                "justification": "Not Found",
                "evidence": [],
            }
        )
    if not result.matched_specializations:
        result.weaknesses.append(
            {
                "name": "Especializacoes",
                "value": 0,
                "maximum": FIELD_MAX["specializations"],
                "justification": "Not Found",
                "evidence": [],
            }
        )

    result.risks = []
    if result.missing_information:
        result.risks.append(
            {
                "name": "Documentacao insuficiente",
                "value": 0,
                "maximum": 10,
                "justification": "Not Found",
                "evidence": [],
            }
        )

    result.compatibility_breakdown = breakdown
    result.score = score
    result.score_explanation = {
        "score": score,
        "label": "Muito elevada" if score >= 90 else "Elevada" if score >= 75 else "Moderada" if score >= 60 else "Baixa" if score >= 40 else "Muito baixa",
        "breakdown": breakdown,
        "dimensions": breakdown,
    }
    result.confidence, result.confidence_reasons = _confidence(result)
    result.recommendation = _final_recommendation(result)

    # Backwards-compatible aliases used across the app.
    result.positive_factors = result.strengths
    result.negative_factors = result.weaknesses
    result.evidence = [
        {
            "field": "project_experience.typologies",
            "company_values": [item.get("typology") for item in relevant_typologies[:5]],
            "competition_values": competition_typology_values,
            "source": "company.profile.project_experience -> competition.typologies",
        },
        {
            "field": "services",
            "company_values": matched_services,
            "competition_values": sorted(competition_services),
            "source": "company.profile.services -> competition.requirements",
        },
        {
            "field": "competences",
            "company_values": matched_competences,
            "competition_values": sorted(competition_team),
            "source": "company.profile.competences -> competition.required_team",
        },
    ]
    return result


def analyze_compatibility(company_context, competition_context) -> CompatibilityResult:
    from .company_matching_v2 import analyze_company_match_v2

    return analyze_company_match_v2(
        competition_context,
        company_context,
    )
