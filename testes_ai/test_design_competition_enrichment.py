import unittest

from app.analise.design_competition_enrichment import (
    enrich_design_competition,
)


class DesignCompetitionEnrichmentTests(unittest.TestCase):
    def test_rejects_tiny_global_useful_area(self) -> None:
        result = enrich_design_competition(
            documents=[],
            facts={},
            program={
                "functional_program": {
                    "area_util": {"value": "2 m²"},
                    "areas": [
                        {
                            "label": "Sala de aula",
                            "kind": "functional_area",
                            "total_area_m2": 60,
                        },
                        {
                            "label": "Laboratório",
                            "kind": "functional_area",
                            "total_area_m2": 80,
                        },
                    ],
                }
            },
        )
        self.assertEqual(
            result["functional_program"]["area_util"],
            {},
        )

    def test_requires_explicit_panel_quantity(self) -> None:
        result = enrich_design_competition(
            documents=[
                (
                    "programa.pdf",
                    "O painel deve respeitar o anonimato.",
                    "o painel deve respeitar o anonimato",
                )
            ],
            facts={},
            program={"functional_program": {"areas": []}},
        )
        self.assertIsNone(
            result["submission"]["physical_panels"]["quantity"]
        )

    def test_extracts_a3_booklet_and_vat(self) -> None:
        result = enrich_design_competition(
            documents=[
                (
                    "programa.pdf",
                    "texto",
                    (
                        "caderno a3 digital em pdf orientacao horizontal "
                        "maximo de 20 paginas incluindo memoria descritiva "
                        "ao preco dos servicos acresce iva a taxa legal em vigor"
                    ),
                )
            ],
            facts={
                "design_services_value": {
                    "value": "1 221 957,00 EUR",
                }
            },
            program={"functional_program": {"areas": []}},
        )
        booklet = result["submission"]["digital_booklet"]
        self.assertTrue(booklet["required"])
        self.assertEqual(booklet["format"], "PDF")
        self.assertEqual(booklet["page_size"], "A3")
        self.assertEqual(booklet["orientation"], "horizontal")
        self.assertEqual(booklet["max_pages"], 20)
        self.assertEqual(
            result["financial"]["design_services_vat_status"],
            "excluded",
        )


if __name__ == "__main__":
    unittest.main()
