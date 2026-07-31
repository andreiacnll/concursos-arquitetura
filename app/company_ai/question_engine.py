from __future__ import annotations

from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field

from .models import KnowledgeFact


QuestionType = Literal[
    "boolean_confirmation",
    "single_choice",
    "multi_choice",
    "free_text",
]

QuestionPriority = Literal["high", "medium", "low"]


class QuestionOption(BaseModel):
    value: str
    label: str


class Question(BaseModel):
    field: str
    type: QuestionType
    priority: QuestionPriority
    question: str
    options: list[QuestionOption] = Field(default_factory=list)
    reason: str = ""
    question_source: Literal["discovery", "validation"] = "discovery"
    knowledge_fact_id: int | None = None
    source: str = ""
    evidence: str = ""
    confidence: float = 0.0
    suggested_answer: Any | None = None


_DISCOVERY_QUESTION_BANK: dict[str, Question] = {
    "company.identity": Question(
        field="company.identity",
        type="free_text",
        priority="high",
        question="Como descrevem a identidade e o posicionamento institucional da empresa?",
        reason=(
            "A identidade institucional ajuda a consolidar a visão base da "
            "empresa antes de perguntas mais específicas."
        ),
    ),
    "company.services": Question(
        field="company.services",
        type="multi_choice",
        priority="high",
        question="Que serviços prestam atualmente?",
        options=[
            QuestionOption(value="arquitetura", label="Arquitetura"),
            QuestionOption(value="reabilitacao", label="Reabilitação"),
            QuestionOption(value="interiores", label="Interiores"),
            QuestionOption(value="urbanismo", label="Urbanismo"),
            QuestionOption(value="consultoria", label="Consultoria"),
            QuestionOption(value="paisagismo", label="Paisagismo"),
            QuestionOption(value="outro", label="Outro"),
        ],
        reason=(
            "Os serviços prestados ajudam a filtrar concursos e a definir a "
            "base do perfil da empresa."
        ),
    ),
    "company.strategy": Question(
        field="company.strategy",
        type="multi_choice",
        priority="high",
        question="Quais são as áreas estratégicas onde pretendem concentrar novos concursos?",
        options=[
            QuestionOption(value="cultura", label="Cultura"),
            QuestionOption(value="educacao", label="Educação"),
            QuestionOption(value="saude", label="Saúde"),
            QuestionOption(value="habitacao", label="Habitação"),
            QuestionOption(value="espaco_publico", label="Espaço público"),
            QuestionOption(value="paisagismo", label="Paisagismo"),
            QuestionOption(value="outro", label="Outro"),
        ],
        reason=(
            "As prioridades estratégicas influenciam as recomendações futuras "
            "e a forma como a empresa é posicionada."
        ),
    ),
    "team.competences": Question(
        field="team.competences",
        type="multi_choice",
        priority="high",
        question="Que competências principais a equipa já domina?",
        options=[
            QuestionOption(value="bim", label="BIM"),
            QuestionOption(value="coordenacao", label="Coordenação"),
            QuestionOption(value="reabilitacao", label="Reabilitação"),
            QuestionOption(value="visualizacao", label="Visualização"),
            QuestionOption(value="gestao", label="Gestão"),
            QuestionOption(value="outro", label="Outro"),
        ],
        reason=(
            "As competências da equipa são base para leitura interna da "
            "capacidade técnica disponível."
        ),
    ),
    "team.experience": Question(
        field="team.experience",
        type="multi_choice",
        priority="medium",
        question="Em que áreas a equipa já tem experiência relevante?",
        options=[
            QuestionOption(value="arquitetura", label="Arquitetura"),
            QuestionOption(value="reabilitacao", label="Reabilitação"),
            QuestionOption(value="interiores", label="Interiores"),
            QuestionOption(value="urbanismo", label="Urbanismo"),
            QuestionOption(value="bim", label="BIM"),
            QuestionOption(value="outro", label="Outro"),
        ],
        reason=(
            "A experiência da equipa ajuda a distinguir conhecimento técnico "
            "da simples disponibilidade operacional."
        ),
    ),
    "team.specializations": Question(
        field="team.specializations",
        type="multi_choice",
        priority="medium",
        question="Que especializações melhor representam a equipa?",
        options=[
            QuestionOption(value="arquitetura", label="Arquitetura"),
            QuestionOption(value="reabilitacao", label="Reabilitação"),
            QuestionOption(value="interiores", label="Interiores"),
            QuestionOption(value="urbanismo", label="Urbanismo"),
            QuestionOption(value="outro", label="Outro"),
        ],
        reason=(
            "As especializações ajudam a distinguir competências gerais de "
            "áreas de foco da equipa."
        ),
    ),
    "projects.items": Question(
        field="projects.items",
        type="free_text",
        priority="medium",
        question="Que projetos relevantes gostariam de registar como referência?",
        reason=(
            "Projetos de referência reforçam a leitura da experiência da "
            "empresa e dos membros."
        ),
    ),
    "projects.typologies": Question(
        field="projects.typologies",
        type="multi_choice",
        priority="medium",
        question="Que tipologias de projeto representam a experiência mais forte?",
        options=[
            QuestionOption(value="habitacao", label="Habitação"),
            QuestionOption(value="cultura", label="Cultura"),
            QuestionOption(value="educacao", label="Educação"),
            QuestionOption(value="saude", label="Saúde"),
            QuestionOption(value="espaco_publico", label="Espaço público"),
            QuestionOption(value="outro", label="Outro"),
        ],
        reason=(
            "As tipologias de experiência ajudam a organizar a base de "
            "conhecimento e as futuras recomendações."
        ),
    ),
}


def _normalizar_texto(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split())


def _boolean_question(
    fact: KnowledgeFact,
    *,
    question_text: str,
    evidence: str,
) -> Question:
    return Question(
        field=fact.field,
        type="boolean_confirmation",
        priority="medium" if float(fact.confidence or 0.0) >= 0.5 else "high",
        question=question_text,
        reason=(
            "Facto extraído automaticamente para confirmação rápida."
        ),
        question_source="validation",
        knowledge_fact_id=fact.id,
        source=_source_label(fact),
        evidence=evidence,
        confidence=float(fact.confidence or 0.0),
        suggested_answer=True,
    )


def _source_label(fact: KnowledgeFact) -> str:
    source = _normalizar_texto(fact.source)
    source_type = _normalizar_texto(fact.source_type)
    if source.startswith("website") or source_type == "website":
        return "Website"
    if source.startswith("portfolio") or source_type == "portfolio":
        return "Portfólio"
    if source.startswith("document") or source_type == "document":
        return "Documento"
    return source or source_type or "Documento"


def _summarize_fact_value(value: Any) -> str:
    if isinstance(value, list):
        itens = [_normalizar_texto(item) for item in value if _normalizar_texto(item)]
        if not itens:
            return ""
        if len(itens) == 1:
            return itens[0]
        if len(itens) == 2:
            return f"{itens[0]} e {itens[1]}"
        return f"{', '.join(itens[:-1])} e {itens[-1]}"
    if isinstance(value, dict):
        partes = [
            _normalizar_texto(item)
            for item in value.values()
            if _normalizar_texto(item)
        ]
        return ", ".join(partes)
    return _normalizar_texto(value)


def _build_validation_question(fact: KnowledgeFact) -> Question | None:
    value_summary = _summarize_fact_value(fact.value)
    if not value_summary:
        return None

    field_labels = {
        "company.services": "A empresa trabalha em",
        "company.competences": "A empresa utiliza",
        "team.competences": "A equipa domina",
        "team.experience": "A equipa tem experiência em",
        "team.specializations": "A equipa está focada em",
        "projects.typologies": "A empresa tem experiência em",
        "company.identity": "Esta descrição da empresa está correta",
    }

    if fact.field == "company.identity":
        question_text = "A descrição resumida da empresa está correta?"
    else:
        prefix = field_labels.get(fact.field, "Confirma-se que")
        question_text = f"{prefix} {value_summary}?"

    return _boolean_question(
        fact,
        question_text=question_text,
        evidence=f"Identificado em {_source_label(fact)}: {value_summary}.",
    )


def _discovery_question_for_field(field: str) -> Question | None:
    question = _DISCOVERY_QUESTION_BANK.get(field)
    if question is None:
        return None
    return question.model_copy(deep=True)


def _known_fields(knowledge_facts: Iterable[KnowledgeFact] | None) -> set[str]:
    fields: set[str] = set()
    for fact in knowledge_facts or []:
        if isinstance(fact, KnowledgeFact):
            status = _normalizar_texto(fact.status).lower()
            if status == "confirmed":
                fields.add(fact.field)
    return fields


def generate_questions(
    missing_information: list[str],
    company_profile: Any | None = None,
    knowledge_facts: Iterable[KnowledgeFact] | None = None,
) -> list[Question]:
    """
    Transforma lacunas conhecidas em perguntas estruturadas.

    Esta camada é determinística e serve de base para o AI Interviewer,
    Question Engine e futuras decisões de priorização.
    """
    known_fields = _known_fields(knowledge_facts)
    if company_profile is not None and hasattr(company_profile, "model_dump"):
        profile_data = company_profile.model_dump()
        if _normalizar_texto(profile_data.get("identity", {}).get("company_name")):
            known_fields.add("company.identity")
        if profile_data.get("services"):
            known_fields.add("company.services")
        if profile_data.get("competences"):
            known_fields.add("team.competences")
        if profile_data.get("project_experience"):
            known_fields.add("projects.items")
        strategy = profile_data.get("strategy") or {}
        if any(strategy.get(key) for key in ("priority_areas", "secondary_areas")):
            known_fields.add("company.strategy")

    questions: list[Question] = []

    for field in missing_information:
        if field in known_fields:
            continue
        question = _discovery_question_for_field(field)
        if question is None:
            continue
        questions.append(question)

    priority_order = {"high": 0, "medium": 1, "low": 2}
    questions.sort(
        key=lambda item: (
            priority_order.get(item.priority, 99),
            item.field,
        )
    )

    return questions


def build_validation_question_from_fact(fact: KnowledgeFact) -> Question | None:
    return _build_validation_question(fact)
