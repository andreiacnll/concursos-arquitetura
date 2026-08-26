from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

from app.analise.canonical_analysis import apply_canonical_analysis
from app.analise.legacy_procedure_recovery import (
    analysis_body,
    recover_procedure_from_legacy,
)
from app.company_ai.router import _cv_canonical_is_material

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "concursos.db"
DESIGN = ROOT / "frontend" / "src" / "components" / "analise" / "DesignCompetitionAnalysis.tsx"
DISPLAY = ROOT / "frontend" / "src" / "lib" / "analysis-display.ts"
MODAL = ROOT / "frontend" / "src" / "components" / "analise" / "AnalysisQuestionsModal.tsx"


class PrePostModalScoreV1716Tests(unittest.TestCase):
    def _analysis(self, analysis_id: int) -> dict:
        if not DB.exists():
            self.skipTest("concursos.db não existe neste checkout")
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT concurso_id, dados_json FROM analises WHERE id = ?",
                (analysis_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        data = json.loads(row["dados_json"])
        return {"concurso_id": row["concurso_id"], "data": data}

    def test_new_447_legacy_team_becomes_pre_award_profile_questions(self):
        payload = self._analysis(29)
        ficha = analysis_body(payload["data"])
        procedure, meta = recover_procedure_from_legacy(
            ficha,
            base_procedure=ficha.get("procedure_analysis"),
        )

        self.assertIn(
            meta.get("mode"),
            {"existing_procedure_analysis", "legacy_team_descriptors"},
        )
        if meta.get("mode") == "legacy_team_descriptors":
            self.assertGreaterEqual(meta.get("subfactor_count") or 0, 4)

        canonical = apply_canonical_analysis(
            ficha=ficha,
            procedure=procedure or {},
            concurso={"id": payload["concurso_id"]},
        )
        requirements = canonical.get("requirements") or []
        questions = canonical.get("questions") or []
        profile_dependent = [r for r in requirements if r.get("profile_dependent")]

        self.assertGreaterEqual(len(profile_dependent), 4)
        self.assertGreaterEqual(len(questions), 1)
        self.assertTrue(all(r.get("stage") == "pre_award" for r in profile_dependent))

        joined = json.dumps(profile_dependent, ensure_ascii=False).lower()
        self.assertIn("coordenador", joined)
        self.assertIn("gestor", joined)
        self.assertIn('"location": "EU"'.lower(), joined)
        self.assertIn('"completed": true', joined)
        self.assertIn('"period_unit": "years"', joined)

    def test_generic_requirements_without_profile_questions_are_not_material(self):
        canonical = {
            "requirements": [
                {"nature": "eligibility", "profile_dependent": False},
            ],
            "questions": [],
            "criteria": {"factors": []},
        }
        self.assertFalse(_cv_canonical_is_material(canonical))

    def test_frontend_score_no_longer_uses_heuristic_compatibility_as_ball(self):
        source = DESIGN.read_text(encoding="utf-8")
        self.assertIn("buildOfficialScore", source)
        self.assertNotIn("scoreCandidate", source)
        self.assertNotIn("matching?.score_compatibilidade ??", source)
        self.assertIn("Pontuação demonstrável", source)
        self.assertIn("Não foi atribuída pontuação média", source)
        self.assertIn("officialWeightGroups", source)
        self.assertIn("Math.max(current.weight", source)

    def test_modal_repairs_visible_material_without_profile_dependent_questions(self):
        source = MODAL.read_text(encoding="utf-8")
        self.assertIn("profileDependent.length === 0", source)
        self.assertIn("visibleProcedureIsMaterial", source)
        self.assertIn("stage === \"post_award\"", source)

    def test_presentation_filters_noise_and_summarizes_contract_risks(self):
        source = DISPLAY.read_text(encoding="utf-8")
        self.assertIn("looksLikeDocumentNoise", source)
        self.assertIn("riskPrimaryFromText", source)
        self.assertIn("Penalidade:", source)
        self.assertNotIn('primaryValue = "Requisito identificado"', source)


if __name__ == "__main__":
    unittest.main()
