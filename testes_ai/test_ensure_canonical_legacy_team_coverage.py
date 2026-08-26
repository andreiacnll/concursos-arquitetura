from __future__ import annotations

import importlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

router = importlib.import_module("app.company_ai.router")


class EnsureCanonicalLegacyTeamCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "ensure-canonical.db"
        self.user = SimpleNamespace(id="legacy-user")
        self.company = SimpleNamespace(id=28)
        self._create_fixture()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _open_db(self):
        conn = self._connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _create_fixture(self) -> None:
        procedure = {
            "family": "design_build",
            "technical_team": [
                {
                    "role": "Coordenador de Projeto",
                    "required_at_submission": True,
                    "source_document": "Programa do Concurso.pdf",
                    "source_heading": "Equipa tecnica da proposta",
                },
                {
                    "role": "Autor do Projeto de Arquitetura",
                    "required_at_submission": True,
                    "source_document": "Programa do Concurso.pdf",
                    "source_heading": "Equipa tecnica da proposta",
                },
                {
                    "role": "Autor do Projeto de Estruturas",
                    "required_at_submission": True,
                    "source_document": "Programa do Concurso.pdf",
                    "source_heading": "Equipa tecnica da proposta",
                },
            ],
        }
        legacy_canonical = {
            "question_policy_version": "decision-facts-v17.3",
            "recovery_status": "no_procedural_evidence",
            "requirements": [
                {
                    "label": label,
                    "nature": "eligibility",
                    "stage": "pre_award",
                    "profile_dependent": False,
                }
                for label in (
                    "Audiencia previa",
                    "Relatorio final",
                    "Nao adjudicacao",
                    "Caucao",
                    "Relatorio preliminar",
                )
            ],
            "questions": [],
            # This makes the old existence-based material check return true.
            "criteria": {"factors": [{"label": "Relatorio final"}]},
        }
        ficha = {
            "procedure_analysis": procedure,
            "analysis_canonical": legacy_canonical,
        }

        with self._open_db() as conn:
            conn.executescript(
                """
                CREATE TABLE analises (
                    id INTEGER PRIMARY KEY,
                    concurso_id INTEGER,
                    user_id TEXT,
                    company_id INTEGER,
                    estado TEXT,
                    updated_at TEXT,
                    score INTEGER,
                    dados_json TEXT
                );
                CREATE TABLE concursos (
                    id INTEGER PRIMARY KEY,
                    titulo TEXT
                );
                """
            )
            conn.execute(
                "INSERT INTO concursos (id, titulo) VALUES (?, ?)",
                (446, "Concurso legacy"),
            )
            conn.execute(
                """
                INSERT INTO analises (
                    id, concurso_id, user_id, company_id, estado,
                    updated_at, dados_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    31,
                    446,
                    self.user.id,
                    28,
                    "concluida",
                    "2026-08-26 10:00:00",
                    json.dumps(ficha, ensure_ascii=False),
                ),
            )

    def _call_ensure(self) -> dict:
        with patch.object(router, "_cv_open_db", side_effect=self._open_db), patch.object(
            router, "_cv_company_for_user", return_value=self.company
        ), patch.object(router, "_cv_analysis_facts", return_value={}), patch.object(
            router, "_cv_get_profile", return_value=SimpleNamespace(cv=[])
        ):
            return router.cv_ensure_canonical_analysis(446, self.user)

    def _stored_canonical(self) -> dict:
        with self._open_db() as conn:
            row = conn.execute(
                "SELECT dados_json FROM analises WHERE id = 31"
            ).fetchone()
        return json.loads(row["dados_json"])["analysis_canonical"]

    def test_legacy_team_coverage_forces_rebuild_and_is_idempotent(self):
        before = self._stored_canonical()
        with self._open_db() as conn:
            row = conn.execute(
                "SELECT dados_json FROM analises WHERE id = 31"
            ).fetchone()
        ficha_before = json.loads(row["dados_json"])
        self.assertTrue(router._cv_canonical_is_material(before))
        self.assertFalse(
            router._cv_canonical_covers_visible_procedure(before, ficha_before)
        )

        first = self._call_ensure()
        self.assertTrue(first["changed"])
        self.assertEqual(first["analise_id"], 31)
        self.assertEqual(first["recovery_status"], "recovered_from_current_analysis")

        after = self._stored_canonical()
        team = [
            item
            for item in after["requirements"]
            if item.get("nature") == "team"
            and item.get("stage") == "pre_award"
            and item.get("profile_dependent") is True
        ]
        self.assertEqual(len(team), 3)
        self.assertEqual(len(after["questions"]), 3)
        self.assertTrue(
            router._cv_canonical_covers_visible_procedure(
                after,
                {
                    "procedure_analysis": ficha_before["procedure_analysis"],
                    "analysis_canonical": after,
                },
            )
        )
        labels = " ".join(item.get("label", "").lower() for item in after["requirements"])
        self.assertNotIn("audiencia", labels)
        self.assertNotIn("relatorio final", labels)

        second = self._call_ensure()
        self.assertFalse(second["changed"])
        persisted_again = self._stored_canonical()
        self.assertEqual(after["requirements"], persisted_again["requirements"])
        self.assertEqual(after["questions"], persisted_again["questions"])


if __name__ == "__main__":
    unittest.main()