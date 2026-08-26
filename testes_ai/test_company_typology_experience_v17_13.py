from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import database
from app.company_ai.company_context import build_company_context
from app.company_ai.company_matching_v2 import analyze_company_match_v2
from app.company_ai.company_storage import criar_empresa
from app.company_ai.intelligence_builder import build_company_intelligence
from app.company_ai.models import (
    CompanyIdentity,
    CompanyPreferences,
    CompanyProfile,
    CompanyProjectExperience,
)
from app.company_ai.profile_storage import guardar_company_profile

ROOT = Path(__file__).resolve().parents[1]
COMPANY_EXPERIENCE_CARDS = ROOT / "frontend" / "src" / "components" / "company" / "CompanyExperienceCards.tsx"


class CompanyTypologyExperienceV1713Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_concursos.db"
        database.DB_PATH = self.db_path
        database.criar_base_dados()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _save_profile(self, profile: CompanyProfile) -> int:
        company = criar_empresa("user-v17-13", "Atelier Tipologias", None)
        guardar_company_profile(company["id"], profile)
        return int(company["id"])

    def test_multiple_projects_same_typology_are_counted_and_listed(self) -> None:
        company_id = self._save_profile(
            CompanyProfile(
                project_experience=[
                    CompanyProjectExperience(name="Escola A", typology="Educação"),
                    CompanyProjectExperience(name="Escola B", typology="Escola"),
                    CompanyProjectExperience(name="Centro Escolar C", typology="Ensino"),
                ],
            )
        )

        intelligence = build_company_intelligence(company_id)
        summary = {
            item["typology"]: item
            for item in intelligence["projects"]["summary"]
        }

        self.assertEqual(intelligence["projects"]["counts_by_typology"].get("educacao"), 3)
        self.assertEqual(summary["educacao"]["project_count"], 3)
        self.assertEqual(
            {project["name"] for project in summary["educacao"]["projects"]},
            {"Escola A", "Escola B", "Centro Escolar C"},
        )

    def test_multitypology_project_appears_in_each_real_category(self) -> None:
        company_id = self._save_profile(
            CompanyProfile(
                project_experience=[
                    CompanyProjectExperience(
                        name="Reabilitação de escola histórica",
                        typology="Educação; Reabilitação; Património",
                    )
                ],
            )
        )

        counts = build_company_intelligence(company_id)["projects"]["counts_by_typology"]

        self.assertEqual(counts.get("educacao"), 1)
        self.assertEqual(counts.get("reabilitacao"), 1)
        self.assertEqual(counts.get("patrimonio"), 1)

    def test_duplicate_project_is_not_counted_twice_in_same_typology(self) -> None:
        company_id = self._save_profile(
            CompanyProfile(
                project_experience=[
                    CompanyProjectExperience(name="Escola Central", typology="Educação", location="Lisboa"),
                    CompanyProjectExperience(name="Escola Central", typology="Escola", location="Lisboa"),
                    CompanyProjectExperience(name="Escola Central", typology="Educação", location="Lisboa"),
                ],
            )
        )

        counts = build_company_intelligence(company_id)["projects"]["counts_by_typology"]

        self.assertEqual(counts.get("educacao"), 1)

    def test_unknown_names_and_service_terms_do_not_become_typologies(self) -> None:
        company_id = self._save_profile(
            CompanyProfile(
                project_experience=[
                    CompanyProjectExperience(name="Alegria desk"),
                    CompanyProjectExperience(name="Anita"),
                    CompanyProjectExperience(name="BIM is More", typology="BIM"),
                    CompanyProjectExperience(name="Conference", typology="Conference"),
                    CompanyProjectExperience(name="Construction site visit"),
                ],
            )
        )

        intelligence = build_company_intelligence(company_id)
        counts = intelligence["projects"]["counts_by_typology"]
        summary_keys = {item["typology"] for item in intelligence["projects"]["summary"]}

        self.assertEqual(counts, {})
        self.assertEqual(summary_keys, set())
        self.assertNotIn("alegria desk", summary_keys)
        self.assertNotIn("anita", summary_keys)
        self.assertNotIn("bim", summary_keys)

    def test_company_context_uses_same_counts_as_intelligence(self) -> None:
        company_id = self._save_profile(
            CompanyProfile(
                project_experience=[
                    CompanyProjectExperience(name="Escola A", typology="Educação"),
                    CompanyProjectExperience(name="Escola B", typology="Educação"),
                    CompanyProjectExperience(name="Habitação A", typology="Habitação"),
                ],
            )
        )

        intelligence = build_company_intelligence(company_id)
        context = build_company_context(company_id)

        self.assertEqual(
            context.project_counts_by_typology,
            intelligence["projects"]["counts_by_typology"],
        )
        self.assertEqual(context.project_counts_by_typology.get("educacao"), 2)

    def test_matching_uses_project_summary_counts(self) -> None:
        company = CompanyProfile(
            identity=CompanyIdentity(location="Lisboa"),
            services=["Projeto de arquitetura"],
            competences=["BIM"],
            project_experience=[
                CompanyProjectExperience(name="Escola A", typology="Educação"),
                CompanyProjectExperience(name="Escola B", typology="Educação"),
                CompanyProjectExperience(name="Escola C", typology="Educação"),
            ],
            preferences=CompanyPreferences(typologies=["Educação"]),
        )
        competition = {
            "procedure_identity": {"title": "Escola nova", "location": "Lisboa"},
            "source_data": {"typologies": ["Educação"]},
            "award_strategy": ["experiência em escolas"],
        }

        result = analyze_company_match_v2(competition, company)

        self.assertTrue(result.matched_projects)
        self.assertEqual(result.experience_summary[0]["project_count"], 3)

    def test_frontend_typology_normalizer_is_strict_not_free_text(self) -> None:
        source = COMPANY_EXPERIENCE_CARDS.read_text(encoding="utf-8")
        normalizer = source.split("function normalizeTypology", 1)[1].split("function splitTypologyValues", 1)[0]

        self.assertIn('return "";', normalizer)
        self.assertNotIn("return cleanText(value);", normalizer)


class RealCompanyPayloadV1713Tests(unittest.TestCase):
    def test_real_company_28_does_not_expose_false_typology_labels(self) -> None:
        root = Path(__file__).resolve().parents[1]
        real_db = root / "concursos.db"
        if not real_db.exists():
            self.skipTest("concursos.db não existe neste checkout")

        original_db_path = database.DB_PATH
        database.DB_PATH = real_db
        try:
            intelligence = build_company_intelligence(28)
        finally:
            database.DB_PATH = original_db_path

        summary_keys = {item["typology"] for item in intelligence["projects"]["summary"]}
        counts = intelligence["projects"]["counts_by_typology"]
        forbidden = {
            "1",
            "alegria desk",
            "anita",
            "antónio",
            "arquitetura",
            "bim",
            "bim is more",
            "cenografia",
            "community",
            "conference",
            "construction site visit",
            "espinho",
            "family",
        }

        self.assertTrue(summary_keys)
        self.assertTrue(forbidden.isdisjoint(summary_keys))
        self.assertTrue(forbidden.isdisjoint(counts.keys()))
        self.assertGreaterEqual(counts.get("educacao", 0), 1)


if __name__ == "__main__":
    unittest.main()
