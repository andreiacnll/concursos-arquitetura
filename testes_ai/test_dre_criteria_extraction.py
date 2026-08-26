import unittest

from app.dre import extrair_criterio


class DreCriteriaExtractionTests(unittest.TestCase):
    def test_explicit_monofactor_without_weight_is_extracted(self) -> None:
        result = extrair_criterio(
            """
            21 - CRITERIO DE ADJUDICACAO
            Multifator: Nao
            Monofator:
            Nome: Preco
            24 - CONDICOES DO CONTRATO
            """
        )

        self.assertEqual(result["criterio_tipo"], "Monofator")
        self.assertEqual(result["criterio_resumo"], "Preco")
        self.assertEqual(result["criterio_detalhe"], "Preco")

    def test_missing_criterion_does_not_create_a_fallback(self) -> None:
        result = extrair_criterio("24 - CONDICOES DO CONTRATO\nFaturacao: Permitido")

        self.assertEqual(
            result,
            {
                "criterio_tipo": None,
                "criterio_resumo": None,
                "criterio_detalhe": None,
            },
        )


if __name__ == "__main__":
    unittest.main()