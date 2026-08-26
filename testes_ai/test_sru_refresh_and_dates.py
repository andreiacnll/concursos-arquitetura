from __future__ import annotations

import unittest

from app.analise.worker import (
    _campos_concurso_extraidos,
    _data_encontrada,
)


class SruRefreshAndDatesTests(unittest.TestCase):
    def test_portuguese_textual_date_is_parsed(self) -> None:
        parsed = _data_encontrada(
            "A entrega ocorre em 18 de setembro de 2026, até às 17:00."
        )
        self.assertEqual(
            parsed,
            ("18/09/2026", "18-09-2026 17:00"),
        )

    def test_dot_separated_date_is_parsed(self) -> None:
        parsed = _data_encontrada(
            "Publicado em 05.08.2026."
        )
        self.assertEqual(
            parsed,
            ("05/08/2026", "05-08-2026"),
        )

    def test_design_facts_enrich_empty_competition_dates(self) -> None:
        concurso = {
            "data": "",
            "data_entrega_propostas": "",
            "preco_base": "",
            "tipo_procedimento": "Concurso Público",
            "criterio_tipo": "",
            "criterio_resumo": "",
            "criterio_detalhe": "",
            "entregaveis": "",
        }
        ficha = {
            "identificacao": {
                "tipo_procedimento": "Conceção-Construção",
            },
            "design_competition_extraction": {
                "facts": {
                    "publication_date": {
                        "value": "Publicado em 5 de agosto de 2026.",
                    },
                    "submission_deadline": {
                        "value": (
                            "As propostas são entregues até "
                            "18 de setembro de 2026 às 17:00."
                        ),
                    },
                },
            },
            "criterios": {
                "criterio_adjudicacao": "Qualidade + Preço",
                "resumo": "Qualidade 70% • Preço 30%",
            },
        }

        fields = _campos_concurso_extraidos(
            concurso,
            ficha,
        )

        self.assertEqual(fields["data"], "05/08/2026")
        self.assertEqual(
            fields["data_entrega_propostas"],
            "18-09-2026 17:00",
        )
        self.assertEqual(
            fields["tipo_procedimento"],
            "Conceção-Construção",
        )
        self.assertEqual(
            fields["criterio_tipo"],
            "Qualidade + Preço",
        )


if __name__ == "__main__":
    unittest.main()
