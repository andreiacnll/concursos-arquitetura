from __future__ import annotations

import unittest

from app.analise.universal_document_sections import (
    enrich_procedure_from_documents,
    extract_universal_document_sections,
)


class UniversalProgramReaderV18Tests(unittest.TestCase):
    def test_program_extracts_scoring_team_submission_and_habilitation(self):
        textos = {
            "Processo/2_Programa_Concurso.pdf": """
PROGRAMA DO CONCURSO

10. CRITÉRIO DE ADJUDICAÇÃO
Fator 1: Preço 40%
Fator 2: Valia Técnica da Equipa de Projeto 60%
Subfator 2.1 - Experiência do Coordenador de Projeto 20%
O Coordenador de Projeto deve demonstrar pelo menos 10 anos de experiência.
Subfator 2.2 - Experiência do Autor do Projeto de Arquitetura 20%
Pontua a experiência em 2 projetos de referência.

11. EQUIPA TÉCNICA
- Coordenador de Projeto, com 10 anos de experiência
- Autor do Projeto de Arquitetura

12. DOCUMENTOS QUE INSTRUEM A PROPOSTA
a) Declaração de aceitação do caderno de encargos
b) Curriculum vitae do Coordenador
c) Certidão da Ordem profissional

13. CONTEÚDO TÉCNICO DA PROPOSTA
a) Memória descritiva
b) Metodologia de desenvolvimento dos serviços

14. APRESENTAÇÃO DA PROPOSTA
a) Ficheiro PDF assinado
b) Formulário eletrónico

15. DOCUMENTOS DE HABILITAÇÃO
a) Certidão permanente
""",
        }

        result = extract_universal_document_sections(textos)

        self.assertEqual(len(result["program_documents"]), 1)
        self.assertGreaterEqual(
            len(result["award_criteria"]["scoring_requirements"]),
            2,
        )
        self.assertGreaterEqual(len(result["technical_team"]), 2)
        self.assertGreaterEqual(
            len(result["submission"]["participant_documents"]),
            2,
        )
        self.assertGreaterEqual(
            len(result["submission"]["proposal_documents"]),
            2,
        )
        self.assertGreaterEqual(
            len(result["submission"]["post_selection_documents"]),
            1,
        )

    def test_contract_extracts_execution_sections(self):
        textos = {
            "1_Caderno_de_Encargos.pdf": """
CADERNO DE ENCARGOS

OBJETO DO CONTRATO
Elaboração do projeto de arquitetura e especialidades.

FASES DO PROJETO
- Estudo prévio
- Projeto de execução

CONDIÇÕES DE PAGAMENTO
- 30% após estudo prévio
- 70% após aprovação do projeto de execução

ELEMENTOS A ENTREGAR
- Peças desenhadas
- Peças escritas

PENALIDADES
- Aplicação de penalidade por atraso imputável ao adjudicatário.
""",
        }

        result = extract_universal_document_sections(textos)

        self.assertEqual(len(result["contract_documents"]), 1)
        self.assertTrue(result["contract"]["phases"])
        self.assertTrue(result["contract"]["payments"])
        self.assertTrue(result["contract"]["deliverables"])
        self.assertTrue(result["contract"]["risks"])

    def test_enrichment_never_discards_existing_data(self):
        procedure = {
            "award_criteria": {
                "factors": [{"code": "P", "label": "Preço", "weight_percent": 40}],
                "scoring_requirements": [],
            },
            "technical_team": [{"title": "Arquiteto"}],
        }

        extra = {
            "version": "test",
            "program_documents": ["Programa.pdf"],
            "contract_documents": [],
            "award_criteria": {
                "factors": [],
                "scoring_requirements": [
                    {
                        "title": "Experiência do Coordenador",
                        "subfactor_code": "2.1",
                        "weight_percent": 20,
                    }
                ],
            },
            "technical_team": [{"title": "Coordenador de Projeto"}],
            "eligibility": {},
            "submission": {},
            "contract": {},
        }

        enriched = enrich_procedure_from_documents(procedure, extra)

        self.assertEqual(len(enriched["award_criteria"]["factors"]), 1)
        self.assertEqual(
            len(enriched["award_criteria"]["scoring_requirements"]),
            1,
        )
        self.assertGreaterEqual(len(enriched["technical_team"]), 2)


if __name__ == "__main__":
    unittest.main()
