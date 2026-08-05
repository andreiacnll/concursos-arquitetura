from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    ANNOUNCEMENT = "announcement"
    TERMS_OF_REFERENCE = "terms_of_reference"
    PROCEDURE_PROGRAM = "procedure_program"
    SPECIFICATIONS = "specifications"
    PRELIMINARY_PROGRAM = "preliminary_program"
    AWARD_CRITERIA = "award_criteria"
    TECHNICAL_ANNEX = "technical_annex"
    ADMINISTRATIVE_ANNEX = "administrative_annex"
    CONTRACT_DRAFT = "contract_draft"
    CLARIFICATION = "clarification"
    RECTIFICATION = "rectification"
    OTHER = "other"
    UNKNOWN = "unknown"


class EvidenceStatus(str, Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    CONTRADICTORY = "contradictory"
    NOT_FOUND = "not_found"


class SourceDocument(BaseModel):
    document_id: str
    concurso_id: int | None = None
    filename: str
    path: str | None = None
    origin: str
    source_role: str
    content_type: str | None = None
    sha256: str | None = None
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassifiedDocument(BaseModel):
    source: SourceDocument
    document_type: DocumentType = DocumentType.UNKNOWN
    title: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    document_category: str = "Outros"
    lifecycle_phase: str = "administrative"
    lifecycle_purpose: str = "obrigacao administrativa"
    document_priority: int = 0


class DocumentClassification(BaseModel):
    document_id: str
    filename: str
    document_category: str = "Outros"
    lifecycle_phase: str = "administrative"
    lifecycle_purpose: str = "obrigacao administrativa"
    document_type: str = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    document_priority: int = 0
    reasons: list[str] = Field(default_factory=list)
    source_role: str = ""
    source_url: str | None = None


class InformationItem(BaseModel):
    field_name: str
    value: Any = None
    normalized_value: Any = None
    knowledge_block: str = "other"
    phase: str = "administrative"
    purpose: str = "obrigacao administrativa"
    source_document: str = ""
    source_document_id: str = ""
    document_category: str = "Outros"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    document_priority: int = 0
    reader_name: str = ""
    section: str = ""


class DocumentSection(BaseModel):
    section_id: str
    document_id: str
    title: str | None = None
    article: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    text: str
    topics: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    evidence_id: str
    source_document_id: str
    filename: str
    page: int | None = None
    section: str | None = None
    excerpt: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: EvidenceStatus = EvidenceStatus.CONFIRMED
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedField(BaseModel):
    field_name: str
    value: Any = None
    normalized_value: Any = None
    evidences: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: EvidenceStatus = EvidenceStatus.NOT_FOUND


class ReaderResult(BaseModel):
    reader_name: str
    document_ids: list[str] = Field(default_factory=list)
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    evidences: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


def default_submission_checklist() -> dict[str, list[dict[str, Any]]]:
    return {
        "administrative": [],
        "technical": [],
        "financial": [],
        "team": [],
        "post_award": [],
    }


class ConsolidatedCompetitionData(BaseModel):
    schema_version: str = "1.0"
    document_quality: str = "insufficient"
    quality_report: dict[str, Any] = Field(default_factory=dict)
    document_index: list[DocumentClassification] = Field(default_factory=list)
    information_model: list[InformationItem] = Field(default_factory=list)
    knowledge_intents: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)

    procedure_identity: dict[str, Any] = Field(default_factory=dict)
    prices: dict[str, Any] = Field(default_factory=dict)
    award_strategy: dict[str, Any] = Field(default_factory=dict)

    required_team: list[dict[str, Any]] = Field(default_factory=list)
    phases_and_deliverables: list[dict[str, Any]] = Field(
        default_factory=list
    )

    submission_checklist: dict[str, list[dict[str, Any]]] = Field(
        default_factory=default_submission_checklist
    )

    drawing_rules: list[dict[str, Any]] = Field(default_factory=list)
    financial_conditions: dict[str, Any] = Field(default_factory=dict)
    technical_constraints: list[dict[str, Any]] = Field(
        default_factory=list
    )
    exclusion_risks: list[dict[str, Any]] = Field(default_factory=list)
    document_alerts: list[dict[str, Any]] = Field(default_factory=list)

    evidences: list[Evidence] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
