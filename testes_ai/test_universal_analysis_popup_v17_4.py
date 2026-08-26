
from __future__ import annotations

import unittest

from app.analise.canonical_analysis import build_canonical_analysis


class UniversalPopupV174Tests(unittest.TestCase):
    def test_market_like_competition_generates_profile_question(self) -> None:
        procedure = {
            "family": "project_services",
            "family_label": "Prestação de serviços de projeto",
            "award_criteria": {
                "model": "Melhor relação qualidade-preço",
                "factors": [
                    {
                        "code": "A",
                        "label": "Experiência da equipa",
                        "weight_percent": 60,
                        "subfactors": [
                            {
                                "code": "A1",
                                "label": "Experiência do coordenador",
                                "weight_percent": 100,
                                "summary": (
                                    "Coordenador com pelo menos 5 anos "
                                    "de experiência profissional."
                                ),
                                "source_document": "Programa do Procedimento.pdf",
                            }
                        ],
                    },
                    {
                        "code": "B",
                        "label": "Preço",
                        "weight_percent": 40,
                    },
                ],
            },
        }

        result = build_canonical_analysis(
            ficha={},
            procedure=procedure,
            concurso={
                "id": 999,
                "titulo": "Reabilitação de Mercado Municipal",
            },
        )

        questions = result.get("questions") or []
        self.assertTrue(questions)

        years = [
            question
            for question in questions
            if (question.get("required") or {}).get("metric") == "years"
        ]
        self.assertTrue(years)
        self.assertEqual(years[0]["required"]["threshold"], 5)
        self.assertIn("5", years[0]["text"])

    def test_price_only_competition_does_not_force_popup(self) -> None:
        procedure = {
            "family": "project_services",
            "award_criteria": {
                "factors": [
                    {
                        "code": "P",
                        "label": "Preço",
                        "weight_percent": 100,
                    }
                ]
            },
        }

        result = build_canonical_analysis(
            ficha={},
            procedure=procedure,
            concurso={"id": 1000},
        )

        self.assertEqual(result.get("questions") or [], [])


if __name__ == "__main__":
    unittest.main()
