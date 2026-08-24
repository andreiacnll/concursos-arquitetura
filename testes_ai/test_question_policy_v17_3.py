from __future__ import annotations

import unittest

from app.analise.canonical_analysis import (
    _build_deduplicated_questions,
    _dedupe_requirements,
)


def requirement(
    *,
    req_id: str,
    reuse_key: str,
    metric: str | None,
    threshold=None,
    nature: str = "evaluation",
    subfactor: str = "A1",
    scope: str = "project",
    phase: str = "competition",
):
    followups = []

    if scope == "person":
        followups.append(
            {
                "id": "person",
                "type": "person",
                "label": "Quem?",
                "required_when": ["yes"],
            }
        )
    elif scope == "project":
        followups.append(
            {
                "id": "project",
                "type": "project",
                "label": "Que projeto?",
                "required_when": ["yes"],
            }
        )

    if metric:
        followups.append(
            {
                "id": "value",
                "type": "number",
                "metric": metric,
                "label": "Qual é o valor real?",
                "required_when": ["yes", "no"],
            }
        )

    return {
        "id": req_id,
        "factor_code": "A",
        "subfactor_code": subfactor,
        "label": "Experiência relevante",
        "phase": phase,
        "nature": nature,
        "profile_dependent": True,
        "required": {
            "text": "Experiência relevante",
            "metric": metric,
            "operator": ">=" if metric else None,
            "threshold": threshold,
            "unit": "€" if metric == "project_value_eur" else None,
        },
        "profile_target": {
            "scope": scope,
            "role": "",
            "reuse_key": reuse_key,
        },
        "profile": {
            "status": "missing",
            "summary": "Não demonstrado",
            "evidence": [],
        },
        "result": {"status": "pending", "label": "Por confirmar"},
        "source": {
            "document": "Programa do Procedimento.pdf",
            "section": "Critérios de adjudicação",
            "excerpt": "Experiência relevante",
        },
        "question": {
            "id": f"q-{req_id}",
            "type": "yes_no",
            "text": "Tem experiência?",
            "profile_target": {
                "scope": scope,
                "role": "",
                "reuse_key": reuse_key,
            },
            "followups": followups,
        },
    }


class QuestionPolicyV173Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.hierarchy = {
            "factors": [
                {
                    "code": "A",
                    "display_weight_percent": 50,
                    "subfactors": [
                        {
                            "code": "A1",
                            "display_weight_percent": 40,
                            "effective_weight_percent": 20,
                        },
                        {
                            "code": "A2",
                            "display_weight_percent": 40,
                            "effective_weight_percent": 20,
                        },
                    ],
                }
            ]
        }

    def test_score_bands_survive_requirement_dedupe(self) -> None:
        items = [
            requirement(
                req_id="r1",
                reuse_key="project.public_urbanization.project_value_eur",
                metric="project_value_eur",
                threshold=1_000_000,
            ),
            requirement(
                req_id="r2",
                reuse_key="project.public_urbanization.project_value_eur",
                metric="project_value_eur",
                threshold=2_000_000,
            ),
        ]
        deduped = _dedupe_requirements(items)
        self.assertEqual(len(deduped), 2)

    def test_multiple_thresholds_become_one_real_question(self) -> None:
        items = [
            requirement(
                req_id="r1",
                reuse_key="project.public_urbanization.project_value_eur",
                metric="project_value_eur",
                threshold=1_000_000,
            ),
            requirement(
                req_id="r2",
                reuse_key="project.public_urbanization.project_value_eur",
                metric="project_value_eur",
                threshold=2_000_000,
            ),
        ]
        questions = _build_deduplicated_questions(
            items,
            self.hierarchy,
        )
        self.assertEqual(len(questions), 1)
        self.assertEqual(set(questions[0]["requirement_ids"]), {"r1", "r2"})
        self.assertEqual(
            questions[0]["required"]["thresholds"],
            [1_000_000.0, 2_000_000.0],
        )

    def test_generic_question_removed_when_metric_exists(self) -> None:
        generic = requirement(
            req_id="generic",
            reuse_key="project.public_urbanization.qualification",
            metric=None,
        )
        metric = requirement(
            req_id="metric",
            reuse_key="project.public_urbanization.project_value_eur",
            metric="project_value_eur",
            threshold=2_000_000,
        )
        questions = _build_deduplicated_questions(
            [generic, metric],
            self.hierarchy,
        )
        self.assertEqual(len(questions), 1)
        self.assertEqual(
            questions[0]["required"]["metric"],
            "project_value_eur",
        )

    def test_submission_and_execution_do_not_become_cv_questions(self) -> None:
        submission = requirement(
            req_id="submission",
            reuse_key="company.docs",
            metric=None,
            nature="submission",
            scope="company",
        )
        execution = requirement(
            req_id="execution",
            reuse_key="person.execution.years",
            metric="years",
            nature="team",
            scope="person",
            phase="execution",
        )
        questions = _build_deduplicated_questions(
            [submission, execution],
            self.hierarchy,
        )
        self.assertEqual(questions, [])

    def test_eligibility_is_before_scoring(self) -> None:
        scoring = requirement(
            req_id="score",
            reuse_key="project.public_urbanization.project_value_eur",
            metric="project_value_eur",
            threshold=2_000_000,
            nature="evaluation",
        )
        eligibility = requirement(
            req_id="gate",
            reuse_key="person.coordinator.years",
            metric="years",
            threshold=5,
            nature="eligibility",
            scope="person",
            subfactor="",
        )
        eligibility["factor_code"] = ""
        eligibility["source"]["excerpt"] = (
            "Coordenador obrigatório com pelo menos 5 anos de experiência."
        )

        questions = _build_deduplicated_questions(
            [scoring, eligibility],
            self.hierarchy,
        )
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]["priority_label"], "Elegibilidade")
        self.assertEqual(questions[1]["priority_label"], "Pontuação")

    def test_loose_unweighted_evaluation_is_excluded(self) -> None:
        loose = requirement(
            req_id="loose",
            reuse_key="project.generic.qualification",
            metric=None,
            nature="evaluation",
            subfactor="ZZ",
        )
        loose["factor_code"] = "ZZ"
        questions = _build_deduplicated_questions(
            [loose],
            self.hierarchy,
        )
        self.assertEqual(questions, [])

    def test_v17_2_direct_call_remains_compatible(self) -> None:
        items = [
            requirement(
                req_id="r1",
                reuse_key="project:value:urbanizacao",
                metric="project_value_eur",
                threshold=1_000_000,
            ),
            requirement(
                req_id="r2",
                reuse_key="project:value:urbanizacao",
                metric="project_value_eur",
                threshold=2_000_000,
            ),
        ]
        questions = _build_deduplicated_questions(items)
        self.assertEqual(len(questions), 1)
        self.assertEqual(set(questions[0]["requirement_ids"]), {"r1", "r2"})


if __name__ == "__main__":
    unittest.main()
