from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CARDS = (
    ROOT
    / "frontend"
    / "src"
    / "components"
    / "analise"
    / "ProcedureSpecificCards.tsx"
)
DESIGN = (
    ROOT
    / "frontend"
    / "src"
    / "components"
    / "analise"
    / "DesignCompetitionAnalysis.tsx"
)
MODAL = (
    ROOT
    / "frontend"
    / "src"
    / "components"
    / "analise"
    / "AnalysisQuestionsModal.tsx"
)
PROCEDURE = ROOT / "app" / "analise" / "procedure_analysis.py"
API = ROOT / "app" / "api.py"


class UniversalAnalysisV176BTests(unittest.TestCase):
    def test_new_analyses_are_canonicalized_automatically(self):
        source = PROCEDURE.read_text(encoding="utf-8")
        self.assertIn("CNLL_CANONICAL_ANALYSIS_V16", source)
        self.assertIn("apply_canonical_analysis(", source)

    def test_api_uses_active_database_payload_first(self):
        source = API.read_text(encoding="utf-8")
        self.assertIn(
            "CNLL_API_ACTIVE_ANALYSIS_SOURCE_V17_5_5",
            source,
        )
        db_pos = source.find(
            'dados_json = analise_ativa.get("dados_json")'
        )
        file_pos = source.find(
            'ficheiro_relativo = analise_ativa.get("ficheiro_ficha")',
            db_pos,
        )
        self.assertGreaterEqual(db_pos, 0)
        self.assertGreater(file_pos, db_pos)

    def test_template_passes_canonical_hierarchy_to_cards(self):
        source = DESIGN.read_text(encoding="utf-8")
        self.assertIn(
            "canonical_criteria:",
            source,
        )
        self.assertIn(
            "ficha?.analysis_canonical?.criteria",
            source,
        )
        self.assertIn(
            "canonical_requirements:",
            source,
        )
        self.assertIn(
            "ficha?.analysis_canonical?.requirements",
            source,
        )

    def test_quiz_remains_canonical_and_automatic(self):
        source = MODAL.read_text(encoding="utf-8")
        self.assertIn("analysis_canonical", source)
        self.assertIn("/company/analysis-facts", source)
        self.assertIn("canonical?.questions", source)

    def test_missing_is_not_rendered_as_zero(self):
        source = CARDS.read_text(encoding="utf-8")
        self.assertIn(
            'return count > 0 ? String(count) : "Por confirmar";',
            source,
        )
        self.assertIn(
            '"Por confirmar"',
            source,
        )

    def test_empty_contractual_cards_are_hidden(self):
        source = CARDS.read_text(encoding="utf-8")
        self.assertIn("const showScope = scope.length > 0;", source)
        self.assertIn(
            "const showPhases = phases.length > 0 || payments.length > 0;",
            source,
        )
        self.assertIn("const showRisks = risks.length > 0;", source)

    def test_scoring_weight_uses_canonical_hierarchy(self):
        source = CARDS.read_text(encoding="utf-8")
        self.assertIn("effective_weight_percent", source)
        self.assertIn("canonical_criteria", source)
        self.assertIn("canonical_requirements", source)
        self.assertIn("matchedParents.length === 1", source)
        self.assertIn("nonPriceFactors.length === 1", source)

    def test_no_named_competition_special_cases_in_dynamic_cards(self):
        source = CARDS.read_text(encoding="utf-8").lower()
        for forbidden in (
            "mercado municipal",
            "castelo branco",
            "lumiar",
            "vale de santo",
            "parque urbano",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
