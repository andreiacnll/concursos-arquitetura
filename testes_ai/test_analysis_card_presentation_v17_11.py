from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "frontend" / "src" / "components" / "analise" / "DesignCompetitionAnalysis.tsx"
SUBMISSION = ROOT / "frontend" / "src" / "components" / "analise" / "UniversalSubmissionCards.tsx"
PROCEDURE = ROOT / "frontend" / "src" / "components" / "analise" / "ProcedureSpecificCards.tsx"
DECISION = ROOT / "frontend" / "src" / "components" / "analise" / "UniversalDecisionCriteria.tsx"
DB = ROOT / "concursos.db"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def best_detail(item: dict[str, Any]) -> str:
    required = item.get("required") if isinstance(item.get("required"), dict) else {}
    candidates = [
        required.get("text"),
        item.get("detail"),
        item.get("detalhe"),
        item.get("condition"),
        item.get("requirement_text"),
        item.get("source_text"),
        item.get("summary"),
        item.get("description"),
        item.get("descricao"),
        item.get("text"),
        item.get("evidence_excerpt"),
        item.get("source_excerpt"),
        (item.get("source") or {}).get("excerpt") if isinstance(item.get("source"), dict) else "",
    ]
    for candidate in candidates:
        text = clean(candidate)
        if text and text.lower() not in {"confirmado nas peças", "confirmado", "por confirmar"}:
            return text
    return "Requisito identificado"


class AnalysisCardPresentationV1711Tests(unittest.TestCase):
    def test_submission_cards_use_concrete_detail_renderer(self):
        source = SUBMISSION.read_text(encoding="utf-8")
        self.assertIn("function renderRows", source)
        self.assertIn("formatAnalysisItemForDisplay(item, kind)", source)
        self.assertIn("display.qualifiers", source)
        self.assertIn("title={display.provenance}", source)
        self.assertIn("{renderRows(", source)

    def test_procedure_cards_prefer_required_text_over_status_label(self):
        source = PROCEDURE.read_text(encoding="utf-8")
        self.assertIn("function requiredCondition", source)
        self.assertIn("required?.text", source)
        self.assertIn("return \"Requisito identificado\";", source)
        self.assertIn("title={display.provenance}", source)

    def test_decision_criteria_hide_repetitive_documented_status(self):
        source = DECISION.read_text(encoding="utf-8")
        self.assertIn("isDocumentedProvenance", source)
        self.assertIn("? \"✓\"", source)
        self.assertIn("title={item.statusLabel}", source)

    def test_award_fit_445_can_show_real_requirement_text(self):
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
        finally:
            conn.close()

        self.assertIsNotNone(row)
        dados = json.loads(row["dados_json"])
        requirements = (dados.get("analysis_canonical") or {}).get("requirements") or []

        by_label = {clean(item.get("label")): item for item in requirements if isinstance(item, dict)}

        self.assertIn("Formação do Gestor BIM", by_label)
        self.assertIn("Mínimo de 80 horas", best_detail(by_label["Formação do Gestor BIM"]))

        parks = [
            item
            for item in requirements
            if clean(item.get("label")) == "Projetos de parques urbanos"
        ]
        self.assertTrue(parks)
        self.assertTrue(
            any("últimos 15 anos" in best_detail(item) for item in parks),
        )

    def test_fallback_is_requirement_identified_when_no_detail_exists(self):
        self.assertEqual(best_detail({"title": "Item sem detalhe"}), "Requisito identificado")


if __name__ == "__main__":
    unittest.main()
