from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import database
from app.coletor_lisboa_sru import (
    ACTIVE_SECTION,
    CONTRACTING_SECTION,
    CONCLUDED_SECTION,
    SourceProcedure,
    collect,
    evaluate_relevance,
    find_base_match,
    parse_page,
    title_similarity,
    update_known_source_state,
)


HTML = """
<html><body>
  <h2>Procedimentos em concurso</h2>
  <h2>Concurso Público para a Elaboração de Projeto de Arquitetura Paisagista e Especialidades das Obras de Urbanização do Parque Urbano do Vale de Santo António</h2>
  <p>SRU20260000323CPI</p>
  <a href="https://example.test/vale">PEÇAS DO PROCEDIMENTO</a>

  <h2>Empreitada de Construção do Mercado dos Olivais - Célula B</h2>
  <p>SRU20260000273CP</p>
  <a href="https://example.test/mercado">PEÇAS DO PROCEDIMENTO</a>

  <h2>Elaboração do projeto do conjunto habitacional da Vila Macieira e prolongamento da Rua General Justiniano Padrel</h2>
  <p>SRU20260000204CP</p>
  <a href="https://example.test/vila">PEÇAS DO PROCEDIMENTO</a>

  <h2>Aquisição de serviços de vigilância das instalações</h2>
  <p>SRU20260000999CP</p>

  <h2>Procedimentos em fase de contratação</h2>
  <h2>Aquisição de Serviços de Elaboração de Projeto de Requalificação e Ampliação da Escola Básica Eugénio dos Santos</h2>
  <p>SRU20260000029CP</p>
  <a href="https://example.test/escola">PEÇAS DO PROCEDIMENTO</a>

  <h2>Procedimentos concluídos</h2>
  <h2>Concurso Público para elaboração de projeto antigo</h2>
  <p>SRU20250000001CP</p>
</body></html>
"""


class LisboaSruParserTests(unittest.TestCase):
    def test_parser_preserves_sections_references_and_links(self) -> None:
        items = parse_page(HTML)
        self.assertEqual(len(items), 6)
        self.assertEqual(items[0].reference, "SRU20260000323CPI")
        self.assertEqual(items[0].status, ACTIVE_SECTION)
        self.assertEqual(items[0].documents_url, "https://example.test/vale")
        self.assertEqual(items[4].status, CONTRACTING_SECTION)
        self.assertEqual(items[5].status, CONCLUDED_SECTION)

    def test_deterministic_filter_accepts_project_and_rejects_pure_works(self) -> None:
        items = parse_page(HTML)
        target = next(item for item in items if item.reference == "SRU20260000323CPI")
        works = next(item for item in items if item.reference == "SRU20260000273CP")
        security = next(item for item in items if item.reference == "SRU20260000999CP")
        self.assertTrue(evaluate_relevance(target)[0])
        self.assertFalse(evaluate_relevance(works)[0])
        self.assertFalse(evaluate_relevance(security)[0])

    def test_collection_only_selects_active_relevant_items(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "checkpoint.json"
            selected, report = collect(
                html=HTML,
                dry_run=True,
                checkpoint_path=checkpoint,
            )
        references = {item.reference for item in selected}
        self.assertEqual(
            references,
            {"SRU20260000323CPI", "SRU20260000204CP"},
        )
        self.assertEqual(report.relevant, 2)
        self.assertEqual(report.rejected, 2)
        self.assertFalse(checkpoint.exists())

    def test_title_similarity_is_strong_for_same_project(self) -> None:
        left = (
            "Concurso Público para a Elaboração de Projeto de Arquitetura "
            "Paisagista e Especialidades das Obras de Urbanização do Parque "
            "Urbano do Vale de Santo António"
        )
        right = (
            "Aquisição de serviços para elaboração do projeto de arquitetura "
            "paisagista e especialidades do Parque Urbano do Vale de Santo António"
        )
        self.assertGreaterEqual(title_similarity(left, right), 0.90)

    def test_weak_generic_titles_are_not_considered_same(self) -> None:
        self.assertLess(
            title_similarity(
                "Elaboração de projeto de espaço público no Lumiar",
                "Elaboração de projeto de espaço público em Alcântara",
            ),
            0.90,
        )


class LisboaSruDatabasePriorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.previous = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "concursos.db"
        database.criar_base_dados()

    def tearDown(self) -> None:
        database.DB_PATH = self.previous
        self.temp.cleanup()

    def _insert_external(self) -> int:
        external_id = database.guardar_concurso(
            titulo=(
                "Concurso Público para a Elaboração de Projeto de Arquitetura "
                "Paisagista e Especialidades das Obras de Urbanização do Parque "
                "Urbano do Vale de Santo António"
            ),
            entidade="Lisboa Ocidental SRU, EM, S.A.",
            link=(
                "https://www.lisboasru.pt/contratacao-publica"
                "#SRU20260000323CPI"
            ),
            data=None,
            tipo_procedimento="Concurso Público Internacional",
        )
        connection = database.abrir_conexao()
        connection.execute(
            """
            INSERT INTO concurso_fontes (
                concurso_id, fonte, referencia, pagina_url, documentos_url,
                estado_fonte, titulo_origem, first_seen_at, last_seen_at,
                principal, metadata_json
            ) VALUES (?, 'lisboa_sru', 'SRU20260000323CPI', ?, ?,
                      'em_concurso', ?, CURRENT_TIMESTAMP,
                      CURRENT_TIMESTAMP, 1, '{}')
            """,
            (
                external_id,
                "https://www.lisboasru.pt/contratacao-publica",
                "https://example.test/pecas",
                "Projeto de Arquitetura Paisagista do Parque Urbano do Vale de Santo António",
            ),
        )
        connection.commit()
        connection.close()
        return int(external_id)

    def test_base_promotes_existing_record_and_preserves_relations(self) -> None:
        external_id = self._insert_external()
        connection = database.abrir_conexao()
        connection.execute(
            "INSERT INTO favoritos (user_id, concurso_id) VALUES ('user-a', ?)",
            (external_id,),
        )
        connection.execute(
            """
            INSERT INTO alerta_subscricoes (user_id, concurso_id, ativo, origem)
            VALUES ('user-a', ?, 1, 'manual')
            """,
            (external_id,),
        )
        connection.commit()
        connection.close()

        base_id = database.guardar_concurso(
            titulo=(
                "Aquisição de serviços para elaboração do projeto de arquitetura "
                "paisagista e especialidades do Parque Urbano do Vale de Santo António"
            ),
            entidade="Lisboa Ocidental SRU – Sociedade de Reabilitação Urbana EM, S.A.",
            link="https://www.base.gov.pt/Base4/pt/detalhe/?type=anuncios&id=999999",
            data="2026-08-05",
            preco_base="998318.87",
            tipo_procedimento="Concurso público",
        )
        self.assertEqual(base_id, external_id)

        connection = database.abrir_conexao()
        concursos = connection.execute("SELECT * FROM concursos").fetchall()
        source = connection.execute(
            "SELECT * FROM concurso_fontes WHERE concurso_id = ?",
            (external_id,),
        ).fetchone()
        favorito = connection.execute(
            "SELECT * FROM favoritos WHERE concurso_id = ?",
            (external_id,),
        ).fetchone()
        subscription = connection.execute(
            "SELECT * FROM alerta_subscricoes WHERE concurso_id = ?",
            (external_id,),
        ).fetchone()
        connection.close()

        self.assertEqual(len(concursos), 1)
        self.assertIn("base.gov.pt", concursos[0]["link"])
        self.assertEqual(source["principal"], 0)
        self.assertIsNotNone(favorito)
        self.assertIsNotNone(subscription)

    def test_known_source_state_can_move_to_concluded(self) -> None:
        external_id = self._insert_external()
        procedure = SourceProcedure(
            title="Projeto de Arquitetura Paisagista do Parque Urbano do Vale de Santo António",
            reference="SRU20260000323CPI",
            status=CONCLUDED_SECTION,
            page_url="https://www.lisboasru.pt/contratacao-publica#SRU20260000323CPI",
            documents_url="https://example.test/pecas",
            raw_text="Projeto de arquitetura paisagista",
            first_seen_at="2026-08-01T10:00:00+01:00",
            last_seen_at="2026-08-06T10:00:00+01:00",
            relevant=True,
            relevance_reason="teste",
        )
        self.assertTrue(update_known_source_state(procedure))
        connection = database.abrir_conexao()
        state = connection.execute(
            "SELECT estado_fonte FROM concurso_fontes WHERE concurso_id = ?",
            (external_id,),
        ).fetchone()[0]
        connection.close()
        self.assertEqual(state, CONCLUDED_SECTION)

    def test_ambiguous_multiple_base_matches_are_not_merged(self) -> None:
        connection = database.abrir_conexao()
        for suffix, title in (
            ("1", "Projeto de requalificação do espaço público da Praça Central - Lote 1"),
            ("2", "Projeto de requalificação do espaço público da Praça Central - Lote 2"),
        ):
            connection.execute(
                """
                INSERT INTO concursos (titulo, entidade, link, relevante)
                VALUES (?, ?, ?, 1)
                """,
                (
                    title,
                    "Lisboa Ocidental SRU, EM, S.A.",
                    f"https://www.base.gov.pt/Base4/pt/detalhe/?id={suffix}",
                ),
            )
        connection.commit()
        procedure = SourceProcedure(
            title="Projeto de requalificação do espaço público da Praça Central",
            reference="SRU20260000111CP",
            status=ACTIVE_SECTION,
            page_url="https://example.test/sru",
            documents_url="",
            raw_text="Projeto de espaço público",
        )
        match = find_base_match(connection, procedure)
        connection.close()
        self.assertIsNone(match)


if __name__ == "__main__":
    unittest.main()
