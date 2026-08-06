from __future__ import annotations

import unittest

from app.analise.submission_requirements import (
    extract_submission_requirements,
)


TERMS = """
ÍNDICE
Artigo 10º - Documentos do Concorrente. 8
Artigo 11º - Documentos que materializam os trabalhos de conceção. 9
Artigo 12º - Modo de apresentação dos ficheiros na plataforma eletrónica. 11
Artigo 22º - Habilitações. 17

Artigo 10º - Documentos do Concorrente
1. O concorrente apresenta:
a) Boletim de Identificação (ANEXO III)
Um ficheiro em formato PDF denominado Boletim de Identificação.
b) Declaração de Compromisso (ANEXO IV)
Um ficheiro em formato PDF denominado Declaração de Compromisso.
2. A assinatura dos documentos deve ser digital, mediante certificado qualificado.

Artigo 11º - Documentos que materializam os trabalhos de conceção
1. Elementos a entregar em formato físico:
1.1 Painéis A1
O trabalho deve ser apresentado sobre 3 (três) painéis DIN A1,
com orientação vertical.
Os painéis contêm planta de implantação, plantas, cortes e alçados,
organograma funcional e representações tridimensionais.

2. Documentos a submeter na plataforma:
2.1 Caderno A3 digital
Um ficheiro PDF DIN A3 horizontal, com o número máximo de 20 (vinte) páginas.
Inclui conceito geral da proposta, acessibilidade e espaços exteriores,
organização interna e cumprimento do Programa Preliminar, materialidade
e viabilidade técnica e financeira, eficiência e sustentabilidade energética
e faseamento da obra.

2.2 Um (1) ficheiro único com o Quadro de Áreas, com orientação vertical e de dimensão A4, em formato PDF, identificado como B_QuadroAreas.pdf.

2.3 Cinco (5) ficheiros contendo peças gráficas para divulgação,
em formato JPG, identificados C_Imagem1.jpg a C_Imagem5.jpg.

2.4 Três (3) ficheiros, um por cada painel A1, em formato JPG,
com máximo de 10 MB, identificados D_Painel1.jpg a D_Painel3.jpg.

3. Não é permitida a apresentação de maquetas físicas.

Artigo 12º - Modo de apresentação dos ficheiros na plataforma eletrónica
Os documentos do artigo 10 devem ser assinados.
Os documentos do artigo 11 não devem ser assinados e são anónimos.

Artigo 13º - Modo de apresentação dos painéis A1 em formato físico
Os painéis são entregues em invólucro opaco.

Artigo 22º - Habilitações
O selecionado apresenta no prazo de 5 dias úteis:
a) Declaração da Ordem dos Arquitetos;
b) Certidão comercial.
"""


class SubmissionRequirementsV2Tests(unittest.TestCase):
    def test_article_aware_extraction(self) -> None:
        result = extract_submission_requirements(
            {"Termos de Referência.pdf": TERMS}
        )
        groups = result["groups"]

        self.assertEqual(len(groups["participant_documents"]), 2)
        self.assertEqual(len(groups["design_work"]), 5)
        self.assertEqual(len(groups["complementary_documents"]), 0)
        self.assertEqual(len(groups["post_selection_documents"]), 2)

        keys = {
            item["key"]: item
            for item in groups["design_work"]
        }

        self.assertEqual(keys["panels"]["quantity"], 3)
        self.assertEqual(keys["panels"]["page_size"], "A1")
        self.assertEqual(keys["panels"]["orientation"], "vertical")
        self.assertIn(
            "Plantas, cortes e alçados",
            keys["panels"]["contents"],
        )

        self.assertEqual(
            keys["digital_booklet"]["maximum_pages"],
            20,
        )
        self.assertEqual(
            keys["publication_images"]["quantity"],
            5,
        )
        self.assertEqual(
            keys["panel_reproductions"]["quantity"],
            3,
        )
        self.assertEqual(
            keys["panel_reproductions"]["maximum_size_mb"],
            10,
        )

        self.assertEqual(
            result["counts"]["physical_units"],
            3,
        )
        self.assertEqual(
            result["counts"]["digital_files"],
            10,
        )

    def test_does_not_promote_contents_to_deliverables(self) -> None:
        result = extract_submission_requirements(
            {"Termos de Referência.pdf": TERMS}
        )
        keys = {
            item["key"]
            for item in result["groups"]["design_work"]
        }

        self.assertNotIn("drawings", keys)
        self.assertNotIn("diagrams", keys)
        self.assertNotIn("three_dimensional_views", keys)
        self.assertNotIn("cost_estimate", keys)
        self.assertNotIn("schedule", keys)
        self.assertNotIn("video", keys)


if __name__ == "__main__":
    unittest.main()
