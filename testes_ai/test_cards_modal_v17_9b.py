from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "frontend" / "src" / "lib" / "analysis-universal.ts"
DESIGN = ROOT / "frontend" / "src" / "components" / "analise" / "DesignCompetitionAnalysis.tsx"
MODAL = ROOT / "frontend" / "src" / "components" / "analise" / "AnalysisQuestionsModal.tsx"


class CardsModalV179BTests(unittest.TestCase):
    def test_adapter_materializes_cards_from_all_existing_layers(self):
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("buildProcedureCardAnalysis", source)
        self.assertIn("canonicalScoring", source)
        self.assertIn("canonicalTeam", source)
        self.assertIn("legacyScoring", source)
        self.assertIn("legacyTeam", source)

    def test_design_uses_card_materializer(self):
        source = DESIGN.read_text(encoding="utf-8")
        self.assertIn("buildProcedureCardAnalysis", source)
        self.assertIn("const procedureCardAnalysis =", source)
        self.assertIn("ProcedureSpecificCards", source)
        self.assertIn("procedureAnalysis={procedureAnalysis}", source)

    def test_modal_uses_one_effective_question_source(self):
        source = MODAL.read_text(encoding="utf-8")
        self.assertIn(
            "CNLL_EDITABLE_QUESTIONS_FROM_REQUIREMENTS_V17_9B",
            source,
        )
        self.assertIn("CNLL_EFFECTIVE_MODAL_QUESTIONS_V17_10", source)
        self.assertIn("const effectiveQuestions =", source)
        self.assertIn(
            "editingAll ? effectiveQuestions : pendingQuestions",
            source,
        )
        self.assertIn(
            "if (!loaded || !effectiveQuestions.length) return null;",
            source,
        )

    def test_auto_open_uses_effective_questions(self):
        source = MODAL.read_text(encoding="utf-8")
        self.assertIn("const hasPending = effectiveQuestions.some", source)
        self.assertIn(
            "effectiveQuestions.filter((question) =>",
            source,
        )


if __name__ == "__main__":
    unittest.main()
