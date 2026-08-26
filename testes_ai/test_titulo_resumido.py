from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path

from app import database
from app.architecture_intelligence.llm.provider import LLMProviderError
from app.titulo_resumido import (
    gerar_titulo_resumido,
    limpar_titulo_deterministico,
    validar_titulo_resumido,
)
from scripts.backfill_titulos_resumidos import executar_backfill


LUMIAR = (
    "AQUISICAO DE SERVICOS N 8/AQ/DMMC/DEM/DPCE/25 - CONCURSO PUBLICO "
    "DE CONCECAO PARA A ELABORACAO DO PROJETO DE REABILITACAO DA "
    "Escola Secundaria do Lumiar"
)
VALE = (
    "Concurso Publico para a Elaboracao de Projeto de Arquitetura Paisagista "
    "e Especialidades das Obras de Urbanizacao do Parque Urbano do Vale de Santo Antonio"
)


class FakeProvider:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls = 0

    def generate_text(self, _system: str, _user: str) -> str:
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class TituloResumidoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.previous_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "concursos.db"
        database.criar_base_dados()

    def tearDown(self) -> None:
        database.DB_PATH = self.previous_db_path
        self.temp.cleanup()

    def test_limpeza_deterministica_identifica_lumiar(self) -> None:
        self.assertEqual(
            limpar_titulo_deterministico(LUMIAR),
            "Escola Secundaria do Lumiar",
        )

    def test_limpeza_deterministica_identifica_vale(self) -> None:
        self.assertEqual(
            limpar_titulo_deterministico(VALE),
            "Parque Urbano do Vale de Santo Antonio",
        )

    def test_limpeza_deterministica_aceita_acentos_portugueses(self) -> None:
        self.assertEqual(
            limpar_titulo_deterministico(
                "Concurso P\u00fablico para a Elabora\u00e7\u00e3o de Projeto de "
                "Recupera\u00e7\u00e3o do Patrim\u00f3nio Municipal"
            ),
            "Recupera\u00e7\u00e3o do Patrim\u00f3nio Municipal",
        )
    def test_titulo_ja_humano_nao_precisa_ollama(self) -> None:
        provider = FakeProvider("Nao deve ser usado")
        self.assertEqual(
            gerar_titulo_resumido("Mercado Municipal de Arroios", provider=provider),
            "Mercado Municipal de Arroios",
        )
        self.assertEqual(provider.calls, 0)

    def test_resposta_ollama_valida_e_fiel_e_aceite(self) -> None:
        official = "Procedimento para criacao de equipamento comunitario Aurora"
        self.assertEqual(
            gerar_titulo_resumido(
                official,
                provider=FakeProvider("Equipamento Comunitario Aurora"),
            ),
            "Equipamento Comunitario Aurora",
        )

    def test_resposta_ollama_invalida_usa_fallback_deterministico(self) -> None:
        official = "Procedimento para criacao de equipamento comunitario Aurora"
        self.assertEqual(
            gerar_titulo_resumido(official, provider=FakeProvider('{"titulo":"Inventado"}')),
            limpar_titulo_deterministico(official),
        )

    def test_ollama_indisponivel_nao_bloqueia_fallback(self) -> None:
        official = "Procedimento para criacao de equipamento comunitario Aurora"
        self.assertEqual(
            gerar_titulo_resumido(
                official,
                provider=FakeProvider(LLMProviderError("ollama_disabled")),
            ),
            limpar_titulo_deterministico(official),
        )

    def test_timeout_ollama_nao_bloqueia_fallback(self) -> None:
        official = "Procedimento para criacao de equipamento comunitario Aurora"
        self.assertEqual(
            gerar_titulo_resumido(official, provider=FakeProvider(TimeoutError("timeout"))),
            limpar_titulo_deterministico(official),
        )

    def test_resultado_vazio_do_ollama_nao_e_persistido(self) -> None:
        official = "Procedimento para criacao de equipamento comunitario Aurora"
        self.assertEqual(
            gerar_titulo_resumido(official, provider=FakeProvider("")),
            limpar_titulo_deterministico(official),
        )

    def test_validacao_rejeita_nome_sem_suporte_no_contexto(self) -> None:
        self.assertIsNone(
            validar_titulo_resumido(
                "Centro Cultural Inventado",
                titulo_oficial="Projeto de requalificacao de edificio municipal na Rua X",
            )
        )

    def test_guardar_concurso_preserva_titulo_oficial(self) -> None:
        concurso_id = database.guardar_concurso(
            titulo=LUMIAR,
            entidade="Camara Municipal de Lisboa",
            link="https://example.test/lumiar",
            data="2026-08-01",
        )
        with closing(database.abrir_conexao()) as connection:
            row = connection.execute(
                "SELECT titulo, titulo_resumido FROM concursos WHERE id = ?",
                (concurso_id,),
            ).fetchone()
        self.assertEqual(row["titulo"], LUMIAR)
        self.assertEqual(row["titulo_resumido"], "Escola Secundaria do Lumiar")

    def test_titulo_resumido_existente_nao_e_recalculado(self) -> None:
        concurso_id = database.guardar_concurso(
            titulo=VALE,
            entidade="Entidade exemplo",
            link="https://example.test/vale",
            data="2026-08-01",
        )
        with closing(database.abrir_conexao()) as connection:
            connection.execute(
                "UPDATE concursos SET titulo_resumido = ? WHERE id = ?",
                ("Titulo definido manualmente", concurso_id),
            )
            connection.commit()
        self.assertFalse(database._preencher_titulo_resumido_se_em_falta(int(concurso_id)))
        with closing(database.abrir_conexao()) as connection:
            summary = connection.execute(
                "SELECT titulo_resumido FROM concursos WHERE id = ?",
                (concurso_id,),
            ).fetchone()[0]
        self.assertEqual(summary, "Titulo definido manualmente")

    def test_backfill_dry_run_nao_escreve(self) -> None:
        with closing(database.abrir_conexao()) as connection:
            cursor = connection.execute(
                "INSERT INTO concursos (titulo, link, relevante) VALUES (?, ?, 1)",
                (VALE, "https://example.test/backfill-dry"),
            )
            concurso_id = int(cursor.lastrowid)
            connection.commit()
            results = executar_backfill(connection, commit=False)
            summary = connection.execute(
                "SELECT titulo_resumido FROM concursos WHERE id = ?",
                (concurso_id,),
            ).fetchone()[0]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], concurso_id)
        self.assertEqual(results[0]["titulo_resumido"], "Parque Urbano do Vale de Santo Antonio")
        self.assertIsNone(summary)

    def test_backfill_commit_processa_apenas_campos_vazios(self) -> None:
        with closing(database.abrir_conexao()) as connection:
            blank = connection.execute(
                "INSERT INTO concursos (titulo, link, relevante) VALUES (?, ?, 1)",
                (LUMIAR, "https://example.test/backfill-blank"),
            ).lastrowid
            preserved = connection.execute(
                "INSERT INTO concursos (titulo, link, relevante, titulo_resumido) VALUES (?, ?, 1, ?)",
                (VALE, "https://example.test/backfill-existing", "Titulo existente"),
            ).lastrowid
            connection.commit()
            results = executar_backfill(connection, commit=True)
            rows = connection.execute(
                "SELECT id, titulo_resumido FROM concursos ORDER BY id",
            ).fetchall()
        self.assertEqual([result["id"] for result in results], [blank])
        values = {row[0]: row[1] for row in rows}
        self.assertEqual(values[blank], "Escola Secundaria do Lumiar")
        self.assertEqual(values[preserved], "Titulo existente")


if __name__ == "__main__":
    unittest.main()
