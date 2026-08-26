from __future__ import annotations

import unittest

from app.analise.procedure_analysis import (
    ROLE_CONTRACT_SPECIFICATIONS,
    ROLE_PROCEDURE_PROGRAM,
    classify_document_role,
    extract_procedure_analysis,
)
from app.analise.project_services_profile import extract_project_services_profile
from app.analise.pre_analysis_enrichment import _build_updates


PC_TEXT = r"""
PROGRAMA DO CONCURSO
OBJETO
Aquisição de serviços de elaboração de projeto de arquitetura paisagista e especialidades.

PRAZO PARA APRESENTAÇÃO DAS PROPOSTAS
O prazo termina às 17:00 horas do 45.º dia a contar da data do envio do anúncio para publicação no Diário da República e no JOUE.

DOCUMENTOS QUE INSTRUEM A PROPOSTA
Documento Europeu Único de Contratação Pública — DEUCP.
Declaração de indicação do preço contratual constante do Anexo I.
Boletim de Identificação da Equipa constante do Anexo II.
Declaração da Experiência do Gestor BIM constante do Anexo III.
Documento preenchido do ANEXO X — Atributos da proposta para determinação da pontuação do Fator A, em XLSX.
Certificados de formação profissional da pessoa indicada para Gestão BIM.
1 ficheiro CadernoA3.pdf, em PDF, A3 horizontal, 300 dpi, máximo de 40 MB e cerca de 20 páginas.
1 ficheiro Estimativa.xls com o quadro de Estimativa de Custo de Obra na matriz oficial do Anexo V.
1 ficheiro Imagem1.jpg, JPG, 300 dpi, máximo de 10 MB.
Documento comprovativo dos poderes de representação.
Tratando-se de agrupamento, devem ser juntos os instrumentos de mandato.
Outra documentação que os concorrentes considerem indispensável.

MODO DE APRESENTAÇÃO DAS PROPOSTAS
A proposta é submetida na plataforma eletrónica AnoGov e assinada com assinatura eletrónica qualificada.
Os documentos são redigidos em língua portuguesa ou acompanhados de tradução legalizada.
O preço é expresso em euros, com duas casas decimais, e não inclui IVA.
Não são admitidas propostas variantes.
Os membros de agrupamento não podem integrar outro agrupamento concorrente.

PRAZO DA OBRIGAÇÃO DE MANUTENÇÃO DAS PROPOSTAS
Os concorrentes são obrigados a manter as propostas pelo prazo de 180 (cento e oitenta) dias úteis.

CRITÉRIO DE ADJUDICAÇÃO
Fator A — Experiência da equipa técnica (50%)
A1 — Experiência em Projeto de Parques Urbanos — ponderação de 40%.
A2 — Experiência em Projeto de Obras de Urbanização Públicas — ponderação de 40%.
A3 — Experiência em Projeto de Remodelação de Terrenos — ponderação de 15%.
A4 — Formação do Gestor BIM — peso parcial de 5%.
Para A1 são pontuáveis até 5 projetos na União Europeia, nos últimos 15 anos, com empreitada igual ou superior a 2.000.000,00 €.
Para A2 são pontuáveis até 5 projetos de obras de urbanização públicas.
Para A3 são pontuáveis até 5 projetos de remodelação de terrenos com movimentação de terras igual ou superior a 100.000 m3.
Para A4 é exigida formação em processos colaborativos BIM igual ou superior a 80 horas.
Fator B — Proposta de conceção (30%)
B1. Qualidade estética e coerência geral da proposta — 40%.
B2. Adequação ao Programa de Intervenção — 30%.
B3. Adequação aos Princípios Orientadores — 30%.
Fator C — Preço (20%)
Em caso de empate aplica-se sucessivamente o Fator A, o Fator B e o Fator C; persistindo, sorteio.

CAUSAS DE EXCLUSÃO DAS PROPOSTAS
Serão excluídas as propostas em que os técnicos de coordenação indicados também integrem outra proposta de outro concorrente.
Serão excluídas as propostas cujo Gestor BIM não tenha formação mínima de 80 horas em processos colaborativos BIM; formação exclusivamente em software de modelação não conta.

HABILITAÇÃO DO ADJUDICATÁRIO
O adjudicatário apresenta a declaração do Anexo II do CCP, comprovativos de inexistência de impedimentos, declarações das ordens profissionais, plano de prevenção de corrupção e RCBE.

PRESTAÇÃO DE CAUÇÃO
O valor da caução é de 5% do preço contratual. Quando o preço seja anormalmente baixo, a caução é de 10%.
O adjudicatário apresenta seguros de responsabilidade civil de cada técnico.

ANEXO IV — TRABALHO — FATOR B
A. Caderno A3
Planta de implantação à escala 1:2000.
Perfis de implantação à escala 1:2000.
Axonometria geral.
Sistemas construtivos, materiais e plantações.
Elementos a manter, demolir e construir.
Movimentação de terras.
Gestão e reaproveitamento das águas pluviais, retardamento e infiltração.
Acessos, estacionamento e rede viária.
Exequibilidade das infraestruturas.
Memória descritiva e justificativa.
O CadernoA3.pdf é A3 horizontal, PDF, 300 dpi, máximo 40 MB.
Deve ser utilizada exclusivamente a matriz de estimativa de custo apresentada no ANEXO VI e entregue como Estimativa.xls.
A imagem Imagem1.jpg é JPG, 300 dpi e máximo 10 MB. Só é permitida uma imagem.
NOTA: A não verificação do exigido neste anexo não determina a exclusão da proposta.

LISTA DE ANEXOS
ANEXO V — Estimativa de Custo de Obra.
ANEXO XII — Atributos da proposta para determinação da pontuação do Fator A.
O Programa Preliminar integra as peças do procedimento.
"""


CE_TEXT = r"""
CADERNO DE ENCARGOS
OBJETO DO CONTRATO
Projeto de arquitetura paisagista, espaço público, terraplenagem, fundações e estruturas, redes de águas, esgotos, rede viária, sistemas elétricos, medições, orçamento, manutenção e metodologia BIM.

FASES DA PRESTAÇÃO DE SERVIÇOS
Fase 1 — Plano de Execução BIM — 15 dias.
Fase 2 — Estudo Prévio — 60 dias.
Fase 3 — Anteprojeto — 60 dias.
Fase 4 — Projeto de Execução — 90 dias.
Fase 5 — Projeto de Execução Final — 15 dias.
Fase 6 — Assistência Técnica até à receção provisória da obra.
O prazo máximo é de 1815 dias.
Devem ser entregues telas finais e modelos tridimensionais BIM.

PENALIDADES POR VIOLAÇÃO DOS PRAZOS
Por cada dia de atraso aplica-se 1 por mil do preço contratual.
Nos prazos parciais o valor é reduzido a metade.
Há sanção pecuniária de 100 € por dia noutros incumprimentos.
O cocontratante responde por erros e defeitos do projeto.
Os direitos de propriedade sobre a informação BIM pertencem à entidade adjudicante.

PREÇO BASE
O preço base é de 998 318,87 €, acrescido de IVA à taxa legal.

CONDIÇÕES DE PAGAMENTO
5% — Fase 1 — Plano de Execução BIM.
15% — Fase 2 — Estudo Prévio.
20% — Fase 3 — Anteprojeto.
35% — Fase 4 — Projeto de Execução.
10% — Fase 5 — Projeto de Execução Final.
15% — Assistência Técnica.
"""


ANNEX_TEXT = """
BOLETIM DE IDENTIFICAÇÃO DA EQUIPA
Coordenador do projeto; Gestor BIM; Coordenador BIM arquitetura e paisagismo;
Coordenador BIM estruturas; Coordenador BIM infraestruturas; Arquitetura paisagista;
Arquitetura de espaço público; Terraplanagens; Escavação e contenção periférica;
Fundações e estruturas; Águas; Esgotos domésticos e pluviais; Eletricidade;
Comunicações; Gás; Rede viária; Sinalização; Sinalética; Arqueologia;
Acessibilidades; Segurança e saúde; Resíduos de construção e demolição;
Mapa de trabalhos, medições e estimativa.
"""


class ProjectServicesProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = [
            {"filename": "PC_Projeto.docx", "role": "procedure_program", "text": PC_TEXT},
            {"filename": "CE_Projeto.docx", "role": "contract_specifications", "text": CE_TEXT},
            {"filename": "PC_ANEXO_II_Boletim.docx", "role": "proposal_annex", "text": ANNEX_TEXT},
            {"filename": "ANEXO XII - Pontuacao Fator A.xlsx", "role": "proposal_annex", "text": "Folha oficial"},
            {"filename": "ANEXO V - Estimativa.xlsx", "role": "proposal_annex", "text": "Matriz oficial"},
        ]

    def test_document_roles_do_not_mix_pc_and_ce(self) -> None:
        self.assertEqual(classify_document_role("PC_Projeto.docx", PC_TEXT)[0], ROLE_PROCEDURE_PROGRAM)
        self.assertEqual(classify_document_role("CE_Projeto.docx", CE_TEXT)[0], ROLE_CONTRACT_SPECIFICATIONS)

    def test_extracts_only_structured_submission_items(self) -> None:
        profile = extract_project_services_profile(self.documents)
        submission = profile["submission"]
        self.assertEqual(submission["mandatory_checklist_count"], 10)
        self.assertEqual(len(submission["participant_documents"]), 12)
        self.assertEqual(len(submission["proposal_documents"]), 10)
        titles = " ".join(item["title"] for item in submission["participant_documents"]).casefold()
        self.assertIn("deucp", titles)
        self.assertIn("estimativa", titles)
        self.assertNotIn("abertura eletrónica", titles)
        self.assertNotIn("esclarecimentos", titles)

    def test_preserves_main_and_subfactor_weights(self) -> None:
        criteria = extract_project_services_profile(self.documents)["award_criteria"]
        self.assertEqual([item["weight"] for item in criteria["factors"]], [50.0, 30.0, 20.0])
        factor_a = criteria["factors"][0]
        self.assertEqual([item["absolute_weight"] for item in factor_a["subfactors"]], [20.0, 20.0, 7.5, 2.5])
        self.assertEqual(criteria["curriculum_weight"], 47.5)
        self.assertEqual(criteria["summary"], "Experiência da equipa técnica 50% • Proposta de conceção 30% • Preço 20%")

    def test_extracts_relative_deadline_price_and_validity(self) -> None:
        profile = extract_project_services_profile(self.documents)
        metrics = profile["top_metric_overrides"]
        self.assertEqual(metrics["procedure_value"]["value"], "998 318,87 € + IVA")
        self.assertEqual(metrics["construction_cost"]["value"], "A entregar na proposta")
        self.assertEqual(metrics["submission_deadline"]["status"], "relative_confirmed")
        self.assertIn("45.º dia", metrics["submission_deadline"]["value"])
        self.assertEqual(metrics["proposal_validity"]["value"], "180 dias úteis")
        self.assertEqual(metrics["contract_duration"]["value"], "1815 dias")

    def test_explicit_exclusions_are_not_generic_formal_rules(self) -> None:
        profile = extract_project_services_profile(self.documents)
        exclusions = profile["submission"]["critical_conditions"]
        self.assertEqual(len(exclusions), 2)
        self.assertTrue(all(item["effect"] == "explicit_exclusion" for item in exclusions))
        titles = " ".join(item["title"] for item in exclusions).casefold()
        self.assertIn("técnicos", titles)
        self.assertIn("80 horas", titles)
        formal_titles = " ".join(item["title"] for item in profile["submission"]["formal_risks"]).casefold()
        self.assertIn("não determinam", formal_titles)
        self.assertNotIn("não determinam", titles)

    def test_contract_information_stays_post_award(self) -> None:
        profile = extract_project_services_profile(self.documents)
        contract = profile["contract"]
        self.assertEqual(len(contract["phases"]), 6)
        self.assertEqual(sum(item["percentage"] for item in contract["payments"]), 100)
        risk_titles = " ".join(item["title"] for item in contract["risks"]).casefold()
        self.assertIn("1‰", risk_titles)
        self.assertIn("caução", risk_titles)
        self.assertIn("seguros", risk_titles)
        submission_titles = " ".join(
            item["title"]
            for item in profile["submission"]["participant_documents"] + profile["submission"]["proposal_documents"]
        ).casefold()
        self.assertNotIn("projeto de execução final", submission_titles)
        self.assertNotIn("telas finais", submission_titles)

    def test_missing_source_and_document_inconsistencies(self) -> None:
        profile = extract_project_services_profile(self.documents)
        self.assertEqual(len(profile["document_gaps"]), 1)
        self.assertIn("Programa Preliminar", profile["document_gaps"][0]["title"])
        titles = " ".join(item["title"] for item in profile["inconsistencies"])
        self.assertIn("Anexo X e Anexo XII", titles)
        self.assertIn("Anexo VI", titles)

    def test_pre_analysis_populates_search_without_ai_analysis(self) -> None:
        textos = {item["filename"]: item["text"] for item in self.documents}
        concurso = {
            "titulo": "Aquisição de serviços de elaboração de projeto de arquitetura paisagista",
            "tipo_procedimento": "Concurso Público Internacional",
            "preco_base": None,
            "data_entrega_propostas": None,
            "data_limite": None,
        }
        procedure = extract_procedure_analysis(
            ficha={"common_project_extraction": {}},
            textos=textos,
            concurso=concurso,
        )
        updates = _build_updates(concurso, {}, procedure)
        self.assertEqual(updates["tipo_procedimento"], "Prestação de serviços de projeto com proposta de conceção")
        self.assertEqual(updates["preco_base"], "998 318,87 € + IVA")
        self.assertIn("45.º dia", updates["data_entrega_propostas"])
        self.assertEqual(updates["criterio_resumo"], "Experiência da equipa técnica 50% • Proposta de conceção 30% • Preço 20%")

    def test_integrated_analysis_uses_profile_not_legacy_noise(self) -> None:
        textos = {item["filename"]: item["text"] for item in self.documents}
        result = extract_procedure_analysis(
            ficha={"common_project_extraction": {}},
            textos=textos,
            concurso={
                "titulo": "Aquisição de serviços de elaboração de projeto de arquitetura paisagista",
                "tipo_procedimento": "Concurso Público Internacional",
                "preco_base": None,
            },
        )
        self.assertEqual(result["family"], "project_services")
        self.assertEqual(result["counts"]["critical_conditions"], 2)
        self.assertEqual(result["award_criteria"]["summary"], "Experiência da equipa técnica 50% • Proposta de conceção 30% • Preço 20%")
        metric_map = {item["key"]: item for item in result["top_metrics"]}
        self.assertEqual(metric_map["construction_cost"]["status"], "required")
        self.assertEqual(metric_map["submission_deadline"]["status"], "relative_confirmed")


    def test_profile_recovers_from_stale_cached_roles(self) -> None:
        stale = [
            {"filename": "002-PC_VSA_ElabProjeto.docx", "role": "other", "text": PC_TEXT},
            {"filename": "004-CE_VSA_ElabProjeto.docx", "role": "other", "text": CE_TEXT},
            {"filename": "PC_ ANEXO II - Boletim de Identificacao da Equipa.docx", "role": "other", "text": ANNEX_TEXT},
            {"filename": "ANEXO XII - Pontuacao Fator A.xlsx", "role": "other", "text": "Folha oficial"},
            {"filename": "ANEXO V - Estimativa.xlsx", "role": "other", "text": "Matriz oficial"},
        ]
        profile = extract_project_services_profile(stale)
        self.assertTrue(profile)
        self.assertTrue(all(profile["features"].values()))
        self.assertEqual(
            profile["award_criteria"]["summary"],
            "Experiência da equipa técnica 50% • Proposta de conceção 30% • Preço 20%",
        )
        self.assertEqual(len(profile["submission"]["critical_conditions"]), 2)


    def test_realistic_program_with_index_uses_body_sections(self) -> None:
        noisy_pc = r"""
ÍNDICE
7.DOCUMENTOS QUE INSTRUEM A PROPOSTA5
14.CRITÉRIO DE ADJUDICAÇÃO8
17.CAUSAS DE EXCLUSÃO DAS PROPOSTAS21
21.HABILITAÇÃO DO ADJUDICATÁRIO23
""" + PC_TEXT + r"""
RELATÓRIO PRELIMINAR
As propostas são analisadas atendendo ao critério de adjudicação definido.
RELATÓRIO FINAL
O júri pode propor exclusão se verificar qualquer causa de exclusão das propostas.
"""
        documents = [
            {"filename": "002-PC_VSA_ElabProjeto.docx", "role": "other", "text": noisy_pc},
            {"filename": "004-CE_VSA_ElabProjeto.docx", "role": "other", "text": CE_TEXT},
            {"filename": "PC_ANEXO_II_Boletim.docx", "role": "other", "text": ANNEX_TEXT},
            {"filename": "ANEXO XII - Pontuacao Fator A.xlsx", "role": "other", "text": "Folha oficial"},
            {"filename": "ANEXO V - Estimativa.xlsx", "role": "other", "text": "Matriz oficial"},
        ]
        profile = extract_project_services_profile(documents)
        self.assertTrue(all(profile["features"].values()))
        self.assertEqual(
            profile["award_criteria"]["summary"],
            "Experiência da equipa técnica 50% • Proposta de conceção 30% • Preço 20%",
        )
        self.assertEqual(len(profile["submission"]["critical_conditions"]), 2)
        self.assertGreaterEqual(len(profile["submission"]["participant_documents"]), 10)


    def test_inconsistencies_are_detected_without_materialized_annex_files(self) -> None:
        documents = [
            {"filename": "002-PC_VSA_ElabProjeto.docx", "role": "other", "text": PC_TEXT},
            {"filename": "004-CE_VSA_ElabProjeto.docx", "role": "other", "text": CE_TEXT},
        ]
        profile = extract_project_services_profile(documents)
        titles = {
            str(item.get("title") or "")
            for item in profile.get("inconsistencies") or []
        }
        self.assertIn(
            "Referência ao Fator A diverge entre Anexo X e Anexo XII",
            titles,
        )
        self.assertIn(
            "Matriz da estimativa diverge entre Anexo V e Anexo VI",
            titles,
        )

    def test_design_submission_uses_clear_terrain_wording(self) -> None:
        profile = extract_project_services_profile([
            {"filename": "PC_VSA_ElabProjeto.docx", "role": "procedure_program", "text": PC_TEXT},
            {"filename": "CE_VSA_ElabProjeto.docx", "role": "contract_specifications", "text": CE_TEXT},
        ])
        titles = {item.get("title") for item in profile["submission"]["proposal_documents"]}
        self.assertIn("Modelação do terreno, escavações e aterros", titles)
        self.assertNotIn("Movimentação de terras", titles)



if __name__ == "__main__":
    unittest.main()
