from __future__ import annotations

import unittest

from app.architecture_intelligence.knowledge_router import KnowledgeRouter
from app.architecture_intelligence.schemas import InformationItem


class KnowledgeRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.router = KnowledgeRouter()

    def test_routes_estimated_construction_cost(self) -> None:
        item = InformationItem(
            field_name="prices.estimated_construction_cost",
            value=24439134,
            knowledge_block="financials",
        )

        routed = self.router.route_item(item)

        self.assertEqual(
            routed["semantic_type"],
            "estimated_construction_cost",
        )
        self.assertEqual(
            routed["knowledge_intent"],
            "understand_project",
        )
        self.assertEqual(routed["knowledge_block"], "financials")

    def test_separates_submission_panels_from_contract_work(self) -> None:
        panel = InformationItem(
            field_name="submission_checklist.drawing_requirements",
            value="Entrega de quatro painéis em formato A1",
            knowledge_block="submission_deliverables",
        )
        execution = InformationItem(
            field_name="phases_and_deliverables.deliverables_by_phase",
            value="Projeto de execução e assistência técnica",
            knowledge_block="contract_deliverables",
        )

        routed_panel = self.router.route_item(panel)
        routed_execution = self.router.route_item(execution)

        self.assertEqual(
            routed_panel["knowledge_intent"],
            "prepare_submission",
        )
        self.assertIn(
            routed_panel["semantic_type"],
            {"submission_panel", "submission_panel_format"},
        )
        self.assertEqual(
            routed_execution["semantic_type"],
            "execution_project",
        )
        self.assertEqual(
            routed_execution["knowledge_intent"],
            "understand_contract",
        )

    def test_keeps_prize_and_construction_cost_distinct(self) -> None:
        prize = self.router.route_item(
            {
                "field_name": "prices.competition_prizes",
                "value": [{"rank": 1, "amount": 26000}],
                "knowledge_block": "awards",
            }
        )
        construction = self.router.route_item(
            {
                "field_name": "prices.estimated_construction_cost",
                "value": 24439134,
                "knowledge_block": "financials",
            }
        )

        self.assertEqual(prize["semantic_type"], "competition_prize")
        self.assertEqual(
            construction["semantic_type"],
            "estimated_construction_cost",
        )
        self.assertNotEqual(
            prize["semantic_type"],
            construction["semantic_type"],
        )

    def test_unknown_field_preserves_existing_block(self) -> None:
        routed = self.router.route_item(
            {
                "field_name": "custom.future_field",
                "value": "Informação ainda não tipificada",
                "knowledge_block": "team",
            }
        )

        self.assertIsNone(routed["semantic_type"])
        self.assertEqual(routed["knowledge_block"], "team")
        self.assertEqual(
            routed["knowledge_intent"],
            "understand_team",
        )
        self.assertEqual(
            routed["routing"]["reason"],
            "knowledge_block_fallback",
        )

    def test_groups_items_by_knowledge_intent(self) -> None:
        grouped = self.router.group_by_intent(
            [
                {
                    "field_name": "submission_checklist.drawing_rules",
                    "value": "Painéis A1",
                    "knowledge_block": "submission_deliverables",
                },
                {
                    "field_name": "award_strategy.tie_break_rules",
                    "value": "Regra de desempate",
                    "knowledge_block": "evaluation",
                },
            ]
        )

        self.assertIn("prepare_submission", grouped)
        self.assertIn("understand_evaluation", grouped)
        self.assertEqual(len(grouped["prepare_submission"]), 1)
        self.assertEqual(len(grouped["understand_evaluation"]), 1)


if __name__ == "__main__":
    unittest.main()
