import unittest
from pathlib import Path

import app.database as database

from app.architecture_intelligence.llm.presentation_builder import PresentationBuilder
from app.architecture_intelligence.llm.presentation_schema import Presentation
from app.routes.analises import _consolidated_for_analysis


class FakeProvider:
    model = "test"

    def __init__(self, result=None):
        self.result = result

    def generate(self, payload, schema):
        return self.result


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self._database_path = database.DB_PATH
        database.DB_PATH = Path(__file__).resolve().parents[1] / "concursos.db"
        self.data = {
            "document_quality": "partial",
            "procedure_identity": {"object": {"value": "Lumiar"}},
            "prices": {"competition_prizes": {"value": ["15.000 €", "10.000 €", "5.000 €"]}},
            "award_strategy": {"evaluation_model": {"value": "concurso"}},
            "submission_checklist": {"administrative": [{"value": "Declaração"}]},
            "evidences": [],
        }

    def tearDown(self):
        database.DB_PATH = self._database_path

    def test_valid_structured_output_is_validated(self):
        output = {"document_status": "complete", "executive_summary": "Resumo", "cards": [], "risks": [], "opportunities": [], "checklist": [], "missing_information": [], "warnings": []}
        result = PresentationBuilder(provider=FakeProvider(output)).build(self.data)
        self.assertIsInstance(result, Presentation)
        self.assertEqual(result.executive_summary, "Resumo")

    def test_invalid_response_uses_deterministic_fallback_and_preserves_values(self):
        result = PresentationBuilder(provider=FakeProvider({"invalid": True})).deterministic(self.data)
        values = [item.value for card in result.cards for item in card.items]
        self.assertIn("15.000 €; 10.000 €; 5.000 €", values)
        self.assertEqual(result.document_status, "partial")

    def test_cache_key_changes_when_consolidated_changes(self):
        builder = PresentationBuilder(provider=FakeProvider())
        first = builder.cache_key(self.data)
        changed = {**self.data, "document_quality": "complete"}
        self.assertNotEqual(first, builder.cache_key(changed))

    def test_existing_analysis_20_uses_legacy_structured_json_adapter(self):
        resolved = _consolidated_for_analysis(20)
        self.assertIsNotNone(resolved)
        consolidated, context = resolved
        self.assertEqual(context, {"analysis_id": 20, "concurso_id": 438, "job_id": 56})
        self.assertEqual(consolidated.document_quality, "partial")
        self.assertEqual(consolidated.prices["procedure_value"]["value"], "15.000,00 €")

    def test_missing_analysis_is_not_resolved(self):
        self.assertIsNone(_consolidated_for_analysis(999999999))

    def test_existing_analysis_fallback_can_generate(self):
        resolved = _consolidated_for_analysis(20)
        consolidated, _ = resolved
        result = PresentationBuilder(provider=FakeProvider({"invalid": True})).build(consolidated, force=True)
        self.assertTrue(result.cards)


if __name__ == "__main__":
    unittest.main()
