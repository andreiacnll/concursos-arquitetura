from __future__ import annotations

from contextlib import closing

import tempfile
import unittest
from pathlib import Path

from app import database


class AtualizarDadosConcursoLinkDrTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self.temp_dir.name) / "test_concursos.db"
        database.criar_base_dados()
        self.link = "https://base.example/procedimentos/123"
        database.guardar_concurso(
            titulo="Concurso de teste",
            entidade="Entidade de teste",
            link=self.link,
            data="2026-08-25",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _concurso(self) -> dict:
        with closing(database.abrir_conexao()) as connection:
            row = connection.execute(
                "SELECT * FROM concursos WHERE link = ?",
                (self.link,),
            ).fetchone()
        return dict(row)

    def test_persiste_e_atualiza_link_anuncio_dr(self) -> None:
        link_dr = "https://diariodarepublica.pt/dr/detalhe/anuncio/123"

        updated = database.atualizar_dados_concurso(
            self.link,
            link_anuncio_dr=link_dr,
        )

        self.assertTrue(updated)
        self.assertEqual(self._concurso()["link_anuncio_dr"], link_dr)

    def test_chamada_sem_link_anuncio_dr_mantem_valor_existente(self) -> None:
        link_dr = "https://diariodarepublica.pt/dr/detalhe/anuncio/123"
        database.atualizar_dados_concurso(
            self.link,
            link_anuncio_dr=link_dr,
        )

        updated = database.atualizar_dados_concurso(
            self.link,
            preco_base="100000",
        )

        concurso = self._concurso()
        self.assertTrue(updated)
        self.assertEqual(concurso["link_anuncio_dr"], link_dr)
        self.assertEqual(concurso["preco_base"], "100000")


if __name__ == "__main__":
    unittest.main()