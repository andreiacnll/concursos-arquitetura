from __future__ import annotations

import unittest

from app.analise.universal_document_sections import (
    extract_universal_document_sections,
)


class UniversalReaderQualityV181Tests(unittest.TestCase):
    def test_narrative_contract_paragraphs_are_not_phases_or_risks(self):
        textos = {
            "1_Caderno_de_Encargos.pdf": """
CADERNO DE ENCARGOS

FASES DO PROJETO
A execução da empreitada, com solução de eventual instalação de estruturas
provisórias que viabilizem a sua implementação. O projeto deverá englobar
as seguintes fases:
Fase I - Sondagens geotécnicas
Fase II - Estudo Prévio
Fase III - Projeto de Execução

RESPONSABILIDADE
A participação dos técnicos autores, a compatibilidade entre os diversos
projetos necessários e o cumprimento das disposições legais aplicáveis a
cada especialidade, bem como a relação com o dono da obra ou representante.

PENALIDADES
Será aplicada penalidade por atraso imputável ao adjudicatário.
""",
        }

        result = extract_universal_document_sections(textos)
        phases = result["contract"]["phases"]
        risks = result["contract"]["risks"]

        self.assertEqual(len(phases), 3)
        self.assertEqual(len(risks), 1)

        joined_phases = " ".join(item["title"] for item in phases).lower()
        joined_risks = " ".join(item["title"] for item in risks).lower()

        self.assertNotIn("execução da empreitada, com solução", joined_phases)
        self.assertNotIn("participação dos técnicos autores", joined_risks)
        self.assertIn("penalidade", joined_risks)

    def test_submission_rejects_narrative_lines_with_document_words(self):
        textos = {
            "2_Programa_Concurso.pdf": """
PROGRAMA DO CONCURSO

DOCUMENTOS QUE INSTRUEM A PROPOSTA
Os documentos apresentados pelo concorrente serão analisados pelo júri.
a) Declaração de aceitação do conteúdo do caderno de encargos
b) Curriculum vitae do coordenador
A falta de um documento poderá determinar a exclusão nos termos legais.
""",
        }

        result = extract_universal_document_sections(textos)
        items = result["submission"]["participant_documents"]

        self.assertEqual(len(items), 2)

        joined = " ".join(item["title"] for item in items).lower()
        self.assertNotIn("serão analisados pelo júri", joined)
        self.assertNotIn("poderá determinar a exclusão", joined)

    def test_payment_and_deliverable_quality_gate(self):
        textos = {
            "Caderno_de_Encargos.pdf": """
CADERNO DE ENCARGOS

CONDIÇÕES DE PAGAMENTO
- 30% após aprovação do Estudo Prévio
- 70% após aprovação do Projeto de Execução
O adjudicatário deverá articular com todas as entidades envolvidas.

ELEMENTOS A ENTREGAR
- Peças escritas em PDF
- Peças desenhadas em DWG
A coordenação do projeto deverá garantir a compatibilidade das especialidades.
""",
        }

        result = extract_universal_document_sections(textos)

        self.assertEqual(len(result["contract"]["payments"]), 2)
        self.assertEqual(len(result["contract"]["deliverables"]), 2)


if __name__ == "__main__":
    unittest.main()
