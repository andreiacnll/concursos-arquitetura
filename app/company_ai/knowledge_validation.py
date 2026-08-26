from __future__ import annotations

from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field

from .knowledge_storage import get_company_knowledge
from .models import KnowledgeFact
from .question_engine import QuestionPriority, QuestionType, build_validation_question_from_fact


class KnowledgeValidationRequest(BaseModel):
    company_id: int
    field: str
    value: Any
    confidence: float = 0.0
    status: str = "unknown"


class ValidationQuestion(BaseModel):
    field: str
    value: Any
    type: QuestionType = "boolean_confirmation"
    question: str
    reason: str
    priority: QuestionPriority = "medium"
    question_source: Literal["discovery", "validation"] = "validation"
    knowledge_fact_id: int | None = None
    source: str = ""
    evidence: str = ""
    confidence: float = 0.0
    suggested_answer: Any | None = None
    options: list[Any] = Field(default_factory=list)


def _normalizar_factos(
    knowledge_facts: Iterable[KnowledgeFact | dict[str, Any]],
) -> list[KnowledgeFact]:
    resultado: list[KnowledgeFact] = []
    for fact in knowledge_facts:
        if isinstance(fact, KnowledgeFact):
            resultado.append(fact)
            continue
        if isinstance(fact, dict):
            resultado.append(KnowledgeFact.model_validate(fact))
    return resultado


def _deve_validar(fact: KnowledgeFact) -> bool:
    status = str(fact.status or "unknown").strip().lower()
    confidence = float(fact.confidence or 0.0)
    if status in {"confirmed", "rejected"}:
        return False
    return confidence < 0.8


def generate_validation_questions(
    knowledge_facts,
) -> list[ValidationQuestion]:
    """
    Cria perguntas determinísticas para factos que precisam de validação.
    """
    facts = _normalizar_factos(knowledge_facts or [])
    questions: list[ValidationQuestion] = []

    for fact in facts:
        if not _deve_validar(fact):
            continue

        question = build_validation_question_from_fact(fact)
        if question is None:
            continue

        questions.append(
            ValidationQuestion(
                field=fact.field,
                value=fact.value,
                question=question.question,
                reason=question.reason,
                priority=question.priority,
                knowledge_fact_id=fact.id,
                source=question.source,
                evidence=question.evidence,
                confidence=question.confidence,
                suggested_answer=question.suggested_answer,
            )
        )

    return questions


def generate_knowledge_validation_questions(
    company_id: int,
) -> list[ValidationQuestion]:
    """Gera perguntas de validação diretamente a partir da knowledge memory."""
    return generate_validation_questions(get_company_knowledge(company_id))
