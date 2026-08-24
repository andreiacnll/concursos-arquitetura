from __future__ import annotations

import json
import sqlite3
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "concursos.db"
HELPER = ROOT / "frontend" / "src" / "lib" / "analysis-display.ts"
PROCEDURE = ROOT / "frontend" / "src" / "components" / "analise" / "ProcedureSpecificCards.tsx"
LUMIAR_JOB60 = ROOT / "analise_documentos" / "420959" / "jobs" / "60" / "ficha.json"


class GoldenReferencesV1714Tests(unittest.TestCase):
    def _analysis(self, concurso_id: int) -> dict:
        if not DB.exists():
            self.skipTest("concursos.db não existe neste checkout")
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """
                SELECT dados_json
                FROM analises
                WHERE concurso_id = ?
                  AND dados_json IS NOT NULL
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (concurso_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            self.skipTest(f"análise {concurso_id} não encontrada")
        return json.loads(row["dados_json"])

    def _format(self, examples: list[dict]) -> list[dict]:
        script = r'''
const fs = require("fs");
const vm = require("vm");
const ts = require("typescript");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const src = fs.readFileSync("src/lib/analysis-display.ts", "utf8");
const js = ts.transpileModule(src, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const moduleRef = { exports: {} };
vm.runInNewContext(js, { module: moduleRef, exports: moduleRef.exports, require, console });
console.log(JSON.stringify(input.map((entry) => moduleRef.exports.formatAnalysisItemForDisplay(entry.item, entry.kind))));
'''
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

    def test_445_capacity_items_are_composed_not_concatenated(self):
        data = self._analysis(445)
        procedure = data["procedure_analysis"]
        by_code = {
            item.get("criterion_code"): item
            for item in procedure["award_criteria"]["scoring_requirements"]
        }
        formatted = self._format(
            [
                {"kind": "requirement", "item": by_code["A1"]},
                {"kind": "requirement", "item": by_code["A3"]},
                {"kind": "requirement", "item": by_code["A4"]},
                {"kind": "exclusion", "item": procedure["eligibility"]["explicit_exclusions"][0]},
                {"kind": "exclusion", "item": procedure["eligibility"]["explicit_exclusions"][1]},
                {"kind": "requirement", "item": procedure["technical_team"][0]},
                {"kind": "scope", "item": procedure["contract"]["scope_services"][0]},
            ]
        )

        parques, terrenos, bim, repeated, bim_exclusion, team, scope = formatted
        self.assertEqual(parques["primaryValue"], "Até 5 projetos")
        self.assertEqual(parques["qualifiers"][0], "40% da avaliação")
        self.assertIn("UE", parques["qualifiers"])
        self.assertIn("concluídos", parques["qualifiers"])
        self.assertIn("últimos 15 anos", parques["qualifiers"])
        self.assertIn("≥ 2 M€", parques["qualifiers"])

        self.assertEqual(terrenos["primaryValue"], "Até 5 projetos")
        self.assertIn("15% da avaliação", terrenos["qualifiers"])
        self.assertIn("≥ 100 000 m³", terrenos["qualifiers"])

        self.assertEqual(bim["primaryValue"], "Formação ≥ 80 h")
        self.assertEqual(bim["qualifiers"][0], "5% da avaliação")
        self.assertIn("Só formação em software não é aceite", bim["qualifiers"])

        self.assertEqual(repeated["primaryValue"], "Exclusão explícita")
        self.assertNotIn("Exclusão se incumprido", repeated["qualifiers"])
        self.assertEqual(bim_exclusion["primaryValue"], "Formação ≥ 80 h")
        self.assertIn("Exclusão se incumprido", bim_exclusion["qualifiers"])

        self.assertEqual(team["primaryValue"], "Coordenação BIM — arquitetura e paisagismo")
        self.assertIn("Coordenação BIM — estruturas", team["qualifiers"])
        self.assertEqual(scope["primaryValue"], "Espaço público")

        rendered_text = " ".join(
            [item["label"] + " " + item["primaryValue"] + " " + " ".join(item["qualifiers"]) for item in formatted]
        )
        for bad in ["urbanos40%", "projetosúltimos", "anosUE", "BIM5%", "horassó", "propostaExclusão", "BIMRequisito"]:
            self.assertNotIn(bad, rendered_text)

    def test_procedure_rows_owns_child_styles_for_styled_jsx(self):
        source = PROCEDURE.read_text(encoding="utf-8")
        child_block = source.split("function ProcedureRows", 1)[1].split("export default function", 1)[0]

        self.assertIn("<style jsx>", child_block)
        self.assertIn(".analysis-display-item", child_block)
        self.assertIn("display: grid", child_block)
        self.assertIn(".analysis-qualifiers", child_block)
        self.assertIn("flex-wrap: wrap", child_block)
        self.assertIn("gap: 5px", child_block)
        self.assertNotIn("qualifiers.join(\"\")", source)
        self.assertIn("showScoring", source)
        self.assertIn("showTeam", source)

    def test_lumiar_is_golden_for_document_depth_not_forced_project_services_layout(self):
        self.assertTrue(LUMIAR_JOB60.exists())
        data = json.loads(LUMIAR_JOB60.read_text(encoding="utf-8"))

        self.assertGreater(len(json.dumps(data.get("programa_funcional"), ensure_ascii=False)), 1000)
        self.assertGreater(len(json.dumps(data.get("document_insights"), ensure_ascii=False)), 1000)
        self.assertIn("submission_requirements", data)
        self.assertIn("design_work", data["submission_requirements"].get("groups", {}))

        procedure_source = PROCEDURE.read_text(encoding="utf-8")
        self.assertIn('if (family === "design_competition") return null', procedure_source)

    def test_445_is_golden_for_project_service_capacity_depth(self):
        data = self._analysis(445)
        procedure = data["procedure_analysis"]
        canonical = data.get("analysis_canonical") or {}

        self.assertEqual(procedure.get("family"), "project_services")
        self.assertGreaterEqual(len(procedure["documents"]), 5)
        self.assertGreaterEqual(len(procedure["award_criteria"]["scoring_requirements"]), 4)
        self.assertGreaterEqual(len(procedure["technical_team"]), 5)
        self.assertGreaterEqual(len(procedure["eligibility"]["explicit_exclusions"]), 2)
        self.assertGreaterEqual(len(procedure["contract"]["scope_services"]), 5)
        self.assertGreaterEqual(len(procedure["contract"]["phases"]), 3)
        self.assertTrue(any(req.get("profile_dependent") for req in canonical.get("requirements", [])))

    def test_third_procedure_keeps_its_own_family_and_does_not_inherit_445_cards(self):
        data = self._analysis(446)
        procedure = data["procedure_analysis"]

        self.assertEqual(procedure.get("family"), "design_build")
        self.assertGreaterEqual(len(procedure.get("documents") or []), 1)
        self.assertGreaterEqual(len(procedure.get("contract", {}).get("scope_services") or []), 1)
        self.assertEqual(len(procedure.get("technical_team") or []), 0)
        self.assertEqual(len(procedure.get("eligibility", {}).get("requirements") or []), 0)

        source = PROCEDURE.read_text(encoding="utf-8")
        self.assertIn("const showTeam = team.length > 0", source)
        self.assertIn("const showScoring = scoring.length > 0 || experienceWeight !== null", source)


if __name__ == "__main__":
    unittest.main()
