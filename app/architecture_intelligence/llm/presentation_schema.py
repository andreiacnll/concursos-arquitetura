from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class PresentationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    value: str
    status: Literal["confirmed", "partial", "insufficient_evidence"]


class PresentationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    source_document: str = ""
    page: int | None = None
    section: str = ""
    excerpt: str = ""
    confidence: float | None = None


class PresentationCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    title: str
    summary: str
    items: list[PresentationItem] = Field(default_factory=list)
    confidence: Literal["confirmed", "partial", "limited"]
    evidence_ids: list[str] = Field(default_factory=list)


class PresentationRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    summary: str
    severity: Literal["critical", "warning", "info"]
    status: Literal["confirmed", "partial", "insufficient_evidence"]
    evidence_ids: list[str] = Field(default_factory=list)


class Presentation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_status: Literal["complete", "partial", "insufficient", "announcement_only"]
    executive_summary: str
    cards: list[PresentationCard] = Field(default_factory=list)
    risks: list[PresentationRisk] = Field(default_factory=list)
    opportunities: list[PresentationRisk] = Field(default_factory=list)
    checklist: list[PresentationRisk] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[PresentationEvidence] = Field(default_factory=list)
    competition_type: str = ""
    competition_subtype: str = ""
    classification_confidence: float = 0.0
    classification_reasons: list[str] = Field(default_factory=list)
    recommended_section_order: list[str] = Field(default_factory=list)
    section_visibility: dict[str, bool] = Field(default_factory=dict)
    section_priority: dict[str, int] = Field(default_factory=dict)
    special_features: list[str] = Field(default_factory=list)


def presentation_json_schema() -> dict:
    return Presentation.model_json_schema()
