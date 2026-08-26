from __future__ import annotations

import unittest
from unittest.mock import patch

from app.fontes import espaco_arquitetura


class ExternalSourceTransportTests(unittest.TestCase):
    def test_espaco_falls_back_to_current_year_archive(self) -> None:
        archive_html = """
        <html><body>
          <article>
            <a href="/concursos/projeto-de-arquitetura-exemplo/">
              Projeto de Arquitetura Exemplo
            </a>
            <p>Publicado em 5 de Agosto de 2026</p>
          </article>
        </body></html>
        """

        calls: list[str] = []

        def fake_fetch(url: str, **_kwargs: object) -> str:
            calls.append(url)
            if url == espaco_arquitetura.LIST_URL:
                raise RuntimeError("503 temporário")
            if "categoria-concurso" in url:
                return archive_html
            return "<html><body><h1>Projeto de Arquitetura Exemplo</h1></body></html>"

        with patch.object(
            espaco_arquitetura,
            "fetch_html",
            side_effect=fake_fetch,
        ):
            results = espaco_arquitetura.collect()

        self.assertTrue(
            any("categoria-concurso" in url for url in calls)
        )
        self.assertEqual(len(results), 1)
        self.assertIn(
            "Projeto de Arquitetura Exemplo",
            results[0].title,
        )


if __name__ == "__main__":
    unittest.main()
