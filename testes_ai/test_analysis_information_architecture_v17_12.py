from __future__ import annotations

import json
import sqlite3
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "frontend" / "src" / "lib" / "analysis-display.ts"
UNIVERSAL_SUBMISSION = ROOT / "frontend" / "src" / "components" / "analise" / "UniversalSubmissionCards.tsx"
PROCEDURE = ROOT / "frontend" / "src" / "components" / "analise" / "ProcedureSpecificCards.tsx"
DESIGN = ROOT / "frontend" / "src" / "components" / "analise" / "DesignCompetitionAnalysis.tsx"
MODAL = ROOT / "frontend" / "src" / "components" / "analise" / "AnalysisQuestionsModal.tsx"
LUMIAR_JOB60 = ROOT / "analise_documentos" / "420959" / "jobs" / "60" / "ficha.json"
DB = ROOT / "concursos.db"


class AnalysisInformationArchitectureV1712Tests(unittest.TestCase):
    def _format_with_frontend_helper(self, examples):
        script = r"""
const fs = require("fs");
const vm = require("vm");
const ts = require("typescript");

const input = JSON.parse(fs.readFileSync(0, "utf8"));
const src = fs.readFileSync("src/lib/analysis-display.ts", "utf8");
const js = ts.transpileModule(src, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;

const moduleRef = { exports: {} };
vm.runInNewContext(js, {
  module: moduleRef,
  exports: moduleRef.exports,
  require,
  console,
});

const format = moduleRef.exports.formatAnalysisItemForDisplay;
console.log(JSON.stringify(input.map((entry) => format(entry.item, entry.kind))));
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT / "frontend",
            input=json.dumps(examples, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_central_display_helper_exists_and_keeps_evidence_separate(self):
        source = HELPER.read_text(encoding="utf-8")

        self.assertIn("formatAnalysisItemForDisplay", source)
        self.assertIn("primaryValue", source)
        self.assertIn("provenance", source)
        self.assertIn("source: {", source)
        self.assertNotIn("safeExcerptSummary", source)
        self.assertIn("fallbackPrimary", source)
        self.assertIn("A confirmar nas peças", source)
        self.assertNotIn("primaryValue = \"Requisito identificado\"", source)

    def test_status_label_is_not_used_as_primary_value(self):
        source = HELPER.read_text(encoding="utf-8")
        primary_block = source.split("let primaryValue", 1)[1].split("return {", 1)[0]

        self.assertNotIn("status_label", primary_block)
        self.assertNotIn("source.excerpt", primary_block)
        self.assertIn("isProvenanceOnly", primary_block)

    def test_cards_have_accessible_sources_qualifiers_and_show_all_controls(self):
        combined = "\n".join(
            [
                UNIVERSAL_SUBMISSION.read_text(encoding="utf-8"),
                PROCEDURE.read_text(encoding="utf-8"),
            ]
        )

        self.assertIn('type="button"', combined)
        self.assertIn("Fontes", combined)
        self.assertIn("Ver todos", combined)
        self.assertIn("aria-expanded", combined)
        self.assertIn("display.source.excerpt", combined)
        self.assertIn("display.qualifiers", combined)

    def test_submission_separates_documents_technical_content_and_formats(self):
        source = UNIVERSAL_SUBMISSION.read_text(encoding="utf-8")

        self.assertIn('"document"', source)
        self.assertIn('"technical"', source)
        self.assertIn('"format"', source)
        self.assertIn('"exclusion"', source)

    def test_design_award_fit_uses_central_requirement_formatter(self):
        source = DESIGN.read_text(encoding="utf-8")

        self.assertIn("formatAnalysisItemForDisplay(requirement, \"requirement\")", source)

    def test_dynamic_modal_logic_is_not_changed_by_this_layer(self):
        source = MODAL.read_text(encoding="utf-8")

        self.assertIn("CNLL_EFFECTIVE_MODAL_QUESTIONS_V17_10", source)
        self.assertIn("const effectiveQuestions =", source)

    def test_lumiar_job60_still_contains_rich_existing_data(self):
        self.assertTrue(LUMIAR_JOB60.exists())
        data = json.loads(LUMIAR_JOB60.read_text(encoding="utf-8"))

        self.assertIn("programa_funcional", data)
        self.assertIn("document_insights", data)
        self.assertIn("submission_requirements", data)
        self.assertGreater(len(json.dumps(data.get("programa_funcional"), ensure_ascii=False)), 1000)
        self.assertGreater(len(json.dumps(data.get("document_insights"), ensure_ascii=False)), 1000)

    def test_445_keeps_rich_source_data_for_expansion(self):
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
        data = json.loads(row["dados_json"])
        procedure = data.get("procedure_analysis") or {}
        submission = procedure.get("submission") or {}
        formats = submission.get("formats_and_limits") or []
        technical = submission.get("proposal_documents") or []
        exclusions = submission.get("critical_conditions") or []

        self.assertGreaterEqual(len(formats), 5)
        self.assertGreaterEqual(len(technical), 5)
        self.assertGreaterEqual(len(exclusions), 1)
        self.assertTrue(any(item.get("source_excerpt") for item in formats))
        self.assertTrue(any(item.get("source_excerpt") for item in technical))

        format_titles = {item.get("title") for item in formats}
        technical_titles = {item.get("title") for item in technical}
        self.assertNotEqual(format_titles, technical_titles)

    def test_real_lumiar_formatter_uses_semantic_values_not_contaminated_excerpts(self):
        self.assertTrue(LUMIAR_JOB60.exists())
        data = json.loads(LUMIAR_JOB60.read_text(encoding="utf-8"))
        design_work = data["submission_requirements"]["groups"]["design_work"]

        def find(title_part: str):
            return next(item for item in design_work if title_part in item.get("title", ""))

        formatted = self._format_with_frontend_helper(
            [
                {"kind": "technical", "item": find("Imagens para divulgação")},
                {"kind": "technical", "item": find("Caderno digital")},
                {"kind": "technical", "item": find("Reprodução digital dos painéis")},
            ]
        )

        imagens = formatted[0]
        self.assertEqual(imagens["primaryValue"], "5 imagens")
        self.assertEqual(imagens["qualifiers"], ["JPG"])
        self.assertNotIn("QuadroAreas", imagens["primaryValue"])
        self.assertNotIn("pdf", " ".join(imagens["qualifiers"]).lower())

        caderno = formatted[1]
        self.assertEqual(caderno["primaryValue"], "Memória / peças previstas para o caderno")
        self.assertNotIn("ma Preliminar", caderno["primaryValue"])

        reproducao = formatted[2]
        self.assertEqual(reproducao["primaryValue"], "Reprodução digital dos painéis")

    def test_real_445_formatter_keeps_requirements_as_separate_structured_chips(self):
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
        data = json.loads(row["dados_json"])
        scope = data["procedure_analysis"]["contract"]["scope_services"][0]
        requirements = data["analysis_canonical"]["requirements"]
        parques = next(item for item in requirements if item.get("label") == "Projetos de parques urbanos")
        formacao = next(item for item in requirements if item.get("label") == "Formação do Gestor BIM")

        formatted = self._format_with_frontend_helper(
            [
                {"kind": "scope", "item": scope},
                {"kind": "requirement", "item": parques},
                {"kind": "requirement", "item": formacao},
            ]
        )

        self.assertEqual(formatted[0]["primaryValue"], "Espaço público")
        self.assertNotIn("PARQUE URBANO", formatted[0]["primaryValue"])

        self.assertEqual(formatted[1]["primaryValue"], "Até 5 projetos")
        self.assertIn("últimos 15 anos", formatted[1]["qualifiers"])
        self.assertIn("UE", formatted[1]["qualifiers"])
        self.assertIn("concluídos", formatted[1]["qualifiers"])
        self.assertIn("≥ 2 M€", formatted[1]["qualifiers"])
        self.assertNotIn("≥ 15 anos", formatted[1]["qualifiers"])

        self.assertEqual(formatted[2]["primaryValue"], "Formação ≥ 80 h")
        self.assertIn("Só formação em software não é aceite", formatted[2]["qualifiers"])


if __name__ == "__main__":
    unittest.main()
