from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .company_storage import listar_membros
from .intelligence_builder import build_company_intelligence
from .knowledge_storage import get_company_knowledge
from .member_storage import obter_member_profile
from .profile_storage import obter_company_profile


class CompanyContext(BaseModel):
    company: dict[str, Any] = Field(default_factory=dict)
    team: dict[str, Any] = Field(default_factory=dict)
    projects: dict[str, Any] = Field(default_factory=dict)
    project_experience_summary: list[dict[str, Any]] = Field(default_factory=list)
    project_counts_by_typology: dict[str, int] = Field(default_factory=dict)
    knowledge: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)


def _construir_team_context(company_id: int) -> dict[str, Any]:
    members = listar_membros(company_id)
    return {
        "member_count": len(members),
        "members": [
            {
                "member": member,
                "profile": obter_member_profile(member["id"]).model_dump(),
            }
            for member in members
        ],
    }


def _construir_projects_context(company_intelligence: dict[str, Any]) -> dict[str, Any]:
    return {
        "items": list(company_intelligence.get("projects", {}).get("items", [])),
        "typologies": list(
            company_intelligence.get("projects", {}).get("typologies", [])
        ),
    }


def _construir_knowledge_context(company_id: int, company_intelligence: dict[str, Any]) -> dict[str, Any]:
    # Futuro:
    # - recommendation engine;
    # - LLM context;
    # - matching;
    # - decision support.
    return {
        "memory": [fact.model_dump() for fact in get_company_knowledge(company_id)],
        "intelligence": company_intelligence.get("knowledge", {}),
    }


def build_company_context(company_id: int) -> CompanyContext:
    """
    Compoe um contexto empresarial único a partir dos blocos já existentes.

    Esta camada não altera dados nem substitui build_company_intelligence;
    serve apenas como ponto de agregação para integrações futuras.
    """
    company_profile = obter_company_profile(company_id)
    company_intelligence = build_company_intelligence(company_id)

    return CompanyContext(
        company={
            "profile": company_profile.model_dump(),
            "intelligence": company_intelligence.get("company", {}),
        },
        team={
            **company_intelligence.get("team", {}),
            **_construir_team_context(company_id),
        },
        projects=_construir_projects_context(company_intelligence),
        project_experience_summary=list(
            company_intelligence.get("projects", {}).get("summary", [])
        ),
        project_counts_by_typology=dict(
            company_intelligence.get("projects", {}).get(
                "counts_by_typology", {}
            )
        ),
        knowledge=_construir_knowledge_context(
            company_id,
            company_intelligence,
        ),
        missing_information=list(
            company_intelligence.get("knowledge", {}).get(
                "missing_information", []
            )
        ),
    )
