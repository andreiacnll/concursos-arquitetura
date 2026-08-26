from __future__ import annotations

import unittest
from pathlib import Path

from app.analise.legacy_procedure_recovery import (
    recover_procedure_from_legacy,
)

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "app" / "company_ai" / "router.py"
MODAL = (
    ROOT
    / "frontend"
    / "src"
    / "components"
    / "analise"
    / "AnalysisQuestionsModal.tsx"
)


class CanonicalVisibleSyncV1753BTests(unittest.TestCase):
    def test_recovery_exposes_team_descriptors(self):
        ficha = {
            "identificacao": {"analysis_family": "project_services"},
            "criterios": {
                "criterio_adjudicacao": "Multifator",
                "resumo": "Preço 40% • FATOR 2: Valia Técnica da Equipa de Projeto (60%)",
            },
            "equipa": [
                {
                    "titulo": "Subfator 2.1 - Coordenador de Projeto (20%)",
                    "descricao": "Experiência do Coordenador em projetos de referência.",
                },
                {
                    "titulo": "Subfator 2.2 - Arquiteto (20%)",
                    "descricao": "Experiência do Arquiteto em projetos de referência.",
                },
            ],
        }

        procedure, meta = recover_procedure_from_legacy(ficha)
        self.assertIsNotNone(procedure)
        self.assertEqual(meta["mode"], "legacy_team_descriptors")
        self.assertGreaterEqual(
            len(procedure.get("technical_team") or []),
            2,
        )

    def test_router_sync_layer_exists(self):
        source = ROUTER.read_text(encoding="utf-8")
        self.assertIn(
            "CNLL_CANONICAL_VISIBLE_SYNC_V17_5_3B",
            source,
        )
        self.assertIn(
            "_cv_sync_recovered_procedure_to_visible_analysis(",
            source,
        )
        self.assertIn(
            "and _cv_visible_procedure_is_material(ficha)",
            source,
        )

    def test_modal_does_not_depend_on_old_dedupe_function(self):
        source = MODAL.read_text(encoding="utf-8")
        self.assertIn(
            "function dedupeCanonicalQuestions(",
            source,
        )
        self.assertIn(
            "return dedupeCanonicalQuestions(rawQuestions);",
            source,
        )
        self.assertIn(
            'policy === "decision-facts-v17.3"',
            source,
        )
        self.assertIn(
            "!visibleProcedureIsMaterial",
            source,
        )


if __name__ == "__main__":
    unittest.main()
