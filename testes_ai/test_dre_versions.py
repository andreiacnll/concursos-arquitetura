import unittest

from app.dre import resolver_versoes_dr


class DRVersions(unittest.TestCase):
    def _resolver(self, referencia: str):
        original = {"numero": "18356/2026", "id_dr": "419967294"}
        candidato = {"numero": "20870/2026", "texto": referencia}
        return resolver_versoes_dr(original, [candidato]), candidato

    def _assert_match(self, referencia: str):
        resultado, candidato = self._resolver(referencia)
        self.assertTrue(resultado["resolved"])
        self.assertEqual(resultado["current"], candidato)

    def test_n_ponto_ordinal(self):
        self._assert_match(
            "Altera\u00e7\u00e3o do An\u00fancio de procedimento n.\u00ba 18356/2026"
        )

    def test_n_ordinal(self):
        self._assert_match(
            "Altera\u00e7\u00e3o do An\u00fancio de procedimento n\u00ba 18356/2026"
        )

    def test_n_ponto_grau(self):
        self._assert_match(
            "Altera\u00e7\u00e3o do An\u00fancio de procedimento n.\u00b0 18356/2026"
        )

    def test_n_grau(self):
        self._assert_match(
            "Altera\u00e7\u00e3o do An\u00fancio de procedimento n\u00b0 18356/2026"
        )

    def test_n_ponto_o(self):
        self._assert_match(
            "Altera\u00e7\u00e3o do An\u00fancio de procedimento n.o 18356/2026"
        )

    def test_espacos_e_nbsp(self):
        self._assert_match(
            "Altera\u00e7\u00e3o do An\u00fancio de procedimento "
            "N.\u00ba\u00a0  18356/2026"
        )

    def test_rejeita_titulo_sem_referencia(self):
        resultado, _ = self._resolver(
            "Projeto com o mesmo t\u00edtulo e a mesma entidade"
        )
        self.assertFalse(resultado["resolved"])

    def test_rejeita_alteracao_de_outro_anuncio(self):
        resultado, _ = self._resolver(
            "Altera\u00e7\u00e3o do An\u00fancio de procedimento n.\u00ba 99999/2026"
        )
        self.assertFalse(resultado["resolved"])

    def test_cadeia(self):
        original = {"numero": "10000/2026"}
        versao_b = {
            "numero": "20000/2026",
            "texto": "Altera\u00e7\u00e3o do An\u00fancio de procedimento n.\u00ba 10000/2026",
        }
        versao_c = {
            "numero": "30000/2026",
            "texto": "Altera\u00e7\u00e3o do An\u00fancio de procedimento n\u00ba 20000/2026",
        }
        resultado = resolver_versoes_dr(original, [versao_b, versao_c])
        self.assertEqual(resultado["chain"], [original, versao_b, versao_c])
        self.assertEqual(resultado["current"], versao_c)

    def test_rejeita_ambiguidade_sem_evidencia(self):
        original = {"numero": "18356/2026"}
        candidatos = [
            {"texto": "Projeto escolar semelhante"},
            {"texto": "Projeto escolar da mesma entidade"},
        ]
        resultado = resolver_versoes_dr(original, candidatos)
        self.assertFalse(resultado["resolved"])
        self.assertEqual(resultado["chain"], [original])


if __name__ == "__main__":
    unittest.main()