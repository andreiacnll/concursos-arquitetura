from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ADAPTER = ROOT / "frontend" / "src" / "lib" / "analysis-universal.ts"
DESIGN = ROOT / "frontend" / "src" / "components" / "analise" / "DesignCompetitionAnalysis.tsx"
CARDS = ROOT / "frontend" / "src" / "components" / "analise" / "ProcedureSpecificCards.tsx"
DECISION = ROOT / "frontend" / "src" / "components" / "analise" / "UniversalDecisionCriteria.tsx"


class UniversalMergeV178Tests(unittest.TestCase):
    def test_procedure_sources_are_merged_not_first_non_null(self):
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("mergeProcedureSections", source)
        self.assertIn("root?.procedure_analysis", source)
        self.assertIn("extraction?.procedure_analysis", source)
        self.assertIn("insights?.procedure_analysis", source)
        self.assertNotIn(
            "root?.procedure_analysis ??\n    extraction?.procedure_analysis",
            source,
        )

    def test_arrays_are_unioned_instead_of_richest_wins(self):
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("mergeUniversalItems", source)
        self.assertNotIn("function richest(", source)
        self.assertIn("submission?.participant_documents", source)
        self.assertIn("submission?.proposal_documents", source)

    def test_design_uses_merged_procedure(self):
        source = DESIGN.read_text(encoding="utf-8")
        self.assertIn("getProcedureAnalysis(ficha)", source)
        self.assertIn("buildCriteriaSummary(", source)

    def test_empty_eligibility_array_does_not_mask_award_scoring(self):
        source = CARDS.read_text(encoding="utf-8")
        self.assertIn("mergeMaterialItems(", source)
        self.assertIn("eligibility?.scoring_requirements", source)
        self.assertIn("analysis?.award_criteria?.scoring_requirements", source)
        bad = re.compile(
            r"eligibility\?\.scoring_requirements\s*\?\?\s*"
            r"analysis\?\.award_criteria\?\.scoring_requirements"
        )
        self.assertIsNone(bad.search(source))

    def test_canonical_is_fallback_for_scoring_and_team(self):
        source = CARDS.read_text(encoding="utf-8")
        self.assertIn("canonicalScoring", source)
        self.assertIn("canonicalTeam", source)
        self.assertIn("canonicalEligibility", source)

    def test_decision_prefers_scored_profile_rows(self):
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("const scored = scoringRows", source)
        self.assertIn("if (scored.length) return scored;", source)
        self.assertIn("procedure?.award_criteria?.scoring_requirements", source)

    def test_summary_parser_is_segment_based_and_rejects_punctuation(self):
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn(".split(/[•·;\\n]+/)", source)
        self.assertIn("validCriterionLabel", source)
        self.assertIn("sanitizeCriterionLabel", source)

    def test_missing_still_not_zero(self):
        source = CARDS.read_text(encoding="utf-8")
        self.assertIn('"Por confirmar"', source)


if __name__ == "__main__":
    unittest.main()
