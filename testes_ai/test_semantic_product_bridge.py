from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.analise.semantic_product_bridge import (
    attach_semantic_product_data,
    build_compact_consolidated,
)
from app.architecture_intelligence.llm.presentation_builder import (
    PresentationBuilder,
    SECTION_ORDER_TEMPLATES,
)
from app.architecture_intelligence.schemas import (
    ConsolidatedCompetitionData,
    Evidence,
    InformationItem,
)


class SemanticProductBridgeTests(unittest.TestCase):
    def enriched_data(self):
        return ConsolidatedCompetitionData(
            document_quality="complete",
            procedure_identity={
                "procedure_type": {
                    "value": "Concurso de conceção"
                }
            },
            prices={
                "competition_prizes": {
                    "value": "€ 26 000,00"
                },
                "procedure_value": {
                    "value": "€ 26 000,00"
                },
                "estimated_construction_cost": {
                    "value": "€ 24 439 134"
                },
            },
            information_model=[
                InformationItem(
                    field_name="competition_prize",
                    value="€ 26 000,00",
                    normalized_value="26000",
                    knowledge_block="financials",
                    phase="administrative",
                    purpose="compreender valores",
                    source_document="termos.pdf",
                    source_document_id="doc-1",
                    confidence=0.8,
                    evidence_ids=["ev-prize"],
                    reader_name="semantic_evidence_filter",
                ),
                InformationItem(
                    field_name="submission_panel_quantity",
                    value="3",
                    normalized_value="3",
                    knowledge_block="submission_deliverables",
                    phase="submission",
                    purpose="preparar candidatura",
                    source_document="termos.pdf",
                    source_document_id="doc-1",
                    confidence=0.81,
                    evidence_ids=["ev-panel"],
                    reader_name="semantic_evidence_filter",
                ),
                InformationItem(
                    field_name="execution_project",
                    value="Projeto de execução",
                    normalized_value="projeto de execucao",
                    knowledge_block="contract_deliverables",
                    phase="contract_execution",
                    purpose="compreender contrato",
                    source_document="ce.pdf",
                    source_document_id="doc-2",
                    confidence=0.84,
                    evidence_ids=["ev-contract"],
                    reader_name="semantic_evidence_filter",
                ),
            ],
            evidences=[
                Evidence(
                    evidence_id="ev-prize",
                    source_document_id="doc-1",
                    filename="termos.pdf",
                    excerpt=(
                        "Montante global dos prémios: "
                        "€ 26.000,00"
                    ),
                    confidence=0.8,
                ),
                Evidence(
                    evidence_id="ev-panel",
                    source_document_id="doc-1",
                    filename="termos.pdf",
                    excerpt="Três ficheiros, um por painel A1",
                    confidence=0.81,
                ),
                Evidence(
                    evidence_id="ev-contract",
                    source_document_id="doc-2",
                    filename="ce.pdf",
                    excerpt="Entrega do Projeto de Execução",
                    confidence=0.84,
                ),
            ],
        )

    def test_disabled_does_not_mutate_ficha(self):
        ficha = {}
        result = attach_semantic_product_data(
            textos={"termos.txt": "Painéis A1"},
            ficha=ficha,
            enabled=False,
        )
        self.assertEqual(result["status"], "disabled")
        self.assertEqual(ficha, {})

    def test_builds_small_semantic_consolidated(self):
        compact = build_compact_consolidated(
            self.enriched_data()
        )
        self.assertIn(
            "competition_prizes",
            compact.prices,
        )
        self.assertEqual(
            len(compact.information_model),
            3,
        )
        self.assertTrue(
            compact.submission_checklist["technical"]
        )
        values = [
            item.get("value")
            for item in compact.phases_and_deliverables
        ]
        self.assertIn("Projeto de execução", values)

    def test_attaches_data_and_caches_presentation(self):
        enriched = self.enriched_data()

        def runner(sources, write_debug_exports=True):
            self.assertFalse(write_debug_exports)
            return SimpleNamespace(
                consolidated=ConsolidatedCompetitionData(
                    evidences=enriched.evidences
                ).model_dump(mode="json")
            )

        def enricher(base, enabled=None):
            self.assertTrue(enabled)
            return enriched, {
                "status": "ok",
                "version": "test",
                "facts_total": 3,
                "information_items_added": 3,
                "warnings": [],
                "groups": [],
            }

        cache_dir = Path(tempfile.mkdtemp())
        builder = PresentationBuilder(
            cache_dir=cache_dir
        )
        ficha = {"document_insights": {}}
        report = attach_semantic_product_data(
            textos={"termos.txt": "Painéis A1"},
            ficha=ficha,
            enabled=True,
            runner=runner,
            enricher=enricher,
            presentation_builder=builder,
        )

        self.assertEqual(report["status"], "ok")
        intelligence = ficha["architecture_intelligence"]
        self.assertIn("consolidated", intelligence)
        self.assertIn("presentation", intelligence)
        self.assertTrue(list(cache_dir.glob("*.json")))
        self.assertIn(
            "semantic_summary",
            ficha["document_insights"],
        )

    def test_design_competition_shows_financial_card(self):
        self.assertIn(
            "financial_conditions",
            SECTION_ORDER_TEMPLATES[
                "design_competition"
            ],
        )


if __name__ == "__main__":
    unittest.main()
