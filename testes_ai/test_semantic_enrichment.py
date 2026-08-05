from __future__ import annotations

import unittest

from app.architecture_intelligence.semantic_enrichment import (
    EvidenceTopic,
    enrich_consolidated_semantics,
    select_topic_evidences,
)
from app.architecture_intelligence.schemas import (
    ConsolidatedCompetitionData,
    Evidence,
)


class FakeEvidenceFilter:
    def filter_evidences(self, **kwargs):
        field_name = kwargs["field_name"]
        if field_name == "financial_documents":
            facts = [
                {
                    "semantic_type": "competition_prize",
                    "value": "€ 26 000,00",
                    "validated_confidence": 0.8,
                    "evidence_ids": ["prize"],
                    "source_documents": ["terms.pdf"],
                },
                {
                    "semantic_type": "estimated_construction_cost",
                    "value": "€ 24 439 134",
                    "validated_confidence": 0.82,
                    "evidence_ids": ["construction"],
                    "source_documents": ["ce.pdf"],
                },
            ]
        elif field_name == "physical_formats":
            facts = [
                {
                    "semantic_type": "submission_panel_quantity",
                    "value": "3",
                    "validated_confidence": 0.81,
                    "evidence_ids": ["panels"],
                    "source_documents": ["terms.pdf"],
                }
            ]
        else:
            facts = [
                {
                    "semantic_type": "execution_project",
                    "value": "Projeto de execução",
                    "validated_confidence": 0.84,
                    "evidence_ids": ["contract"],
                    "source_documents": ["ce.pdf"],
                }
            ]
        return {
            "status": "ok",
            "facts": facts,
            "warnings": [],
            "prompt_version": "fake",
        }


class FailingEvidenceFilter:
    def filter_evidences(self, **kwargs):
        raise RuntimeError("offline")


class SemanticEnrichmentTests(unittest.TestCase):
    def base_data(self):
        return ConsolidatedCompetitionData(
            evidences=[
                Evidence(
                    evidence_id="prize",
                    source_document_id="doc-terms",
                    filename="terms.pdf",
                    excerpt=(
                        "O montante global dos prémios é "
                        "€ 26.000,00."
                    ),
                    confidence=0.8,
                ),
                Evidence(
                    evidence_id="construction",
                    source_document_id="doc-ce",
                    filename="ce.pdf",
                    excerpt=(
                        "Valor de obra que não deverá exceder "
                        "€ 24 439 134."
                    ),
                    confidence=0.82,
                ),
                Evidence(
                    evidence_id="panels",
                    source_document_id="doc-terms",
                    filename="terms.pdf",
                    excerpt="Três ficheiros, um por cada painel A1.",
                    confidence=0.81,
                ),
                Evidence(
                    evidence_id="contract",
                    source_document_id="doc-ce",
                    filename="ce.pdf",
                    excerpt="Entrega do Projeto de Execução.",
                    confidence=0.84,
                ),
            ]
        )

    def test_disabled_preserves_model(self):
        data = self.base_data()
        enriched, report = enrich_consolidated_semantics(
            data,
            enabled=False,
        )
        self.assertIs(enriched, data)
        self.assertEqual(report["status"], "disabled")

    def test_enriches_prices_information_model_and_intents(self):
        enriched, report = enrich_consolidated_semantics(
            self.base_data(),
            enabled=True,
            evidence_filter=FakeEvidenceFilter(),
        )
        self.assertEqual(report["status"], "ok")
        self.assertIn("competition_prizes", enriched.prices)
        self.assertIn(
            "estimated_construction_cost",
            enriched.prices,
        )
        fields = {
            item.field_name
            for item in enriched.information_model
            if item.reader_name == "semantic_evidence_filter"
        }
        self.assertIn("competition_prize", fields)
        self.assertIn("execution_project", fields)
        self.assertIn(
            "understand_financials",
            enriched.knowledge_intents,
        )
        self.assertIn(
            "understand_contract",
            enriched.knowledge_intents,
        )

    def test_failure_is_non_blocking(self):
        data = self.base_data()
        enriched, report = enrich_consolidated_semantics(
            data,
            enabled=True,
            evidence_filter=FailingEvidenceFilter(),
        )
        self.assertEqual(
            report["status"],
            "insufficient_evidence",
        )
        self.assertEqual(
            enriched.model_dump(mode="json"),
            data.model_dump(mode="json"),
        )
        self.assertTrue(report["warnings"])

    def test_selection_is_ranked_and_bounded(self):
        topic = EvidenceTopic(
            "test",
            "financial_documents",
            "financials",
            "administrative",
            "test",
            (r"preco", r"procedimento"),
            1,
        )
        selected = select_topic_evidences(
            [
                {
                    "evidence_id": "weak",
                    "excerpt": "Preço indicado.",
                    "confidence": 0.9,
                },
                {
                    "evidence_id": "strong",
                    "excerpt": "Preço base do procedimento.",
                    "confidence": 0.8,
                },
            ],
            topic,
        )
        self.assertEqual(
            selected[0]["evidence_id"],
            "strong",
        )
        self.assertEqual(len(selected), 1)


if __name__ == "__main__":
    unittest.main()
