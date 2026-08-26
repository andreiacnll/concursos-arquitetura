from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SemanticFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semantic_type: str
    value: str
    source_excerpt: str
    confidence: float = Field(ge=0.0, le=1.0)


class SemanticFilterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "insufficient_evidence"]
    facts: list[SemanticFact] = Field(default_factory=list)
    discarded_fragments: list[str] = Field(default_factory=list)


def semantic_filter_json_schema() -> dict:
    return SemanticFilterResponse.model_json_schema()
