from __future__ import annotations

import unittest

from app.analise.semantic_product_bridge import (
    _explicit_financial_facts,
)


class DesignCompetitionFinancialRepairTests(unittest.TestCase):
    def test_separates_financial_concepts(self) -> None:
        result = _explicit_financial_facts(
            {
                "anuncio.pdf": (
                    "O preço base do procedimento é "
                    "26.000,00 EUR."
                ),
                "caderno.pdf": (
                    "O custo estimado da obra é "
                    "24.439.134,00 EUR."
                ),
                "honorarios.pdf": (
                    "O valor máximo dos serviços de projeto "
                    "é 598.452,00 EUR, sem IVA."
                ),
            }
        )

        self.assertIn(
            "26 000,00",
            result["procedure_value"][0],
        )
        self.assertIn(
            "24 439 134,00",
            result["estimated_construction_cost"][0],
        )
        self.assertIn(
            "598 452,00",
            result["design_services_value"][0],
        )

    def test_does_not_copy_procedure_to_construction(self) -> None:
        result = _explicit_financial_facts(
            {
                "anuncio.pdf": (
                    "O preço base do procedimento é "
                    "26.000,00 EUR."
                ),
                "caderno.pdf": (
                    "Este documento não indica o custo "
                    "estimado da obra."
                ),
            }
        )

        self.assertIn("procedure_value", result)
        self.assertNotIn(
            "estimated_construction_cost",
            result,
        )

    def test_honorarios_need_explicit_phrase(self) -> None:
        result = _explicit_financial_facts(
            {
                "documento.pdf": (
                    "O custo da obra é 24.439.134,00 EUR. "
                    "O procedimento vale 26.000,00 EUR."
                )
            }
        )

        self.assertNotIn(
            "design_services_value",
            result,
        )


if __name__ == "__main__":
    unittest.main()
