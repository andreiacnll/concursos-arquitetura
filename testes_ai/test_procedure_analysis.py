from __future__ import annotations

import unittest

from app.analise.procedure_analysis import (
    FAMILY_DESIGN_BUILD,
    FAMILY_DESIGN_COMPETITION,
    FAMILY_PROJECT_SERVICES,
    apply_procedure_analysis,
    assess_company_award_fit,
    classify_document_role,
    extract_procedure_analysis,
    infer_analysis_family,
)


PROJECT_PC = """
PROGRAMA DO PROCEDIMENTO
Artigo 8.º - Documentos que constituem a proposta
1. Declaração do Anexo I ao Código dos Contratos Públicos.
2. Proposta de preço, devidamente assinada.
3. Memória metodológica com o máximo de 20 páginas, em formato PDF.
4. Plano de trabalhos e cronograma.
5. Identificação da equipa técnica e currículos dos técnicos.

Artigo 9.º - Apresentação das propostas
1. A proposta deve ser submetida na plataforma eletrónica em formato PDF.
2. Os ficheiros devem ser assinados eletronicamente.
3. A falta da proposta de preço determina a exclusão da proposta.

Artigo 12.º - Prazo para apresentação das propostas
As propostas devem ser entregues até 18 de setembro de 2026, às 17:00.

Artigo 15.º - Critério de adjudicação
A adjudicação é feita segundo a proposta economicamente mais vantajosa.
Qualidade técnica - 70%
Preço - 30%
Em caso de empate prevalece a maior pontuação da Qualidade técnica.

Artigo 20.º - Documentos de habilitação
1. Certidão de situação tributária regularizada.
2. Certidão de situação contributiva regularizada.
"""

PROJECT_CE = """
CADERNO DE ENCARGOS
Cláusula 4.ª - Objeto e âmbito dos serviços
O adjudicatário desenvolve Estudo Prévio, Anteprojeto, Projeto de Execução,
especialidades, mapa de quantidades, estimativa orçamental e assistência técnica.

Cláusula 8.ª - Condições de pagamento
O pagamento é efetuado por fase, no prazo de 30 dias após a fatura.

Cláusula 16.ª - Penalizações por atraso
O atraso determina penalizações contratuais.

Cláusula 18.ª - Erros e omissões
O adjudicatário é responsável por erros e omissões do projeto.
"""


class ProcedureAnalysisTests(unittest.TestCase):
    def test_three_families_are_distinct(self) -> None:
        design = infer_analysis_family(
            {"titulo": "Concurso de conceção para uma escola"}
        )
        services = infer_analysis_family(
            {"titulo": "Aquisição de serviços para elaboração de projeto e especialidades"}
        )
        build = infer_analysis_family(
            {"titulo": "Concurso Público Conceção-Construção Pavilhão"}
        )
        self.assertEqual(design["family"], FAMILY_DESIGN_COMPETITION)
        self.assertEqual(services["family"], FAMILY_PROJECT_SERVICES)
        self.assertEqual(build["family"], FAMILY_DESIGN_BUILD)

    def test_document_roles_are_classified(self) -> None:
        self.assertEqual(
            classify_document_role("PC_Projeto.docx", PROJECT_PC)[0],
            "procedure_program",
        )
        self.assertEqual(
            classify_document_role("CE_Projeto.docx", PROJECT_CE)[0],
            "contract_specifications",
        )
        self.assertEqual(
            classify_document_role("EIR.pdf", "Exchange Information Requirements")[0],
            "eir",
        )

    def test_project_services_extracts_weighted_criteria_and_deadline(self) -> None:
        result = extract_procedure_analysis(
            ficha={
                "common_project_extraction": {
                    "submission_deadline": {
                        "value": "18-09-2026 17:00",
                        "source_document": "PC_Projeto.docx",
                    },
                    "publication_date": {},
                }
            },
            textos={
                "PC_Projeto.docx": PROJECT_PC,
                "CE_Projeto.docx": PROJECT_CE,
            },
            concurso={
                "titulo": "Elaboração de Projeto de Arquitetura Paisagista e Especialidades",
                "tipo_procedimento": "Concurso Público",
            },
        )
        self.assertEqual(result["family"], FAMILY_PROJECT_SERVICES)
        self.assertEqual(
            result["award_criteria"]["summary"],
            "Qualidade técnica 70% • Preço 30%",
        )
        deadline_metric = next(
            item
            for item in result["top_metrics"]
            if item["key"] == "submission_deadline"
        )
        self.assertEqual(deadline_metric["value"], "18-09-2026 17:00")

    def test_submission_and_contract_are_not_mixed(self) -> None:
        result = extract_procedure_analysis(
            ficha={"common_project_extraction": {}},
            textos={
                "PC_Projeto.docx": PROJECT_PC,
                "CE_Projeto.docx": PROJECT_CE,
            },
            concurso={"titulo": "Aquisição de serviços de projeto"},
        )
        proposal_titles = {
            item["title"]
            for item in result["submission"]["proposal_documents"]
        }
        contract_titles = {
            item["title"]
            for item in result["contract"]["deliverables"]
        }
        self.assertTrue(any("Memória metodológica" in title for title in proposal_titles))
        self.assertNotIn("Projeto de execução", {title.casefold() for title in proposal_titles})
        self.assertIn("Projeto de execução", contract_titles)
        self.assertEqual(
            len(result["submission"]["post_selection_documents"]),
            2,
        )

    def test_apply_keeps_legacy_shape_without_parallel_page(self) -> None:
        ficha: dict = {
            "common_project_extraction": {},
            "identificacao": {},
            "criterios": {},
        }
        result = apply_procedure_analysis(
            ficha=ficha,
            textos={
                "PC_Projeto.docx": PROJECT_PC,
                "CE_Projeto.docx": PROJECT_CE,
            },
            concurso={"titulo": "Aquisição de serviços para elaboração de projeto"},
        )
        self.assertEqual(ficha["analysis_family"], FAMILY_PROJECT_SERVICES)
        self.assertIs(ficha["procedure_analysis"], result)
        groups = ficha["submission_requirements"]["groups"]
        self.assertIn("design_work", groups)
        self.assertIn("post_selection_documents", groups)
        self.assertTrue(ficha["criterios"]["resumo"].endswith("Preço 30%"))

    def test_project_submission_uses_exact_section_and_rejects_procedure_noise(self) -> None:
        pc = """
PROGRAMA DO PROCEDIMENTO
7 DOCUMENTOS QUE INSTRUEM A PROPOSTA
7.1 Declaração do Anexo I.
7.2 Proposta de preço.
7.3 Memória metodológica.
8 MODO DE APRESENTAÇÃO DAS PROPOSTAS
8.1 Os documentos devem ser apresentados em formato PDF.
9 ABERTURA DAS PROPOSTAS
9.1 A abertura eletrónica é efetuada pelo júri.
"""
        result = extract_procedure_analysis(
            ficha={"common_project_extraction": {}},
            textos={"PC_Projeto.docx": pc},
            concurso={"titulo": "Aquisição de serviços para elaboração de projeto"},
        )
        submission = result["submission"]
        titles = {item["title"] for item in submission["participant_documents"] + submission["proposal_documents"]}
        self.assertIn("Declaração do Anexo I", titles)
        self.assertIn("Proposta de preço", titles)
        self.assertIn("Memória metodológica", titles)
        joined = " ".join(titles).casefold()
        self.assertNotIn("abertura eletrónica", joined)
        self.assertNotIn("formato pdf", joined)
        self.assertLessEqual(len(titles), 4)

    def test_cost_estimate_required_is_not_reported_as_unknown(self) -> None:
        pc = """
PROGRAMA DO PROCEDIMENTO
7 DOCUMENTOS QUE INSTRUEM A PROPOSTA
7.1 Proposta de preço.
7.2 Memória metodológica.
7.3 Estimativa de custo da obra.
"""
        result = extract_procedure_analysis(
            ficha={"common_project_extraction": {}},
            textos={"PC_Projeto.docx": pc},
            concurso={"titulo": "Aquisição de serviços para elaboração de projeto"},
        )
        metric = next(
            item for item in result["top_metrics"]
            if item["key"] == "construction_cost"
        )
        self.assertEqual(metric["value"], "A entregar na proposta")
        self.assertEqual(metric["status"], "required")
        self.assertEqual(metric["status_label"], "Exigido")

    def test_missing_scored_project_experience_reduces_company_score(self) -> None:
        procedure = {
            "award_criteria": {
                "factors": [
                    {
                        "name": "Experiência da equipa",
                        "weight": 50,
                        "subfactors": [
                            {
                                "name": "Experiência em Projeto de Parques Urbanos",
                                "weight": 40,
                                "evidence_excerpt": "Projetos de parques urbanos concluídos",
                            },
                            {
                                "name": "Experiência em Obras de Urbanização Públicas",
                                "weight": 40,
                                "evidence_excerpt": "Obras de urbanização públicas",
                            },
                            {
                                "name": "Experiência em Remodelação de Terrenos",
                                "weight": 20,
                                "evidence_excerpt": "Remodelação de terrenos",
                            },
                        ],
                    },
                    {"name": "Qualidade da proposta", "weight": 50, "subfactors": []},
                ]
            }
        }
        result = assess_company_award_fit(
            procedure,
            {
                "project_experience": [
                    {
                        "name": "Reabilitação de edifício habitacional",
                        "typology": "Habitação",
                    }
                ]
            },
            {"profiled_members_count": 2, "relevant_members": []},
        )
        self.assertTrue(result["active"])
        self.assertEqual(result["relevant_weight"], 50)
        self.assertEqual(result["coverage_percent"], 0)
        self.assertGreaterEqual(result["penalty"], 25)
        self.assertEqual(len(result["missing_requirements"]), 3)

    def test_subfactor_percentages_are_not_promoted_to_top_level(self) -> None:
        pc = """
PROGRAMA DO PROCEDIMENTO
15 CRITÉRIO DE ADJUDICAÇÃO
Fator A - Experiência da equipa
A1 - Experiência em parques urbanos - 40%
A2 - Experiência em urbanização - 40%
A3 - Experiência em terrenos - 20%
"""
        result = extract_procedure_analysis(
            ficha={"common_project_extraction": {}},
            textos={"PC_Projeto.docx": pc},
            concurso={"titulo": "Aquisição de serviços para elaboração de projeto"},
        )
        criteria = result["award_criteria"]
        self.assertFalse(criteria.get("verified_top_level_weights"))
        self.assertEqual(criteria.get("factors"), [])
        self.assertIn("Ponderações principais por confirmar", criteria.get("summary", ""))

    def test_unrelated_typologies_do_not_count_for_scored_urbanism_experience(self) -> None:
        procedure = {
            "award_criteria": {
                "factors": [
                    {
                        "name": "Experiência da equipa técnica",
                        "weight": 50,
                        "subfactors": [
                            {"name": "Projetos de parques urbanos", "weight": 40, "absolute_weight": 20},
                            {"name": "Projetos de obras de urbanização públicas", "weight": 40, "absolute_weight": 20},
                            {"name": "Projetos de remodelação de terrenos", "weight": 15, "absolute_weight": 7.5},
                            {"name": "Formação do Gestor BIM 80 horas", "weight": 5, "absolute_weight": 2.5},
                        ],
                    },
                    {"name": "Proposta de conceção", "weight": 30},
                    {"name": "Preço", "weight": 20},
                ]
            }
        }
        fit = assess_company_award_fit(
            procedure,
            {
                "project_experience": [
                    {"name": "VL8", "typology": "Habitação"},
                    {"name": "Vilela School", "typology": "Educação"},
                    {"name": "FACE", "typology": "Cultura"},
                    {"name": "Casa histórica", "typology": "Reabilitação"},
                ],
                "competences": ["BIM", "Urbanismo", "Arquitetura"],
            },
            {"competences": ["BIM", "Urbanismo"], "profiled_members_count": 3},
        )
        self.assertTrue(fit["active"])
        self.assertEqual(fit["relevant_weight"], 50)
        self.assertEqual(fit["coverage_percent"], 0)
        self.assertEqual(fit["documented_weight"], 0)
        self.assertEqual(fit["pending_weight"], 50)
        self.assertIn("Habitação", fit["unrelated_project_typologies"])
        self.assertTrue(all(item["status"] == "not_demonstrated" for item in fit["assessed_requirements"]))
        self.assertFalse(any(item["matched_projects"] for item in fit["assessed_requirements"]))



    def test_experience_factor_propagates_to_named_project_subfactors(self) -> None:
        procedure = {
            "award_criteria": {
                "factors": [
                    {
                        "name": "Experiência da equipa técnica",
                        "weight": 50,
                        "subfactors": [
                            {"name": "Projetos de parques urbanos", "weight": 40, "absolute_weight": 20},
                            {"name": "Projetos de obras de urbanização públicas", "weight": 40, "absolute_weight": 20},
                            {"name": "Projetos de remodelação de terrenos", "weight": 15, "absolute_weight": 7.5},
                            {"name": "Formação do Gestor BIM 80 horas", "weight": 5, "absolute_weight": 2.5},
                        ],
                    }
                ]
            }
        }
        fit = assess_company_award_fit(
            procedure,
            {
                "project_experience": [
                    {"name": "Projeto habitacional", "typology": "Habitação"},
                ]
            },
            {},
        )
        self.assertEqual(fit["relevant_weight"], 50)
        weights = {
            item["display_name"]: item["absolute_weight"]
            for item in fit["assessed_requirements"]
        }
        self.assertEqual(weights["Parques urbanos"], 20)
        self.assertEqual(weights["Obras de urbanização pública"], 20)
        self.assertEqual(weights["Remodelação/modelação de terrenos"], 7.5)
        self.assertEqual(weights["Formação do Gestor BIM 80 horas"], 2.5)
        self.assertEqual(fit["documented_weight"], 0)
        self.assertEqual(fit["pending_weight"], 50)


if __name__ == "__main__":
    unittest.main()
