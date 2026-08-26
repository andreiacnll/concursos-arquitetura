from __future__ import annotations

import json
from typing import Any

from .company_extractor import (
    CompanyExtractionResult,
    ExtractedFact,
    extract_company_information,
)
from .knowledge_storage import (
    get_knowledge_by_field,
    save_knowledge_fact,
)
from .models import CompanyProfile
from .profile_builder import apply_extraction_to_profile
from .profile_storage import (
    guardar_company_profile,
    obter_company_profile,
)


def _valor_canonico(valor: Any) -> str:
    if hasattr(valor, "model_dump"):
        valor = valor.model_dump()
    return json.dumps(valor, ensure_ascii=False, sort_keys=True)


def _facto_ja_guardado(
    company_id: int,
    fact: ExtractedFact,
    source_type: str,
) -> bool:
    factos_existentes = get_knowledge_by_field(company_id, fact.field)
    valor_atual = _valor_canonico(fact.value)
    origem_atual = str(fact.source or "").strip()
    tipo_atual = str(source_type or "").strip()
    estado_atual = str(fact.status or "unknown").strip()
    url_atual = str(fact.url or "").strip()
    section_atual = str(fact.section or "").strip()

    for existente in factos_existentes:
        if _valor_canonico(existente.value) != valor_atual:
            continue
        if str(existente.source or "").strip() != origem_atual:
            continue
        if str(existente.source_type or "").strip() != tipo_atual:
            continue
        if str(existente.status or "unknown").strip() != estado_atual:
            continue
        if str(existente.url or "").strip() != url_atual:
            continue
        if str(existente.section or "").strip() != section_atual:
            continue
        return True

    return False


def _guardar_factos_no_conhecimento(
    company_id: int,
    extraction: CompanyExtractionResult,
    source: str,
) -> list[Any]:
    source_text = str(source or "").strip().lower()
    if source_text.startswith("website:"):
        source_type = "website"
    elif source_text.startswith("portfolio:"):
        source_type = "portfolio"
    elif source_text.startswith("institutional:"):
        source_type = "document"
    else:
        source_type = "document"

    factos_guardados: list[Any] = []

    for fact in extraction.facts:
        if not fact.source:
            fact.source = source

        if _facto_ja_guardado(company_id, fact, source_type):
            continue

        facto_guardado = save_knowledge_fact(
            company_id=company_id,
            field=fact.field,
            value=fact.value,
            source=fact.source or source,
            source_type=source_type,
            url=fact.url,
            section=fact.section,
            evidence_text=fact.evidence_text,
            confidence=fact.confidence,
            status=fact.status,
        )
        factos_guardados.append(facto_guardado)

    return factos_guardados


def ingest_company_information(
    company_id: int,
    text: str,
    source: str = "",
    project_names: list[str] | None = None,
    section_urls: dict[str, str] | None = None,
    section_evidence: dict[str, str] | None = None,
    company_identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Orquestra a ingestão de informação empresarial.

    Fluxo:
    - texto documental;
    - extractor determinístico;
    - knowledge memory rastreável;
    - builder de CompanyProfile;
    - persistência do profile.
    """
    current_profile = obter_company_profile(company_id)
    identity_context = company_identity or {
        "company_name": current_profile.identity.company_name,
        "website": current_profile.identity.website,
        "location": current_profile.identity.location,
    }

    extraction = extract_company_information(
        text,
        source=source,
        project_names=project_names,
        section_urls=section_urls,
        section_evidence=section_evidence,
        company_identity=identity_context,
    )

    if not isinstance(extraction, CompanyExtractionResult):
        return {
            "profile": current_profile,
            "extraction": extraction,
            "facts_created": 0,
            "saved_facts": [],
        }

    if not text or not extraction.facts:
        return {
            "profile": current_profile,
            "extraction": extraction,
            "facts_created": 0,
            "saved_facts": [],
        }

    factos_guardados = _guardar_factos_no_conhecimento(
        company_id,
        extraction,
        source,
    )

    updated_profile = apply_extraction_to_profile(
        current_profile,
        extraction,
    )

    if isinstance(updated_profile, CompanyProfile):
        persisted_profile = guardar_company_profile(
            company_id,
            updated_profile,
        )
    else:
        persisted_profile = current_profile

    return {
        "profile": persisted_profile,
        "extraction": extraction,
        "facts_created": len(factos_guardados),
        "saved_facts": factos_guardados,
    }
