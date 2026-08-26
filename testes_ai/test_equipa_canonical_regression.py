from __future__ import annotations

import json
from pathlib import Path
import unittest

from app.analise.canonical_analysis import build_canonical_analysis
from app.analise.legacy_procedure_recovery import recover_procedure_from_legacy
from app.analise.universal_document_sections import extract_universal_document_sections


class TeamCanonicalRegressionTests(unittest.TestCase):
    def test_cross_reference_inherits_proposal_phase_and_annex_roles(self):
        textos = {
            "Programa do Concurso.pdf": """
PROGRAMA DO CONCURSO
8. DOCUMENTOS QUE INSTRUEM A PROPOSTA
E) Documento com a identificação da equipa técnica a apresentar com a proposta,
conforme modelo constante do ANEXO X.
ANEXO X
Ficha de identificação da equipa técnica
Coordenador de projeto
Autor do Projeto de Arquitetura
Autor do Projeto de Estruturas
"""
        }

        extracted = extract_universal_document_sections(textos)
        roles = extracted["technical_team"]

        self.assertEqual(
            {item["role"] for item in roles},
            {
                "Coordenador de projeto",
                "Autor do Projeto de Arquitetura",
                "Autor do Projeto de Estruturas",
            },
        )
        self.assertTrue(all(item["required_at_submission"] for item in roles))
        self.assertTrue(all(item["stage"] == "pre_award" for item in roles))
        self.assertTrue(all(item["phase"] == "competition" for item in roles))
        self.assertTrue(all(item["profile_dependent"] for item in roles))
        self.assertTrue(all(item["cross_reference"]["kind"] == "annex" for item in roles))

        canonical = build_canonical_analysis(ficha={}, procedure=extracted)
        team_requirements = [
            item
            for item in canonical["requirements"]
            if item.get("nature") == "team"
            and item.get("required_at_submission") is True
        ]
        self.assertEqual(len(team_requirements), 3)
        self.assertEqual(len(canonical["questions"]), 3)
        self.assertTrue(all(item["question"]["type"] == "yes_no" for item in team_requirements))

    def test_post_award_team_does_not_create_pre_competition_question(self):
        procedure = {
            "family": "design_build",
            "technical_team": [
                {
                    "role": "Coordenador de obra",
                    "title": "Coordenador de obra",
                    "phase": "habilitation",
                    "stage": "post_award",
                    "nature": "habilitation",
                    "source_heading": "Habilitação do adjudicatário",
                    "source_document": "Programa do Concurso.pdf",
                    "evidence_excerpt": "O adjudicatário apresenta a equipa após adjudicação.",
                }
            ],
        }

        canonical = build_canonical_analysis(ficha={}, procedure=procedure)

        self.assertFalse(any(item.get("nature") == "team" for item in canonical["requirements"]))
        self.assertEqual(canonical["questions"], [])

    def test_multiple_roles_do_not_mean_multiple_people(self):
        procedure = {
            "technical_team": [
                {
                    "role": "Coordenador de projeto",
                    "required_at_submission": True,
                    "source_heading": "Ficha de identificação da equipa",
                    "source_document": "Programa.pdf",
                },
                {
                    "role": "Autor do Projeto de Arquitetura",
                    "required_at_submission": True,
                    "source_heading": "Ficha de identificação da equipa",
                    "source_document": "Programa.pdf",
                },
            ]
        }
        canonical = build_canonical_analysis(ficha={}, procedure=procedure)
        roles = [item for item in canonical["requirements"] if item.get("nature") == "team"]
        self.assertEqual(len(roles), 2)
        self.assertTrue(all(item["profile_target"]["scope"] == "person" for item in roles))
        self.assertEqual(len({item["profile_target"]["reuse_key"] for item in roles}), 2)
        self.assertNotIn("2 pessoas", " ".join(item["required"]["text"] for item in roles))

    def test_regression_fixture_446_has_team_questions_without_post_award_noise(self):
        fixture = Path("analise_documentos/446/jobs/100/ficha.json")
        if not fixture.exists():
            self.skipTest("fixture local do caso 446 não está disponível")
        ficha = json.loads(fixture.read_text(encoding="utf-8"))
        procedure = ficha.get("procedure_analysis") or {}
        recovered, meta = recover_procedure_from_legacy(
            ficha,
            base_procedure=procedure,
        )
        self.assertIsNotNone(recovered)
        self.assertEqual(meta["mode"], "existing_procedure_analysis")

        canonical = build_canonical_analysis(
            ficha=ficha,
            procedure=recovered or procedure,
            concurso={"id": 446},
        )
        team = [
            item
            for item in canonical["requirements"]
            if item.get("nature") == "team"
            and item.get("required_at_submission") is True
        ]
        self.assertGreaterEqual(len(team), 3)
        self.assertTrue(canonical["questions"])
        self.assertFalse(
            any(
                any(marker in str(item.get("label", "")).lower() for marker in ("audiência", "relatório final", "caução"))
                for item in canonical["requirements"]
            )
        )

    def test_vale_preserves_existing_profile_requirements(self):
        fixture = Path("analise_documentos/445/ficha.json")
        if not fixture.exists():
            self.skipTest("fixture local do Vale não está disponível")
        ficha = json.loads(fixture.read_text(encoding="utf-8"))
        procedure = ficha.get("procedure_analysis") or {}
        canonical = build_canonical_analysis(ficha=ficha, procedure=procedure, concurso={"id": 445})
        labels = " ".join(str(item.get("label", "")).lower() for item in canonical["requirements"])
        self.assertGreater(len(canonical["requirements"]), 0)
        self.assertIn("projet", labels)

    def test_lumiar_does_not_invent_team_requirement(self):
        fixture = Path("analise_documentos/420959/ficha.json")
        if not fixture.exists():
            self.skipTest("fixture local do Lumiar não está disponível")
        ficha = json.loads(fixture.read_text(encoding="utf-8"))
        procedure = ficha.get("procedure_analysis") or {}
        canonical = build_canonical_analysis(ficha=ficha, procedure=procedure, concurso={"id": 420959})
        self.assertFalse(any(item.get("nature") == "team" for item in canonical["requirements"]))


if __name__ == "__main__":
    unittest.main()