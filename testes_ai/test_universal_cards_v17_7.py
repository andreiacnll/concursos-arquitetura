from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "frontend" / "src" / "lib" / "analysis-universal.ts"
DESIGN = ROOT / "frontend" / "src" / "components" / "analise" / "DesignCompetitionAnalysis.tsx"
SUBMISSION = ROOT / "frontend" / "src" / "components" / "analise" / "UniversalSubmissionCards.tsx"
SIDEBAR = ROOT / "frontend" / "src" / "components" / "analise" / "dashboard" / "ProjectInfoPanel.tsx"
DECISION = ROOT / "frontend" / "src" / "components" / "analise" / "UniversalDecisionCriteria.tsx"


class UniversalCardsV177Tests(unittest.TestCase):
    def test_submission_reads_procedure_analysis(self):
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("submission?.participant_documents", source)
        self.assertIn("submission?.proposal_documents", source)
        self.assertIn("submission?.formats_and_limits", source)
        self.assertIn("submission?.critical_conditions", source)
        self.assertIn("submission?.post_selection_documents", source)

    def test_missing_counts_are_not_zero(self):
        source = SUBMISSION.read_text(encoding="utf-8")
        self.assertIn('return count > 0 ? String(count) : "Por confirmar";', source)
        self.assertNotIn('>0<', source)

    def test_sidebar_uses_same_universal_source(self):
        source = SIDEBAR.read_text(encoding="utf-8")
        self.assertIn("buildUniversalSubmission", source)
        self.assertIn("buildUniversalContract", source)
        self.assertIn('"Por confirmar"', source)

    def test_decision_uses_real_criteria_before_generic_relevance(self):
        source = DECISION.read_text(encoding="utf-8")
        self.assertIn("buildDecisionCriteria", source)
        self.assertIn("Critério confirmado nas peças", ADAPTER.read_text(encoding="utf-8"))
        design = DESIGN.read_text(encoding="utf-8")
        self.assertIn("<UniversalDecisionCriteria", design)
        self.assertIn("O que decide a nota", design)

    def test_price_only_summary_can_be_parsed(self):
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("summary.matchAll(pattern)", source)
        self.assertIn("criteriaSummary", source)


if __name__ == "__main__":
    unittest.main()
