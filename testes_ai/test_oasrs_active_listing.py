from __future__ import annotations

import unittest
from unittest.mock import patch

from app.fontes import oasrs_encomenda


ACTIVE_HTML = """
<html><body>
  <article>
    <span>Concurso • 2026-08-05</span>
    <a href="/concursos/detalhe/abc/projeto-paisagista">
      Projeto de Arquitetura Paisagista
    </a>
  </article>
</body></html>
"""

DETAIL_HTML = """
<html><body>
  <main>
    <h1>Projeto de Arquitetura Paisagista</h1>
    <p>Promotor</p><p>Município Exemplo</p>
    <p>Localização</p><p>Lisboa</p>
  </main>
</body></html>
"""


class OasrsActiveListingTests(unittest.TestCase):
    def test_forced_active_status_does_not_depend_on_card_wording(self) -> None:
        items = oasrs_encomenda.parse_listing(
            ACTIVE_HTML,
            base_url=oasrs_encomenda.ACTIVE_LIST_URLS[0],
            forced_status="em_curso",
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["status"], "em_curso")
        self.assertEqual(
            items[0]["publication_date"],
            "2026-08-05",
        )

    def test_collect_uses_official_active_sections(self) -> None:
        calls: list[str] = []

        def fake_fetch(url: str, **_kwargs: object) -> str:
            calls.append(url)
            if url == oasrs_encomenda.ACTIVE_LIST_URLS[0]:
                return ACTIVE_HTML
            if url == oasrs_encomenda.ACTIVE_LIST_URLS[1]:
                return "<html><body>Sem concursos em curso</body></html>"
            if "/concursos/detalhe/" in url:
                return DETAIL_HTML
            raise AssertionError(f"URL inesperado: {url}")

        with patch.object(
            oasrs_encomenda,
            "fetch_html",
            side_effect=fake_fetch,
        ):
            results = oasrs_encomenda.collect()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "em_curso")
        self.assertIn(
            oasrs_encomenda.ACTIVE_LIST_URLS[0],
            calls,
        )
        self.assertIn(
            oasrs_encomenda.ACTIVE_LIST_URLS[1],
            calls,
        )


if __name__ == "__main__":
    unittest.main()
