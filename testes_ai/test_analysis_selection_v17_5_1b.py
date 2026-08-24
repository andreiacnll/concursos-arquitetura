from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import database


class AnalysisSelectionV1751BTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.old_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "selection.db"

        # IMPORTANTE NO WINDOWS:
        # sqlite3.Connection.__exit__ faz commit/rollback mas NÃO fecha
        # a ligação. Fechamos explicitamente para não bloquear o ficheiro.
        conn = sqlite3.connect(database.DB_PATH)
        try:
            conn.execute(
                """
                CREATE TABLE analises (
                    id INTEGER PRIMARY KEY,
                    concurso_id INTEGER NOT NULL,
                    user_id TEXT,
                    company_id INTEGER,
                    estado TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    score INTEGER,
                    dados_json TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO analises
                VALUES
                    (19, 389, NULL, NULL, 'concluida',
                     '2026-08-07 15:00:00', 86, '{}')
                """
            )
            conn.execute(
                """
                INSERT INTO analises
                VALUES
                    (2, 389, 'user-a', 28, 'concluida',
                     '2026-08-07 14:00:00', 38,
                     '{"analysis_canonical":{"questions":[1,2,3,4]}}')
                """
            )
            conn.execute(
                """
                INSERT INTO analises
                VALUES
                    (99, 389, 'user-b', 28, 'concluida',
                     '2026-08-07 16:00:00', 99, '{}')
                """
            )
            conn.execute(
                """
                INSERT INTO analises
                VALUES
                    (30, 500, NULL, NULL, 'concluida',
                     '2026-08-07 16:00:00', 70, '{}')
                """
            )
            conn.execute(
                """
                INSERT INTO analises
                VALUES
                    (40, 600, NULL, 28, 'concluida',
                     '2026-08-07 16:00:00', 66, '{}')
                """
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self) -> None:
        database.DB_PATH = self.old_db_path
        self.temp.cleanup()

    def test_user_company_analysis_wins_over_newer_system(self) -> None:
        row = database.obter_analise_ativa_concurso(
            389, "user-a", 28
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], 2)
        self.assertEqual(row["score"], 38)

    def test_other_user_never_wins(self) -> None:
        row = database.obter_analise_ativa_concurso(
            389, "user-a", 28
        )
        self.assertNotEqual(row["id"], 99)

    def test_user_analysis_wins_without_company_id(self) -> None:
        row = database.obter_analise_ativa_concurso(
            389, "user-a", None
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], 2)

    def test_anonymous_gets_public_system_analysis(self) -> None:
        row = database.obter_analise_ativa_concurso(
            389, None, None
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], 19)

    def test_unknown_user_falls_back_to_public_system(self) -> None:
        row = database.obter_analise_ativa_concurso(
            500, "user-x", 999
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], 30)

    def test_company_legacy_analysis_can_be_used_for_same_company(self) -> None:
        row = database.obter_analise_ativa_concurso(
            600, "user-a", 28
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], 40)


if __name__ == "__main__":
    unittest.main()
