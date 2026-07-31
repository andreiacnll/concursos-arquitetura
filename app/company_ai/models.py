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

    def merge(self, other: "CompanyProfile") -> "CompanyProfile":
        """
        Mantém o formato simples da base actual: a última versão
        recebida substitui a anterior por completo.
        """
        return other


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
