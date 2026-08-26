from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from contextlib import closing
from types import SimpleNamespace

from app import database
from app.database import (
    analise_concluida_por_concurso,
    criar_ou_obter_analise_job,
    guardar_analise,
)
from app.company_ai.company_storage import criar_empresa
from app.company_ai.compatibility_analysis import analyze_compatibility
from app.company_ai.compatibility_score import calculate_compatibility_score
from app.company_ai.company_context import build_company_context
from app.company_ai.competition_context import build_competition_context
from app.company_ai.company_extractor import CompanyExtractionResult, ExtractedFact
from app.company_ai.company_matching_v2 import analyze_company_match_v2
from app.company_ai.profile_builder import apply_extraction_to_profile
from app.company_ai.profile_updater import apply_answer_to_profile
from app.company_ai.intelligence_builder import build_company_intelligence
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
from app.company_ai.profile_storage import (
    guardar_company_profile,
    obter_company_profile,
)
from app.company_ai.question_engine import generate_questions
from app.company_ai.source_management import delete_company_source
from app.company_ai.models import (
    CompanyMemory,
    CompanyPreferences,
    CompanyProjectExperience,
)
from app.architecture_intelligence.schemas import ConsolidatedCompetitionData
from app.company_ai.recommendation_engine import generate_recommendation
from app.company_ai.recommendation_presenter import build_recommendation_card
from app.analise.worker import _enriquecer_ficha_com_empresa


class CompanyAiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_concursos.db"
        database.DB_PATH = self.db_path
        database.criar_base_dados()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()


def _ficha_concurso_saude_bim() -> dict:
    return {
        "identificacao": {
            "concurso_id": 42,
            "titulo": "Centro de Saude com requisitos BIM",
            "tipo_procedimento": "Concurso publico",
        },
        "programa": {
            "descricao": "Projeto para unidade de saude com coordenacao BIM.",
            "tipo": ["Saude"],
            "usos": ["Saude"],
            "requisitos": ["Modelo BIM federado"],
            "condicionantes": ["Prazo documental apertado"],
        },
        "programa_funcional": {
            "requisitos": ["Modelo BIM federado"],
            "condicionantes": ["Prazo documental apertado"],
        },
        "localizacao": {"municipio": "Lisboa"},
        "investimento": {"prazo_projeto": "30 dias"},
        "economia": {"valor_procedimento": "100 000 EUR"},
        "criterios": {"resumo": "Qualidade 70%; Preco 30%"},
        "entregaveis": {"principais": ["Projeto de arquitetura", "Modelo BIM"]},
        "especialidades": {"lista": ["Arquitetura", "BIM"]},
        "requisitos": {
            "obrigatorios": ["Modelo BIM federado"],
            "riscos_participacao": ["Documentos obrigatorios incompletos"],
        },
        "equipa": {"competencias": ["BIM"]},
        "estrategia": {},
        "decisao": {"score": 70, "classificacao": "Interessante"},
        "analise_ai": {"score": 70},
    }


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


class CompanyIntelligenceAggregationTests(CompanyAiTestCase):
    def test_project_counts_by_typology_deduplicate_repeated_projects(self) -> None:
        company = criar_empresa("user-agg", "Atelier Agregado", None)
        guardar_company_profile(
            company["id"],
            CompanyProfile(
                company_id=company["id"],
                project_experience=[
                    CompanyProjectExperience(
                        name="Escola Central",
                        typology="Escola Secundaria",
                        location="Lisboa",
                        skills_demonstrated=["BIM"],
                    ),
                    CompanyProjectExperience(
                        name="Escola do Lumiar",
                        typology="Educação",
                        location="Lisboa",
                        skills_demonstrated=["Coordenacao"],
                    ),
                    CompanyProjectExperience(
                        name="Escola Central",
                        typology="Escola Secundaria",
                        location="Lisboa",
                        skills_demonstrated=["BIM"],
                    ),
                    CompanyProjectExperience(
                        name="Moradia A",
                        typology="Habitação",
                        location="Porto",
                    ),
                ],
            ),
        )

        intelligence = build_company_intelligence(company["id"])
        counts = intelligence["projects"]["counts_by_typology"]
        summary = intelligence["projects"]["summary"]

        self.assertEqual(counts.get("educacao"), 2)
        self.assertEqual(counts.get("habitacao"), 1)
        educacao_summary = next(
            item for item in summary if item["typology"] == "educacao"
        )
        self.assertEqual(educacao_summary["project_count"], 2)
        self.assertEqual(len(educacao_summary["projects"]), 2)
        self.assertTrue(
            all(
                project.get("normalized_typology") == "Educacao"
                for project in educacao_summary["projects"]
            )
        )

    def test_project_counts_by_typology_infer_real_projects_and_ignore_placeholders(
        self,
    ) -> None:
        company = criar_empresa("user-agg-2", "Atelier Relevante", None)
        guardar_company_profile(
            company["id"],
            CompanyProfile(
                company_id=company["id"],
                project_experience=[
                    CompanyProjectExperience(
                        name="Educacao",
                        typology="Educacao",
                    ),
                    CompanyProjectExperience(
                        name="Vilela School",
                        typology="",
                        location="Espinho",
                    ),
                    CompanyProjectExperience(
                        name="Sobrosa School",
                        typology="Escola",
                    ),
                    CompanyProjectExperience(
                        name="Paramos House",
                        typology="",
                    ),
                    CompanyProjectExperience(
                        name="Espinho Church",
                        typology="",
                    ),
                    CompanyProjectExperience(
                        name="Back to top",
                        typology="",
                    ),
                    CompanyProjectExperience(
                        name="Paramos House",
                        typology="",
                    ),
                ],
            ),
        )

        intelligence = build_company_intelligence(company["id"])
        counts = intelligence["projects"]["counts_by_typology"]
        summary = intelligence["projects"]["summary"]

        self.assertEqual(counts.get("educacao"), 2)
        self.assertEqual(counts.get("habitacao"), 1)
        self.assertEqual(counts.get("cultura"), 1)

        educacao_summary = next(
            item for item in summary if item["typology"] == "educacao"
        )
        habitacao_summary = next(
            item for item in summary if item["typology"] == "habitacao"
        )
        cultura_summary = next(
            item for item in summary if item["typology"] == "cultura"
        )

        self.assertEqual(educacao_summary["project_count"], 2)
        self.assertEqual(habitacao_summary["project_count"], 1)
        self.assertEqual(cultura_summary["project_count"], 1)
        self.assertTrue(
            all(
                "back to top" not in (project.get("name") or "").casefold()
                for project in educacao_summary["projects"]
            )
        )


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


class StrategicCompatibilityExplanationTests(CompanyAiTestCase):
    def _education_competition(self, rich_documents: bool = True) -> dict:
        return {
            "identificacao": {
                "concurso_id": 710,
                "titulo": "Escola basica com modelo BIM",
                "tipo_procedimento": "Concurso publico",
            },
            "programa": {
                "descricao": (
                    "Projeto de arquitetura para equipamento de Educacao "
                    "com reabilitacao energetica e BIM."
                ),
                "tipo": ["Educacao"],
                "requisitos": ["BIM", "Eficiencia energetica"],
            },
            "localizacao": {"municipio": "Braga"},
            "economia": {"valor_procedimento": "250 000 EUR"},
            "entregaveis": {
                "principais": [
                    "Projeto de arquitetura",
                    "Modelo BIM",
                    "Mapa de quantidades",
                    "Plano de execucao",
                    "Pecas desenhadas",
                    "Memoria descritiva",
                ]
            },
            "especialidades": {"lista": ["Arquitetura", "BIM"]},
            "requisitos": {
                "obrigatorios": ["BIM", "Eficiencia energetica"],
            },
            "equipa": {"competencias": ["BIM", "Eficiencia energetica"]},
            "documentos": (
                {"avisos": []}
                if rich_documents
                else {"avisos": ["Apenas dados BASE disponiveis."]}
            ),
        }

    def test_strong_education_profile_gets_explained_score_and_card_summary(self) -> None:
        company = criar_empresa("user-edu", "Atelier Educacao", None)
        guardar_company_profile(
            company["id"],
            CompanyProfile(
                company_id=company["id"],
                identity=CompanyIdentity(location="Norte"),
                services=["Projeto de arquitetura"],
                competences=["BIM", "Eficiencia energetica"],
                project_experience=[
                    CompanyProjectExperience(
                        name=f"Escola {i}",
                        typology="Educacao",
                        location="Norte",
                        skills_demonstrated=["BIM"],
                    )
                    for i in range(26)
                ],
                preferences=CompanyPreferences(
                    typologies=["Educacao"],
                    locations=["Norte"],
                    project_scale=["media"],
                ),
            ),
        )
        save_knowledge_fact(
            company["id"],
            "company.competences",
            ["BIM"],
            source="portfolio",
            source_type="portfolio",
            confidence=0.9,
            status="confirmed",
        )

        competition = build_competition_context(
            self._education_competition(True)
        )
        compatibility = analyze_compatibility(
            build_company_context(company["id"]),
            competition,
        )
        recommendation = generate_recommendation(
            company["id"],
            competition.competition_id,
            compatibility,
        )
        card = build_recommendation_card(recommendation, competition, {})

        self.assertGreaterEqual(compatibility.score or 0, 75)
        self.assertIn(
            compatibility.confidence,
            {"Elevada", "Muito elevada"},
        )
        self.assertTrue(compatibility.positive_factors)
        self.assertTrue(compatibility.experience_summary)
        self.assertEqual(
            compatibility.experience_summary[0]["project_count"],
            26,
        )
        self.assertTrue(compatibility.requirements)
        self.assertTrue(
            any(item["status"] == "encontrado" for item in compatibility.requirements)
        )
        self.assertEqual(card.confidence_label, compatibility.confidence)
        self.assertLessEqual(len(card.strengths), 3)
        self.assertTrue(card.attention_points)

    def test_different_profiles_change_explanation_without_changing_competition(self) -> None:
        education_company = criar_empresa("user-edu-2", "Atelier Escolas", None)
        housing_company = criar_empresa("user-housing", "Atelier Habitacao", None)
        empty_company = criar_empresa("user-empty", "Atelier Novo", None)

        guardar_company_profile(
            education_company["id"],
            CompanyProfile(
                company_id=education_company["id"],
                competences=["BIM"],
                project_experience=[
                    CompanyProjectExperience(
                        name=f"Escola {i}",
                        typology="Educacao",
                        skills_demonstrated=["BIM"],
                    )
                    for i in range(18)
                ],
                preferences=CompanyPreferences(typologies=["Educacao"]),
            ),
        )
        guardar_company_profile(
            housing_company["id"],
            CompanyProfile(
                company_id=housing_company["id"],
                competences=["Habitacao"],
                project_experience=[
                    CompanyProjectExperience(
                        name=f"Habitacao {i}",
                        typology="Habitacao",
                    )
                    for i in range(20)
                ],
                preferences=CompanyPreferences(typologies=["Habitacao"]),
            ),
        )
        guardar_company_profile(empty_company["id"], CompanyProfile())

        competition_data = self._education_competition(False)
        competition = build_competition_context(competition_data)
        edu_fit = analyze_compatibility(
            build_company_context(education_company["id"]),
            competition,
        )
        housing_fit = analyze_compatibility(
            build_company_context(housing_company["id"]),
            competition,
        )
        empty_fit = analyze_compatibility(
            build_company_context(empty_company["id"]),
            competition,
        )

        self.assertEqual(
            build_competition_context(competition_data).model_dump(),
            competition.model_dump(),
        )
        self.assertNotEqual(edu_fit.score, housing_fit.score)
        self.assertNotEqual(
            edu_fit.score_explanation,
            housing_fit.score_explanation,
        )
        self.assertTrue(edu_fit.experience_summary)
        self.assertFalse(housing_fit.experience_summary)
        self.assertTrue(empty_fit.missing_information)
        self.assertTrue(
            all(
                item.get("status") != "encontrado"
                for item in empty_fit.requirements
            )
        )
        self.assertTrue(
            any(
                risk.get("name") == "Documentacao insuficiente"
                for risk in empty_fit.risks
            )
        )


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


class CompanyProfilePersistenceTests(CompanyAiTestCase):
    def test_profile_save_merges_without_erasing_existing_fields(self) -> None:
        company = criar_empresa("user-5", "Atelier Persistente", "https://example.com")
        original = CompanyProfile(
            company_id=company["id"],
            identity=CompanyIdentity(
                company_name="Atelier Persistente",
                description="Resumo manual aprovado.",
                location="Lisboa",
                website="https://example.com",
            ),
            services=["arquitetura"],
            competences=["BIM"],
            specializations=["patrimonio"],
            project_experience=[
                CompanyProjectExperience(
                    name="Museu Central",
                    typology="cultura",
                    location="Lisboa",
                )
            ],
            preferences=CompanyPreferences(
                typologies=["cultura"],
                procedures=["concurso publico"],
                locations=["Portugal"],
                project_scale=["media"],
            ),
            strategy={
                "priority_areas": ["cultura"],
                "secondary_areas": ["educacao"],
                "avoid_areas": ["industrial"],
                "future_goals": ["internacionalizacao"],
            },
            ai_memory=CompanyMemory(confirmed_facts=["facto manual"]),
        )
        guardar_company_profile(company["id"], original)

        incoming = CompanyProfile(
            company_id=company["id"],
            identity=CompanyIdentity(description="Resumo validado no onboarding."),
            services=["urbanismo", ""],
            competences=[],
            specializations=["BIM"],
            project_experience=[
                CompanyProjectExperience(
                    name="Escola Nova",
                    typology="educacao",
                )
            ],
            strategy={
                "priority_areas": ["habitacao"],
                "secondary_areas": [],
                "avoid_areas": [],
                "future_goals": [],
            },
        )

        saved = guardar_company_profile(company["id"], incoming)
        reloaded = obter_company_profile(company["id"])

        self.assertEqual(saved, reloaded)
        self.assertEqual(reloaded.identity.company_name, "Atelier Persistente")
        self.assertEqual(reloaded.identity.location, "Lisboa")
        self.assertEqual(reloaded.identity.description, "Resumo validado no onboarding.")
        self.assertEqual(reloaded.services, ["arquitetura", "urbanismo"])
        self.assertEqual(reloaded.competences, ["BIM"])
        self.assertEqual(reloaded.specializations, ["patrimonio", "BIM"])
        self.assertIn("cultura", reloaded.preferences.typologies)
        self.assertIn("habitacao", reloaded.strategy["priority_areas"])
        self.assertIn("industrial", reloaded.strategy["avoid_areas"])
        self.assertTrue(
            any(project.name == "Museu Central" for project in reloaded.project_experience)
        )
        self.assertTrue(
            any(project.name == "Escola Nova" for project in reloaded.project_experience)
        )

    def test_interview_answers_apply_projects_and_specializations(self) -> None:
        company = criar_empresa("user-6", "Atelier Entrevista", None)
        guardar_company_profile(company["id"], CompanyProfile(company_id=company["id"]))

        with_specializations = apply_answer_to_profile(
            company["id"],
            "team.specializations",
            ["reabilitacao", "BIM"],
        )
        guardar_company_profile(company["id"], with_specializations)

        with_projects = apply_answer_to_profile(
            company["id"],
            "projects.items",
            ["Casa Azul"],
        )
        guardar_company_profile(company["id"], with_projects)

        with_typologies = apply_answer_to_profile(
            company["id"],
            "projects.typologies",
            ["habitacao"],
        )
        saved = guardar_company_profile(company["id"], with_typologies)

        self.assertEqual(saved.specializations, ["reabilitacao", "BIM"])
        self.assertTrue(
            any(project.name == "Casa Azul" for project in saved.project_experience)
        )
        self.assertTrue(
            any(project.typology == "habitacao" for project in saved.project_experience)
        )


class IndividualAnalysisPersonalizationTests(CompanyAiTestCase):
    def test_same_competition_gets_different_company_fit(self) -> None:
        bim_company = criar_empresa("user-bim", "Atelier BIM Saude", None)
        generic_company = criar_empresa("user-generic", "Atelier Habitacao", None)

        guardar_company_profile(
            bim_company["id"],
            CompanyProfile(
                company_id=bim_company["id"],
                identity=CompanyIdentity(location="Lisboa"),
                services=["Projeto de arquitetura"],
                competences=["BIM"],
                specializations=["Saude", "BIM"],
                project_experience=[
                    CompanyProjectExperience(
                        name="Clinica Central",
                        typology="Saude",
                        location="Lisboa",
                        skills_demonstrated=["BIM"],
                    )
                ],
                preferences=CompanyPreferences(
                    typologies=["Saude"],
                    procedures=["Concurso publico"],
                ),
            ),
        )
        save_knowledge_fact(
            bim_company["id"],
            "team.competences",
            ["BIM"],
            source="portfolio",
            source_type="portfolio",
            confidence=0.9,
            status="confirmed",
        )

        guardar_company_profile(
            generic_company["id"],
            CompanyProfile(
                company_id=generic_company["id"],
                identity=CompanyIdentity(location="Porto"),
                services=["Projeto de arquitetura"],
                competences=["Habitacao"],
                specializations=["Habitacao"],
                project_experience=[
                    CompanyProjectExperience(
                        name="Moradia Norte",
                        typology="Habitacao",
                        location="Porto",
                    )
                ],
                preferences=CompanyPreferences(typologies=["Habitacao"]),
            ),
        )

        ficha_bim = _enriquecer_ficha_com_empresa(
            _ficha_concurso_saude_bim(),
            bim_company["id"],
        )
        ficha_generica = _enriquecer_ficha_com_empresa(
            _ficha_concurso_saude_bim(),
            generic_company["id"],
        )

        self.assertEqual(
            ficha_bim["analise_concurso"],
            ficha_generica["analise_concurso"],
        )
        self.assertIn(
            "BIM",
            ficha_bim["adequacao_empresa"]["competencias_relevantes"],
        )
        self.assertTrue(
            ficha_bim["adequacao_empresa"]["experiencia_semelhante_encontrada"]
        )
        self.assertFalse(
            ficha_generica["adequacao_empresa"]["experiencia_semelhante_encontrada"]
        )
        self.assertNotEqual(
            ficha_bim["adequacao_empresa"]["score_compatibilidade"],
            ficha_generica["adequacao_empresa"]["score_compatibilidade"],
        )

    def test_profile_change_changes_company_fit_not_competition_analysis(self) -> None:
        company = criar_empresa("user-change", "Atelier Evolutivo", None)
        guardar_company_profile(
            company["id"],
            CompanyProfile(
                company_id=company["id"],
                competences=["Habitacao"],
                preferences=CompanyPreferences(typologies=["Habitacao"]),
            ),
        )
        antes = _enriquecer_ficha_com_empresa(
            _ficha_concurso_saude_bim(),
            company["id"],
        )

        guardar_company_profile(
            company["id"],
            CompanyProfile(
                company_id=company["id"],
                competences=["BIM"],
                specializations=["Saude"],
                project_experience=[
                    CompanyProjectExperience(
                        name="Unidade Local de Saude",
                        typology="Saude",
                        skills_demonstrated=["BIM"],
                    )
                ],
            ),
        )
        depois = _enriquecer_ficha_com_empresa(
            _ficha_concurso_saude_bim(),
            company["id"],
        )

        self.assertEqual(antes["analise_concurso"], depois["analise_concurso"])
        self.assertNotEqual(
            antes["adequacao_empresa"]["score_compatibilidade"],
            depois["adequacao_empresa"]["score_compatibilidade"],
        )
        self.assertIn(
            "BIM",
            depois["adequacao_empresa"]["competencias_relevantes"],
        )


class CompanyMatchingV2Tests(CompanyAiTestCase):
    def _competition(self) -> ConsolidatedCompetitionData:
        return ConsolidatedCompetitionData(
            document_quality="complete",
            quality_report={
                "documents_official": 3,
                "documents_read": 3,
                "documents_ignored": 0,
                "conflicts": 0,
                "fields_filled": 8,
                "fields_empty": 0,
                "confidence_global": 0.88,
            },
            procedure_identity={
                "object": {
                    "field": "object",
                    "kind": "scalar",
                    "value": "Centro Escolar de nova geracao",
                    "normalized_value": "Centro Escolar de nova geracao",
                    "confidence": 0.92,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [],
                    "source_readers": ["procedure_reader"],
                    "document_ids": ["doc-1"],
                },
                "location": {
                    "field": "location",
                    "kind": "scalar",
                    "value": "Lisboa",
                    "normalized_value": "Lisboa",
                    "confidence": 0.9,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [],
                    "source_readers": ["procedure_reader"],
                    "document_ids": ["doc-1"],
                },
                "submission_deadline": {
                    "field": "submission_deadline",
                    "kind": "scalar",
                    "value": "2026-10-15",
                    "normalized_value": "2026-10-15",
                    "confidence": 0.9,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [],
                    "source_readers": ["procedure_reader"],
                    "document_ids": ["doc-1"],
                },
            },
            prices={
                "design_services_value": {
                    "field": "design_services_value",
                    "kind": "scalar",
                    "value": 1221957.0,
                    "normalized_value": 1221957.0,
                    "confidence": 0.9,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [],
                    "source_readers": ["financial_reader"],
                    "document_ids": ["doc-2"],
                },
                "estimated_construction_cost": {
                    "field": "estimated_construction_cost",
                    "kind": "scalar",
                    "value": 24439134.0,
                    "normalized_value": 24439134.0,
                    "confidence": 0.9,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [],
                    "source_readers": ["financial_reader"],
                    "document_ids": ["doc-2"],
                },
            },
            award_strategy={
                "award_criterion": {
                    "field": "award_criterion",
                    "kind": "scalar",
                    "value": "Proposta economicamente mais vantajosa",
                    "normalized_value": "Proposta economicamente mais vantajosa",
                    "confidence": 0.9,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [],
                    "source_readers": ["award_reader"],
                    "document_ids": ["doc-3"],
                }
            },
            required_team=[
                {
                    "field": "coordinator",
                    "kind": "scalar",
                    "value": {"role": "arquiteto", "minimum_years": 5},
                    "normalized_value": {"role": "arquiteto", "minimum_years": 5},
                    "confidence": 0.9,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [],
                    "source_readers": ["team_reader"],
                    "document_ids": ["doc-4"],
                }
            ],
            phases_and_deliverables=[
                {
                    "field": "payments_by_phase",
                    "kind": "list",
                    "value": [{"phase": "Fase 1", "percentage": 25}],
                    "normalized_value": ["fase 1"],
                    "confidence": 0.8,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [],
                    "source_readers": ["financial_reader"],
                    "document_ids": ["doc-2"],
                }
            ],
            submission_checklist={
                "administrative": [],
                "technical": [],
                "financial": [],
                "team": [],
                "post_award": [],
            },
            drawing_rules=[],
            financial_conditions={},
            technical_constraints=[],
            exclusion_risks=[],
            document_alerts=[],
        )

    def test_conceptual_taxonomy_matches_school_family(self) -> None:
        company = CompanyProfile(
            company_id=1,
            identity=CompanyIdentity(location="Lisboa"),
            services=["Projeto de arquitetura", "BIM"],
            competences=["BIM", "Coordenacao"],
            specializations=["Educacao"],
            project_experience=[
                CompanyProjectExperience(
                    name=f"Escola {index}",
                    typology="Escola Secundaria",
                    location="Lisboa",
                    skills_demonstrated=["BIM"],
                )
                for index in range(20)
            ],
            preferences=CompanyPreferences(
                typologies=["Educacao"],
                locations=["Lisboa"],
                project_scale=["media"],
            ),
            strategy={
                "priority_areas": ["Educacao"],
                "secondary_areas": [],
                "avoid_areas": [],
                "future_goals": [],
            },
        )

        competition = self._competition()
        result = analyze_company_match_v2(competition, company)

        self.assertIsNotNone(result.compatibility_score)
        self.assertEqual(result.compatibility_score, result.score)
        self.assertGreaterEqual(result.compatibility_score or 0, 75)
        self.assertTrue(result.compatibility_breakdown)
        self.assertTrue(result.matched_projects)
        self.assertIn("Educacao", result.strategic_fit["competition_typologies"])
        self.assertIn("avancar", {"avancar", "avaliar", "nao prioritario", "dados insuficientes"})
        self.assertIn(result.recommendation["decision"], {"avancar", "avaliar"})
        self.assertIn("Experiencia", {item["name"] for item in result.compatibility_breakdown})
        self.assertTrue(result.score_explanation["breakdown"])
        self.assertTrue(result.evidence)
        self.assertTrue(result.strengths)
        self.assertTrue(result.matched_projects)

    def test_accented_school_typology_is_normalized_to_education(self) -> None:
        company = CompanyProfile(
            company_id=11,
            identity=CompanyIdentity(location="Lisboa"),
            services=["Projeto de arquitetura", "Coordenação"],
            competences=["BIM"],
            specializations=["Educação"],
            project_experience=[
                CompanyProjectExperience(
                    name=f"Escola Secundária {index}",
                    typology="Escola Secundária",
                    location="Lisboa",
                    skills_demonstrated=["BIM", "coordenação"],
                )
                for index in range(22)
            ],
            preferences=CompanyPreferences(
                typologies=["Educação"],
                locations=["Lisboa"],
            ),
            strategy={
                "priority_areas": ["Educação"],
                "secondary_areas": [],
                "avoid_areas": [],
                "future_goals": [],
            },
        )

        competition = self._competition()
        result = analyze_company_match_v2(competition, company)

        self.assertIsNotNone(result.compatibility_score)
        self.assertGreaterEqual(result.compatibility_score or 0, 80)
        self.assertTrue(result.matched_projects)
        self.assertIn("Educacao", {item.get("typology") for item in result.experience_summary})
        self.assertEqual(result.recommendation["decision"], "avancar")

    def test_profiles_change_the_fit_without_changing_the_conceptual_competition(self) -> None:
        education_company = CompanyProfile(
            company_id=2,
            identity=CompanyIdentity(location="Lisboa"),
            services=["Projeto de arquitetura", "BIM"],
            competences=["BIM"],
            specializations=["Educacao"],
            project_experience=[
                CompanyProjectExperience(
                    name=f"Escola {index}",
                    typology="Escola",
                    location="Lisboa",
                    skills_demonstrated=["BIM"],
                )
                for index in range(20)
            ],
            preferences=CompanyPreferences(
                typologies=["Educacao"],
                locations=["Lisboa"],
            ),
        )
        housing_company = CompanyProfile(
            company_id=3,
            identity=CompanyIdentity(location="Porto"),
            services=["Projeto de arquitetura"],
            competences=["Habitacao"],
            specializations=["Habitacao"],
            project_experience=[
                CompanyProjectExperience(
                    name=f"Habitacao {index}",
                    typology="Habitacao",
                    location="Porto",
                )
                for index in range(12)
            ],
            preferences=CompanyPreferences(typologies=["Habitacao"], locations=["Porto"]),
        )

        competition = self._competition()
        education_fit = analyze_company_match_v2(competition, education_company)
        housing_fit = analyze_company_match_v2(competition, housing_company)

        self.assertGreater(education_fit.compatibility_score or 0, housing_fit.compatibility_score or 0)
        self.assertNotEqual(education_fit.recommendation, housing_fit.recommendation)
        self.assertNotEqual(education_fit.strengths, housing_fit.strengths)
        self.assertTrue(housing_fit.missing_information)

    def test_saved_analysis_is_scoped_by_company_id(self) -> None:
        company_a = criar_empresa("user-a", "Atelier A", None)
        company_b = criar_empresa("user-b", "Atelier B", None)
        with closing(database.abrir_conexao()) as conexao:
            concurso_id = conexao.execute(
                """
                INSERT INTO concursos (titulo, entidade, link, data)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "Centro de Saude",
                    "Municipio",
                    "https://base.gov.pt?id=9001",
                    "2026-01-01",
                ),
            ).lastrowid
            conexao.commit()

        job_a, _ = criar_ou_obter_analise_job(
            "user-a",
            concurso_id,
            company_a["id"],
        )
        job_b, _ = criar_ou_obter_analise_job(
            "user-b",
            concurso_id,
            company_b["id"],
        )

        guardar_analise(
            concurso_id=concurso_id,
            nivel="AI",
            resumo="A",
            dados_json='{"empresa":"A"}',
            user_id="user-a",
            company_id=company_a["id"],
            job_id=job_a["id"],
            score=60,
        )
        guardar_analise(
            concurso_id=concurso_id,
            nivel="AI",
            resumo="B",
            dados_json='{"empresa":"B"}',
            user_id="user-b",
            company_id=company_b["id"],
            job_id=job_b["id"],
            score=80,
        )

        analise_a = analise_concluida_por_concurso(
            concurso_id,
            "user-a",
            company_a["id"],
        )
        analise_b = analise_concluida_por_concurso(
            concurso_id,
            "user-b",
            company_b["id"],
        )

        self.assertEqual(analise_a["user_id"], "user-a")
        self.assertEqual(analise_a["company_id"], company_a["id"])
        self.assertEqual(analise_b["user_id"], "user-b")
        self.assertEqual(analise_b["company_id"], company_b["id"])
        self.assertNotEqual(analise_a["score"], analise_b["score"])


if __name__ == "__main__":
    unittest.main()
