from __future__ import annotations

import unittest

from app.analise.worker import _campos_concurso_extraidos
from app.coletor_lisboa_sru import infer_procedure_type
from app.fontes.common import infer_procedure_type as infer_external_type


class SruSourceEnrichmentTests(unittest.TestCase):
    def test_conception_build_has_priority_over_public_tender(self) -> None:
        title = (
            "Concurso Público Conceção-Construção "
            "Pavilhão da Flamenga"
        )
        self.assertEqual(
            infer_procedure_type(title),
            "Conceção-Construção",
        )
        self.assertEqual(
            infer_external_type(title),
            "Conceção-Construção",
        )

    def test_document_analysis_can_fill_empty_card_fields(self) -> None:
        concurso = {
            "link": "https://www.lisboasru.pt/contratacao-publica#REF",
            "data": None,
            "data_entrega_propostas": None,
            "preco_base": None,
            "tipo_procedimento": "Concurso Público",
            "criterio_tipo": None,
            "criterio_resumo": None,
            "criterio_detalhe": None,
            "entregaveis": None,
        }
        ficha = {
            "identificacao": {
                "tipo_procedimento": "Conceção-Construção",
            },
            "economia": {
                "valor_procedimento": "125 000,00 €",
            },
            "criterios": {
                "criterio_adjudicacao": "Melhor relação qualidade-preço",
                "resumo": "Qualidade 70% • Preço 30%",
                "detalhe": "Qualidade 70%; Preço 30%",
                "percentagens": [
                    {
                        "criterio": "Qualidade",
                        "percentagem": "70%",
                    },
                    {
                        "criterio": "Preço",
                        "percentagem": "30%",
                    },
                ],
            },
            "entregaveis": [
                "Memória descritiva",
                "Peças desenhadas",
            ],
            "document_insights": {
                "timeline": [
                    {
                        "type": "publicacao",
                        "date": "2026-08-05",
                        "confirmed": True,
                    },
                    {
                        "type": "entrega_propostas",
                        "date": "2026-09-18 17:00",
                        "confirmed": True,
                    },
                ],
                "procedure_summary": {},
            },
        }

        fields = _campos_concurso_extraidos(
            concurso,
            ficha,
        )

        self.assertEqual(
            fields["data"],
            "05/08/2026",
        )
        self.assertEqual(
            fields["data_entrega_propostas"],
            "18-09-2026 17:00",
        )
        self.assertEqual(
            fields["tipo_procedimento"],
            "Conceção-Construção",
        )
        self.assertEqual(
            fields["criterio_resumo"],
            "Qualidade 70% • Preço 30%",
        )


if __name__ == "__main__":
    unittest.main()
