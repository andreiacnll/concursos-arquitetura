from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
