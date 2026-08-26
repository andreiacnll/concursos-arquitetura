from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "frontend" / "src" / "components" / "analise" / "DesignCompetitionAnalysis.tsx"
CARDS = ROOT / "frontend" / "src" / "components" / "analise" / "ProcedureSpecificCards.tsx"


class DirectFichaCardsV1710Tests(unittest.TestCase):
    def test_design_passes_full_ficha_to_cards(self):
        source = DESIGN.read_text(encoding="utf-8")
        self.assertIn(
            '<ProcedureSpecificCards analysis={procedureAnalysis} ficha={ficha} />',
            source,
        )

    def test_cards_read_root_procedure_directly(self):
        source = CARDS.read_text(encoding="utf-8")
        self.assertIn("CNLL_DIRECT_FICHA_CARDS_V17_10", source)
        self.assertIn("ficha?.procedure_analysis", source)
        self.assertIn(
            "ficha?.design_competition_extraction",
            source,
        )
        self.assertIn("ficha?.analysis_canonical?.requirements", source)
        self.assertIn("ficha?.equipa", source)

    def test_cards_merge_scoring_and_team_from_all_sources(self):
        source = CARDS.read_text(encoding="utf-8")
        self.assertIn("const scoring = mergeItems(", source)
        self.assertIn("const team = mergeItems(", source)
        self.assertIn("canonicalScoring", source)
        self.assertIn("canonicalTeam", source)
        self.assertIn("legacyScoring", source)
        self.assertIn("legacyTeam", source)

    def test_missing_is_not_zero(self):
        source = CARDS.read_text(encoding="utf-8")
        self.assertIn('"Por confirmar"', source)


if __name__ == "__main__":
    unittest.main()
