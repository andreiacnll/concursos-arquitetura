from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing, suppress
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import sqlite_snapshot
from app.sqlite_snapshot import (
    marcar_snapshot_pendente,
    restaurar_snapshot_se_ativo,
    sincronizar_snapshot,
)


class _Cursor:
    def __init__(self, *, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _SnapshotStore:
    row = None


class _Connection:
    def __init__(self, store: _SnapshotStore):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def transaction(self):
        return self

    def commit(self):
        return None

    def execute(self, statement, parameters=()):
        sql = " ".join(statement.lower().split())
        if "select rolname from pg_roles" in sql:
            return _Cursor(many=[("anon",), ("authenticated",)])
        if sql.startswith("create table") or sql.startswith("alter table"):
            return _Cursor()
        if sql.startswith("revoke all"):
            return _Cursor()
        if sql.startswith("insert into app_state_snapshots"):
            self.store.row = {
                "payload_gzip": bytes(parameters[1]),
                "sha256": str(parameters[2]),
                "sqlite_size": int(parameters[3]),
                "gzip_size": int(parameters[4]),
                "metadata": parameters[5],
            }
            return _Cursor()
        if "select sha256, sqlite_size, gzip_size" in sql:
            row = self.store.row
            return _Cursor(
                one=(row["sha256"], row["sqlite_size"], row["gzip_size"])
                if row
                else None
            )
        if "select payload_gzip, sha256, sqlite_size, metadata" in sql:
            row = self.store.row
            return _Cursor(
                one=(
                    row["payload_gzip"],
                    row["sha256"],
                    row["sqlite_size"],
                    row["metadata"],
                )
                if row
                else None
            )
        raise AssertionError(f"SQL inesperado no fake: {statement}")


class _Psycopg:
    def __init__(self, store: _SnapshotStore):
        self.store = store

    def connect(self, _database_url):
        return _Connection(self.store)


class SqliteSnapshotLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            prefix="sqlite_snapshot_lifecycle_"
        )
        self.addCleanup(self.temp_dir.cleanup)
        self.store = _SnapshotStore()
        self.env = patch.dict(
            os.environ,
            {
                "CNLL_SQLITE_SNAPSHOT_ENABLED": "1",
                "CNLL_SQLITE_SNAPSHOT_KEY": "bird-production",
                "DATABASE_URL": "postgresql://snapshot-test",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.modules = patch.object(
            sqlite_snapshot,
            "_psycopg_modulos",
            return_value=(
                _Psycopg(self.store),
                lambda metadata: metadata,
            ),
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)
        with sqlite_snapshot._state_lock:
            sqlite_snapshot._generation = 0
            sqlite_snapshot._synced_generation = 0

    def _criar_origem_381(self) -> Path:
        caminho = Path(self.temp_dir.name) / "origem.db"
        with closing(sqlite3.connect(caminho)) as conn:
            conn.execute(
                """
                CREATE TABLE concursos (
                    id INTEGER PRIMARY KEY,
                    criterio_tipo TEXT,
                    criterio_resumo TEXT,
                    criterio_fatores TEXT,
                    data_limite TEXT,
                    has_updates INTEGER
                )
                """
            )
            conn.execute(
                """
                INSERT INTO concursos (
                    id, criterio_tipo, criterio_resumo, criterio_fatores,
                    data_limite, has_updates
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    381,
                    "Multifator",
                    "Qualidade 35% · Adequação 25% · Exequibilidade 20% · Preço 20%",
                    '[{"nome":"Qualidade","peso":35},{"nome":"Adequação","peso":25},{"nome":"Exequibilidade","peso":20},{"nome":"Preço","peso":20}]',
                    "30-09-2026 17:00",
                    1,
                ),
            )
            conn.commit()
        return caminho

    def test_upload_restore_and_restart_preserve_381(self):
        origem = self._criar_origem_381()
        destino = Path(self.temp_dir.name) / "render" / "concursos.db"

        marcar_snapshot_pendente()
        self.assertTrue(sincronizar_snapshot(origem))
        self.assertIsNotNone(self.store.row)

        self.assertTrue(restaurar_snapshot_se_ativo(destino))
        with closing(sqlite3.connect(destino)) as conn:
            linha = conn.execute(
                """
                SELECT criterio_tipo, criterio_resumo, criterio_fatores,
                       data_limite, has_updates
                FROM concursos WHERE id = 381
                """
            ).fetchone()

        self.assertEqual(linha[0], "Multifator")
        self.assertIn("35%", linha[1])
        self.assertIn('"peso":35', linha[2])
        self.assertEqual(linha[3], "30-09-2026 17:00")
        self.assertEqual(linha[4], 1)

        # Simula um reinício: o snapshot validado não volta a substituir uma
        # cópia local que já lhe corresponde.
        self.assertFalse(restaurar_snapshot_se_ativo(destino))


class SnapshotStartupOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_restore_occurs_before_database_initialization(self):
        from app import api

        eventos = []

        def restore(_path):
            eventos.append("restore")

        def create_database():
            eventos.append("database")

        async def sync(_path):
            eventos.append("sync")

        async def close(task, _path):
            await task

        with patch.dict(os.environ, {"CNLL_ANALISE_WORKER": "0"}):
            with patch.object(api, "restaurar_snapshot_se_ativo", restore):
                with patch.object(api, "criar_base_dados", create_database):
                    with patch.object(api, "executar_sincronizador_snapshot", sync):
                        with patch.object(api, "encerrar_sincronizador_snapshot", close):
                            async with api.lifespan(None):
                                self.assertEqual(eventos[:2], ["restore", "database"])


if __name__ == "__main__":
    unittest.main()