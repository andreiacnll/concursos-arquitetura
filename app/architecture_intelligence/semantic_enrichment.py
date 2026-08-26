from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from .knowledge_router import get_default_router
from .llm.semantic_evidence_filter import SemanticEvidenceFilter
from .schemas import ConsolidatedCompetitionData, Evidence, InformationItem


TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class EvidenceTopic:
    topic_id: str
    field_name: str
    knowledge_block: str
    phase: str
    purpose: str
    patterns: tuple[str, ...]
    limit: int


TOPICS = (
    EvidenceTopic(
        "financial_core",
        "financial_documents",
        "financials",
        "administrative",
        "compreender valores financeiros",
        (
            r"\bpremios?\b",
            r"montante global dos premios",
            r"preco base do procedimento",
            r"valor do preco base do procedimento",
            r"preco base s iva",
            r"valor de obra",
            r"custo estimado da obra",
            r"estimativa de custo de obra",
            r"preco base da empreitada",
            r"preco contratual",
            r"\bpagamento\b",
        ),
        28,
    ),
    EvidenceTopic(
        "submission_panels",
        "physical_formats",
        "submission_deliverables",
        "submission",
        "preparar candidatura",
        (
            r"\bpaineis?\b",
            r"\bpranchas?\b",
            r"formato a[0-4]\b",
            r"um por cada painel",
            r"ficheiros?.{0,40}painel",
            r"formato \.jpg",
            r"formato \.pdf",
        ),
        20,
    ),
    EvidenceTopic(
        "contract_deliverables",
        "technical_documents",
        "contract_deliverables",
        "contract_execution",
        "compreender execução do contrato",
        (
            r"projeto de execucao",
            r"\banteprojeto\b",
            r"estudo previo",
            r"assistencia tecnica",
            r"telas finais",
            r"mapa de medicoes",
            r"mapa de quantidades",
            r"estimativa orcamental",
            r"\bbim\b",
            r"aprovacao.{0,60}projeto",
        ),
        28,
    ),
)


def semantic_enrichment_enabled() -> bool:
    return (
        os.getenv("SEMANTIC_EVIDENCE_ENABLED", "0")
        .strip()
        .lower()
        in TRUE_VALUES
    )


def enrich_consolidated_semantics(
    consolidated: ConsolidatedCompetitionData,
    *,
    enabled: bool | None = None,
    evidence_filter: Any | None = None,
) -> tuple[ConsolidatedCompetitionData, dict[str, Any]]:
    active = semantic_enrichment_enabled() if enabled is None else enabled
    if not active:
        return consolidated, _report("disabled", [], [], 0)

    evidences = [
        _evidence_dict(item)
        for item in consolidated.evidences or []
    ]
    evidences = [item for item in evidences if item.get("excerpt")]
    if not evidences:
        return consolidated, _report(
            "insufficient_evidence",
            [],
            ["no_consolidated_evidences"],
            0,
        )

    evidence_by_id = {
        str(item["evidence_id"]): item
        for item in evidences
        if item.get("evidence_id")
    }
    semantic_filter = evidence_filter or SemanticEvidenceFilter()
    facts: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    warnings: list[str] = []

    for topic in TOPICS:
        selected = select_topic_evidences(evidences, topic)
        if not selected:
            groups.append(
                {
                    "topic_id": topic.topic_id,
                    "status": "no_matching_evidence",
                    "evidences_selected": 0,
                    "facts": [],
                    "warnings": [],
                }
            )
            continue

        try:
            result = semantic_filter.filter_evidences(
                field_name=topic.field_name,
                knowledge_block=topic.knowledge_block,
                evidences=selected,
                source_document=" | ".join(
                    sorted(
                        {
                            str(item.get("filename"))
                            for item in selected
                            if item.get("filename")
                        }
                    )
                ),
            )
        except Exception as exc:
            message = (
                f"{topic.topic_id}:semantic_filter_error:"
                f"{type(exc).__name__}:{exc}"
            )
            warnings.append(message)
            groups.append(
                {
                    "topic_id": topic.topic_id,
                    "status": "error",
                    "evidences_selected": len(selected),
                    "facts": [],
                    "warnings": [message],
                }
            )
            continue

        group_facts = []
        for raw in result.get("facts") or []:
            if not raw.get("semantic_type"):
                continue
            fact = {
                **dict(raw),
                "_knowledge_block": topic.knowledge_block,
                "_phase": topic.phase,
                "_purpose": topic.purpose,
            }
            facts.append(fact)
            group_facts.append(_public_fact(fact))

        group_warnings = list(result.get("warnings") or [])
        warnings.extend(
            f"{topic.topic_id}:{item}"
            for item in group_warnings
        )
        groups.append(
            {
                "topic_id": topic.topic_id,
                "status": result.get("status"),
                "evidences_selected": len(selected),
                "facts": group_facts,
                "warnings": group_warnings,
                "prompt_version": result.get("prompt_version"),
            }
        )

    facts = _dedupe_facts(facts)
    if not facts:
        return consolidated, _report(
            "insufficient_evidence",
            groups,
            warnings,
            0,
        )

    payload = consolidated.model_dump(mode="json")
    payload["prices"] = _enrich_prices(
        dict(payload.get("prices") or {}),
        facts,
        evidence_by_id,
    )

    old_items = list(payload.get("information_model") or [])
    new_items = [
        _fact_to_information_item(
            fact,
            evidence_by_id,
            payload.get("document_index") or [],
        )
        for fact in facts
    ]
    merged_items = _merge_information_items(old_items, new_items)
    payload["information_model"] = merged_items
    payload["knowledge_intents"] = (
        get_default_router().group_by_intent(merged_items)
    )

    enriched = ConsolidatedCompetitionData.model_validate(payload)
    report = _report("ok", groups, warnings, len(facts))
    report["information_items_added"] = (
        len(merged_items) - len(old_items)
    )
    return enriched, report


def select_topic_evidences(
    evidences: Iterable[dict[str, Any]],
    topic: EvidenceTopic,
) -> list[dict[str, Any]]:
    patterns = tuple(re.compile(item) for item in topic.patterns)
    ranked: list[tuple[int, float, str, dict[str, Any]]] = []

    for evidence in evidences:
        excerpt = str(evidence.get("excerpt") or "").strip()
        if not excerpt:
            continue
        normalized = _normalize(excerpt)
        hits = sum(
            1 for pattern in patterns if pattern.search(normalized)
        )
        if hits:
            ranked.append(
                (
                    hits,
                    float(evidence.get("confidence") or 0.0),
                    str(evidence.get("evidence_id") or ""),
                    evidence,
                )
            )

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, _, _, evidence in ranked:
        signature = str(evidence.get("evidence_id") or "")
        signature = signature or _normalize(evidence.get("excerpt"))
        if not signature or signature in seen:
            continue
        seen.add(signature)
        selected.append(evidence)
        if len(selected) >= topic.limit:
            break
    return selected


def _report(
    status: str,
    groups: list[dict[str, Any]],
    warnings: list[str],
    facts_total: int,
) -> dict[str, Any]:
    return {
        "status": status,
        "version": "semantic-enrichment-v0.1",
        "facts_total": facts_total,
        "groups": groups,
        "warnings": warnings,
    }


def _evidence_dict(value: Evidence | dict[str, Any]) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else value.model_dump(mode="json")


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char for char in text if not unicodedata.combining(char)
    )
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _public_fact(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in fact.items()
        if not key.startswith("_")
    }


def _dedupe_facts(
    facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    indexes: dict[tuple[str, str], int] = {}
    for fact in facts:
        key = (
            str(fact.get("semantic_type") or ""),
            _normalize(fact.get("value")),
        )
        if not all(key):
            continue
        index = indexes.get(key)
        if index is None:
            indexes[key] = len(result)
            result.append(fact)
            continue
        current = result[index]
        current["evidence_ids"] = sorted(
            set(current.get("evidence_ids") or [])
            | set(fact.get("evidence_ids") or [])
        )
        current["source_documents"] = sorted(
            set(current.get("source_documents") or [])
            | set(fact.get("source_documents") or [])
        )
        current["validated_confidence"] = max(
            float(current.get("validated_confidence") or 0.0),
            float(fact.get("validated_confidence") or 0.0),
        )
    return result


def _fact_to_information_item(
    fact: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
    document_index: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_ids = [
        str(item) for item in fact.get("evidence_ids") or []
    ]
    evidence = next(
        (
            evidence_by_id[item]
            for item in evidence_ids
            if item in evidence_by_id
        ),
        {},
    )
    document_id = str(evidence.get("source_document_id") or "")
    document = next(
        (
            item
            for item in document_index
            if str(item.get("document_id") or "") == document_id
        ),
        {},
    )
    source_document = str(evidence.get("filename") or "")
    if not source_document:
        source_document = next(
            iter(fact.get("source_documents") or []),
            "",
        )

    return InformationItem(
        field_name=str(fact.get("semantic_type") or ""),
        value=fact.get("value"),
        normalized_value=_normalize(fact.get("value")),
        knowledge_block=str(
            fact.get("_knowledge_block") or "other"
        ),
        phase=str(fact.get("_phase") or "administrative"),
        purpose=str(
            fact.get("_purpose") or "compreender concurso"
        ),
        source_document=source_document,
        source_document_id=document_id,
        document_category=str(
            document.get("document_category") or "Outros"
        ),
        confidence=min(
            float(fact.get("validated_confidence") or 0.0),
            1.0,
        ),
        evidence_ids=evidence_ids,
        document_priority=int(
            document.get("document_priority") or 0
        ),
        reader_name="semantic_evidence_filter",
        section="semantic_evidence",
    ).model_dump(mode="json")


def _merge_information_items(
    existing: list[dict[str, Any]],
    new_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = list(existing)
    seen = {
        (
            str(item.get("field_name") or ""),
            _normalize(item.get("normalized_value")),
            tuple(sorted(item.get("evidence_ids") or [])),
        )
        for item in result
    }
    for item in new_items:
        signature = (
            str(item.get("field_name") or ""),
            _normalize(item.get("normalized_value")),
            tuple(sorted(item.get("evidence_ids") or [])),
        )
        if signature not in seen:
            seen.add(signature)
            result.append(item)
    return result


def _enrich_prices(
    prices: dict[str, Any],
    facts: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    updated = dict(prices)
    for fact in facts:
        semantic_type = str(fact.get("semantic_type") or "")
        if semantic_type == "competition_prize":
            _append_prize(updated, fact, evidence_by_id)
        elif semantic_type in {
            "procedure_value",
            "design_services_value",
            "estimated_construction_cost",
        }:
            _fill_scalar_price(
                updated,
                semantic_type,
                fact,
                evidence_by_id,
            )
    return updated


def _fact_evidences(
    fact: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        evidence_by_id[item]
        for item in fact.get("evidence_ids") or []
        if item in evidence_by_id
    ]


def _scalar_entry(
    field_name: str,
    fact: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    evidences = _fact_evidences(fact, evidence_by_id)
    return {
        "field": field_name,
        "kind": "scalar",
        "value": fact.get("value"),
        "normalized_value": _normalize(fact.get("value")),
        "confidence": float(
            fact.get("validated_confidence") or 0.0
        ),
        "conflict": False,
        "alternatives": [],
        "evidences": evidences,
        "source_readers": ["semantic_evidence_filter"],
        "document_ids": sorted(
            {
                str(item.get("source_document_id"))
                for item in evidences
                if item.get("source_document_id")
            }
        ),
    }


def _fill_scalar_price(
    prices: dict[str, Any],
    field_name: str,
    fact: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    candidate = _scalar_entry(field_name, fact, evidence_by_id)
    existing = prices.get(field_name)
    if not isinstance(existing, dict):
        prices[field_name] = candidate
        return

    if _normalize(existing.get("value")) == _normalize(
        candidate.get("value")
    ):
        existing["confidence"] = max(
            float(existing.get("confidence") or 0.0),
            float(candidate.get("confidence") or 0.0),
        )
        existing["evidences"] = _merge_evidences(
            list(existing.get("evidences") or [])
            + list(candidate.get("evidences") or [])
        )
        return

    alternatives = list(existing.get("alternatives") or [])
    alternatives.append(candidate)
    existing["alternatives"] = alternatives
    existing["conflict"] = True


def _append_prize(
    prices: dict[str, Any],
    fact: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    item = _scalar_entry(
        "competition_prizes",
        fact,
        evidence_by_id,
    )
    item.pop("field", None)
    item.pop("kind", None)
    item.pop("conflict", None)
    item.pop("alternatives", None)

    existing = prices.get("competition_prizes")
    if not isinstance(existing, dict):
        prices["competition_prizes"] = {
            "field": "competition_prizes",
            "kind": "list",
            "value": [item],
            "normalized_value": [item["normalized_value"]],
            "confidence": item["confidence"],
            "conflict": False,
            "alternatives": [],
            "evidences": item["evidences"],
            "source_readers": ["semantic_evidence_filter"],
            "document_ids": item["document_ids"],
        }
        return

    values = list(existing.get("value") or [])
    signatures = {
        _normalize(
            value.get("value")
            if isinstance(value, dict)
            else value
        )
        for value in values
    }
    if item["normalized_value"] not in signatures:
        values.append(item)
    existing["value"] = values
    existing["normalized_value"] = [
        _normalize(
            value.get("value")
            if isinstance(value, dict)
            else value
        )
        for value in values
    ]
    existing["confidence"] = max(
        float(existing.get("confidence") or 0.0),
        float(item.get("confidence") or 0.0),
    )
    existing["evidences"] = _merge_evidences(
        list(existing.get("evidences") or [])
        + list(item.get("evidences") or [])
    )


def _merge_evidences(
    values: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        evidence_id = str(value.get("evidence_id") or "")
        if evidence_id and evidence_id not in seen:
            seen.add(evidence_id)
            result.append(value)
    return result
