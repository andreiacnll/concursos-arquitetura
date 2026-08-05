from __future__ import annotations

import unittest

from app.architecture_intelligence.llm.provider import LLMProvider
from app.architecture_intelligence.llm.semantic_evidence_filter import (
    SemanticEvidenceFilter,
)
from app.architecture_intelligence.llm.semantic_fact_filter import (
    SemanticFactFilter,
)


class FakeProvider(LLMProvider):
    def __init__(self, response: dict) -> None:
        self.response = response

    def generate(self, payload: dict, schema: dict) -> dict:
        return self.response


class SemanticEvidenceFilterTests(unittest.TestCase):
    def make_filter(self, facts: list[dict] | None = None):
        provider = FakeProvider(
            {
                "status": "ok" if facts else "insufficient_evidence",
                "facts": facts or [],
                "discarded_fragments": [],
            }
        )
        return SemanticEvidenceFilter(
            SemanticFactFilter(provider=provider)
        )

    def test_extracts_competition_prize_deterministically(self) -> None:
        result = self.make_filter().filter_evidences(
            field_name="financial_documents",
            knowledge_block="financials",
            evidences=[
                {
                    "evidence_id": "prize-1",
                    "filename": "termos.pdf",
                    "excerpt": (
                        "O montante global dos prémios é de: "
                        "€ 26.000,00 (vinte e seis mil euros)."
                    ),
                    "confidence": 0.8,
                }
            ],
        )

        fact = result["facts"][0]
        self.assertEqual(
            fact["semantic_type"],
            "competition_prize",
        )
        self.assertEqual(fact["value"], "€ 26 000,00")
        self.assertEqual(
            fact["extraction_method"],
            "deterministic_financial_rule",
        )
        self.assertEqual(fact["evidence_ids"], ["prize-1"])

    def test_distinguishes_three_financial_meanings(self) -> None:
        result = self.make_filter().filter_evidences(
            field_name="financial_documents",
            knowledge_block="financials",
            evidences=[
                {
                    "evidence_id": "prize",
                    "excerpt": (
                        "O montante global dos prémios é de: "
                        "€ 26.000,00."
                    ),
                    "confidence": 0.8,
                },
                {
                    "evidence_id": "procedure",
                    "excerpt": (
                        "Valor do preço base do procedimento: "
                        "26.000,00 EUR"
                    ),
                    "confidence": 0.88,
                },
                {
                    "evidence_id": "construction",
                    "excerpt": (
                        "Deve ser considerado um valor de obra que "
                        "não deverá exceder de € 24 439 134."
                    ),
                    "confidence": 0.8,
                },
            ],
        )

        found = {
            fact["semantic_type"]: fact["value"]
            for fact in result["facts"]
        }
        self.assertEqual(
            set(found),
            {
                "competition_prize",
                "procedure_value",
                "estimated_construction_cost",
            },
        )
        self.assertEqual(
            found["estimated_construction_cost"],
            "€ 24 439 134",
        )

    def test_financial_rules_do_not_require_provider(self) -> None:
        class ProviderMustNotRun(LLMProvider):
            def generate(self, payload: dict, schema: dict) -> dict:
                raise AssertionError("O provider não devia ser chamado.")

        evidence_filter = SemanticEvidenceFilter(
            SemanticFactFilter(provider=ProviderMustNotRun())
        )
        result = evidence_filter.filter_evidences(
            field_name="financial_documents",
            knowledge_block="financials",
            evidences=[
                {
                    "evidence_id": "prize",
                    "excerpt": (
                        "O montante global dos prémios é de: "
                        "€ 26.000,00."
                    ),
                    "confidence": 0.8,
                }
            ],
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["facts"][0]["semantic_type"],
            "competition_prize",
        )
        self.assertIn(
            "ollama_skipped_deterministic_financial",
            result["warnings"],
        )

    def test_merges_llm_and_deterministic_same_value(self) -> None:
        result = self.make_filter(
            [
                {
                    "semantic_type": "procedure_value",
                    "value": "26.000,00 EUR",
                    "source_excerpt": (
                        "Valor do preço base do procedimento: "
                        "26.000,00 EUR"
                    ),
                    "confidence": 1.0,
                }
            ]
        ).filter_evidences(
            field_name="financial_documents",
            knowledge_block="financials",
            evidences=[
                {
                    "evidence_id": "ev-1",
                    "filename": "anuncio.pdf",
                    "excerpt": (
                        "Valor do preço base do procedimento: "
                        "26.000,00 EUR"
                    ),
                    "confidence": 0.88,
                }
            ],
        )

        self.assertEqual(len(result["facts"]), 1)
        fact = result["facts"][0]
        self.assertEqual(
            fact["semantic_type"],
            "procedure_value",
        )
        self.assertEqual(fact["evidence_ids"], ["ev-1"])

    def test_deduplicates_contract_fact(self) -> None:
        result = self.make_filter(
            [
                {
                    "semantic_type": "technical_assistance",
                    "value": "10% do preço contratual",
                    "source_excerpt": "Fase 5: Assistência Técnica",
                    "confidence": 1.0,
                },
                {
                    "semantic_type": "technical_assistance",
                    "value": "Assistência técnica em obra",
                    "source_excerpt": (
                        "A assistência técnica em fase de obra"
                    ),
                    "confidence": 1.0,
                },
            ]
        ).filter_evidences(
            field_name="technical_documents",
            knowledge_block="contract_deliverables",
            evidences=[
                {
                    "evidence_id": "ev-1",
                    "excerpt": "Fase 5: Assistência Técnica",
                    "confidence": 0.8,
                },
                {
                    "evidence_id": "ev-2",
                    "excerpt": (
                        "A assistência técnica em fase de obra"
                    ),
                    "confidence": 0.84,
                },
            ],
        )

        self.assertEqual(len(result["facts"]), 1)
        self.assertEqual(
            result["facts"][0]["value"],
            "Assistência técnica",
        )

    def test_rejects_unmatched_llm_excerpt(self) -> None:
        result = self.make_filter(
            [
                {
                    "semantic_type": "execution_project",
                    "value": "Projeto de execução",
                    "source_excerpt": "Texto inventado",
                    "confidence": 1.0,
                }
            ]
        ).filter_evidences(
            field_name="technical_documents",
            knowledge_block="contract_deliverables",
            evidences=[
                {
                    "evidence_id": "ev-1",
                    "excerpt": "Entrega do Projeto de Execução",
                    "confidence": 0.8,
                }
            ],
        )

        self.assertEqual(result["facts"], [])
        self.assertEqual(
            result["status"],
            "insufficient_evidence",
        )


if __name__ == "__main__":
    unittest.main()
