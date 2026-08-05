from __future__ import annotations

import unittest

from app.analise.design_competition_extractor import (
    apply_design_competition_extraction,
)
from app.architecture_intelligence.schemas import (
    ConsolidatedCompetitionData,
)


def empty_consolidated() -> ConsolidatedCompetitionData:
    return ConsolidatedCompetitionData.model_validate(
        {
            "schema_version": "1.0",
            "document_quality": "partial",
            "quality_report": {},
            "document_index": [],
            "information_model": [],
            "knowledge_intents": {},
            "evidences": [],
            "sources": [],
            "warnings": [],
        }
    )


class DesignCompetitionExtractorTests(unittest.TestCase):
    def test_extracts_complete_design_competition_model(self) -> None:
        textos = {
            "Anuncio.pdf": (
                "Valor do preço base do procedimento: "
                "26.000,00 EUR."
            ),
            "Termos.pdf": (
                "Ao concorrente em primeiro lugar é atribuído "
                "um prémio de 10.000,00 EUR. Ao concorrente em "
                "segundo lugar é atribuído um prémio de "
                "8.000,00 EUR. Ao concorrente em terceiro lugar "
                "é atribuído um prémio de 8.000,00 EUR. "
                "O montante global dos prémios é 26.000,00 EUR. "
                "A proposta contém três painéis A1 em formato "
                "físico, memória descritiva, ficheiros PDF e JPG "
                "e é submetida anonimamente na plataforma "
                "eletrónica acinGov."
            ),
            "Caderno.pdf": (
                "O preço base da empreitada estima-se em "
                "24 439 134 €. Cláusula 30.ª - Preço contratual. "
                "Pela aquisição dos serviços objeto do contrato, "
                "a entidade pagará ao prestador o montante de "
                "1 221 957.00 €. Fase 1 elaboração do Estudo "
                "Prévio. Fase 2 elaboração do Anteprojeto. "
                "Fase 3 elaboração e entrega do Projeto Geral de "
                "Execução. Fase 5 Assistência Técnica e elaboração "
                "das telas finais. Inclui mapa de medições e mapa "
                "de quantidades. Projeto de Arquitetura, Estruturas, "
                "AVAC e instalações elétricas."
            ),
            "Programa.pdf": (
                "Considerações gerais sobre a intervenção. "
                "A intervenção consiste na requalificação da escola, "
                "criando melhores condições de conforto e "
                "funcionalidade nos espaços interiores e exteriores. "
                "A solução deve assegurar articulação funcional, "
                "arquitetura ecológica e sustentável e preservar a "
                "envolvente verde. Para que possam ser atingidos os "
                "objetivos, a intervenção está limitada ao perímetro "
                "da escola e deve considerar vulnerabilidade sísmica. "
                "Biblioteca, laboratórios, salas de aula, refeitório "
                "e ginásio. Área total 12 500 m²."
            ),
        }
        ficha = {}
        result = apply_design_competition_extraction(
            ficha,
            empty_consolidated(),
            textos,
        )
        values = {
            item.field_name: str(item.value)
            for item in result.information_model
        }

        expected = {
            "procedure_value",
            "estimated_construction_cost",
            "design_services_value",
            "competition_prize_first",
            "competition_prize_second",
            "competition_prize_third",
            "competition_prize_total",
            "submission_panel_quantity",
            "submission_panel_format",
            "descriptive_memory",
            "digital_files",
            "anonymity_requirement",
            "submission_platform",
            "execution_project",
            "technical_assistance",
            "final_drawings",
            "measurements",
            "quantity_schedule",
            "specialties",
            "program_summary",
            "main_spaces",
            "functional_requirements",
            "constraints",
        }
        missing = expected.difference(values)
        self.assertFalse(
            missing,
            f"Campos em falta: {sorted(missing)}; "
            f"extraídos: {sorted(values)}",
        )
        self.assertEqual(
            values["submission_panel_quantity"],
            "3",
        )
        self.assertIn(
            "24 439 134",
            values["estimated_construction_cost"],
        )
        self.assertIn(
            "program_summary",
            values,
        )
        self.assertIn(
            "execution_project",
            values,
        )
        self.assertIn(
            "1 221 957,00",
            values["design_services_value"],
        )
        self.assertTrue(
            all(
                item.source_document_id
                for item in result.information_model
            )
        )
        self.assertIn(
            "design_competition_extraction",
            ficha,
        )
        self.assertIn("functional_program", ficha)
        self.assertEqual(
            ficha["functional_program"]["total_area"],
            "12 500 m²",
        )
        self.assertEqual(
            ficha["functional_program"]["area_total"]["value"],
            "12 500 m²",
        )
        self.assertEqual(
            ficha["functional_program"]["area_total"]["kind"],
            "global_area",
        )

    def test_does_not_invent_missing_honorarios(self) -> None:
        ficha = {}
        result = apply_design_competition_extraction(
            ficha,
            empty_consolidated(),
            {
                "Documento.pdf": (
                    "O custo estimado da obra é "
                    "24 439 134 €. Não existe nesta página "
                    "um valor dos serviços de projeto."
                )
            },
        )
        fields = {
            item.field_name
            for item in result.information_model
        }
        self.assertNotIn(
            "design_services_value",
            fields,
        )

    def test_prioritizes_explicit_global_areas_over_generic_area_candidates(self) -> None:
        ficha = {}
        result = apply_design_competition_extraction(
            ficha,
            empty_consolidated(),
            {
                "Programa.pdf": (
                    "Área 1: 999 m². "
                    "Área útil 8 500 m². "
                    "Área bruta 10 200 m². "
                    "Área de intervenção 11 300 m². "
                    "Área total 12 500 m². "
                    "Biblioteca, laboratórios e salas de aula."
                )
            },
        )
        program = ficha["functional_program"]

        self.assertEqual(program["area_total"]["value"], "12 500 m²")
        self.assertEqual(program["area_bruta"]["value"], "10 200 m²")
        self.assertEqual(program["area_intervencao"]["value"], "11 300 m²")
        self.assertEqual(program["area_util"]["value"], "8 500 m²")
        self.assertTrue(program["areas"])
        self.assertEqual(program["areas"][0]["kind"], "global_area")
        self.assertNotEqual(program["areas"][0]["label"], "Área 1")


    def test_rejects_room_subtotal_as_global_area(self) -> None:
        ficha = {}
        apply_design_competition_extraction(
            ficha,
            empty_consolidated(),
            {
                "Programa.pdf": (
                    "QUADRO DE ÁREAS\n"
                    "SALA DE AULA 2 x 60,60 m²\n"
                    "LABORATÓRIO 80 m²\n"
                    "Área total de construção: 8 152 m²\n"
                )
            },
        )
        program = ficha["functional_program"]
        self.assertEqual(program["area_total"]["value"], "8 152 m²")
        self.assertNotEqual(program["area_total"]["value"], "60,60 m²")
        labels = {item["label"] for item in program["areas"]}
        self.assertIn("SALA DE AULA", labels)
        self.assertNotIn("m 2", labels)

    def test_leaves_global_area_unconfirmed_without_explicit_label(self) -> None:
        ficha = {}
        apply_design_competition_extraction(
            ficha,
            empty_consolidated(),
            {
                "Programa.pdf": (
                    "SALA DE AULA 2 x 60,60 m²\n"
                    "SALA DE CIÊNCIAS 80 m²\n"
                )
            },
        )
        program = ficha["functional_program"]
        self.assertEqual(program["area_total"], {})
        self.assertEqual(program["total_area"], "")


if __name__ == "__main__":
    unittest.main()
