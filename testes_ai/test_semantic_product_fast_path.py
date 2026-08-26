from __future__ import annotations

import unittest

from app.analise.semantic_product_bridge import (
    _build_fast_source_consolidated,
    _source_evidence_candidates,
)
from app.architecture_intelligence.semantic_enrichment import (
    TOPICS,
    select_topic_evidences,
)


class SemanticProductFastPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.textos = {
            "419420077.pdf": (
                "Preço base do procedimento: 26.000,00 EUR."
            ),
            "Termos_de_Referencia.pdf": (
                "O montante global dos prémios é de € 26.000,00.\n"
                "Artigo 13.º - Modo de apresentação dos painéis A1 "
                "em formato físico.\n"
                "A memória descritiva e os ficheiros JPG são "
                "submetidos na plataforma eletrónica."
            ),
            "Honorarios.pdf": (
                "O valor máximo dos serviços de projeto é de "
                "598.452,00 EUR, sem IVA. "
                "A remuneração do projetista corresponde ao preço "
                "contratual indicado nas peças."
            ),
            "CE_ES_Lumiar.pdf": (
                "Deve ser considerado um valor de obra que não "
                "deverá exceder € 24 439 134.\n"
                "Fase 3: Projeto de Execução.\n"
                "Fase 5: Assistência Técnica e elaboração das "
                "telas finais.\n"
                "Devem ser entregues o mapa de medições e o "
                "mapa de quantidades."
            ),
        }

    def test_builds_ranked_source_evidences_for_all_topics(self) -> None:
        consolidated = _build_fast_source_consolidated(
            self.textos
        )
        evidences = [
            item.model_dump(mode="json")
            for item in consolidated.evidences
        ]

        selected = {
            topic.topic_id: select_topic_evidences(
                evidences,
                topic,
            )
            for topic in TOPICS
        }

        self.assertTrue(selected["financial_core"])
        self.assertTrue(selected["submission_panels"])
        self.assertTrue(selected["contract_deliverables"])

    def test_candidates_are_compact_and_traceable(self) -> None:
        evidences = _source_evidence_candidates(self.textos)
        self.assertGreaterEqual(len(evidences), 3)
        self.assertTrue(
            all(len(item["excerpt"]) <= 850 for item in evidences)
        )
        self.assertTrue(
            all(item["filename"] for item in evidences)
        )
        self.assertTrue(
            all(item["source_document_id"] for item in evidences)
        )

    def test_ignores_generated_json_files(self) -> None:
        evidences = _source_evidence_candidates(
            {
                "ficha.json": "painéis A1 projeto de execução",
                "analise.json": "assistência técnica",
            }
        )
        self.assertEqual(evidences, [])


if __name__ == "__main__":
    unittest.main()
