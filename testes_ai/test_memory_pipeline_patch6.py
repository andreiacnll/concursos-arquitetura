from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from app import localizacao
from app.analise import worker
from app.analise.criterios import analisar_criterios, analisar_criterios_documentos
from app.analise.equipa import analisar_equipa, analisar_equipa_documentos
from app.analise.normalizador_equipa import normalizar_subfatores


class MemoryPipelinePatch6Tests(unittest.TestCase):
    def test_criterios_ultimo_documento_equivalem_ao_fluxo_legado(self) -> None:
        documentos = [
            "Documento inicial sem criterios relevantes.",
            "Documento intermedio sem percentagens.",
            "Qualidade 70%. Metodologia requerida para a avaliacao.",
        ]

        resultado = analisar_criterios_documentos(documentos)
        legado = analisar_criterios("\n".join(documentos))

        self.assertEqual(resultado, legado)
        self.assertEqual(resultado["qualidade_percentagem"], 70)
        self.assertEqual(resultado["subfatores"], ["metodologia"])

    def test_equipa_ultimo_documento_equivale_ao_fluxo_legado(self) -> None:
        documentos = [
            "Documento inicial sem especialidades.",
            "Documento intermedio sem equipa tecnica.",
            "Arquitetura e AVAC. SUBFATOR 2.1\nExperiencia completa.\n"
            "SUBFATOR 2.2\nSegunda descricao completa.",
        ]

        resultado = analisar_equipa_documentos(documentos)
        legado = analisar_equipa("\n".join(documentos))

        self.assertEqual(resultado, legado)
        self.assertEqual(resultado["especialidades"], ["arquitetura", "avac"])
        self.assertEqual(
            [item["titulo"] for item in resultado["subfatores_equipa"]],
            ["SUBFATOR 2.1", "SUBFATOR 2.2"],
        )

    def test_subfator_nao_atravessa_fronteira_documental_intencionalmente(self) -> None:
        """The old artificial join leaked document B into subfactor 2.1."""
        documentos = [
            "SUBFATOR 2.1\nDescricao exclusiva do documento A.",
            "Texto exclusivo do documento B que nao pertence ao subfator.",
        ]

        legado = analisar_equipa("\n".join(documentos))
        novo = analisar_equipa_documentos(documentos)

        self.assertIn("documento B", legado["subfatores_equipa"][0]["descricao"])
        self.assertNotIn("documento B", novo["subfatores_equipa"][0]["descricao"])
        self.assertEqual(
            novo["subfatores_equipa"][0]["descricao"],
            "Descricao exclusiva do documento A.",
        )

    def test_extratores_normais_equivalem_ao_fluxo_legado(self) -> None:
        documentos = [
            "Documento inicial sem dados programaticos.",
            "Objeto da intervencao: reabilitacao de escola existente. "
            "Preco base 12 000 EUR. Area total 450 m2. "
            "A proposta e obrigatoria para a candidatura. "
            "Projeto de arquitetura previsto. Arquitetura e AVAC.",
        ]
        texto_legado = "\n".join(documentos)
        concurso = {}
        funcoes_legado = worker._extrair_funcoes(texto_legado, "Concurso")
        funcoes_novo = worker._extrair_funcoes_documentos(documentos, "Concurso")

        self.assertEqual(
            worker._extrair_valor_documentos(documentos),
            worker._extrair_valor(texto_legado),
        )
        self.assertEqual(
            worker._extrair_areas_documentos(documentos),
            worker._extrair_areas(texto_legado),
        )
        self.assertEqual(
            worker._extrair_tipo_intervencao_documentos(documentos, "Concurso"),
            worker._extrair_tipo_intervencao(texto_legado, "Concurso"),
        )
        self.assertEqual(funcoes_novo, funcoes_legado)
        self.assertEqual(
            worker._extrair_entregaveis_textos(documentos, concurso),
            worker._extrair_entregaveis(texto_legado, concurso),
        )
        self.assertEqual(
            worker._extrair_especialidades_documentos(documentos),
            worker._extrair_especialidades(texto_legado),
        )
        self.assertEqual(
            worker._extrair_requisitos_textos(documentos),
            worker._extrair_requisitos(texto_legado),
        )
        self.assertEqual(
            worker._sintese_programa_textos(documentos, "Concurso", funcoes_novo),
            worker._sintese_programa(texto_legado, "Concurso", funcoes_legado),
        )

    def test_limites_globais_ordem_e_deduplicacao(self) -> None:
        documentos = [
            f"A proposta obrigatoria numero {indice} tem requisitos claros."
            for indice in range(12)
        ]
        documentos.append("A proposta obrigatoria numero 0 tem requisitos claros.")

        requisitos = worker._extrair_requisitos_textos(documentos)["obrigatorios"]
        especialidades = worker._extrair_especialidades_documentos(
            ["Arquitetura e AVAC.", "AVAC e arquitetura repetidas."]
        )

        self.assertEqual(len(requisitos), 10)
        self.assertTrue(requisitos[0].endswith("numero 0 tem requisitos claros."))
        self.assertTrue(requisitos[-1].endswith("numero 9 tem requisitos claros."))
        self.assertEqual(especialidades, ["Arquitetura", "AVAC"])

    def test_localizacao_tardia_corrige_latitude_decimal_legada(self) -> None:
        """The old parser truncated 38.1234 to 38.0; this is an intentional bug fix."""
        documentos = [
            "Documento inicial sem localizacao.",
            "Concelho: Braga\nFreguesia: Freguesia de Sao Victor\n"
            "4700-000\n38.1234 -9.1234",
        ]

        novo = localizacao.resolver_localizacao({}, documentos=documentos)

        self.assertEqual(novo["municipio"], "Braga")
        self.assertEqual(novo["freguesia"], "Sao Victor")
        self.assertEqual(novo["codigo_postal"], "4700-000")
        self.assertEqual(novo["coordenadas"], "38.12340, -9.12340")

    def test_coordenadas_decimais_e_separadores_aceites(self) -> None:
        for texto in (
            "38.1234 -9.1234",
            "38,1234 -9,1234",
            "38.1234, -9.1234",
            "38.1234 / -9.1234",
            "38.1234; -9.1234",
        ):
            self.assertEqual(
                localizacao._extrair_coordenadas(texto),
                (38.1234, -9.1234),
            )

    def test_numeros_fora_de_portugal_nao_sao_coordenadas(self) -> None:
        for texto in (
            "12.1234 -9.1234",
            "38.1234 -5.1234",
            "99.1234 -9.1234",
            "38.1234 9.1234",
        ):
            self.assertIsNone(localizacao._extrair_coordenadas(texto))

    def test_localizacao_dados_explicitos_precedem_documentos_e_geocoder_uma_vez(self) -> None:
        concurso = {"municipio": "Porto", "morada": "Rua de Teste, Porto"}
        with patch(
            "app.geocoding.obter_coordenadas",
            return_value={"latitude": 41.15, "longitude": -8.61},
        ) as geocoding:
            resultado = localizacao.resolver_localizacao(
                concurso,
                documentos=("Concelho: Braga",),
            )

        self.assertEqual(resultado["municipio"], "Porto")
        self.assertEqual(resultado["fonte"], "geocoding_morada")
        self.assertEqual(geocoding.call_count, 1)

    def test_localizacoes_conhecidas_usam_prioridade_da_tabela(self) -> None:
        resultado = localizacao.resolver_localizacao(
            {},
            documentos=(
                "Mercado Municipal de Castelo Branco.",
                "Escola Secundaria do Lumiar.",
            ),
        )

        self.assertEqual(resultado["municipio"], "Lisboa")
        self.assertEqual(resultado["freguesia"], "Lumiar")
        self.assertEqual(resultado["fonte"], "dados_documentos")

    def test_score_equivale_em_documentos_normais(self) -> None:
        documentos = [
            "Documento inicial.",
            "Qualidade 70%. Metodologia. Arquitetura. "
            "SUBFATOR 2.1\nExperiencia completa.",
        ]
        texto_legado = "\n".join(documentos)
        resumo = {"programa_preliminar": True, "caderno_encargos": True}
        criterios_novos = analisar_criterios_documentos(documentos)
        criterios_legados = analisar_criterios(texto_legado)
        equipa_nova = normalizar_subfatores(
            analisar_equipa_documentos(documentos)["subfatores_equipa"]
        )
        equipa_legada = normalizar_subfatores(
            analisar_equipa(texto_legado)["subfatores_equipa"]
        )

        self.assertEqual(criterios_novos, criterios_legados)
        self.assertEqual(equipa_nova, equipa_legada)
        self.assertEqual(
            worker._calcular_score(resumo, criterios_novos, equipa_nova),
            worker._calcular_score(resumo, criterios_legados, equipa_legada),
        )

    def test_ficha_e_frases_nao_materializam_texto_global(self) -> None:
        fonte_ficha = inspect.getsource(worker._gerar_ficha)
        fonte_frases = inspect.getsource(worker._frases_com_termos)
        fonte_localizacao = inspect.getsource(localizacao._resolver_localizacao_documentos)

        self.assertNotIn('"\\n".join(textos.values())', fonte_ficha)
        self.assertNotIn("texto_total =", fonte_ficha)
        self.assertIn("documentos=documentos_texto", fonte_ficha)
        self.assertNotIn("re.split", fonte_frases)
        self.assertNotIn("join(documentos)", fonte_localizacao)


if __name__ == "__main__":
    unittest.main()