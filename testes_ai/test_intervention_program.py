from __future__ import annotations

import unittest

from app.analise.intervention_program import (
    apply_intervention_program,
    extract_intervention_program,
)


class InterventionProgramTests(unittest.TestCase):
    def test_landscape_project_uses_intervention_variant(self) -> None:
        ficha = {
            "identificacao": {
                "titulo": (
                    "Projeto de Arquitetura Paisagista e Especialidades "
                    "do Parque Urbano do Vale de Santo António"
                )
            }
        }
        textos = {
            "programa.pdf": (
                "O programa de intervenção estabelece a criação de um parque urbano "
                "com arquitetura paisagista e qualificação do espaço público. "
                "A modelação do terreno deve articular os movimentos de terras e os taludes. "
                "A mobilidade e os acessos integram circulação pedonal e ciclovia. "
                "O sistema verde prevê arborização e espécies vegetais adaptadas. "
                "A drenagem de águas pluviais inclui soluções de retenção e infiltração. "
                "As infraestruturas e especialidades incluem iluminação pública e saneamento. "
                "A equipa técnica inclui arquiteto paisagista e engenheiros. "
                "As fases do projeto incluem estudo prévio, anteprojeto e projeto de execução."
            ),
            "bim.pdf": "O adjudicatário deve entregar um modelo BIM num ambiente comum de dados CDE.",
        }
        result = apply_intervention_program(ficha=ficha, textos=textos)
        self.assertTrue(result["active"])
        self.assertEqual(ficha["analysis_variant"], "intervention_program")
        self.assertTrue(result["themes"]["drainage"]["confirmed"])
        self.assertTrue(result["themes"]["bim_requirements"]["confirmed"])
        self.assertTrue(result["themes"]["technical_team"]["confirmed"])

    def test_school_functional_program_is_not_relabelled(self) -> None:
        ficha = {
            "identificacao": {
                "titulo": "Reabilitação da Escola Secundária do Lumiar"
            }
        }
        textos = {
            "programa.pdf": (
                "O programa funcional inclui salas de aula, laboratórios, "
                "biblioteca e espaços exteriores da escola secundária."
            )
        }
        result = extract_intervention_program(ficha=ficha, textos=textos)
        self.assertFalse(result["active"])

    def test_variant_is_generic_and_not_reference_dependent(self) -> None:
        ficha = {
            "identificacao": {
                "titulo": "Requalificação paisagística do Parque Municipal"
            }
        }
        textos = {
            "memoria.pdf": (
                "A intervenção de arquitetura paisagista define o sistema verde, "
                "a drenagem e os percursos de mobilidade do parque urbano."
            )
        }
        result = extract_intervention_program(ficha=ficha, textos=textos)
        self.assertTrue(result["active"])
        self.assertNotIn("SRU20260000323CPI", str(result))


if __name__ == "__main__":
    unittest.main()
