from __future__ import annotations

import json
import unittest

from app.architecture_intelligence.llm.provider import (
    LLMProvider,
    LLMProviderError,
)
from app.architecture_intelligence.llm.semantic_fact_filter import (
    SemanticFactFilter,
)


class FakeProvider(LLMProvider):
    def __init__(self, response: dict | None = None) -> None:
        self.response = response or {}
        self.calls = 0
        self.last_payload: dict | None = None

    def generate(self, payload: dict, schema: dict) -> dict:
        self.calls += 1
        self.last_payload = payload
        return self.response


class FailingProvider(LLMProvider):
    def generate(self, payload: dict, schema: dict) -> dict:
        raise LLMProviderError("offline")


class SemanticFactFilterTests(unittest.TestCase):
    def test_extracts_grounded_contract_facts(self) -> None:
        provider = FakeProvider(
            {
                "status": "ok",
                "facts": [
                    {
                        "semantic_type": "execution_project",
                        "value": "Projeto de execução",
                        "source_excerpt": "Entrega do Projeto de Execução",
                        "confidence": 0.96,
                    },
                    {
                        "semantic_type": "technical_assistance",
                        "value": "Assistência técnica",
                        "source_excerpt": "Assistência técnica à obra",
                        "confidence": 0.93,
                    },
                ],
                "discarded_fragments": [],
            }
        )
        semantic_filter = SemanticFactFilter(provider=provider)

        result = semantic_filter.filter_item(
            {
                "field_name": "phases_and_deliverables",
                "knowledge_block": "contract_deliverables",
                "value": (
                    "Fase 3 — Entrega do Projeto de Execução. "
                    "Fase 5 — Assistência técnica à obra."
                ),
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["facts"]), 2)
        self.assertEqual(provider.calls, 1)

    def test_rejects_type_not_allowed_for_field(self) -> None:
        provider = FakeProvider(
            {
                "status": "ok",
                "facts": [
                    {
                        "semantic_type": "submission_platform",
                        "value": "Plataforma",
                        "source_excerpt": "Entrega do projeto de execução",
                        "confidence": 0.9,
                    }
                ],
                "discarded_fragments": [],
            }
        )
        semantic_filter = SemanticFactFilter(provider=provider)

        result = semantic_filter.filter_item(
            {
                "field_name": "phases_and_deliverables",
                "value": "Entrega do projeto de execução",
            }
        )

        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["facts"], [])
        self.assertIn(
            "semantic_type_not_allowed_for_field:submission_platform",
            result["warnings"],
        )

    def test_rejects_excerpt_not_present_in_source(self) -> None:
        provider = FakeProvider(
            {
                "status": "ok",
                "facts": [
                    {
                        "semantic_type": "execution_project",
                        "value": "Projeto de execução",
                        "source_excerpt": "Frase que não existe",
                        "confidence": 0.9,
                    }
                ],
                "discarded_fragments": [],
            }
        )
        semantic_filter = SemanticFactFilter(provider=provider)

        result = semantic_filter.filter_item(
            {
                "field_name": "technical_documents",
                "value": "Entrega do projeto de execução.",
            }
        )

        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["facts"], [])
        self.assertIn(
            "ungrounded_excerpt:execution_project",
            result["warnings"],
        )

    def test_skips_document_alert_metadata(self) -> None:
        provider = FakeProvider()
        semantic_filter = SemanticFactFilter(provider=provider)

        result = semantic_filter.filter_item(
            {
                "field_name": "document_alerts.message",
                "value": "Aviso repetido",
            }
        )

        self.assertEqual(result["status"], "ignored_metadata")
        self.assertEqual(provider.calls, 0)

    def test_provider_error_has_safe_fallback(self) -> None:
        semantic_filter = SemanticFactFilter(
            provider=FailingProvider()
        )

        result = semantic_filter.filter_item(
            {
                "field_name": "physical_formats",
                "value": "Dois exemplares em papel.",
            }
        )

        self.assertEqual(result["status"], "provider_unavailable")
        self.assertEqual(result["facts"], [])
        self.assertEqual(result["warnings"], ["offline"])

    def test_contract_field_receives_small_allowlist(self) -> None:
        provider = FakeProvider(
            {
                "status": "insufficient_evidence",
                "facts": [],
                "discarded_fragments": [],
            }
        )
        semantic_filter = SemanticFactFilter(provider=provider)

        semantic_filter.filter_item(
            {
                "field_name": "phases_and_deliverables",
                "value": "Fase 3 — Projeto de execução",
            }
        )

        user_payload = json.loads(provider.last_payload["user"])
        allowed = user_payload["allowed_semantic_types"]

        self.assertIn("execution_project", allowed)
        self.assertIn("technical_assistance", allowed)
        self.assertNotIn("submission_platform", allowed)
        self.assertNotIn("competition_prize", allowed)

    def test_compacts_large_noisy_value_around_anchors(self) -> None:
        provider = FakeProvider(
            {
                "status": "insufficient_evidence",
                "facts": [],
                "discarded_fragments": [],
            }
        )
        semantic_filter = SemanticFactFilter(provider=provider)

        result = semantic_filter.filter_item(
            {
                "field_name": "phases_and_deliverables",
                "value": [
                    "texto irrelevante sem conteúdo contratual",
                    "Fase 3 — Entrega do Projeto de Execução",
                    "mais ruído documental",
                    "Fase 5 — Assistência técnica à obra",
                ],
            }
        )

        self.assertEqual(
            result["fragments_sent"],
            [
                "Fase 3 — Entrega do Projeto de Execução",
                "Fase 5 — Assistência técnica à obra",
            ],
        )


if __name__ == "__main__":
    unittest.main()
