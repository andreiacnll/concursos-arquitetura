from __future__ import annotations

import unittest
from unittest.mock import patch

from app.architecture_intelligence.consolidator import Consolidator
from app.architecture_intelligence.schemas import (
    ConsolidatedCompetitionData,
    InformationItem,
)


class KnowledgeRouterPipelineTests(unittest.TestCase):
    def test_schema_keeps_backward_compatible_default(self) -> None:
        data = ConsolidatedCompetitionData()

        self.assertEqual(data.information_model, [])
        self.assertEqual(data.knowledge_intents, {})

    def test_consolidator_adds_parallel_knowledge_intents(self) -> None:
        information_item = InformationItem(
            field_name="submission_checklist.drawing_requirements",
            value="Entrega de quatro painéis em formato A1",
            normalized_value="entrega de quatro paineis em formato a1",
            knowledge_block="submission_deliverables",
            phase="submission",
            purpose="preparar candidatura",
            section="drawing_rules",
            confidence=0.9,
        ).model_dump(mode="json")

        with patch.object(
            Consolidator,
            "_build_information_model",
            return_value=[information_item],
        ):
            result = Consolidator().consolidate([])

        self.assertEqual(len(result.information_model), 1)
        self.assertIn("prepare_submission", result.knowledge_intents)

        routed = result.knowledge_intents["prepare_submission"][0]
        self.assertEqual(routed["knowledge_intent"], "prepare_submission")
        self.assertIn(
            routed["semantic_type"],
            {"submission_panel", "submission_panel_format"},
        )
        self.assertTrue(routed["routing"]["deterministic"])

    def test_current_information_model_is_not_replaced(self) -> None:
        information_item = InformationItem(
            field_name="prices.estimated_construction_cost",
            value=24439134,
            normalized_value=24439134,
            knowledge_block="financials",
            phase="submission",
            purpose="compreender o projeto",
            section="prices",
            confidence=0.95,
        ).model_dump(mode="json")

        with patch.object(
            Consolidator,
            "_build_information_model",
            return_value=[information_item],
        ):
            result = Consolidator().consolidate([])

        original = result.information_model[0]
        self.assertEqual(
            original.field_name,
            "prices.estimated_construction_cost",
        )
        self.assertFalse(hasattr(original, "semantic_type"))

        routed = result.knowledge_intents["understand_project"][0]
        self.assertEqual(
            routed["semantic_type"],
            "estimated_construction_cost",
        )


if __name__ == "__main__":
    unittest.main()
