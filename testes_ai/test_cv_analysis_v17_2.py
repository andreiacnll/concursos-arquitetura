from __future__ import annotations

import unittest

from app.analise.canonical_analysis import (
    _build_deduplicated_questions,
    apply_profile_facts_to_canonical,
)
from app.company_ai.models import CompanyCVEntry, CompanyProfile


class CVAnalysisV172Tests(unittest.TestCase):
    def test_same_fact_generates_one_question_for_multiple_requirements(self) -> None:
        base_question = {
            "text": "Qual é o maior valor comprovável?",
            "profile_target": {
                "scope": "project",
                "role": "",
                "reuse_key": "project:value:urbanizacao",
            },
            "followups": [
                {
                    "id": "value",
                    "type": "number",
                    "metric": "project_value_eur",
                    "label": "Qual é o maior valor?",
                }
            ],
        }
        requirements = [
            {
                "id": "r1",
                "profile_dependent": True,
                "profile_target": base_question["profile_target"],
                "profile": {"status": "missing"},
                "question": dict(base_question),
                "required": {
                    "metric": "project_value_eur",
                    "operator": ">=",
                    "threshold": 1_000_000,
                },
            },
            {
                "id": "r2",
                "profile_dependent": True,
                "profile_target": base_question["profile_target"],
                "profile": {"status": "missing"},
                "question": dict(base_question),
                "required": {
                    "metric": "project_value_eur",
                    "operator": ">=",
                    "threshold": 2_000_000,
                },
            },
        ]

        questions = _build_deduplicated_questions(requirements)
        self.assertEqual(len(questions), 1)
        self.assertEqual(set(questions[0]["requirement_ids"]), {"r1", "r2"})

    def test_one_actual_value_is_applied_to_each_threshold(self) -> None:
        reuse_key = "project:value:urbanizacao"
        ficha = {
            "analysis_canonical": {
                "criteria": {"factors": []},
                "requirements": [
                    {
                        "id": "r1",
                        "label": "Faixa 1",
                        "nature": "evaluation",
                        "profile_dependent": True,
                        "profile_target": {"reuse_key": reuse_key},
                        "profile": {"status": "missing"},
                        "required": {
                            "metric": "project_value_eur",
                            "operator": ">=",
                            "threshold": 1_000_000,
                        },
                        "question": {
                            "text": "Valor?",
                            "profile_target": {"reuse_key": reuse_key},
                        },
                    },
                    {
                        "id": "r2",
                        "label": "Faixa 2",
                        "nature": "evaluation",
                        "profile_dependent": True,
                        "profile_target": {"reuse_key": reuse_key},
                        "profile": {"status": "missing"},
                        "required": {
                            "metric": "project_value_eur",
                            "operator": ">=",
                            "threshold": 2_000_000,
                        },
                        "question": {
                            "text": "Valor?",
                            "profile_target": {"reuse_key": reuse_key},
                        },
                    },
                ],
            }
        }

        result = apply_profile_facts_to_canonical(
            ficha,
            {
                reuse_key: {
                    "reuse_key": reuse_key,
                    "answer": "yes",
                    "numeric_value": 1_500_000,
                    "unit": "EUR",
                }
            },
        )
        statuses = [
            requirement["result"]["status"]
            for requirement in result["requirements"]
        ]
        self.assertEqual(statuses, ["met", "not_met"])
        self.assertEqual(result["questions"], [])

    def test_cv_survives_profile_roundtrip(self) -> None:
        profile = CompanyProfile(
            company_id=7,
            cv=[
                CompanyCVEntry(
                    id="cv-1",
                    title="Formação BIM",
                    reuse_key="person:bim:training_hours",
                    scope="person",
                    person="João Silva",
                    metric="training_hours",
                    numeric_value=60,
                    unit="h",
                    answer="yes",
                )
            ],
        )
        rebuilt = CompanyProfile.model_validate(profile.model_dump())
        self.assertEqual(len(rebuilt.cv), 1)
        self.assertEqual(rebuilt.cv[0].person, "João Silva")
        self.assertEqual(rebuilt.cv[0].numeric_value, 60)


if __name__ == "__main__":
    unittest.main()
