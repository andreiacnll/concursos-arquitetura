from __future__ import annotations

import unittest

from app.analise.pre_analysis_enrichment import _build_updates, _verified_criteria


class PreAnalysisEnrichmentTests(unittest.TestCase):
    def test_verified_criteria_requires_top_level_weights(self) -> None:
        inferred = {
            "award_criteria": {
                "summary": "Experiência 50% • Equipa 50%",
                "factors": [{"name": "Experiência", "weight": 50}],
                "verified_top_level_weights": False,
            }
        }
        self.assertEqual(_verified_criteria(inferred), {})

    def test_research_fields_are_built_without_analysis(self) -> None:
        concurso = {
            "tipo_procedimento": "Concurso Público",
            "data": None,
            "data_limite": None,
            "data_entrega_propostas": None,
            "preco_base": None,
        }
        common = {
            "publication_date": {"value": "01/08/2026"},
            "submission_deadline": {"value": "18-09-2026 17:00"},
            "base_price": {"value": "998 318,87 €"},
        }
        procedure = {
            "family": "project_services",
            "award_criteria": {
                "type": "Qualidade técnica + Preço",
                "summary": "Qualidade técnica 70% • Preço 30%",
                "factors": [
                    {"name": "Qualidade técnica", "weight": 70},
                    {"name": "Preço", "weight": 30},
                ],
                "verified_top_level_weights": True,
            },
        }
        updates = _build_updates(concurso, common, procedure)
        self.assertEqual(updates["tipo_procedimento"], "Prestação de serviços de projeto")
        self.assertEqual(updates["preco_base"], "998 318,87 €")
        self.assertEqual(updates["data_entrega_propostas"], "18-09-2026 17:00")
        self.assertEqual(updates["criterio_resumo"], "Qualidade técnica 70% • Preço 30%")


if __name__ == "__main__":
    unittest.main()
