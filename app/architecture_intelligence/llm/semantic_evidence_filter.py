from __future__ import annotations

import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from .semantic_fact_filter import SemanticFactFilter


CANONICAL_VALUES = {
    "technical_assistance": "Assistência técnica",
    "execution_project": "Projeto de execução",
    "final_drawings": "Telas finais",
    "measurements": "Mapa de medições",
}

SINGLETON_SEMANTIC_TYPES = {
    "competition_prize",
    "contract_value",
    "design_services_value",
    "estimated_construction_cost",
    "execution_project",
    "final_drawings",
    "measurements",
    "procedure_value",
    "technical_assistance",
}

FINANCIAL_PATTERNS = (
    (
        "competition_prize",
        re.compile(
            r"(?:montante\s+global\s+dos\s+pr[eé]mios|"
            r"valor\s+global\s+dos\s+pr[eé]mios)"
            r"[^\d€]{0,30}(?:€\s*)?"
            r"(?P<amount>\d(?:[\d .]*\d)?(?:,\d{2})?)"
            r"(?:\s*(?:eur|euros?))?",
            re.IGNORECASE,
        ),
    ),
    (
        "procedure_value",
        re.compile(
            r"(?:valor\s+do\s+pre[cç]o\s+base\s+do\s+procedimento|"
            r"pre[cç]o\s+base\s+s/?iva)"
            r"[^\d€]{0,30}(?:€\s*)?"
            r"(?P<amount>\d(?:[\d .]*\d)?(?:,\d{2})?)"
            r"(?:\s*(?P<currency>eur|euros?))?",
            re.IGNORECASE,
        ),
    ),
    (
        "estimated_construction_cost",
        re.compile(
            r"(?:valor\s+de\s+obra|"
            r"custo\s+estimado\s+da\s+obra|"
            r"estimativa\s+de\s+custo\s+de\s+obra|"
            r"pre[cç]o\s+base\s+da\s+empreitada)"
            r"[^\d€]{0,50}(?:€\s*)?"
            r"(?P<amount>\d(?:[\d .]*\d)?(?:,\d{2})?)",
            re.IGNORECASE,
        ),
    ),
)


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _matching_evidences(
    excerpt: str,
    evidences: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_excerpt = _normalize(excerpt)
    if not normalized_excerpt:
        return []

    matches: list[dict[str, Any]] = []
    for evidence in evidences:
        evidence_excerpt = _normalize(evidence.get("excerpt"))
        if not evidence_excerpt:
            continue
        if (
            normalized_excerpt in evidence_excerpt
            or evidence_excerpt in normalized_excerpt
        ):
            matches.append(evidence)
    return matches


def _canonical_value(fact: dict[str, Any]) -> str:
    semantic_type = str(fact.get("semantic_type") or "")
    canonical = CANONICAL_VALUES.get(semantic_type)
    if canonical:
        return canonical
    return str(fact.get("value") or "").strip()


def _format_amount(raw: str) -> str:
    compact = re.sub(r"\s+", "", raw.strip())

    if "," in compact:
        integer, decimals = compact.rsplit(",", 1)
        integer = integer.replace(".", "")
        return f"{int(integer):,}".replace(",", " ") + f",{decimals}"

    integer = compact.replace(".", "")
    return f"{int(integer):,}".replace(",", " ")


def _deterministic_financial_facts(
    evidences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []

    for evidence in evidences:
        excerpt = str(evidence.get("excerpt") or "").strip()
        if not excerpt:
            continue

        for semantic_type, pattern in FINANCIAL_PATTERNS:
            match = pattern.search(excerpt)
            if not match:
                continue

            raw_amount = str(match.group("amount") or "").strip()
            try:
                formatted_amount = _format_amount(raw_amount)
            except (ValueError, InvalidOperation):
                continue

            currency = "EUR" if re.search(
                r"\bEUR\b",
                excerpt,
                re.IGNORECASE,
            ) else "€"

            facts.append(
                {
                    "semantic_type": semantic_type,
                    "value": (
                        f"{formatted_amount} EUR"
                        if currency == "EUR"
                        else f"€ {formatted_amount}"
                    ),
                    "source_excerpt": excerpt,
                    "confidence": 1.0,
                    "model_confidence": None,
                    "validated_confidence": min(
                        float(evidence.get("confidence") or 0.0),
                        0.95,
                    ),
                    "evidence_ids": (
                        [str(evidence["evidence_id"])]
                        if evidence.get("evidence_id")
                        else []
                    ),
                    "source_documents": (
                        [str(evidence["filename"])]
                        if evidence.get("filename")
                        else []
                    ),
                    "extraction_method": "deterministic_financial_rule",
                }
            )

    return facts


class SemanticEvidenceFilter:
    """Executa extração evidence-first e valida o resultado."""

    def __init__(
        self,
        semantic_filter: SemanticFactFilter | None = None,
    ) -> None:
        self.semantic_filter = semantic_filter or SemanticFactFilter()

    def filter_evidences(
        self,
        *,
        field_name: str,
        knowledge_block: str,
        evidences: list[dict[str, Any]],
        source_document: str = "",
    ) -> dict[str, Any]:
        usable = [
            evidence
            for evidence in evidences
            if isinstance(evidence, dict)
            and str(evidence.get("excerpt") or "").strip()
        ]

        if not usable:
            return {
                "status": "insufficient_evidence",
                "facts": [],
                "warnings": ["no_usable_evidences"],
                "prompt_version": "semantic-filter-v0.4",
            }

        deterministic_facts = (
            _deterministic_financial_facts(usable)
            if field_name == "financial_documents"
            else []
        )

        financial_llm_enabled = (
            os.getenv("SEMANTIC_FINANCIAL_LLM_ENABLED", "0")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"}
        )
        if (
            field_name == "financial_documents"
            and deterministic_facts
            and not financial_llm_enabled
        ):
            return {
                "status": "ok",
                "facts": self._deduplicate(deterministic_facts),
                "warnings": [
                    "ollama_skipped_deterministic_financial"
                ],
                "prompt_version": "semantic-filter-v0.5",
                "allowed_semantic_types": [],
            }

        item = {
            "field_name": field_name,
            "knowledge_block": knowledge_block,
            "source_document": source_document,
            "value": [
                evidence["excerpt"]
                for evidence in usable
            ],
        }
        result = self.semantic_filter.filter_item(item)

        validated: list[dict[str, Any]] = []

        for fact in result.get("facts") or []:
            matches = _matching_evidences(
                str(fact.get("source_excerpt") or ""),
                usable,
            )
            if not matches:
                continue

            source_confidence = max(
                (
                    float(evidence.get("confidence") or 0.0)
                    for evidence in matches
                ),
                default=0.0,
            )

            validated.append(
                {
                    **fact,
                    "value": _canonical_value(fact),
                    "model_confidence": fact.get("confidence"),
                    "validated_confidence": min(
                        source_confidence,
                        0.95,
                    ),
                    "evidence_ids": sorted(
                        {
                            str(evidence.get("evidence_id"))
                            for evidence in matches
                            if evidence.get("evidence_id")
                        }
                    ),
                    "source_documents": sorted(
                        {
                            str(evidence.get("filename"))
                            for evidence in matches
                            if evidence.get("filename")
                        }
                    ),
                    "extraction_method": "ollama_validated",
                }
            )

        deduplicated = self._deduplicate(
            deterministic_facts + validated
        )
        status = "ok" if deduplicated else result.get("status")
        if status == "ok" and not deduplicated:
            status = "insufficient_evidence"

        return {
            "status": status,
            "facts": deduplicated,
            "warnings": list(result.get("warnings") or []),
            "prompt_version": "semantic-filter-v0.4",
            "allowed_semantic_types": result.get(
                "allowed_semantic_types",
                [],
            ),
        }

    def _deduplicate(
        self,
        facts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        singleton_index: dict[str, int] = {}
        exact_index: dict[tuple[str, str], int] = {}

        for fact in facts:
            semantic_type = str(
                fact.get("semantic_type") or ""
            )
            normalized_value = _normalize(fact.get("value"))

            if semantic_type in SINGLETON_SEMANTIC_TYPES:
                existing_index = singleton_index.get(
                    semantic_type
                )
                if existing_index is None:
                    singleton_index[semantic_type] = len(result)
                    result.append(fact)
                    continue
                self._merge(result[existing_index], fact)
                continue

            key = (semantic_type, normalized_value)
            existing_index = exact_index.get(key)
            if existing_index is None:
                exact_index[key] = len(result)
                result.append(fact)
                continue
            self._merge(result[existing_index], fact)

        return result

    def _merge(
        self,
        existing: dict[str, Any],
        incoming: dict[str, Any],
    ) -> None:
        existing["evidence_ids"] = sorted(
            set(existing.get("evidence_ids") or [])
            | set(incoming.get("evidence_ids") or [])
        )
        existing["source_documents"] = sorted(
            set(existing.get("source_documents") or [])
            | set(incoming.get("source_documents") or [])
        )
        old_confidence = float(
            existing.get("validated_confidence") or 0.0
        )
        new_confidence = float(
            incoming.get("validated_confidence") or 0.0
        )
        existing["validated_confidence"] = max(
            old_confidence,
            new_confidence,
        )
        if new_confidence > old_confidence:
            existing["source_excerpt"] = incoming.get(
                "source_excerpt"
            )
