from __future__ import annotations

import unittest

from app.analise.canonical_analysis import build_canonical_analysis
from app.analise.legacy_procedure_recovery import (
    analysis_body,
    procedural_richness,
    recover_procedure_from_legacy,
)


class LegacyProcedureRecoveryV1742Tests(unittest.TestCase):
    def market_fixture(self):
        return {
            "criterios": {
                "criterio_adjudicacao": "Multifator",
                "resumo": (
                    "Preço 40% • FATOR 2: Valia Técnica da Equipa "
                    "de Projeto (60%)"
                ),
                "percentagens": [
                    {"criterio": "Qualidade", "percentagem": "60%"},
                    {"criterio": "Preco", "percentagem": "40%"},
                ],
            },
            "equipa": [
                {
                    "titulo": "Subfator 2.1 - Coordenador de Projeto (50%)",
                    "descricao": "",
                },
                {
                    "titulo": (
                        "Subfator 2.1 – Experiência Profissional "
                        "do COORDENADOR DE PROJETO"
                    ),
                    "descricao": (
                        "EM PROJETOS SIMILARES. Técnico que tenha assumido "
                        "a coordenação de 1 Projeto de Reabilitação ou "
                        "Construção de um Mercado Municipal Coberto. "
                        "Descritores Pontuação A 10 B 5 C 0."
                    ),
                },
                {
                    "titulo": (
                        "Subfator 2.2 - Autor do Projeto de Arquitetura (50%)"
                    ),
                    "descricao": "",
                },
                {
                    "titulo": (
                        "Subfator 2.2 – Experiência Profissional do Autor "
                        "de Projeto de ARQUITETURA"
                    ),
                    "descricao": (
                        "Arquiteto, autor ou co-autor, de 1 Projeto de "
                        "Reabilitação ou Construção de um Mercado Municipal "
                        "Coberto. Descritores Pontuação A 10 B 5 C 0."
                    ),
                },
            ],
        }

    def test_small_analise_block_is_not_mistaken_for_wrapper(self):
        root = {
            "analise": {"nivel": "alta", "motivos": ["x"]},
            "equipa": [{"titulo": "Subfator 2.1", "descricao": "abc"}],
        }
        self.assertIs(analysis_body(root), root)

    def test_rich_legacy_team_becomes_award_hierarchy(self):
        ficha = self.market_fixture()
        procedure, meta = recover_procedure_from_legacy(ficha)

        self.assertIsNotNone(procedure)
        award = procedure["award_criteria"]
        self.assertEqual(len(award["factors"]), 2)
        self.assertEqual(award["factors"][0]["weight_percent"], 60)
        self.assertEqual(award["factors"][1]["weight_percent"], 40)
        self.assertEqual(
            len(award["factors"][0]["subfactors"]),
            2,
        )
        self.assertEqual(meta["subfactor_count"], 2)

    def test_recovered_procedure_generates_material_questions(self):
        ficha = self.market_fixture()
        procedure, _ = recover_procedure_from_legacy(ficha)
        result = build_canonical_analysis(
            ficha={},
            procedure=procedure,
            concurso={"id": 389},
        )

        self.assertTrue(result["criteria"]["factors"])
        self.assertTrue(result["requirements"])
        self.assertTrue(result["questions"])

        codes = {
            question.get("subfactor_code")
            for question in result["questions"]
        }
        self.assertIn("2.1", codes)
        self.assertIn("2.2", codes)

    def test_empty_announcement_does_not_invent_questions(self):
        ficha = {
            "criterios": {
                "criterio_adjudicacao": "Nao identificado",
                "percentagens": [
                    {"criterio": "Qualidade", "percentagem": None},
                    {"criterio": "Preco", "percentagem": None},
                ],
            },
            "equipa": [],
        }
        procedure, meta = recover_procedure_from_legacy(ficha)
        self.assertIsNone(procedure)
        self.assertEqual(meta["mode"], "no_legacy_team")

    def test_richness_prefers_real_team_descriptors(self):
        poor = {"equipa": [], "criterios": {"resumo": "Preço 100%"}}
        rich = self.market_fixture()
        self.assertGreater(
            procedural_richness(rich),
            procedural_richness(poor),
        )


if __name__ == "__main__":
    unittest.main()
