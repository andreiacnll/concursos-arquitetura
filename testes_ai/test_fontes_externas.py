from __future__ import annotations

import unittest

from app.fontes.common import ExternalProcedure, evaluate_relevance, title_similarity
from app.fontes.espaco_arquitetura import parse_detail as parse_espaco_detail
from app.fontes.oasrs_encomenda import parse_detail as parse_oasrs_detail
from app.fontes.ordem_arquitectos import parse_search_results


class ExternalSourceCommonTests(unittest.TestCase):
    def test_architecture_project_is_relevant(self) -> None:
        item = ExternalProcedure(
            source="fixture",
            source_label="Fixture",
            reference="fixture:1",
            title="Elaboração de projeto de arquitetura e especialidades",
            page_url="https://example.test/1",
            status="em_curso",
            raw_text="Projeto de execução de equipamento público.",
        )
        relevant, _reason = evaluate_relevance(item)
        self.assertTrue(relevant)

    def test_pure_cleaning_is_rejected(self) -> None:
        item = ExternalProcedure(
            source="fixture",
            source_label="Fixture",
            reference="fixture:2",
            title="Serviços de limpeza de edifícios",
            page_url="https://example.test/2",
            status="em_curso",
            raw_text="Prestação de serviços de limpeza corrente.",
        )
        relevant, _reason = evaluate_relevance(item)
        self.assertFalse(relevant)

    def test_title_similarity_handles_boilerplate(self) -> None:
        score = title_similarity(
            "Concurso Público para a elaboração do projeto do Parque Urbano X",
            "Elaboração de Projeto — Parque Urbano X",
        )
        self.assertGreaterEqual(score, 0.88)


class OasrsParserTests(unittest.TestCase):
    def test_detail_extracts_common_fields(self) -> None:
        html = """
        <html><main>
          <h2>Parque Urbano do Vale Verde</h2>
          <div><span>promotor</span><strong>Município Exemplo</strong></div>
          <div><span>localização</span><strong>Lisboa</strong></div>
          <div><span>programa</span><strong>Espaço público</strong></div>
          <p>A decorrer. Propostas até 19 de abril de 2027.</p>
          <p>Concurso público de conceção para elaboração do projeto de arquitetura paisagista.</p>
          <a href="https://www.acingov.pt/procedimento/1">Plataforma eletrónica</a>
        </main></html>
        """
        item = parse_oasrs_detail(
            html,
            detail_url="https://encomenda.oasrs.org/concursos/detalhe/ABC123/parque",
            fallback_title="Fallback",
            listing_text="Concurso • 2027-04-01 • A decorrer",
            publication_date="2027-04-01",
            listing_status="em_curso",
        )
        self.assertEqual(item.title, "Parque Urbano do Vale Verde")
        self.assertEqual(item.entity, "Município Exemplo")
        self.assertEqual(item.deadline, "2027-04-19")
        self.assertTrue(item.relevant)
        self.assertEqual(item.reference, "OASRS:ABC123")


class EspacoArquiteturaParserTests(unittest.TestCase):
    def test_project_competition_is_accepted(self) -> None:
        html = """
        <html><article>
          <h1>Projeto de arquitetura para cooperativa de habitação</h1>
          <p>Publicado em 3 de agosto, 2026 por Espaço de Arquitetura.</p>
          <p>Início em 03/08/2026 até 30/09/2026</p>
          <p>Concurso de conceção promovido pelo Município Exemplo para projeto urbano e paisagístico.</p>
          <a href="https://concursos.municipio.example/projeto">Página oficial</a>
        </article></html>
        """
        item = parse_espaco_detail(
            html,
            detail_url="https://espacodearquitetura.com/concursos/projeto-cooperativa/",
            fallback_title="Fallback",
            listing_text="Publicado em 3 de agosto, 2026",
        )
        self.assertEqual(item.publication_date, "2026-08-03")
        self.assertEqual(item.deadline, "2026-09-30")
        self.assertTrue(item.relevant)

    def test_architecture_award_is_rejected(self) -> None:
        html = """
        <html><article>
          <h1>Prémio Regional de Arquitetura 2026</h1>
          <p>Publicado em 3 de agosto, 2026.</p>
          <p>Início em 03/08/2026 até 30/09/2026</p>
        </article></html>
        """
        item = parse_espaco_detail(
            html,
            detail_url="https://espacodearquitetura.com/concursos/premio-regional/",
            fallback_title="Fallback",
            listing_text="",
        )
        self.assertFalse(item.relevant)


class OrdemArquitectosParserTests(unittest.TestCase):
    def test_search_only_keeps_concurso_cards(self) -> None:
        html = """
        <div class="result">
          <h4>CONCURSO PARQUE URBANO — PRAZO</h4>
          <p>Concurso público de conceção para projeto de arquitetura paisagista.</p>
          <a href="/noticias/concurso-parque">ver mais</a>
        </div>
        <div class="result">
          <h4>Webinar técnico</h4>
          <a href="/agenda/webinar">ver mais</a>
        </div>
        """
        items = parse_search_results(html)
        self.assertEqual(len(items), 1)
        self.assertIn("PARQUE URBANO", items[0]["title"])


class DatabasePromotionTests(unittest.TestCase):
    def test_base_promotes_any_external_source_without_changing_id(self) -> None:
        import tempfile
        from pathlib import Path

        from app import database

        original_path = database.DB_PATH
        with tempfile.TemporaryDirectory() as temporary:
            database.DB_PATH = Path(temporary) / "test.db"
            try:
                database.criar_base_dados()
                connection = database.abrir_conexao()
                try:
                    cursor = connection.execute(
                        """
                        INSERT INTO concursos (
                            titulo, entidade, link, data, relevante
                        ) VALUES (?, ?, ?, ?, 1)
                        """,
                        (
                            "Projeto de arquitetura do Parque Urbano X",
                            "Município Exemplo",
                            "https://fonte.example/concurso-x",
                            "2026-08-01",
                        ),
                    )
                    concurso_id = int(cursor.lastrowid)
                    connection.execute(
                        """
                        INSERT INTO concurso_fontes (
                            concurso_id, fonte, referencia, pagina_url,
                            estado_fonte, titulo_origem,
                            first_seen_at, last_seen_at, principal
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                        """,
                        (
                            concurso_id,
                            "oasrs_encomenda",
                            "OASRS:TEST",
                            "https://fonte.example/concurso-x",
                            "em_curso",
                            "Projeto de arquitetura do Parque Urbano X",
                            "2026-08-01T10:00:00+01:00",
                            "2026-08-01T10:00:00+01:00",
                        ),
                    )
                    connection.commit()
                finally:
                    connection.close()

                promoted_id = database.guardar_concurso(
                    titulo="Concurso Público para elaboração do projeto de arquitetura do Parque Urbano X",
                    entidade="Município Exemplo",
                    link="https://www.base.gov.pt/Base4/pt/detalhe/?type=anuncios&id=999999",
                    data="2026-08-05",
                )
                self.assertEqual(promoted_id, concurso_id)

                connection = database.abrir_conexao()
                try:
                    row = connection.execute(
                        "SELECT id, link FROM concursos WHERE id = ?",
                        (concurso_id,),
                    ).fetchone()
                    self.assertIn("base.gov.pt", row["link"])
                    principals = connection.execute(
                        "SELECT principal FROM concurso_fontes WHERE concurso_id = ?",
                        (concurso_id,),
                    ).fetchall()
                    self.assertTrue(all(item["principal"] == 0 for item in principals))
                finally:
                    connection.close()
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
