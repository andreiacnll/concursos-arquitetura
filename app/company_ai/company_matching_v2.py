from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from pydantic import BaseModel, Field

from ..architecture_intelligence.schemas import ConsolidatedCompetitionData
from .compatibility_analysis import CompatibilityResult
from .models import CompanyProfile
from .taxonomy import (
    SERVICE_TAXONOMY,
    TYPOLOGY_TAXONOMY,
    collect_concepts,
    gather_texts,
    infer_service_hints,
    normalize_concept,
)


class CompanyMatchingResult(CompatibilityResult):
    compatibility_score: int | None = None


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(value, dict):
        return dict(value)
    return {}


def _flatten(values: Any) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, list):
        return list(values)
    if isinstance(values, tuple):
        return list(values)
    return [values]


def _unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = " ".join(str(value or "").strip().split())
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _extract_company_profile(company_profile: CompanyProfile | dict[str, Any] | Any) -> dict[str, Any]:
    data = _as_dict(company_profile)
    if "company" in data and isinstance(data.get("company"), dict) and data["company"].get("profile"):
        profile = data["company"]["profile"]
        return profile if isinstance(profile, dict) else {}
    return data


def _extract_competition_data(
    competition: ConsolidatedCompetitionData | dict[str, Any] | Any,
) -> dict[str, Any]:
    data = _as_dict(competition)
    if data.get("procedure_identity") or data.get("prices") or data.get("award_strategy"):
        return data

    source = data.get("source_data") if isinstance(data.get("source_data"), dict) else {}
    if not isinstance(source, dict):
        source = {}

    ident = source.get("identificacao") if isinstance(source.get("identificacao"), dict) else {}
    programa = source.get("programa") if isinstance(source.get("programa"), dict) else {}
    programa_funcional = source.get("programa_funcional") if isinstance(source.get("programa_funcional"), dict) else {}
    localizacao = source.get("localizacao") if isinstance(source.get("localizacao"), dict) else {}
    entregaveis = source.get("entregaveis") if isinstance(source.get("entregaveis"), dict) else {}
    especialidades = source.get("especialidades") if isinstance(source.get("especialidades"), dict) else {}
    requisitos = source.get("requisitos") if isinstance(source.get("requisitos"), dict) else {}
    equipa = source.get("equipa") if isinstance(source.get("equipa"), dict) else {}
    estrategia = source.get("estrategia") if isinstance(source.get("estrategia"), dict) else {}
    decisao = source.get("decisao") if isinstance(source.get("decisao"), dict) else {}
    investimento = source.get("investimento") if isinstance(source.get("investimento"), dict) else {}
    economia = source.get("economia") if isinstance(source.get("economia"), dict) else {}
    criteros = source.get("criterios") if isinstance(source.get("criterios"), dict) else {}
    documentos = source.get("documentos") if isinstance(source.get("documentos"), dict) else {}

    procedure_identity = {
        "object": ident.get("titulo") or data.get("title") or programa.get("descricao") or "",
        "contracting_entity": ident.get("entidade") or ident.get("entidade_adjudicante") or "",
        "procedure_type": ident.get("tipo_procedimento") or data.get("procedure_type") or "",
        "cpv": ident.get("cpv") or "",
        "submission_deadline": data.get("deadline") or ident.get("prazo") or "",
        "execution_period": investimento.get("prazo_projeto") or "",
        "location": data.get("location") or localizacao.get("municipio") or localizacao.get("local") or "",
        "reference": ident.get("referencia") or ident.get("ref") or "",
    }

    prices = {
        "competition_prizes": [],
        "procedure_value": {
            "value": economy_value(economia.get("valor_procedimento")),
            "normalized_value": economy_value(economia.get("valor_procedimento")),
            "evidences": [],
            "confidence": 0.7,
            "status": "confirmed" if economy_value(economia.get("valor_procedimento")) is not None else "not_found",
        } if economy_value(economia.get("valor_procedimento")) is not None else {},
        "design_services_value": {
            "value": economy_value(economia.get("valor_servicos")),
            "normalized_value": economy_value(economia.get("valor_servicos")),
            "evidences": [],
            "confidence": 0.7,
            "status": "confirmed" if economy_value(economia.get("valor_servicos")) is not None else "not_found",
        } if economy_value(economia.get("valor_servicos")) is not None else {},
        "estimated_construction_cost": {
            "value": economy_value(economia.get("valor_estimado_obra")),
            "normalized_value": economy_value(economia.get("valor_estimado_obra")),
            "evidences": [],
            "confidence": 0.7,
            "status": "confirmed" if economy_value(economia.get("valor_estimado_obra")) is not None else "not_found",
        } if economy_value(economia.get("valor_estimado_obra")) is not None else {},
    }

    award_strategy = {
        "award_criterion": criteros.get("resumo") or decisao.get("classificacao") or "",
        "factors": _flatten(criteros.get("fatores") or []),
        "subfactors": _flatten(criteros.get("subfatores") or []),
        "price_weight": criteros.get("preco"),
        "technical_weight": criteros.get("qualidade"),
        "evaluation_model": criteros.get("modelo") or "",
        "maximum_score_requirements": [],
        "tie_break_rules": [],
        "abnormally_low_price_rule": "",
    }

    required_team = _flatten(equipa.get("competencias") or []) + _flatten(requisitos.get("obrigatorios") or [])
    technical_constraints = _flatten(requisitos.get("restricoes") or []) + _flatten(requisitos.get("riscos_participacao") or []) + _flatten(programa.get("condicionantes") or []) + _flatten(programa_funcional.get("condicionantes") or [])
    exclusion_risks = _flatten(requisitos.get("riscos_participacao") or []) + _flatten(decisao.get("riscos") or [])
    phases_and_deliverables = _flatten(entregaveis.get("principais") or [])
    document_alerts = _flatten(documentos.get("avisos") or [])

    return {
        "competition_id": data.get("competition_id") or ident.get("concurso_id"),
        "title": data.get("title") or ident.get("titulo") or "",
        "location": data.get("location") or localizacao.get("municipio") or "",
        "typologies": _flatten(data.get("typologies") or [])
        + _flatten(programa.get("tipo") or [])
        + _flatten(programa.get("usos") or [])
        + _flatten(especialidades.get("lista") or []),
        "requirements": _flatten(data.get("requirements") or [])
        + _flatten(programa.get("requisitos") or [])
        + _flatten(programa_funcional.get("requisitos") or [])
        + _flatten(requisitos.get("obrigatorios") or []),
        "competences": _flatten(data.get("competences") or []) + _flatten(equipa.get("competencias") or []),
        "specializations": _flatten(data.get("specializations") or []) + _flatten(especialidades.get("lista") or []),
        "scale": data.get("scale") or {
            "investment": {
                "value_obra": investimento.get("valor_obra") or "",
                "prazo_projeto": investimento.get("prazo_projeto") or "",
            },
            "economy": {
                "value_procedimento": economia.get("valor_procedimento") or "",
                "value_estimado_obra": economia.get("valor_estimado_obra") or "",
            },
            "decision": {
                "score": decisao.get("score"),
                "classificacao": decisao.get("classificacao") or "",
            },
        },
        "constraints": _flatten(data.get("constraints") or []) + technical_constraints,
        "source_data": {
            "identificacao": ident,
            "programa": programa,
            "programa_funcional": programa_funcional,
            "localizacao": localizacao,
            "investimento": investimento,
            "economia": economia,
            "criterios": criteros,
            "documentos": documentos,
            "entregaveis": entregaveis,
            "especialidades": especialidades,
            "requisitos": requisitos,
            "equipa": equipa,
            "estrategia": estrategia,
            "decisao": decisao,
            "analise_ai": source.get("analise_ai") or {},
            "procedure_identity": procedure_identity,
            "prices": prices,
            "award_strategy": award_strategy,
            "required_team": required_team,
            "phases_and_deliverables": phases_and_deliverables,
            "technical_constraints": technical_constraints,
            "exclusion_risks": exclusion_risks,
            "document_alerts": document_alerts,
        },
        "procedure_identity": procedure_identity,
        "prices": prices,
        "award_strategy": award_strategy,
        "required_team": required_team,
        "phases_and_deliverables": phases_and_deliverables,
        "submission_checklist": {
            "administrative": [],
            "technical": [],
            "financial": [],
            "team": [],
            "post_award": [],
        },
        "drawing_rules": [],
        "financial_conditions": {},
        "technical_constraints": technical_constraints,
        "exclusion_risks": exclusion_risks,
        "document_alerts": document_alerts,
    }


def economy_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = " ".join(str(value).strip().split())
    if not text:
        return None
    raw = ""
    for token in text.replace("EUR", " ").replace("€", " ").split():
        if any(ch.isdigit() for ch in token):
            raw = token
            break
    if not raw:
        return None
    raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _normalize_profile(
    company_profile: CompanyProfile | dict[str, Any] | Any,
) -> dict[str, Any]:
    profile = _extract_company_profile(company_profile)
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    if not isinstance(identity, dict):
        identity = {}

    project_experience = _flatten(profile.get("project_experience") or [])
    project_experience_summary = _flatten(profile.get("project_experience_summary") or [])
    project_counts_by_typology = profile.get("project_counts_by_typology") if isinstance(profile.get("project_counts_by_typology"), dict) else {}
    ai_memory = profile.get("ai_memory") if isinstance(profile.get("ai_memory"), dict) else {}
    knowledge_memory = profile.get("knowledge_memory") if isinstance(profile.get("knowledge_memory"), dict) else {}
    if not knowledge_memory and isinstance(ai_memory, dict):
        knowledge_memory = ai_memory

    services = _unique(gather_texts(profile.get("services")))
    competences = _unique(gather_texts(profile.get("competences")))
    specializations = _unique(gather_texts(profile.get("specializations")))

    projects = []
    counts: dict[str, int] = defaultdict(int)
    summary: list[dict[str, Any]] = []

    for project in project_experience:
        project_dict = _as_dict(project)
        typology = normalize_concept(project_dict.get("typology") or project_dict.get("type"), TYPOLOGY_TAXONOMY)
        name = " ".join(str(project_dict.get("name") or "").strip().split()) or "Not Found"
        location = " ".join(str(project_dict.get("location") or "").strip().split()) or "Not Found"
        skills = _unique(gather_texts(project_dict.get("skills_demonstrated") or project_dict.get("skills") or []))
        if typology and typology != "Not Found":
            counts[typology] += 1
        if name != "Not Found" or typology != "Not Found":
            projects.append(
                {
                    "name": name,
                    "typology": typology or "Not Found",
                    "normalized_typology": typology or "Not Found",
                    "location": location,
                    "skills_demonstrated": skills,
                    "source": "company_profile",
                }
            )

    for item in project_experience_summary:
        item_dict = _as_dict(item)
        typology = normalize_concept(item_dict.get("typology"), TYPOLOGY_TAXONOMY)
        if not typology:
            continue
        count = int(item_dict.get("project_count") or 0)
        counts[typology] = max(counts[typology], count)
        summary.append(
            {
                "typology": typology,
                "project_count": count,
                "experience_level": " ".join(str(item_dict.get("experience_level") or "Not Found").split()) or "Not Found",
                "experience_level_score": int(item_dict.get("experience_level_score") or 0),
                "origins": _unique(gather_texts(item_dict.get("origins") or [])),
                "confidence": float(item_dict.get("confidence") or 0.0),
                "projects": [project for project in _flatten(item_dict.get("projects") or []) if isinstance(project, dict)][:5],
            }
        )

    for typology, count in project_counts_by_typology.items():
        canonical = normalize_concept(typology, TYPOLOGY_TAXONOMY)
        if canonical:
            counts[canonical] = max(counts[canonical], int(count or 0))

    if not summary and counts and not projects:
        for typology, count in counts.items():
            summary.append(
                {
                    "typology": typology,
                    "project_count": int(count),
                    "experience_level": "Not Found",
                    "experience_level_score": 0,
                    "origins": ["project_experience"],
                    "confidence": 0.5,
                    "projects": [],
                }
            )

    return {
        "identity": identity,
        "services": services,
        "competences": competences,
        "specializations": specializations,
        "project_experience": projects,
        "project_counts_by_typology": dict(counts),
        "project_experience_summary": summary,
        "preferences": _as_dict(profile.get("preferences")),
        "strategy": _as_dict(profile.get("strategy")),
        "knowledge_memory": knowledge_memory,
        "ai_memory": ai_memory,
    }


def _relevant_texts(comp: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key in (
        "procedure_identity",
        "prices",
        "award_strategy",
        "required_team",
        "phases_and_deliverables",
        "submission_checklist",
        "drawing_rules",
        "financial_conditions",
        "technical_constraints",
        "exclusion_risks",
        "document_alerts",
        "source_data",
    ):
        texts.extend(gather_texts(comp.get(key)))
    return _unique(texts)


def _best_concept_match(
    values: list[str],
    taxonomy: dict[str, tuple[str, ...]],
) -> list[str]:
    matched: list[str] = []
    for value in values:
        normalized = normalize_concept(value, taxonomy)
        if normalized in taxonomy:
            matched.append(normalized)
    return _unique(matched)


def _first_text(value: Any) -> str:
    texts = gather_texts(value)
    return texts[0] if texts else ""


def _field_scalar(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        for key in ("normalized_value", "amount", "value", "label", "name", "text", "description"):
            current = value.get(key)
            if current in (None, ""):
                continue
            scalar = _field_scalar(current)
            if scalar not in (None, "", {}, []):
                return scalar
        return ""
    return value


def _field_number(value: Any) -> float | None:
    scalar = _field_scalar(value)
    if isinstance(scalar, (int, float)):
        return float(scalar)
    if isinstance(scalar, str):
        text = " ".join(scalar.strip().split())
        if not text:
            return None
        match = re.search(r"(\d[\d\s.,]*)", text)
        if not match:
            return None
        candidate = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
        try:
            return float(candidate)
        except ValueError:
            return None
    return None


def _build_project_summary(profile: dict[str, Any], competition_concepts: list[str]) -> list[dict[str, Any]]:
    competition_norms = {value.casefold() for value in competition_concepts if value and value != "Not Found"}
    explicit = profile.get("project_experience_summary") or []
    if explicit:
        result: list[dict[str, Any]] = []
        for item in explicit:
            typology = normalize_concept(item.get("typology"), TYPOLOGY_TAXONOMY)
            if competition_norms and typology.casefold() not in competition_norms:
                continue
            result.append(
                {
                    "typology": typology,
                    "project_count": int(item.get("project_count") or 0),
                    "experience_level": item.get("experience_level") or "Not Found",
                    "experience_level_score": int(item.get("experience_level_score") or 0),
                    "origins": _unique(gather_texts(item.get("origins") or [])),
                    "confidence": float(item.get("confidence") or 0.0),
                    "projects": [project for project in _flatten(item.get("projects") or []) if isinstance(project, dict)][:5],
                }
            )
        if result:
            return sorted(result, key=lambda item: (item.get("project_count") or 0, item.get("experience_level_score") or 0), reverse=True)

    projects = profile.get("project_experience") or []
    grouped: dict[str, dict[str, Any]] = {}
    for project in projects:
        typology = normalize_concept(project.get("typology"), TYPOLOGY_TAXONOMY)
        if not typology or typology == "Not Found":
            continue
        if competition_norms and typology.casefold() not in competition_norms:
            continue
        entry = grouped.setdefault(
            typology.casefold(),
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
        entry["project_count"] += 1
        if len(entry["projects"]) < 5:
            entry["projects"].append(
                {
                    "name": project.get("name") or "Not Found",
                    "location": project.get("location") or "Not Found",
                    "source": project.get("source") or "company_profile",
                    "skills_demonstrated": list(project.get("skills_demonstrated") or []),
                }
            )

    for item in grouped.values():
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
    if not result and profile.get("project_counts_by_typology"):
        for typology, count in profile["project_counts_by_typology"].items():
            if count <= 0:
                continue
            if competition_norms and typology.casefold() not in competition_norms:
                continue
            result.append(
                {
                    "typology": typology,
                    "project_count": int(count),
                    "experience_level": "Not Found",
                    "experience_level_score": 0,
                    "origins": ["project_counts_by_typology"],
                    "confidence": 0.5,
                    "projects": [],
                }
            )
    return sorted(result, key=lambda item: (item.get("project_count") or 0, item.get("experience_level_score") or 0), reverse=True)


def _company_location(profile: dict[str, Any]) -> str:
    location = profile.get("identity", {}).get("location") if isinstance(profile.get("identity"), dict) else ""
    return " ".join(str(location or "").strip().split())


def _preferred_locations(profile: dict[str, Any]) -> list[str]:
    preferences = profile.get("preferences") or {}
    return _unique(gather_texts(preferences.get("locations") or []))


def _preferred_typologies(profile: dict[str, Any]) -> list[str]:
    preferences = profile.get("preferences") or {}
    return _best_concept_match(gather_texts(preferences.get("typologies") or []), TYPOLOGY_TAXONOMY)


def _strategy_values(profile: dict[str, Any]) -> dict[str, list[str]]:
    strategy = profile.get("strategy") or {}
    return {
        "priority_areas": _best_concept_match(gather_texts(strategy.get("priority_areas") or []), TYPOLOGY_TAXONOMY),
        "secondary_areas": _best_concept_match(gather_texts(strategy.get("secondary_areas") or []), TYPOLOGY_TAXONOMY),
        "avoid_areas": _best_concept_match(gather_texts(strategy.get("avoid_areas") or []), TYPOLOGY_TAXONOMY),
        "future_goals": _unique(gather_texts(strategy.get("future_goals") or [])),
    }


def _competition_concepts(competition: dict[str, Any]) -> dict[str, list[str]]:
    competition_texts = _relevant_texts(competition)
    typologies = _best_concept_match(competition_texts, TYPOLOGY_TAXONOMY)
    service_hints = infer_service_hints(typologies)
    services = _unique(_best_concept_match(competition_texts, SERVICE_TAXONOMY) + service_hints)
    team = _unique(_best_concept_match(competition_texts, SERVICE_TAXONOMY) + service_hints)
    return {
        "typologies": typologies,
        "services": services,
        "team": team,
    }


def _match_projects(
    profile: dict[str, Any],
    competition_typologies: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    project_summary = _build_project_summary(profile, competition_typologies)
    matched_projects: list[dict[str, Any]] = []
    experience_count = 0
    competition_norms = {item.casefold() for item in competition_typologies if item and item != "Not Found"}
    for item in project_summary:
        typology = item.get("typology") or "Not Found"
        if typology.casefold() in competition_norms or not competition_norms:
            experience_count += int(item.get("project_count") or 0)
            for project in item.get("projects") or []:
                matched_projects.append(
                    {
                        "name": project.get("name") or "Not Found",
                        "typology": typology,
                        "normalized_typology": typology,
                        "location": project.get("location") or "Not Found",
                        "source": project.get("source") or "company_profile",
                        "confidence": float(item.get("confidence") or 0.5),
                        "evidence": [
                            {
                                "source": "company_profile.project_experience",
                                "value": typology,
                                "project": project.get("name") or "Not Found",
                            }
                        ],
                    }
                )
    return matched_projects[:8], project_summary, experience_count


def _score_dimension(
    value: int,
    maximum: int,
    label: str,
    justification: str,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "name": label,
        "value": max(0, min(maximum, int(value))),
        "maximum": maximum,
        "justification": justification,
        "evidence": list(evidence or []),
        "status": "confirmed" if value > 0 else "missing",
    }


def _confidence_from_signals(result: CompanyMatchingResult) -> tuple[str, list[str]]:
    signals = 0
    if result.matched_projects:
        signals += 2
    signals += len(result.matched_services)
    signals += len(result.matched_competences)
    signals += len(result.matched_specializations)
    signals += len([item for item in result.requirements if item.get("status") in {"confirmed", "encontrado"} or item.get("match_status") == "confirmed"])
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


def _recommendation(result: CompanyMatchingResult) -> dict[str, Any]:
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


def analyze_company_match_v2(
    competition: ConsolidatedCompetitionData | dict[str, Any] | Any,
    company_profile: CompanyProfile | dict[str, Any] | Any,
) -> CompanyMatchingResult:
    competition_data = _extract_competition_data(competition)
    profile = _normalize_profile(company_profile)

    competition_concepts = _competition_concepts(competition_data)
    competition_typologies = competition_concepts["typologies"]
    competition_services = competition_concepts["services"]
    competition_team = competition_concepts["team"]

    company_services = _best_concept_match(profile.get("services") or [], SERVICE_TAXONOMY)
    company_competences = _best_concept_match(profile.get("competences") or [], SERVICE_TAXONOMY)
    company_specializations = _best_concept_match(profile.get("specializations") or [], TYPOLOGY_TAXONOMY)
    company_team_values = _unique([*company_services, *company_competences, *company_specializations])
    company_location = _company_location(profile)
    preferred_locations = _preferred_locations(profile)
    preferred_typologies = _preferred_typologies(profile)
    strategy_fit = _strategy_values(profile)

    matched_projects, project_summary, experience_count = _match_projects(profile, competition_typologies or preferred_typologies)
    matched_services = _unique(sorted(set(company_services) & set(competition_services)))
    if not matched_services and company_services and competition_typologies:
        matched_services = _unique(sorted(set(company_services) & set(competition_typologies)))
    matched_competences = _unique(sorted(set(company_competences) & set(competition_team)))
    matched_specializations = _unique(sorted(set(company_specializations) & set(competition_typologies)))

    result = CompanyMatchingResult()
    result.compatibility_score = None

    if not any((matched_projects, matched_services, matched_competences, matched_specializations, competition_typologies, competition_services, competition_team)):
        result.confidence = "Baixa"
        result.confidence_reasons = ["Nao existem sinais suficientes para calcular compatibilidade."]
        result.score_explanation = {
            "score": None,
            "label": "Sem dados suficientes",
            "explanation": "Not Found",
            "breakdown": [],
            "dimensions": [],
        }
        result.recommendation = _recommendation(result)
        result.unknowns = ["company.profile", "competition.profile"]
        result.missing_information = ["company.profile", "competition.profile"]
        result.strategic_fit = {
            "location": {"company": company_location or "Not Found", "competition": "Not Found", "status": "Not Found", "preferred_locations": preferred_locations},
            "scale": {"company": "Not Found", "competition_base_price": "Not Found"},
            "strategy": strategy_fit,
            "competition_typologies": competition_typologies,
        }
        result.matched_projects = []
        result.matched_services = []
        result.matched_competences = []
        result.matched_specializations = []
        result.compatibility_breakdown = []
        result.score = None
        return result

    experience_value = min(35, min(20, experience_count) * 2 + min(10, len(matched_projects) * 2) + min(5, len(project_summary)))
    if not matched_projects and project_summary:
        experience_value = min(35, sum(int(item.get("project_count") or 0) for item in project_summary) // 2)

    team_value = min(
        20,
        (len(matched_competences) * 6)
        + (len(matched_services) * 4)
        + (2 if company_team_values else 0),
    )
    services_value = min(15, len(matched_services) * 6 if matched_services else 0)
    specializations_value = min(
        10,
        max(
            len(matched_specializations) * 5 if matched_specializations else 0,
            6 if matched_projects and competition_typologies else 0,
        ),
    )
    criteria_bias = 6 if competition_data.get("award_strategy") else 3
    if competition_data.get("award_strategy") and (matched_projects or matched_services or matched_competences):
        criteria_bias = 8
    criteria_value = min(
        10,
        criteria_bias + (2 if matched_projects else 0) + (2 if matched_services else 0),
    )

    competition_scale = _field_number(competition_data.get("prices", {}).get("procedure_value"))
    if competition_scale in (None, "", "Not Found"):
        competition_scale = _field_number(competition_data.get("prices", {}).get("design_services_value"))
    project_scale = " ".join(gather_texts(profile.get("preferences", {}).get("project_scale") or []))
    price_value = 0
    if competition_scale not in (None, "", "Not Found"):
        if project_scale:
            price_value = 3 if any(token in project_scale.casefold() for token in ("media", "media", "pequena", "grande")) else 2
        elif competition_scale <= 250000:
            price_value = 3
        else:
            price_value = 2
        if competition_scale >= 500000 and experience_value >= 20:
            price_value = 5

    competition_location = _first_text(competition_data.get("location") or competition_data.get("procedure_identity", {}).get("location"))
    location_value = 0
    if competition_location:
        company_norm = company_location.casefold()
        competition_norm = competition_location.casefold()
        if company_norm and (company_norm in competition_norm or competition_norm in company_norm):
            location_value = 5
        elif any(pref.casefold() in competition_norm or competition_norm in pref.casefold() for pref in preferred_locations):
            location_value = 5
        elif preferred_locations:
            location_value = 3

    breakdown = [
        _score_dimension(experience_value, 35, "Experiencia", "Experiencia em tipologias semelhantes.", matched_projects[:5]),
        _score_dimension(team_value, 20, "Equipa", "Cobertura da equipa e competences relevantes.", [{"company_values": company_team_values[:5], "competition_values": competition_team[:5]}] if company_team_values else []),
        _score_dimension(services_value, 15, "Servicos", "Servicos da empresa alinhados com o concurso.", [{"company_values": matched_services[:5], "competition_values": competition_services[:5]}] if matched_services else []),
        _score_dimension(specializations_value, 10, "Especializacoes", "Especializacoes e tipologias alinhadas.", [{"company_values": matched_specializations[:5], "competition_values": competition_typologies[:5]}] if matched_specializations else []),
        _score_dimension(criteria_value, 10, "Criterios", "A escala de avaliacao parece compativel com a solidez do perfil.", []),
        _score_dimension(price_value, 5, "Preco", "A escala economica do concurso e compatibilidade de posicionamento.", []),
        _score_dimension(location_value, 5, "Localizacao", "Compatibilidade geografica e preferencia territorial.", [{"company": company_location or "Not Found", "competition": competition_location or "Not Found"}] if competition_location else []),
    ]

    score = sum(item["value"] for item in breakdown)
    score = max(0, min(100, int(score)))

    result.compatibility_score = score
    result.score = score
    result.compatibility_breakdown = breakdown
    result.score_explanation = {
        "score": score,
        "label": "Muito elevada" if score >= 90 else "Elevada" if score >= 75 else "Moderada" if score >= 60 else "Baixa" if score >= 40 else "Muito baixa",
        "explanation": "O score soma experiencia, equipa, servicos, especializacoes, criterios, preco e localizacao.",
        "breakdown": breakdown,
        "dimensions": breakdown,
    }

    result.matched_projects = matched_projects
    result.matched_services = matched_services
    result.matched_competences = matched_competences
    result.matched_specializations = matched_specializations
    result.experience_summary = project_summary

    requirements = []
    if competition_typologies:
        requirements.append(
            {
                "field": "project_experience.typologies",
                "company_values": [item.get("typology") for item in project_summary[:5]] or ["Not Found"],
                "competition_values": competition_typologies,
                "status": "encontrado" if matched_projects else "missing",
            }
        )
    if competition_services:
        requirements.append(
            {
                "field": "services",
                "company_values": matched_services or company_services[:5] or ["Not Found"],
                "competition_values": competition_services,
                "status": "encontrado" if matched_services else "missing",
            }
        )
    if competition_team:
        requirements.append(
            {
                "field": "competences",
                "company_values": matched_competences or company_competences[:5] or ["Not Found"],
                "competition_values": competition_team,
                "status": "encontrado" if matched_competences else "missing",
            }
        )
    if competition_location:
        requirements.append(
            {
                "field": "location",
                "company_values": [company_location or "Not Found"] + preferred_locations,
                "competition_values": [competition_location],
                "status": "encontrado" if location_value else "outside_usual_area",
            }
        )
    result.requirements = requirements

    result.matches = [item for item in requirements if item.get("status") == "encontrado"]
    result.gaps = [item for item in requirements if item.get("status") != "encontrado"]
    result.unknowns = []
    if not matched_projects:
        result.unknowns.append("project_experience.typologies")
    if not matched_services and company_services:
        result.unknowns.append("services")
    if not matched_competences and company_competences:
        result.unknowns.append("competences")
    if not matched_specializations and company_specializations:
        result.unknowns.append("specializations")

    result.missing_information = _unique(
        [
            item.get("field") if isinstance(item, dict) else str(item)
            for item in result.gaps
        ]
        + list(competition_data.get("document_alerts") or [])
    )
    if not result.missing_information:
        result.missing_information = []
    if not result.matched_projects:
        result.missing_information.append("experience.summary")
    if not result.matched_services:
        result.missing_information.append("services")
    if not result.matched_competences:
        result.missing_information.append("competences")
    if not result.matched_specializations:
        result.missing_information.append("specializations")
    result.missing_information = _unique(result.missing_information)

    result.strengths = [
        {
            "name": "Experiencia",
            "value": experience_value,
            "maximum": 35,
            "justification": "Tipologias de projeto alinhadas com o concurso.",
            "evidence": matched_projects[:5],
        },
        {
            "name": "Equipa",
            "value": team_value,
            "maximum": 20,
            "justification": "Competences e especializacoes da equipa respondem aos requisitos.",
            "evidence": [item for item in requirements if item.get("field") in {"competences", "services"} and item.get("status") == "compatible"],
        },
    ]

    result.weaknesses = []
    if not matched_services:
        result.weaknesses.append(
            {
                "name": "Servicos",
                "value": 0,
                "maximum": 15,
                "justification": "Not Found",
                "evidence": [],
            }
        )
    if not matched_specializations:
        result.weaknesses.append(
            {
                "name": "Especializacoes",
                "value": 0,
                "maximum": 10,
                "justification": "Not Found",
                "evidence": [],
            }
        )
    if not competition_location:
        result.weaknesses.append(
            {
                "name": "Localizacao",
                "value": 0,
                "maximum": 5,
                "justification": "Not Found",
                "evidence": [],
            }
        )

    result.positive_factors = result.strengths
    result.negative_factors = result.weaknesses
    result.evidence = [
        {
            "field": "project_experience.typologies",
            "company_values": [item.get("typology") for item in project_summary[:5]],
            "competition_values": competition_typologies,
            "source": "company.profile.project_experience -> competition.typologies",
        },
        {
            "field": "services",
            "company_values": matched_services,
            "competition_values": competition_services,
            "source": "company.profile.services -> competition.requirements",
        },
        {
            "field": "competences",
            "company_values": matched_competences,
            "competition_values": competition_team,
            "source": "company.profile.competences -> competition.required_team",
        },
    ]

    result.strategic_fit = {
        "location": {
            "company": company_location or "Not Found",
            "preferred_locations": preferred_locations,
            "competition": competition_location or "Not Found",
            "status": "confirmed" if location_value else "partial" if competition_location else "Not Found",
        },
        "scale": {
            "company": " ".join(str(profile.get("preferences", {}).get("project_scale") or "").split()) or "Not Found",
            "competition_base_price": competition_scale if competition_scale is not None else "Not Found",
        },
        "strategy": strategy_fit,
        "competition_typologies": competition_typologies,
    }

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
        for item in project_summary[:3]
    ]

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

    result.confidence, result.confidence_reasons = _confidence_from_signals(result)
    result.recommendation = _recommendation(result)

    return result
