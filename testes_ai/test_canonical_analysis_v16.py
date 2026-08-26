from __future__ import annotations

import unittest

from app.analise.canonical_analysis import (
    SCHEMA_VERSION,
    build_canonical_analysis,
)


class CanonicalAnalysisV16Tests(unittest.TestCase):
    def test_parque_preserves_published_hierarchy(self) -> None:
        procedure = {
            "family": "project_services",
            "award_criteria": {
                "model": "Melhor relação qualidade-preço",
                "factors": [
                    {
                        "code": "A",
                        "label": "Experiência da equipa técnica",
                        "weight_percent": 50,
                        "subfactors": [
                            {"code": "A1", "label": "Projetos de parques urbanos", "effective_weight_percent": 20},
                            {"code": "A2", "label": "Obras de urbanização públicas", "effective_weight_percent": 20},
                            {"code": "A3", "label": "Remodelação/modelação de terrenos", "effective_weight_percent": 7.5},
                            {"code": "A4", "label": "Formação do Gestor BIM", "effective_weight_percent": 2.5},
                        ],
                    },
                    {
                        "code": "B",
                        "label": "Proposta",
                        "weight_percent": 30,
                        "subfactors": [
                            {"code": "B1", "label": "Qualidade estética", "weight_percent": 40},
                            {"code": "B2", "label": "Adequação ao programa", "weight_percent": 30},
                            {"code": "B3", "label": "Princípios orientadores", "weight_percent": 30},
                        ],
                    },
                    {"code": "C", "label": "Preço", "weight_percent": 20},
                ],
                "experience_rules": {
                    "maximum_projects_per_specialty": 5,
                    "geography": "União Europeia",
                    "period": "Últimos 15 anos",
                    "minimum_updated_construction_value_eur": 2000000,
                    "minimum_earthworks_volume_m3": 100000,
                    "minimum_bim_training_hours": 80,
                },
            },
        }
        result = build_canonical_analysis(ficha={}, procedure=procedure, concurso={"id": 445})
        factor_a = result["criteria"]["factors"][0]
        self.assertEqual(factor_a["published_weight_percent"], 50)
        sub = factor_a["subfactors"]
        self.assertEqual([x["display_weight_percent"] for x in sub], [40, 40, 15, 5])
        self.assertEqual([x["effective_weight_percent"] for x in sub], [20, 20, 7.5, 2.5])
        self.assertTrue(all(x["weight_context"] == "do fator" for x in sub))

        questions = result["questions"]
        bim = [q for q in questions if q.get("subfactor_code") == "A4" and (q.get("required") or {}).get("metric") == "training_hours"]
        self.assertTrue(bim)
        self.assertIn("80", bim[0]["text"])
        self.assertTrue(any(f.get("type") == "person" for f in bim[0]["followups"]))
        self.assertTrue(any(f.get("type") == "number" for f in bim[0]["followups"]))

        a2 = [q for q in questions if q.get("subfactor_code") == "A2" and (q.get("required") or {}).get("metric") == "project_value_eur"]
        self.assertTrue(a2)
        self.assertEqual(a2[0]["required"]["threshold"], 2000000)

    def test_lumiar_coordinator_years_becomes_question(self) -> None:
        procedure = {
            "family": "design_competition",
            "award_criteria": {
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
                                "summary": "Coordenador com pelo menos 10 anos de experiência profissional.",
                                "source_document": "Programa do Procedimento.pdf",
                            }
                        ],
                    },
                    {"code": "B", "label": "Proposta", "weight_percent": 40},
                ]
            },
        }
        result = build_canonical_analysis(ficha={}, procedure=procedure, concurso={"id": 435})
        years = [
            q for q in result["questions"]
            if (q.get("required") or {}).get("metric") == "years"
        ]
        self.assertTrue(years)
        self.assertEqual(years[0]["required"]["threshold"], 10)
        self.assertEqual(years[0]["profile_target"]["scope"], "person")
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)

    def test_contract_requirement_does_not_drive_competition_decision(self) -> None:
        procedure = {
            "family": "project_services",
            "award_criteria": {"factors": []},
            "submission": {
                "team_requirements": [
                    {
                        "title": "Técnico de execução com 15 anos de experiência",
                        "source_document": "Caderno de Encargos.pdf",
                        "section": "Execução do contrato",
                    }
                ]
            },
        }
        result = build_canonical_analysis(ficha={}, procedure=procedure)
        self.assertFalse(result["questions"])


if __name__ == "__main__":
    unittest.main()
