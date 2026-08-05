from __future__ import annotations

import unittest

from app.architecture_intelligence.knowledge_router import KnowledgeRouter


class KnowledgeRouterRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.router = KnowledgeRouter()

    def test_scale_requirements_cannot_become_platform(self) -> None:
        routed = self.router.route_item(
            {
                "field_name": "scale_requirements",
                "value": [
                    "Plantas e cortes à escala 1/500.",
                    "A plataforma usa uma escala de 1 a 10 pontos.",
                ],
                "knowledge_block": "administrative",
            }
        )

        self.assertEqual(
            routed["semantic_type"],
            "submission_panel_format",
        )
        self.assertNotEqual(
            routed["semantic_type"],
            "submission_platform",
        )

    def test_unrelated_platform_word_does_not_route_unknown_field(self) -> None:
        routed = self.router.route_item(
            {
                "field_name": "custom_requirement",
                "value": "O documento menciona uma plataforma externa.",
                "knowledge_block": "team",
            }
        )

        self.assertIsNone(routed["semantic_type"])
        self.assertEqual(routed["knowledge_intent"], "understand_team")

    def test_phases_container_routes_to_contract_without_false_type(self) -> None:
        routed = self.router.route_item(
            {
                "field_name": "phases_and_deliverables",
                "value": {
                    "deliverables": [
                        "Memória descritiva",
                        "Projeto de execução",
                    ]
                },
                "knowledge_block": "submission_deliverables",
            }
        )

        self.assertIsNone(routed["semantic_type"])
        self.assertEqual(
            routed["knowledge_intent"],
            "understand_contract",
        )
        self.assertEqual(
            routed["knowledge_block"],
            "contract_deliverables",
        )

    def test_ambiguous_physical_formats_stay_unmapped(self) -> None:
        routed = self.router.route_item(
            {
                "field_name": "physical_formats",
                "value": [
                    "Dois exemplares em papel do projeto de execução.",
                    "Papeleiras no espaço exterior.",
                ],
                "knowledge_block": "administrative",
            }
        )

        self.assertIsNone(routed["semantic_type"])
        self.assertEqual(routed["knowledge_intent"], "other")
        self.assertEqual(
            routed["routing"]["reason"],
            "field_route_override",
        )

    def test_team_exclusion_requirements_route_to_team(self) -> None:
        routed = self.router.route_item(
            {
                "field_name": "exclusionary_team_requirements",
                "value": "A falta do coordenador determina exclusão.",
                "knowledge_block": "administrative",
            }
        )

        self.assertEqual(
            routed["semantic_type"],
            "minimum_team_requirement",
        )
        self.assertEqual(routed["knowledge_intent"], "understand_team")

    def test_construction_cost_aliases_are_supported(self) -> None:
        for field_name in (
            "estimated_work_cost",
            "estimated_works_cost",
            "construction_cost_estimate",
            "estimated_cost_of_works",
        ):
            with self.subTest(field_name=field_name):
                routed = self.router.route_item(
                    {
                        "field_name": field_name,
                        "value": 24439134,
                        "knowledge_block": "financials",
                    }
                )
                self.assertEqual(
                    routed["semantic_type"],
                    "estimated_construction_cost",
                )
                self.assertEqual(
                    routed["knowledge_intent"],
                    "understand_project",
                )


if __name__ == "__main__":
    unittest.main()
