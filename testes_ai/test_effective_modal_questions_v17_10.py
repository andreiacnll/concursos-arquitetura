from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "concursos.db"
MODAL = ROOT / "frontend" / "src" / "components" / "analise" / "AnalysisQuestionsModal.tsx"
ROUTER = ROOT / "app" / "company_ai" / "router.py"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def reuse_key(question: dict[str, Any]) -> str:
    return clean(
        (question.get("profile_target") or {}).get("reuse_key")
        or (question.get("required") or {}).get("reuse_key")
        or question.get("reuse_key")
    )


def dedupe(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []

    for question in questions:
        key = reuse_key(question)
        text = clean(
            question.get("text")
            or question.get("question")
            or question.get("prompt")
            or question.get("label")
        )
        signature = (
            key
            or clean(question.get("id"))
            or f"{clean(question.get('nature'))}|{clean(question.get('scope'))}|{text}".lower()
        )
        if not signature or signature in seen:
            continue
        seen.add(signature)
        output.append(question)

    return output


def rebuilt_from_requirements(canonical: dict[str, Any]) -> list[dict[str, Any]]:
    rebuilt: list[dict[str, Any]] = []
    for requirement in canonical.get("requirements") or []:
        if not isinstance(requirement, dict):
            continue
        if requirement.get("profile_dependent") is not True:
            continue

        nature = clean(requirement.get("nature")).lower()
        phase = clean(requirement.get("phase")).lower()
        if phase == "execution":
            continue
        if nature in {"submission", "habilitation"}:
            continue

        source = requirement.get("question")
        if not isinstance(source, dict):
            continue

        rebuilt.append(
            {
                **source,
                "requirement_id": clean(requirement.get("id"))
                or clean(source.get("requirement_id"))
                or None,
                "requirement_ids": source.get("requirement_ids")
                if isinstance(source.get("requirement_ids"), list)
                else [clean(requirement.get("id"))],
                "nature": requirement.get("nature") or source.get("nature"),
                "phase": requirement.get("phase") or source.get("phase") or "competition",
                "required": requirement.get("required") or source.get("required") or {},
                "profile_target": requirement.get("profile_target")
                or source.get("profile_target")
                or {},
            }
        )

    return dedupe(rebuilt)


def effective_questions(canonical: dict[str, Any]) -> list[dict[str, Any]]:
    raw = canonical.get("questions") if isinstance(canonical.get("questions"), list) else []
    return dedupe([*raw, *rebuilt_from_requirements(canonical)])


def pending_questions(
    canonical: dict[str, Any],
    facts: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        question
        for question in effective_questions(canonical)
        if reuse_key(question) and reuse_key(question) not in facts
    ]


def sample_requirement(
    key: str = "person.coordenador.years",
    nature: str = "eligibility",
    profile_dependent: bool = True,
) -> dict[str, Any]:
    return {
        "id": "req-1",
        "nature": nature,
        "phase": "competition",
        "profile_dependent": profile_dependent,
        "required": {"metric": "years", "threshold": 10, "unit": "years"},
        "profile_target": {"reuse_key": key, "kind": "person"},
        "question": {
            "id": "q-1",
            "text": "O coordenador tem pelo menos 10 anos de experiência?",
            "required": {"metric": "years", "threshold": 10, "unit": "years"},
            "profile_target": {"reuse_key": key, "kind": "person"},
        },
    }


class EffectiveModalQuestionsV1710Tests(unittest.TestCase):
    def test_persistence_and_recalculate_flow_remains_wired(self):
        modal_source = MODAL.read_text(encoding="utf-8")
        router_source = ROUTER.read_text(encoding="utf-8")

        self.assertIn("/company/analysis-facts", modal_source)
        self.assertIn("await saveRemoteFact(payload);", modal_source)
        self.assertIn("await recalculate(concursoId);", modal_source)
        self.assertIn("/company/analysis-facts/recalculate/", modal_source)
        self.assertIn('router = APIRouter(prefix="/company"', router_source)
        self.assertIn('@router.post("/analysis-facts")', router_source)
        self.assertIn(
            '@router.post("/analysis-facts/recalculate/{concurso_id}")',
            router_source,
        )

    def test_empty_canonical_questions_with_unanswered_requirement_has_pending_question(self):
        canonical = {"questions": [], "requirements": [sample_requirement()]}

        pending = pending_questions(canonical, {})

        self.assertEqual(len(pending), 1)
        self.assertEqual(reuse_key(pending[0]), "person.coordenador.years")

    def test_empty_canonical_questions_with_existing_fact_has_zero_pending_questions(self):
        canonical = {"questions": [], "requirements": [sample_requirement()]}
        facts = {"person.coordenador.years": {"answer": "yes"}}

        self.assertEqual(pending_questions(canonical, facts), [])

    def test_canonical_and_rebuilt_same_question_are_deduplicated(self):
        requirement = sample_requirement()
        canonical = {
            "questions": [requirement["question"]],
            "requirements": [requirement],
        }

        self.assertEqual(len(effective_questions(canonical)), 1)

    def test_competition_without_company_requirements_has_no_modal_questions(self):
        canonical = {
            "questions": [],
            "requirements": [
                sample_requirement(profile_dependent=False),
                sample_requirement(key="submission.format", nature="submission"),
            ],
        }

        self.assertEqual(effective_questions(canonical), [])

    def test_sru_445_reuses_existing_facts_without_repeating_known_questions(self):
        if not DB.exists():
            self.skipTest("concursos.db não existe neste checkout")

        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """
                SELECT dados_json
                FROM analises
                WHERE concurso_id = 445
                  AND dados_json IS NOT NULL
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            self.assertIsNotNone(row, "Análise ativa do concurso 445 não encontrada")

            dados = json.loads(row["dados_json"])
            canonical = dados.get("analysis_canonical") or {}

            facts: dict[str, dict[str, Any]] = {}
            for fact_row in conn.execute(
                """
                SELECT field, value_json
                FROM company_knowledge_memory
                WHERE field LIKE 'analysis.requirements.%'
                """
            ):
                value = json.loads(fact_row["value_json"] or "{}")
                key = clean(
                    value.get("reuse_key")
                    or fact_row["field"].replace("analysis.requirements.", "", 1)
                )
                if key:
                    facts[key] = value
        finally:
            conn.close()

        effective = effective_questions(canonical)
        pending = pending_questions(canonical, facts)

        self.assertGreater(len(effective), 0)
        self.assertGreater(len(facts), 0)
        self.assertLessEqual(len(pending), len(effective))
        self.assertTrue(
            all(reuse_key(question) not in facts for question in pending)
        )
        self.assertEqual(
            len({reuse_key(question) for question in effective if reuse_key(question)}),
            len([question for question in effective if reuse_key(question)]),
        )


if __name__ == "__main__":
    unittest.main()
