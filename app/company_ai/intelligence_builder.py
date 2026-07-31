from __future__ import annotations

from typing import Any

from .company_storage import listar_membros, obter_empresa_utilizador
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


def build_company_intelligence(company_id: int) -> dict[str, Any]:
    """
    Agregação determinística da inteligência da empresa.

    Futuro: esta camada será consumida pelo interviewer, matching engine,
    response generator e knowledge base.
    """
    company_profile = obter_company_profile(company_id)
    members = listar_membros(company_id)

    services = _lista_unica(
        [
            *company_profile.services,
        ]
    )
    competences = _lista_unica(
        [
            *company_profile.competences,
        ]
    )

    team_competences: list[dict[str, Any]] = []
    experience: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = [
        {
            "type": "company_profile",
            "company_id": company_id,
        }
    ]

    for member in members:
        member_profile = obter_member_profile(member["id"])
        sources.append(
            {
                "type": "company_member",
                "member_id": member["id"],
                "user_id": member["user_id"],
                "role": member["role"],
            }
        )

        competences_do_membro = _lista_unica(
            [
                *member_profile.competences.technical,
                *member_profile.competences.software,
                *member_profile.competences.methodologies,
            ]
        )
        if competences_do_membro:
            team_competences.append(
                {
                    "member_id": member["id"],
                    "user_id": member["user_id"],
                    "role": member["role"],
                    "competences": competences_do_membro,
                }
            )

        experiencia_do_membro = _lista_unica(
            [
                *member_profile.experience.projects,
                *member_profile.experience.typologies,
                *member_profile.experience.sectors,
                *member_profile.experience.responsibilities,
            ]
        )
        if experiencia_do_membro:
            experience.append(
                {
                    "member_id": member["id"],
                    "user_id": member["user_id"],
                    "role": member["role"],
                    "experience": experiencia_do_membro,
                }
            )

    company_id_final = company_profile.company_id or company_id

    return {
        "company_id": company_id_final,
        "services": services,
        "competences": competences,
        "team_competences": team_competences,
        "experience": experience,
        "member_count": len(members),
        "sources": sources,
    }
