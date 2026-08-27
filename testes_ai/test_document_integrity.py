from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import database
from app.analise.pre_analysis_enrichment import (
    _build_updates,
    _cached_document_signature,
    _document_signature,
    _persist_updates,
)
from app.analise.platform_documents import PlatformDocument


class DocumentIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temp_dir.name) / "concursos.db"
        database.criar_base_dados()
        self.link = "https://base.example/procedimentos/updated"
        database.guardar_concurso(
            titulo="Concurso documental",
            entidade="Entidade oficial",
            link=self.link,
            data="2026-08-20",
            preco_base="100 000 EUR",
            criterio_tipo="Multifator",
            criterio_resumo="Preco 40% · Qualidade 60%",
            criterio_fatores='[{"nome":"Preco","peso":40}]',
        )

    def tearDown(self) -> None:
        database.DB_PATH = self.previous_db_path
        self.temp_dir.cleanup()

    def _concurso(self) -> dict:
        with closing(database.abrir_conexao()) as connection:
            row = connection.execute(
                "SELECT * FROM concursos WHERE link = ?", (self.link,)
            ).fetchone()
        return dict(row)

    def test_documento_atualizado_substitui_facto_e_guarda_evidencia(self) -> None:
        evidence = {
            "document_signature": "new-sha256",
            "documents": [
                {
                    "source_url": "https://official.example/programa-v2.pdf",
                    "sha256": "new-sha256",
                    "filename": "programa-v2.pdf",
                }
            ],
        }
        updates = _build_updates(
            self._concurso(),
            {
                "base_price": {
                    "value": "120 000 EUR",
                    "source_document": "programa-v2.pdf",
                    "excerpt": "Preco base: 120 000 EUR.",
                },
                "submission_deadline": {},
                "publication_date": {},
                "deliverables": [],
            },
            {"award_criteria": {}},
            revalidate_document=True,
            document_evidence=evidence,
        )
        _persist_updates(self._concurso()["id"], updates)

        concurso = self._concurso()
        self.assertEqual(concurso["preco_base"], "120 000 EUR")
        self.assertIsNone(concurso["criterio_resumo"])
        self.assertEqual(concurso["criterio_estado"], "por_confirmar")
        stored_evidence = json.loads(concurso["evidencia_documental"])
        self.assertEqual(
            stored_evidence["documents"][0]["source_url"],
            "https://official.example/programa-v2.pdf",
        )

    def test_assinatura_deteta_nova_versao_da_mesma_peca(self) -> None:
        cache = Path(self.temp_dir.name) / "cache"
        cache.mkdir()
        old_document = PlatformDocument(
            external_id="programa",
            source_url="https://official.example/programa.pdf",
            filename="programa.pdf",
            sha256="old-hash",
        )
        (cache / "metadata.json").write_text(
            json.dumps({"documents": [old_document.__dict__]}),
            encoding="utf-8",
        )
        self.assertEqual(
            _cached_document_signature(cache),
            _document_signature([old_document]),
        )
        new_document = PlatformDocument(
            external_id="programa",
            source_url="https://official.example/programa.pdf",
            filename="programa.pdf",
            sha256="new-hash",
        )
        self.assertNotEqual(
            _cached_document_signature(cache),
            _document_signature([new_document]),
        )
    def test_formula_explicita_nao_inventa_ponderacoes(self) -> None:
        updates = _build_updates(
            self._concurso(),
            {},
            {
                "award_criteria": {
                    "type": "Proposta economicamente mais vantajosa",
                    "summary": "Proposta economicamente mais vantajosa",
                    "factors": [],
                    "verified_top_level_weights": False,
                    "source_document": "programa.pdf",
                }
            },
            revalidate_document=True,
            document_evidence={"documents": []},
        )

        self.assertEqual(
            updates["criterio_resumo"],
            "Proposta economicamente mais vantajosa",
        )
        self.assertEqual(json.loads(updates["criterio_fatores"]), [])
        self.assertNotIn("40", updates["criterio_resumo"])
        self.assertNotIn("60", updates["criterio_resumo"])


if __name__ == "__main__":
    unittest.main()