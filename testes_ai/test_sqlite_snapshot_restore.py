from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.sqlite_snapshot import (
    _obter_contagens,
    _tabelas_para_validar_snapshot,
    _validar_contagens_snapshot,
)


METADATA_COUNTS = {
    "concursos": 438,
    "analises": 11,
    "analise_versoes": 33,
    "analise_jobs": 42,
    "companies": 13,
    "company_members": 22,
    "company_profiles": 8,
    "favoritos": 4,
    "alertas": 3,
    "timeline_eventos": 16,
}


class SqliteSnapshotRestoreTests(unittest.TestCase):
    def _db_com_contagens(self, counts: dict[str, int]) -> Path:
        temp_dir = Path(tempfile.mkdtemp(prefix="cnll_snapshot_restore_test_"))
        db_path = temp_dir / "snapshot.db"

        with sqlite3.connect(db_path) as conn:
            for table, count in counts.items():
                conn.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY)')
                conn.executemany(
                    f'INSERT INTO "{table}" DEFAULT VALUES',
                    [() for _ in range(count)],
                )
            conn.commit()

        return db_path

    def test_metadata_antiga_com_contagens_iguais_e_aceite(self):
        db_path = self._db_com_contagens(METADATA_COUNTS)
        contagens = _obter_contagens(
            db_path,
            _tabelas_para_validar_snapshot(METADATA_COUNTS),
        )

        # Reproduz o caso cnll-main de 2026-08-21: a metadata tem o conjunto
        # antigo de tabelas, enquanto a aplicação atual conhece tabelas novas.
        self.assertEqual(contagens["concursos"], 438)
        self.assertEqual(contagens["analises"], 11)
        self.assertEqual(contagens["timeline_eventos"], 16)
        self.assertEqual(contagens["company_knowledge_memory"], -1)

        _validar_contagens_snapshot(contagens, METADATA_COUNTS)

    def test_diferenca_real_de_contagem_continua_a_falhar(self):
        db_path = self._db_com_contagens(METADATA_COUNTS)
        contagens = _obter_contagens(
            db_path,
            _tabelas_para_validar_snapshot(METADATA_COUNTS),
        )
        metadata_errada = dict(METADATA_COUNTS)
        metadata_errada["concursos"] = 437

        with self.assertRaisesRegex(RuntimeError, "contagens do snapshot"):
            _validar_contagens_snapshot(contagens, metadata_errada)


if __name__ == "__main__":
    unittest.main()
