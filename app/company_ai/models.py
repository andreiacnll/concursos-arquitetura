from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Company(BaseModel):
    id: int | None = None
    owner_user_id: str
    name: str
    website: str | None = None


class CompanyMember(BaseModel):
    id: int | None = None
    company_id: int
    user_id: str
    role: str = "member"
    status: str = "active"


class MemberIdentity(BaseModel):
    name: str = ""
    role: str = ""
    specialization: str = ""
    education: str = ""


class MemberExperience(BaseModel):
    projects: list[str] = Field(default_factory=list)
    typologies: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)


class MemberCompetences(BaseModel):
    technical: list[str] = Field(default_factory=list)
    software: list[str] = Field(default_factory=list)
    methodologies: list[str] = Field(default_factory=list)


class MemberPreferences(BaseModel):
    preferred_typologies: list[str] = Field(default_factory=list)
    preferred_sectors: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)


class MemberGoals(BaseModel):
    career_goals: list[str] = Field(default_factory=list)
    development_areas: list[str] = Field(default_factory=list)


class MemberVisibility(BaseModel):
    company_visible: list[str] = Field(default_factory=list)
    private: list[str] = Field(default_factory=list)


class MemberProfile(BaseModel):
    # Futuro: perfil individual usado por interviewer individual,
    # extractor, matching e resposta AI.
    id: int | None = None
    member_id: int | None = None
    identity: MemberIdentity = Field(
        default_factory=MemberIdentity
    )
    experience: MemberExperience = Field(
        default_factory=MemberExperience
    )
    competences: MemberCompetences = Field(
        default_factory=MemberCompetences
    )
    preferences: MemberPreferences = Field(
        default_factory=MemberPreferences
    )
    goals: MemberGoals = Field(
        default_factory=MemberGoals
    )
    visibility: MemberVisibility = Field(
        default_factory=MemberVisibility
    )


class CompanyIdentity(BaseModel):
    company_name: str = ""
    description: str = ""
    location: str = ""
    website: str = ""


class CompanyProjectExperience(BaseModel):
    name: str = ""
    typology: str = ""
    location: str = ""
    skills_demonstrated: list[str] = Field(default_factory=list)


class CompanyPreferences(BaseModel):
    typologies: list[str] = Field(default_factory=list)
    procedures: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    project_scale: list[str] = Field(default_factory=list)


class CompanyMemory(BaseModel):
    confirmed_facts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    validated_preferences: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class CompanyProfile(BaseModel):
    # Futuro: este perfil ficará ligado a company_id e será alimentado
    # pelo extractor AI, interviewer, knowledge base e scoring.
    company_id: int | None = None
    identity: CompanyIdentity = Field(
        default_factory=CompanyIdentity
    )
    services: list[str] = Field(default_factory=list)
    competences: list[str] = Field(default_factory=list)
    specializations: list[str] = Field(default_factory=list)
    project_experience: list[CompanyProjectExperience] = Field(
        default_factory=list
    )
    preferences: CompanyPreferences = Field(
        default_factory=CompanyPreferences
    )
    strategy: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "priority_areas": [],
            "secondary_areas": [],
            "avoid_areas": [],
            "future_goals": [],
        }
    )
    ai_memory: CompanyMemory = Field(
        default_factory=CompanyMemory
    )

    def _merge_legacy_unused(self, other: "CompanyProfile") -> "CompanyProfile":
        """
        Mantém o formato simples da base actual: a última versão
        recebida substitui a anterior por completo.
        """
        return other


    def merge(self, other: "CompanyProfile") -> "CompanyProfile":
        """
        Junta uma versao recebida com a versao persistida sem apagar
        informacao valida quando o payload vem parcial.
        """
        def text(value: Any) -> str:
            return str(value or "").strip()

        def merge_text(current: str, incoming: str) -> str:
            incoming_text = text(incoming)
            return incoming_text if incoming_text else text(current)

        def merge_list(*lists: list[str]) -> list[str]:
            seen: set[str] = set()
            result: list[str] = []
            for values in lists:
                for value in values or []:
                    item = text(value)
                    key = " ".join(item.lower().split())
                    if not item or key in seen:
                        continue
                    seen.add(key)
                    result.append(item)
            return result

        def project_key(
            project: CompanyProjectExperience,
        ) -> tuple[str, str, str]:
            name = " ".join(text(project.name).lower().split())
            typology = " ".join(text(project.typology).lower().split())
            location = " ".join(text(project.location).lower().split())
            return name, typology, location

        def merge_projects(
            current: list[CompanyProjectExperience],
            incoming: list[CompanyProjectExperience],
        ) -> list[CompanyProjectExperience]:
            result = [project.model_copy(deep=True) for project in current]
            indexes = {
                project_key(project): index
                for index, project in enumerate(result)
            }

            for project in incoming or []:
                has_content = any(
                    (
                        text(project.name),
                        text(project.typology),
                        text(project.location),
                        *[
                            text(skill)
                            for skill in project.skills_demonstrated
                        ],
                    )
                )
                if not has_content:
                    continue

                key = project_key(project)
                if key in indexes:
                    existing = result[indexes[key]]
                    existing.name = merge_text(existing.name, project.name)
                    existing.typology = merge_text(
                        existing.typology,
                        project.typology,
                    )
                    existing.location = merge_text(
                        existing.location,
                        project.location,
                    )
                    existing.skills_demonstrated = merge_list(
                        existing.skills_demonstrated,
                        project.skills_demonstrated,
                    )
                    continue

                result.append(project.model_copy(deep=True))
                indexes[key] = len(result) - 1

            return result

        merged = self.model_copy(deep=True)
        incoming = other.model_copy(deep=True)
        merged.company_id = incoming.company_id or merged.company_id
        merged.identity.company_name = merge_text(
            merged.identity.company_name,
            incoming.identity.company_name,
        )
        merged.identity.website = merge_text(
            merged.identity.website,
            incoming.identity.website,
        )
        merged.identity.location = merge_text(
            merged.identity.location,
            incoming.identity.location,
        )
        merged.identity.description = merge_text(
            merged.identity.description,
            incoming.identity.description,
        )
        merged.services = merge_list(merged.services, incoming.services)
        merged.competences = merge_list(
            merged.competences,
            incoming.competences,
        )
        merged.specializations = merge_list(
            merged.specializations,
            incoming.specializations,
        )
        merged.project_experience = merge_projects(
            merged.project_experience,
            incoming.project_experience,
        )
        merged.preferences = CompanyPreferences(
            typologies=merge_list(
                merged.preferences.typologies,
                incoming.preferences.typologies,
            ),
            procedures=merge_list(
                merged.preferences.procedures,
                incoming.preferences.procedures,
            ),
            locations=merge_list(
                merged.preferences.locations,
                incoming.preferences.locations,
            ),
            project_scale=merge_list(
                merged.preferences.project_scale,
                incoming.preferences.project_scale,
            ),
        )
        merged.strategy = {
            key: merge_list(
                list(merged.strategy.get(key, [])),
                list(incoming.strategy.get(key, [])),
            )
            for key in (
                "priority_areas",
                "secondary_areas",
                "avoid_areas",
                "future_goals",
            )
        }
        merged.ai_memory = CompanyMemory(
            confirmed_facts=merge_list(
                merged.ai_memory.confirmed_facts,
                incoming.ai_memory.confirmed_facts,
            ),
            assumptions=merge_list(
                merged.ai_memory.assumptions,
                incoming.ai_memory.assumptions,
            ),
            validated_preferences=merge_list(
                merged.ai_memory.validated_preferences,
                incoming.ai_memory.validated_preferences,
            ),
            open_questions=merge_list(
                merged.ai_memory.open_questions,
                incoming.ai_memory.open_questions,
            ),
        )
        return merged


CompanyProfilePayload = CompanyProfile
CompanyProfileData = dict[str, Any]


class KnowledgeFact(BaseModel):
    id: int | None = None
    field: str
    value: Any
    source: str = ""
    source_type: str = ""
    url: str = ""
    section: str = ""
    evidence_text: str = ""
    confidence: float = 0.0
    status: str = "unknown"
