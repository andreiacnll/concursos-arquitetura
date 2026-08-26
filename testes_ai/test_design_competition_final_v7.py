import unittest

from app.analise.design_competition_enrichment import (
    _explicit_panel_quantity,
    _norm,
    _row_from_line,
    enrich_design_competition,
)


class DesignCompetitionFinalV5Tests(unittest.TestCase):
    def base_program(self) -> dict:
        return {
            "functional_program": {
                "summary": "",
                "intervention_type": "",
                "areas": [],
                "main_spaces": [],
                "requirements": [],
                "constraints": [],
            }
        }

    def test_reads_panel_quantity_in_digits_and_words(self) -> None:
        examples = [
            "apresentadas sobre 3 painéis em formato DIN A1",
            "apresentadas sobre três painéis em formato DIN A1",
            "apresentadas sobre 3 (três) painéis",
            "apresentadas sobre três (3) painéis",
            "painéis, em número de três, formato A1",
        ]
        for example in examples:
            with self.subTest(example=example):
                self.assertEqual(
                    _explicit_panel_quantity(_norm(example)),
                    3,
                )

    def test_does_not_invent_one_panel(self) -> None:
        self.assertIsNone(
            _explicit_panel_quantity(
                _norm("O painel deve respeitar o anonimato.")
            )
        )

    def test_preserves_explicit_large_global_useful_area(self) -> None:
        program = self.base_program()
        program["functional_program"]["area_util"] = {
            "value": "8 500 m²",
            "kind": "global_area",
            "total_area_m2": 8500,
            "evidence_excerpt": "Área útil 8 500 m².",
        }
        result = enrich_design_competition(
            documents=[],
            facts={},
            program=program,
        )
        self.assertEqual(
            result["functional_program"]["area_util"]["value"],
            "8 500 m²",
        )

    def test_rejects_small_room_area_as_global_useful_area(self) -> None:
        program = self.base_program()
        program["functional_program"]["area_util"] = {
            "value": "2 m²",
            "kind": "global_area",
            "total_area_m2": 2,
            "evidence_excerpt": "Área útil de uma sala 2 m².",
        }
        result = enrich_design_competition(
            documents=[],
            facts={},
            program=program,
        )
        self.assertEqual(
            result["functional_program"]["area_util"],
            {},
        )

    def test_flattened_row_is_not_duplicated(self) -> None:
        result = enrich_design_competition(
            documents=[
                (
                    "Programa.pdf",
                    "Laboratório de ciências 2 75,00 150,00 m²",
                    "laboratorio de ciencias 2 75,00 150,00 m2",
                )
            ],
            facts={},
            program=self.base_program(),
        )
        rows = result["functional_program"]["area_schedule"]["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["quantity"], 2)
        self.assertAlmostEqual(rows[0]["unit_area_m2"], 75.0)
        self.assertAlmostEqual(rows[0]["total_area_m2"], 150.0)

    def test_layout_rows_work_in_both_column_orders(self) -> None:
        label_first = _row_from_line(
            "SALA DE AULA 2 60,60 121,20",
            "Programa.pdf",
        )
        numbers_first = _row_from_line(
            "2 60,60 121,20 SALA DE AULA",
            "Programa.pdf",
        )
        for row in (label_first, numbers_first):
            self.assertIsNotNone(row)
            self.assertEqual(row["label"], "SALA DE AULA")
            self.assertEqual(row["quantity"], 2)
            self.assertAlmostEqual(row["total_area_m2"], 121.2)


if __name__ == "__main__":
    unittest.main()
