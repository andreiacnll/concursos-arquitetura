import unittest

from app.coletor import atualizar_versao_dr_no_checkpoint


class ColetorDRVersionsTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "id_portal_base": "451478",
            "numero_anuncio": "18356/2026",
            "link_anuncio_dr": "https://files.diariodarepublica.pt/cp_hora/2026/07/137/419967294.pdf",
            "criterio_tipo": "Monofator",
            "enriquecimento_dr_concluido": True,
        }
        self.alteracao = {
            "id_portal_base": "999999",
            "numero_anuncio": "20870/2026",
            "texto": "Altera\u00e7\u00e3o do An\u00fancio de procedimento n.\u00ba 18356/2026",
            "link_anuncio_dr": "https://files.diariodarepublica.pt/cp_hora/2026/08/160/420000000.pdf",
            "data_limite": "30-09-2026 17:00",
        }
        self.chamadas = []

    def enriquecer(self, concurso, link):
        self.chamadas.append(link)
        atualizado = dict(concurso)
        atualizado["criterio_tipo"] = "Multifator"
        atualizado["enriquecimento_dr_concluido"] = True
        return atualizado

    def test_enriquecido_sem_nova_versao_nao_reprocessa(self):
        por_id = {"451478": dict(self.original)}
        candidato = dict(self.alteracao)
        candidato["texto"] = "Projeto escolar com t\u00edtulo semelhante"
        resultado = atualizar_versao_dr_no_checkpoint(
            por_id, candidato, self.enriquecer
        )
        self.assertFalse(resultado["changed"])
        self.assertEqual(self.chamadas, [])
        self.assertEqual(por_id["451478"]["criterio_tipo"], "Monofator")

    def test_enriquecido_com_alteracao_explicita_deteta_nova_versao(self):
        por_id = {"451478": dict(self.original)}
        resultado = atualizar_versao_dr_no_checkpoint(
            por_id, self.alteracao, self.enriquecer
        )
        self.assertTrue(resultado["changed"])
        self.assertEqual(len(self.chamadas), 1)
        self.assertEqual(por_id["451478"]["criterio_tipo"], "Multifator")
        self.assertEqual(por_id["451478"]["numero_anuncio"], "20870/2026")

    def test_alteracao_ambigua_nao_atualiza(self):
        por_id = {
            "451478": dict(self.original),
            "outro": {**self.original, "id_portal_base": "outro"},
        }
        resultado = atualizar_versao_dr_no_checkpoint(
            por_id, self.alteracao, self.enriquecer
        )
        self.assertFalse(resultado["changed"])
        self.assertEqual(resultado["reason"], "ambiguous")
        self.assertEqual(self.chamadas, [])

    def test_nova_versao_mantem_mesmo_concurso_sem_duplicado(self):
        por_id = {"451478": dict(self.original)}
        atualizar_versao_dr_no_checkpoint(
            por_id, self.alteracao, self.enriquecer
        )
        self.assertEqual(list(por_id), ["451478"])
        self.assertEqual(por_id["451478"]["id_portal_base"], "451478")


if __name__ == "__main__":
    unittest.main()