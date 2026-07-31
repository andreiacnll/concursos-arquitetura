from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace

from app import database
from app.company_ai.company_storage import criar_empresa
from app.company_ai.compatibility_score import calculate_compatibility_score
from app.company_ai.company_extractor import CompanyExtractionResult, ExtractedFact
from app.company_ai.profile_builder import apply_extraction_to_profile
from app.company_ai.website_crawler import CrawledPage, WebsiteCrawlResult, crawl_website
from app.company_ai.website_ingestion import ingest_company_website
from app.company_ai.website_normalizer import normalize_website_content
from app.company_ai.interview_storage import (
    create_interview_session,
    get_active_interview_session,
    get_question_answer,
    get_question_context,
    get_session_questions,
    save_answer,
    save_question,
)
from app.company_ai.knowledge_storage import save_knowledge_fact
from app.company_ai.knowledge_validation import generate_validation_questions
from app.company_ai.models import CompanyProfile, CompanyIdentity
from app.company_ai.profile_storage import guardar_company_profile
from app.company_ai.question_engine import generate_questions
from app.company_ai.source_management import delete_company_source
from app.company_ai.models import (
    CompanyMemory,
    CompanyPreferences,
    CompanyProjectExperience,
)


class CompanyAiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_concursos.db"
        database.DB_PATH = self.db_path
        database.criar_base_dados()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()


class QuestionEngineTests(CompanyAiTestCase):
    def test_generates_structured_discovery_and_validation_questions(self) -> None:
        company = criar_empresa("user-1", "Atelier Teste", "https://example.com")
        profile = CompanyProfile(
            company_id=company["id"],
            identity=CompanyIdentity(
                company_name="Atelier Teste",
                website="https://example.com",
            ),
        )
        guardar_company_profile(company["id"], profile)

        fact = save_knowledge_fact(
            company["id"],
            "company.competences",
            ["BIM"],
            source="website:https://example.com",
            source_type="website",
            confidence=0.62,
            status="unknown",
        )

        discovery_questions = generate_questions(
            [
                "company.services",
                "team.competences",
                "projects.items",
            ],
            profile,
            [fact],
        )
        validation_questions = generate_validation_questions([fact])

        self.assertEqual(discovery_questions[0].type, "multi_choice")
        self.assertEqual(discovery_questions[1].type, "multi_choice")
        self.assertEqual(discovery_questions[2].type, "free_text")
        self.assertEqual(validation_questions[0].type, "boolean_confirmation")
        self.assertEqual(validation_questions[0].source, "Website")
        self.assertIn("BIM", validation_questions[0].evidence)


class InterviewStorageTests(CompanyAiTestCase):
    def test_persists_session_question_answer_and_metadata(self) -> None:
        company = criar_empresa("user-2", "Empresa Sessão", None)
        session = create_interview_session(company["id"])

        question = save_question(
            session["id"],
            SimpleNamespace(
                field="company.services",
                question="Que serviços prestam atualmente?",
                type="multi_choice",
                priority="high",
                options=[
                    SimpleNamespace(
                        model_dump=lambda: {
                            "value": "arquitetura",
                            "label": "Arquitetura",
                        }
                    ),
                ],
                question_source="discovery",
                knowledge_fact_id=None,
                source="Website",
                evidence="Identificado em Website: arquitetura.",
                confidence=0.74,
                suggested_answer=["arquitetura"],
            ),
        )

        save_answer(question["id"], ["arquitetura"])

        active_session = get_active_interview_session(company["id"])
        questions = get_session_questions(session["id"])
        answer = get_question_answer(question["id"])
        context = get_question_context(question["id"])

        self.assertIsNotNone(active_session)
        self.assertEqual(active_session["id"], session["id"])
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["source"], "Website")
        self.assertEqual(questions[0]["evidence"], "Identificado em Website: arquitetura.")
        self.assertAlmostEqual(float(questions[0]["confidence"]), 0.74)
        self.assertEqual(questions[0]["suggested_answer"], ["arquitetura"])
        self.assertEqual(answer["answer"], ["arquitetura"])
        self.assertEqual(context["question_source"], "discovery")
        self.assertEqual(context["source"], "Website")


class WebsiteCrawlerTests(CompanyAiTestCase):
    def test_crawls_internal_links_and_collects_project_names(self) -> None:
        pages = {
            "https://cnll.pt/": (
                """
                <html>
                  <head><title>CNLL</title></head>
                  <body>
                    <h1>CNLL</h1>
                    <a href="/works/">Works</a>
                    <a href="/about/">About</a>
                    <a href="/portfolio-item/sophia-bridge/">Sophia Bridge</a>
                  </body>
                </html>
                """
            ),
            "https://cnll.pt/works": (
                """
                <html>
                  <head><title>Works</title></head>
                  <body>
                    <h1>Selected Works</h1>
                    <a href="/portfolio-item/new-bugesera-international-airport/">New Bugesera International Airport</a>
                    <p>Architecture Urbanism Landscape</p>
                  </body>
                </html>
                """
            ),
            "https://cnll.pt/about": (
                """
                <html>
                  <head><title>About</title></head>
                  <body><h1>About</h1><p>Architecture and consulting.</p></body>
                </html>
                """
            ),
            "https://cnll.pt/portfolio-item/sophia-bridge": (
                """
                <html>
                  <head><title>Sophia Bridge</title></head>
                  <body>
                    <h1>Sophia Bridge</h1>
                    <p>Urbanism and landscape design.</p>
                  </body>
                </html>
                """
            ),
            "https://cnll.pt/portfolio-item/new-bugesera-international-airport": (
                """
                <html>
                  <head><title>New Bugesera International Airport</title></head>
                  <body>
                    <h1>New Bugesera International Airport</h1>
                    <p>Architecture, BIM and engineering.</p>
                  </body>
                </html>
                """
            ),
        }

        def fake_fetch(url: str, timeout_seconds: int):
            html = pages[url]
            return url, html, []

        from unittest.mock import patch

        with patch("app.company_ai.website_crawler._fetch_html", side_effect=fake_fetch):
            result = crawl_website("https://cnll.pt/", max_pages=5, max_depth=2)

        self.assertGreaterEqual(result.pages_visited, 4)
        self.assertIn("Sophia Bridge", result.project_names)
        self.assertIn("New Bugesera International Airport", result.project_names)
        self.assertIn("Architecture", result.services_found)
        self.assertIn("Urbanism", result.services_found)

    def test_normalizer_removes_boilerplate_and_sections_content(self) -> None:
        crawl_result = WebsiteCrawlResult(
            start_url="https://cnll.pt/",
            final_url="https://cnll.pt/office/",
            pages_visited=2,
            pages=[
                CrawledPage(
                    url="https://cnll.pt/",
                    depth=0,
                    text=(
                        "works\nnews\noffice\nContact us\n"
                        "Sorry, no posts matched your criteria\n"
                        "CNLL is an architecture studio based in Porto.\n"
                        "Architecture Urbanism Landscape Consulting\n"
                    ),
                ),
                CrawledPage(
                    url="https://cnll.pt/office/",
                    depth=1,
                    text=(
                        "works\nnews\noffice\nMay we help you?\n"
                        "CNLL is an architecture studio based in Porto.\n"
                        "BIM Computational Design Research Innovation\n"
                    ),
                ),
            ],
            project_names=["Sophia Bridge", "GO", "> find more"],
        )

        normalized = normalize_website_content(crawl_result)

        self.assertNotIn("Sorry, no posts matched", normalized.combined_text)
        self.assertNotIn("May we help you", normalized.combined_text)
        self.assertNotIn("Contact us", normalized.combined_text)
        self.assertIn("IDENTIDADE", normalized.combined_text)
        self.assertIn("SERVICOS", normalized.combined_text)
        self.assertIn("Sophia Bridge", normalized.project_names)
        self.assertNotIn("GO", normalized.project_names)


class WebsiteIngestionTests(CompanyAiTestCase):
    def test_persists_project_names_and_returns_structured_summary(self) -> None:
        company = criar_empresa("user-3", "CNLL", "https://cnll.pt")
        crawl_result = WebsiteCrawlResult(
            start_url="https://cnll.pt/",
            final_url="https://cnll.pt/",
            pages_visited=3,
            pages=[
                CrawledPage(
                    url="https://cnll.pt/",
                    depth=0,
                    text="Architecture Urbanism Landscape",
                    project_names=["Sophia Bridge"],
                ),
            ],
            combined_text="Architecture Urbanism Landscape Sophia Bridge",
            project_names=["Sophia Bridge"],
            services_found=["Architecture", "Urbanism", "Landscape"],
            warnings=[],
        )

        from unittest.mock import patch

        with patch(
            "app.company_ai.website_ingestion.crawl_website",
            return_value=crawl_result,
        ):
            result = ingest_company_website(company["id"], "https://cnll.pt/")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["pages_visited"], 3)
        self.assertIn("Sophia Bridge", result["projects_found"])
        self.assertIn("Architecture", result["services_found"])
        self.assertGreaterEqual(result["facts_created"], 1)

        from app.company_ai.knowledge_storage import get_company_knowledge

        facts = get_company_knowledge(company["id"])
        self.assertTrue(
            any(
                fact.field == "projects.items"
                and "Sophia Bridge" in (fact.value or [])
                for fact in facts
            )
        )
        self.assertTrue(
            any(
                fact.field == "projects.items"
                and fact.section == "projects"
                and fact.url == "https://cnll.pt/"
                for fact in facts
            )
        )


class SourceManagementTests(CompanyAiTestCase):
    def test_delete_source_removes_only_values_from_that_source(self) -> None:
        company = criar_empresa("user-4", "Fonte Teste", "https://example.com")
        save_knowledge_fact(
            company["id"],
            "company.services",
            ["Architecture", "BIM"],
            source="website:https://example.com",
            source_type="website",
            confidence=0.8,
            status="confirmed",
        )
        save_knowledge_fact(
            company["id"],
            "company.services",
            ["Urbanism"],
            source="portfolio:portfolio.pdf",
            source_type="portfolio",
            confidence=0.8,
            status="confirmed",
        )
        profile = CompanyProfile(company_id=company["id"])
        profile.services = ["Architecture", "BIM", "Urbanism", "ManualSkill"]
        guardar_company_profile(company["id"], profile)

        deleted = delete_company_source(
            company["id"],
            "website",
            "website:https://example.com",
        )

        from app.company_ai.knowledge_storage import get_company_knowledge
        from app.company_ai.profile_storage import obter_company_profile

        facts = get_company_knowledge(company["id"])
        updated = obter_company_profile(company["id"])

        self.assertEqual(deleted, 1)
        self.assertFalse(any(fact.source_type == "website" for fact in facts))
        self.assertTrue(any(fact.source_type == "portfolio" for fact in facts))
        self.assertNotIn("Architecture", updated.services)
        self.assertNotIn("BIM", updated.services)
        self.assertIn("Urbanism", updated.services)
        self.assertIn("ManualSkill", updated.services)


class CompatibilityScoreTests(unittest.TestCase):
    def test_score_is_deterministic_and_does_not_invent_when_empty(self) -> None:
        empty = calculate_compatibility_score(matches=[], gaps=[], unknowns=[])
        self.assertIsNone(empty.score)
        self.assertEqual(empty.label, "Sem dados suficientes")

        result = calculate_compatibility_score(
            matches=[
                {"field": "competences"},
                {"field": "preferences.typologies"},
            ],
            gaps=[{"field": "location"}],
            unknowns=["company.project_experience.typologies"],
        )

        self.assertEqual(result.score, 90)
        self.assertEqual(result.label, "Muito elevada")
        self.assertEqual(len(result.breakdown), 4)


class ProfileBuilderSummaryTests(unittest.TestCase):
    def test_synthesizes_institutional_identity_summary(self) -> None:
        profile = CompanyProfile(
            company_id=1,
            identity=CompanyIdentity(
                company_name="CNLL",
                location="Porto",
            ),
            services=["arquitetura", "urbanismo", "paisagismo"],
            competences=["BIM", "coordenação técnica", "conceção integrada"],
            project_experience=[
                CompanyProjectExperience(typology="habitação"),
                CompanyProjectExperience(typology="equipamentos coletivos"),
            ],
            preferences=CompanyPreferences(
                typologies=["habitação", "espaço público"]
            ),
            strategy={
                "priority_areas": ["habitação", "equipamentos públicos"],
                "secondary_areas": [],
                "avoid_areas": [],
                "future_goals": ["soluções sustentáveis"],
            },
            ai_memory=CompanyMemory(),
        )

        extraction = CompanyExtractionResult(
            facts=[
                ExtractedFact(
                    field="company.identity",
                    value=(
                        "Menu Home About Works Sophia Bridge Contact us "
                        "Lorem ipsum dolor sit amet."
                    ),
                    source="website:https://cnll.pt",
                    status="confirmed",
                    confidence=0.9,
                )
            ]
        )

        updated = apply_extraction_to_profile(profile, extraction)
        summary = updated.identity.description

        self.assertGreaterEqual(len(summary.split()), 60)
        self.assertLessEqual(len(summary.split()), 120)
        self.assertNotIn("Sophia Bridge", summary)
        self.assertNotIn("Menu", summary)
        self.assertNotIn("Lorem ipsum", summary)
        self.assertIn("CNLL", summary)
        self.assertIn("Porto", summary)


if __name__ == "__main__":
    unittest.main()
