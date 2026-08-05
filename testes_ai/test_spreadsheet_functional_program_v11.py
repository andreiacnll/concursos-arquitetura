from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from app.analise.design_competition_enrichment import (
    _norm,
    enrich_design_competition,
)
from app.analise.reader.architecture_reader import read_architecture_documents
from app.analise.reader.source_manifest import classify_source, create_source_manifest
from app.analise.reader.spreadsheet_reader import read_spreadsheet_document


class SpreadsheetFunctionalProgramV11Tests(unittest.TestCase):
    def _write_xlsx(self, path: Path, rows: list[list[object]]) -> None:
        def column_name(index: int) -> str:
            value = ""
            while index:
                index, remainder = divmod(index - 1, 26)
                value = chr(65 + remainder) + value
            return value

        xml_rows: list[str] = []
        for row_index, row in enumerate(rows, start=1):
            cells: list[str] = []
            for column_index, value in enumerate(row, start=1):
                if value in (None, ""):
                    continue
                ref = f"{column_name(column_index)}{row_index}"
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    cells.append(f'<c r="{ref}"><v>{value}</v></c>')
                else:
                    escaped = (
                        str(value)
                        .replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    cells.append(
                        f'<c r="{ref}" t="inlineStr"><is><t>{escaped}</t></is></c>'
                    )
            xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "[Content_Types].xml",
                """<?xml version="1.0" encoding="UTF-8"?>
                <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
                  <Default Extension="xml" ContentType="application/xml"/>
                  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
                  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
                </Types>""",
            )
            archive.writestr(
                "_rels/.rels",
                """<?xml version="1.0" encoding="UTF-8"?>
                <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
                </Relationships>""",
            )
            archive.writestr(
                "xl/workbook.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
                <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                  <sheets><sheet name="Folha1" sheetId="1" r:id="rId1"/></sheets>
                </workbook>""",
            )
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                """<?xml version="1.0" encoding="UTF-8"?>
                <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
                </Relationships>""",
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>',
            )

    def _official_repeated_rows(self) -> list[list[object]]:
        rows: list[list[object]] = [
            ["ÁREAS GLOBAIS DA PROPOSTA", "", "", "PROPOSTA"],
            ["Área de intervenção", "", "", 22644],
            ["ÁREAS GLOBAIS DO EXISTENTE", "", "", "EXISTENTE"],
            ["Área bruta de construção total", "", "", 8782.7],
            [],
            [
                "Cód.",
                "Compartimento",
                "Área útil proposta (m2)",
                "Área útil Prog. Funcional (m2)",
                "notes",
            ],
            ["A", "ESPAÇOS DE APRENDIZAGEM FORMAL", "", "", ""],
            ["A 1.1", "Sala de aula normal", "", "", ""],
        ]
        for index in range(1, 25):
            rows.append(["", f"Sala de aula normal .{index}", "", 50, ""])
        rows.extend(
            [
                ["E", "FORMAÇÃO E CERTIFICAÇÃO", "", "", ""],
                ["E 1.1", "Área de espera", "", 8, ""],
                ["E 2.1", "Área de espera", "", 8, ""],
            ]
        )
        return rows

    def test_manifest_accepts_spreadsheets_as_official_documents(self) -> None:
        for name in ("quadro.xlsx", "quadro.xls", "quadro.csv"):
            with self.subTest(name=name):
                source_type, accepted, reason = classify_source(Path(name))
                self.assertEqual(source_type, "official_document")
                self.assertTrue(accepted)
                self.assertNotEqual(reason, "Unknown source type.")

    def test_reconstructs_repeated_compartments_and_preserves_equal_named_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ANEXO_QuadroAreas.xlsx"
            self._write_xlsx(path, self._official_repeated_rows())
            result = read_spreadsheet_document(path)
            table = result["tables"][0]
            rows = table["rows"]

            normal = next(row for row in rows if row["label"] == "Sala de aula normal")
            self.assertEqual(normal["quantity"], 24)
            self.assertEqual(normal["unit_area_m2"], 50.0)
            self.assertEqual(normal["total_area_m2"], 1200.0)
            self.assertEqual(normal["functional_group"], "ESPAÇOS DE APRENDIZAGEM FORMAL")
            self.assertEqual(normal["reconstruction_method"], "spreadsheet_repeated_rows")

            waiting = [row for row in rows if row["label"] == "Área de espera"]
            self.assertEqual(len(waiting), 2)
            self.assertEqual({row["code"] for row in waiting}, {"E 1.1", "E 2.1"})

            metrics = {item["key"]: item for item in table["global_metrics"]}
            self.assertEqual(metrics["area_intervencao"]["total_area_m2"], 22644.0)
            self.assertEqual(metrics["area_intervencao"]["scope"], "proposal")
            self.assertEqual(metrics["area_bruta_total"]["scope"], "existing")
            self.assertFalse(table["calculated_total_is_documental"])


    def test_architecture_reader_persists_structured_tables_before_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "ANEXO_QuadroAreas.xlsx"
            self._write_xlsx(path, self._official_repeated_rows())
            manifest = create_source_manifest(root, job_id=60)
            result = read_architecture_documents(
                concurso={"titulo": "Requalificação de escola"},
                manifest=manifest,
                root=root,
            )
            self.assertTrue(result["structured_tables"])
            table = result["structured_tables"][0]
            self.assertEqual(table["table_type"], "functional_area_schedule")
            self.assertGreaterEqual(table["reliable_row_count"], 3)
            source = next(
                item for item in result["official_source_audit"]
                if item["name"] == path.name
            )
            self.assertEqual(source["read_status"], "read")
            self.assertTrue(source["accepted_for_reader"])

    def test_enrichment_uses_spreadsheet_before_flattened_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ANEXO_QuadroAreas.xlsx"
            rows = self._official_repeated_rows()
            for index in range(20):
                rows.append([f"G {index}", f"Espaço técnico {index}", "", 10 + index, ""])
            self._write_xlsx(path, rows)

            text = (
                "1.1 Painéis A1. "
                "As propostas são apresentadas sobre 3 (três) painéis em formato DIN A1, "
                "com orientação vertical e numeração 1-3, 2-3 e 3-3."
            )
            result = enrich_design_competition(
                documents=[("Termos.pdf", text, _norm(text))],
                facts={"area_util": {"value": "2 m²"}},
                program={
                    "functional_program": {
                        "main_spaces": ["Salas de aula", "Biblioteca"],
                        "requirements": ["Acessibilidade universal"],
                        "constraints": ["Manter o funcionamento escolar"],
                    }
                },
                ficha={"_design_competition_source_hints": [str(path)]},
            )
            program = result["functional_program"]
            schedule = program["area_schedule"]
            self.assertGreaterEqual(schedule["row_count"], 23)
            self.assertGreaterEqual(schedule["reliable_row_count"], 23)
            self.assertIn("spreadsheet", str(schedule["reconstruction_method"]))
            self.assertEqual(program["area_intervencao"]["value"], "22 644 m²")
            self.assertEqual(program["area_util"], {})
            self.assertFalse(schedule["calculated_total_is_documental"])
            self.assertEqual(result["submission"]["physical_panels"]["quantity"], 3)


if __name__ == "__main__":
    unittest.main()
