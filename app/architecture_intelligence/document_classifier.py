from __future__ import annotations

import re
import unicodedata

from .schemas import ClassifiedDocument, DocumentType, SourceDocument


_FILENAME_RULES: list[tuple[DocumentType, tuple[str, ...]]] = [
    (
        DocumentType.TERMS_OF_REFERENCE,
        (
            "termos de referencia",
            "termos_de_referencia",
            "termos-referencia",
            "tr_",
        ),
    ),
    (
        DocumentType.PROCEDURE_PROGRAM,
        (
            "programa do procedimento",
            "programa_procedimento",
            "programa-procedimento",
        ),
    ),
    (
        DocumentType.SPECIFICATIONS,
        (
            "caderno de encargos",
            "caderno_encargos",
            "caderno-encargos",
            "ce_",
        ),
    ),
    (
        DocumentType.PRELIMINARY_PROGRAM,
        (
            "programa preliminar",
            "programa_preliminar",
            "programa-preliminar",
        ),
    ),
    (
        DocumentType.AWARD_CRITERIA,
        (
            "criterios de adjudicacao",
            "criterios_adjudicacao",
            "criterios-avaliacao",
            "modelo de avaliacao",
        ),
    ),
    (
        DocumentType.CONTRACT_DRAFT,
        (
            "minuta do contrato",
            "minuta_contrato",
            "minuta-contrato",
        ),
    ),
    (
        DocumentType.CLARIFICATION,
        (
            "esclarecimento",
            "esclarecimentos",
        ),
    ),
    (
        DocumentType.RECTIFICATION,
        (
            "retificacao",
            "retificação",
            "retificacoes",
            "retificações",
        ),
    ),
]


_CONTENT_RULES: list[tuple[DocumentType, tuple[str, ...]]] = [
    (
        DocumentType.TERMS_OF_REFERENCE,
        (
            "termos de referência",
            "concurso de conceção",
            "seleção dos trabalhos de conceção",
        ),
    ),
    (
        DocumentType.PROCEDURE_PROGRAM,
        (
            "programa do procedimento",
            "documentos que constituem a proposta",
            "modo de apresentação da proposta",
        ),
    ),
    (
        DocumentType.SPECIFICATIONS,
        (
            "caderno de encargos",
            "cláusulas jurídicas",
            "prestador de serviços",
            "preço contratual",
        ),
    ),
    (
        DocumentType.PRELIMINARY_PROGRAM,
        (
            "programa preliminar",
            "necessidades funcionais",
            "área de intervenção",
        ),
    ),
    (
        DocumentType.AWARD_CRITERIA,
        (
            "critério de adjudicação",
            "fatores e subfatores",
            "ponderação",
        ),
    ),
    (
        DocumentType.CONTRACT_DRAFT,
        (
            "minuta do contrato",
            "cláusula contratual",
        ),
    ),
    (
        DocumentType.CLARIFICATION,
        (
            "pedido de esclarecimento",
            "resposta aos esclarecimentos",
        ),
    ),
    (
        DocumentType.RECTIFICATION,
        (
            "retificação",
            "retifica-se",
        ),
    ),
]


_DOCUMENT_CATEGORY_MAP: dict[DocumentType, str] = {
    DocumentType.TERMS_OF_REFERENCE: "Programa do Concurso",
    DocumentType.PROCEDURE_PROGRAM: "Programa do Concurso",
    DocumentType.PRELIMINARY_PROGRAM: "Programa Preliminar",
    DocumentType.SPECIFICATIONS: "Caderno de Encargos",
    DocumentType.AWARD_CRITERIA: "Peças do Concurso",
    DocumentType.CONTRACT_DRAFT: "Minuta do Contrato",
    DocumentType.CLARIFICATION: "Anexos",
    DocumentType.RECTIFICATION: "Anexos",
    DocumentType.TECHNICAL_ANNEX: "Condições Técnicas",
    DocumentType.ADMINISTRATIVE_ANNEX: "Anexos",
    DocumentType.OTHER: "Outros",
    DocumentType.ANNOUNCEMENT: "Peças do Concurso",
    DocumentType.UNKNOWN: "Outros",
}


_CATEGORY_PHASE_PURPOSE = {
    "Programa Preliminar": ("submission", "preparar candidatura", 100),
    "Programa do Concurso": ("submission", "preparar candidatura", 95),
    "Regulamento": ("submission", "preparar candidatura", 90),
    "Peças do Concurso": ("evaluation", "avaliação do júri", 85),
    "Caderno de Encargos": ("contract_execution", "execução do contrato", 70),
    "Condições Técnicas": ("contract_execution", "execução do contrato", 75),
    "Minuta do Contrato": ("contract_execution", "execução do contrato", 65),
    "Anexos": ("administrative", "obrigação administrativa", 80),
    "Formulários": ("administrative", "obrigação administrativa", 90),
    "Outros": ("administrative", "obrigação administrativa", 40),
}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    normalized = re.sub(r"[_\-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _document_category(document_type: DocumentType, source: SourceDocument, text: str) -> str:
    filename = _normalize(source.filename)
    content = _normalize(text)
    if "regulamento" in filename or "regulamento" in content:
        return "Regulamento"
    if "formulario" in filename or "formularios" in filename or "formulario" in content or "formularios" in content:
        return "Formulários"
    if "condicoes tecnicas" in filename or "condicoes tecnicas" in content or "especificacoes tecnicas" in content:
        return "Condições Técnicas"
    return _DOCUMENT_CATEGORY_MAP.get(document_type, "Outros")


def _document_lifecycle(category: str) -> tuple[str, str, int]:
    return _CATEGORY_PHASE_PURPOSE.get(category, ("administrative", "obrigação administrativa", 40))


def classify_document(source: SourceDocument) -> ClassifiedDocument:
    filename = _normalize(source.filename)
    text = _normalize(source.text[:12000])

    reasons: list[str] = []

    for document_type, keywords in _FILENAME_RULES:
        for keyword in keywords:
            if _normalize(keyword) in filename:
                reasons.append(f"filename:{keyword}")
                category = _document_category(document_type, source, text)
                phase, purpose, priority = _document_lifecycle(category)
                return ClassifiedDocument(
                    source=source,
                    document_type=document_type,
                    title=source.filename,
                    confidence=0.95,
                    reasons=reasons,
                    document_category=category,
                    lifecycle_phase=phase,
                    lifecycle_purpose=purpose,
                    document_priority=priority,
                )

    matches: list[tuple[DocumentType, int, list[str]]] = []

    for document_type, keywords in _CONTENT_RULES:
        matched_keywords = [
            keyword
            for keyword in keywords
            if _normalize(keyword) in text
        ]

        if matched_keywords:
            matches.append(
                (
                    document_type,
                    len(matched_keywords),
                    matched_keywords,
                )
            )

    if matches:
        matches.sort(key=lambda item: item[1], reverse=True)
        document_type, count, matched_keywords = matches[0]
        confidence = min(0.90, 0.55 + (count * 0.12))
        category = _document_category(document_type, source, text)
        phase, purpose, priority = _document_lifecycle(category)
        reasons.extend(f"content:{keyword}" for keyword in matched_keywords)
        return ClassifiedDocument(
            source=source,
            document_type=document_type,
            title=source.filename,
            confidence=confidence,
            reasons=reasons,
            document_category=category,
            lifecycle_phase=phase,
            lifecycle_purpose=purpose,
            document_priority=priority,
        )

    category = _document_category(DocumentType.UNKNOWN, source, text)
    phase, purpose, priority = _document_lifecycle(category)
    return ClassifiedDocument(
        source=source,
        document_type=DocumentType.UNKNOWN,
        title=source.filename,
        confidence=0.0,
        reasons=["no_rule_match"],
        document_category=category,
        lifecycle_phase=phase,
        lifecycle_purpose=purpose,
        document_priority=priority,
    )
