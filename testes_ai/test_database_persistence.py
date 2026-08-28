from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import database


class DatabasePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_db_path = database.DB_PATH
        self.old_default_db_path = database.DEFAULT_DB_PATH
        self.old_configured = database.DATABASE_PATH_CONFIGURADO

    def tearDown(self) -> None:
        database.DB_PATH = self.old_db_path
        database.DEFAULT_DB_PATH = self.old_default_db_path
        database.DATABASE_PATH_CONFIGURADO = self.old_configured
        self.temp.cleanup()

    def _snapshot(self, name: str = "snapshot.db") -> Path:
        path = self.root / name
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE seed (value TEXT NOT NULL)")
            connection.execute("INSERT INTO seed(value) VALUES ('snapshot')")
            connection.commit()
        finally:
            connection.close()
        return path

    def _read_seed(self, path: Path) -> str:
        connection = sqlite3.connect(path)
        try:
            return str(connection.execute("SELECT value FROM seed").fetchone()[0])
        finally:
            connection.close()

    def test_sem_database_path_mantem_caminho_local(self) -> None:
        self.assertEqual(
            database.resolver_caminho_base_dados({}),
            database.DEFAULT_DB_PATH,
        )

    def test_database_path_configurado_tem_prioridade(self) -> None:
        configured = self.root / "persistent" / "concursos.db"
        self.assertEqual(
            database.resolver_caminho_base_dados(
                {database.DATABASE_PATH_ENV: str(configured)}
            ),
            configured,
        )

    def test_base_existente_nunca_e_sobrescrita(self) -> None:
        snapshot = self._snapshot()
        destination = self.root / "persistent" / "concursos.db"
        destination.parent.mkdir(parents=True)
        connection = sqlite3.connect(destination)
        try:
            connection.execute("CREATE TABLE seed (value TEXT NOT NULL)")
            connection.execute("INSERT INTO seed(value) VALUES ('persistente')")
            connection.commit()
        finally:
            connection.close()

        self.assertFalse(
            database.bootstrap_base_dados_se_necessario(destination, snapshot=snapshot)
        )
        self.assertEqual(self._read_seed(destination), "persistente")

    def test_bootstrap_cria_destino_uma_unica_vez(self) -> None:
        snapshot = self._snapshot()
        destination = self.root / "persistent" / "nested" / "concursos.db"

        self.assertTrue(
            database.bootstrap_base_dados_se_necessario(destination, snapshot=snapshot)
        )
        self.assertEqual(self._read_seed(destination), "snapshot")
        self.assertFalse(
            database.bootstrap_base_dados_se_necessario(destination, snapshot=snapshot)
        )

    def test_restart_preserva_dados_no_caminho_configurado(self) -> None:
        snapshot = self._snapshot()
        destination = self.root / "persistent" / "concursos.db"
        database.DEFAULT_DB_PATH = snapshot
        database.DB_PATH = destination
        database.DATABASE_PATH_CONFIGURADO = True

        connection = database.abrir_conexao()
        try:
            opened_path = Path(connection.execute("PRAGMA database_list").fetchone()[2])
            self.assertEqual(opened_path.resolve(), destination.resolve())
            connection.execute("CREATE TABLE restart_data (value TEXT NOT NULL)")
            connection.execute("INSERT INTO restart_data(value) VALUES ('mantido')")
            connection.commit()
        finally:
            connection.close()

        database.preparar_base_dados_configurada()
        connection = database.abrir_conexao()
        try:
            kept = connection.execute(
                "SELECT value FROM restart_data"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(kept, "mantido")
        self.assertEqual(self._read_seed(destination), "snapshot")


if __name__ == "__main__":
    unittest.main()