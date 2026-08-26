from __future__ import annotations

import os
import unittest
from pathlib import Path

from app import api, database

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ENV = ROOT / "frontend" / ".env.local"


class SearchDashboardRegressionV1715Tests(unittest.TestCase):
    def test_local_frontend_points_to_running_backend_port(self):
        if not FRONTEND_ENV.exists():
            self.skipTest("frontend/.env.local não existe neste checkout")

        env = FRONTEND_ENV.read_text(encoding="utf-8")
        self.assertIn("NEXT_PUBLIC_API_URL=http://localhost:8000", env)
        self.assertNotIn("NEXT_PUBLIC_API_URL=http://localhost:8001", env)

    def test_backend_uses_project_database_with_competitions(self):
        self.assertEqual(database.DB_PATH.resolve(), (ROOT / "concursos.db").resolve())
        self.assertTrue(database.DB_PATH.exists())
        self.assertGreater(database.DB_PATH.stat().st_size, 0)

    def test_search_endpoint_payload_contains_current_relevant_results(self):
        payload = api.executar_listagem(
            periodo="atual",
            pesquisa=None,
            entidade=None,
            tipo_procedimento=None,
            apenas_relevantes=True,
            estado="todos",
            limite=100,
            pagina=1,
        )
        resultados = payload.get("resultados") or []

        self.assertGreater(payload.get("total", 0), 0)
        self.assertGreater(len(resultados), 0)
        self.assertTrue(all(item.get("relevante") == 1 for item in resultados))
        self.assertIn(445, {item.get("id") for item in resultados})
        self.assertTrue(any(item.get("estado") == "aberto" for item in resultados))
        self.assertTrue(any(item.get("estado") == "sem_prazo" for item in resultados))

    def test_unknown_or_relative_deadlines_do_not_disappear_silently(self):
        payload = api.executar_listagem(
            periodo="atual",
            pesquisa=None,
            entidade=None,
            tipo_procedimento=None,
            apenas_relevantes=True,
            estado="sem_prazo",
            limite=100,
            pagina=1,
        )
        resultados = payload.get("resultados") or []

        self.assertGreater(len(resultados), 0)
        self.assertTrue(
            any(
                item.get("data_limite") in (None, "")
                or "publicação" in str(item.get("data_limite") or "").lower()
                for item in resultados
            )
        )

    def test_known_competitions_still_exist(self):
        current = api.executar_listagem(
            periodo="atual",
            pesquisa=None,
            entidade=None,
            tipo_procedimento=None,
            apenas_relevantes=True,
            estado="todos",
            limite=100,
            pagina=1,
        )["resultados"]
        historic = api.executar_listagem(
            periodo="historico",
            pesquisa=None,
            entidade=None,
            tipo_procedimento=None,
            apenas_relevantes=True,
            estado="todos",
            limite=100,
            pagina=1,
        )["resultados"]
        ids = {item.get("id") for item in [*current, *historic]}

        self.assertIn(445, ids)
        self.assertIn(435, ids)


if __name__ == "__main__":
    unittest.main()
