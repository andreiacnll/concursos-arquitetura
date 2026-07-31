from __future__ import annotations

from typing import Any

from .company_storage import listar_membros
from .member_storage import obter_member_profile
from .profile_storage import obter_company_profile


def _lista_unica(valores: list[str]) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []

    for valor in valores:
        texto = str(valor).strip()
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        resultado.append(texto)

    return resultado


def _esta_vazio_texto(valor: Any) -> bool:
    return not str(valor or "").strip()


def _calcular_confianca(total: int, preenchidos: int) -> float:
    if total <= 0:
        return 0.0
    return round(max(0.0, min(1.0, preenchidos / total)), 2)


def _perfil_empresa_vazio(company_profile) -> bool:
    identidade = company_profile.identity.model_dump()
    return (
        all(_esta_vazio_texto(valor) for valor in identidade.values())
        and not company_profile.services
        and not company_profile.competences
        and not any(company_profile.strategy.values())
    )


def _resumir_identidade_empresa(company_profile) -> dict[str, Any]:
    return company_profile.identity.model_dump()


def _resumir_estrategia(company_profile) -> dict[str, Any]:
    return {
        "priority_areas": _lista_unica(
            list(company_profile.strategy.get("priority_areas", []))
        ),
        "secondary_areas": _lista_unica(
            list(company_profile.strategy.get("secondary_areas", []))
        ),
        "avoid_areas": _lista_unica(
            list(company_profile.strategy.get("avoid_areas", []))
        ),
        "future_goals": _lista_unica(
            list(company_profile.strategy.get("future_goals", []))
        ),
    }


def _resumir_projetos(company_profile, members) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    typologies: list[str] = []

    for project in company_profile.project_experience:
        typology = str(project.typology or "").strip()
        if typology:
            typologies.append(typology)

        items.append(
            {
                "name": project.name,
                "typology": project.typology,
                "location": project.location,
                "skills_demonstrated": list(project.skills_demonstrated),
                "source": "company_profile",
            }
        )

    for member in members:
        member_profile = obter_member_profile(member["id"])

        for project_name in member_profile.experience.projects:
            texto = str(project_name).strip()
            if not texto:
                continue
            items.append(
                {
                    "name": texto,
                    "source": "member_profile",
                    "member_id": member["id"],
                    "user_id": member["user_id"],
                }
            )

        typologies.extend(member_profile.experience.typologies)

    return items, _lista_unica(typologies)


def _resumir_equipa(members) -> dict[str, Any]:
    team_competences: list[str] = []
    team_experience: list[dict[str, Any]] = []
    specializations: list[str] = []

    for member in members:
        member_profile = obter_member_profile(member["id"])

        competencias = _lista_unica(
            [
                *member_profile.competences.technical,
                *member_profile.competences.software,
                *member_profile.competences.methodologies,
            ]
        )
        if competencias:
            team_competences.extend(competencias)

        experiencia = _lista_unica(
            [
                *member_profile.experience.projects,
                *member_profile.experience.typologies,
                *member_profile.experience.sectors,
                *member_profile.experience.responsibilities,
            ]
        )
        if experiencia:
            team_experience.append(
                {
                    "member_id": member["id"],
                    "user_id": member["user_id"],
                    "role": member["role"],
                    "experience": experiencia,
                }
            )

        especializacao = str(
            member_profile.identity.specialization or ""
        ).strip()
        if especializacao:
            specializations.append(especializacao)

    return {
        "member_count": len(members),
        "competences": _lista_unica(team_competences),
        "experience": team_experience,
        "specializations": _lista_unica(specializations),
    }


def _calcular_missing_information(
    *,
    company_profile,
    company_block: dict[str, Any],
    team_block: dict[str, Any],
    projects_block: dict[str, Any],
) -> list[str]:
    missing: list[str] = []

    if _perfil_empresa_vazio(company_profile) or not company_block["services"]:
        missing.append("company.services")
    if not company_block["competences"]:
        missing.append("company.competences")
    if all(_esta_vazio_texto(valor) for valor in company_block["identity"].values()):
        missing.append("company.identity")
    if not any(company_block["strategy"].values()):
        missing.append("company.strategy")

    if not team_block["competences"]:
        missing.append("team.competences")
    if not team_block["experience"]:
        missing.append("team.experience")
    if not team_block["specializations"]:
        missing.append("team.specializations")

    if not projects_block["items"]:
        missing.append("projects.items")
    if not projects_block["typologies"]:
        missing.append("projects.typologies")

    return missing


def build_company_intelligence(company_id: int) -> dict[str, Any]:
    """
    Agregação determinística da inteligência da empresa.

    Futuro: esta camada será consumida pelo interviewer, matching engine,
    response generator e knowledge base.
    """
    company_profile = obter_company_profile(company_id)
    members = listar_membros(company_id)

    company_block = {
        "identity": _resumir_identidade_empresa(company_profile),
        "services": _lista_unica(list(company_profile.services)),
        "competences": _lista_unica(list(company_profile.competences)),
        "strategy": _resumir_estrategia(company_profile),
    }

    team_block = _resumir_equipa(members)
    projects_items, projects_typologies = _resumir_projetos(
        company_profile,
        members,
    )

    sources: list[dict[str, Any]] = [
        {
            "type": "company_profile",
            "company_id": company_id,
        }
    ]
    sources.extend(
        {
            "type": "company_member",
            "member_id": member["id"],
            "user_id": member["user_id"],
            "role": member["role"],
        }
        for member in members
    )

    knowledge = {
        "sources": sources,
        "confidence": {
            "company": _calcular_confianca(
                4,
                sum(
                    1
                    for valor in company_block["identity"].values()
                    if not _esta_vazio_texto(valor)
                )
                + int(bool(company_block["services"]))
                + int(bool(company_block["competences"]))
                + int(bool(any(company_block["strategy"].values()))),
            ),
            "team": _calcular_confianca(
                3,
                int(bool(team_block["competences"]))
                + int(bool(team_block["experience"]))
                + int(bool(team_block["specializations"])),
            ),
            "projects": _calcular_confianca(
                2,
                int(bool(projects_items)) + int(bool(projects_typologies)),
            ),
        },
    }
    knowledge["missing_information"] = _calcular_missing_information(
        company_profile=company_profile,
        company_block=company_block,
        team_block=team_block,
        projects_block={
            "items": projects_items,
            "typologies": projects_typologies,
        },
    )

    return {
        "company": {
            "identity": company_block["identity"],
            "services": company_block["services"],
            "competences": company_block["competences"],
            "strategy": company_block["strategy"],
        },
        "team": team_block,
        "projects": {
            "items": projects_items,
            "typologies": projects_typologies,
        },
        "knowledge": knowledge,
    }
