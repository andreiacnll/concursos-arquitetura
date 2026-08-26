from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest
import zipfile
from unittest.mock import patch

from app.architecture_intelligence.consolidator import (
    Consolidator,
    consolidate_reader_results,
)
from app.architecture_intelligence.llm_orchestrator import (
    LLMOrchestrator,
    orchestrate_competition,
)
from app.architecture_intelligence.document_classifier import (
    classify_document,
)
from app.architecture_intelligence.schemas import (
    ClassifiedDocument,
    ConsolidatedCompetitionData,
    DocumentType,
    Evidence,
    EvidenceStatus,
    ExtractedField,
    SourceDocument,
    ReaderResult,
)
from app.architecture_intelligence.section_extractor import (
    detect_topics,
    extract_sections,
)
from app.architecture_intelligence.readers import (
    AwardReader,
    DeliverablesReader,
    FinancialReader,
    ProcedureReader,
    RisksReader,
    SubmissionReader,
    TeamReader,
)
from app.architecture_intelligence.pipeline import (
    run_architecture_intelligence_experiment,
)
from app.company_ai.models import (
    CompanyIdentity,
    CompanyPreferences,
    CompanyProfile,
    CompanyProjectExperience,
)


class ArchitectureIntelligenceTests(unittest.TestCase):
    def test_classifies_caderno_by_filename(self) -> None:
        source = SourceDocument(
            document_id="doc-1",
            filename="CE_ES_Lumiar.pdf",
            origin="acingov",
            source_role="official_document",
            text="",
        )

        result = classify_document(source)

        self.assertEqual(
            result.document_type,
            DocumentType.SPECIFICATIONS,
        )

    def test_classifies_programa_by_content(self) -> None:
        source = SourceDocument(
            document_id="doc-2",
            filename="documento_01.pdf",
            origin="acingov",
            source_role="official_document",
            text=(
                "Programa do procedimento. "
                "Documentos que constituem a proposta."
            ),
        )

        result = classify_document(source)

        self.assertEqual(
            result.document_type,
            DocumentType.PROCEDURE_PROGRAM,
        )

    def test_unknown_document(self) -> None:
        source = SourceDocument(
            document_id="doc-3",
            filename="anexo_generico.pdf",
            origin="acingov",
            source_role="official_document",
            text="Conteúdo sem indicadores suficientes.",
        )

        result = classify_document(source)

        self.assertEqual(
            result.document_type,
            DocumentType.UNKNOWN,
        )

    def test_detects_multiple_topics(self) -> None:
        topics = detect_topics(
            "A equipa técnica deve incluir um coordenador. "
            "O pagamento da Fase 1 corresponde a 25%."
        )

        self.assertIn("team", topics)
        self.assertIn("financial", topics)

    def test_extracts_sections_from_articles(self) -> None:
        source = SourceDocument(
            document_id="doc-4",
            filename="Programa_Procedimento.pdf",
            origin="acingov",
            source_role="official_document",
            text=(
                "ARTIGO 1.º\n"
                "Objeto do procedimento e entidade adjudicante.\n\n"
                "ARTIGO 10.º\n"
                "Documentos que constituem a proposta e assinatura digital.\n\n"
                "ARTIGO 17.º\n"
                "Critério de adjudicação, fatores e ponderação."
            ),
        )

        classified = classify_document(source)
        sections = extract_sections(classified)

        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[0].article, "ARTIGO 1.º")
        self.assertIn("procedure_identity", sections[0].topics)
        self.assertIn("submission", sections[1].topics)
        self.assertIn("award_criteria", sections[2].topics)

    def test_fallback_creates_single_section(self) -> None:
        source = SourceDocument(
            document_id="doc-5",
            filename="anexo.pdf",
            origin="acingov",
            source_role="official_document",
            text=(
                "A equipa técnica deve incluir arquitetura, "
                "estruturas e instalações elétricas."
            ),
        )

        classified = classify_document(source)
        sections = extract_sections(classified)

        self.assertEqual(len(sections), 1)
        self.assertIn("team", sections[0].topics)

    def test_procedure_reader_extracts_identity(self) -> None:
        source = SourceDocument(
            document_id="doc-6",
            filename="Programa_Procedimento.pdf",
            origin="acingov",
            source_role="official_document",
            text=(
                "ARTIGO 1.?\n"
                "Objeto: Requalifica??o da Escola Secund?ria do Lumiar.\n\n"
                "ARTIGO 2.?\n"
                "Entidade adjudicante: Munic?pio de Lisboa.\n\n"
                "ARTIGO 3.?\n"
                "Tipo de procedimento: Concurso de conce??o.\n"
                "C?digo CPV: 71240000-2."
            ),
        )

        classified = classify_document(source)
        sections = extract_sections(classified)

        result = ProcedureReader().extract(
            classified,
            sections,
        )

        self.assertEqual(
            result.fields["object"].value,
            "Requalifica??o da Escola Secund?ria do Lumiar",
        )
        self.assertEqual(
            result.fields["contracting_entity"].value,
            "Munic?pio de Lisboa",
        )
        self.assertEqual(
            result.fields["procedure_type"].value,
            "Concurso de conce??o",
        )
        self.assertEqual(
            result.fields["cpv"].normalized_value,
            "71240000-2",
        )
        self.assertGreater(result.confidence, 0)

    def test_procedure_reader_marks_missing_fields(self) -> None:
        source = SourceDocument(
            document_id="doc-7",
            filename="Programa_Procedimento.pdf",
            origin="acingov",
            source_role="official_document",
            text="ARTIGO 1.?\nObjeto: Reabilita??o de edif?cio p?blico.",
        )

        classified = classify_document(source)
        sections = extract_sections(classified)

        result = ProcedureReader().extract(
            classified,
            sections,
        )

        self.assertEqual(
            result.fields["contracting_entity"].status.value,
            "not_found",
        )


class AwardReaderTests(unittest.TestCase):
    def _build_document(self, text: str) -> tuple[ClassifiedDocument, list]:
        source = SourceDocument(
            document_id="award-doc",
            filename="Criterios_Avaliacao.pdf",
            origin="manual",
            source_role="official_document",
            text=text,
        )
        classified = ClassifiedDocument(
            source=source,
            document_type=DocumentType.AWARD_CRITERIA,
            title=source.filename,
            confidence=1.0,
            reasons=["test"],
        )
        return classified, extract_sections(classified)

    def test_extracts_factors_weights_and_tie_break_rules(self) -> None:
        classified, sections = self._build_document(
            "\n".join(
                [
                    "ARTIGO 17.º",
                    "Critério de adjudicação: proposta economicamente mais vantajosa.",
                    "Modelo de avaliação: Preço 30% e qualidade técnica 70%.",
                    "Fatores:",
                    "- Qualidade arquitetónica 40%",
                    "- Integração urbana 25%",
                    "- Sustentabilidade 20%",
                    "- Viabilidade económica 15%",
                    "Subfatores:",
                    "- Organização funcional 60%",
                    "- Expressão arquitetónica 40%",
                    "Pontuação máxima:",
                    "- 90 pontos na qualidade arquitetónica.",
                    "Desempate:",
                    "- Maior pontuação em qualidade arquitetónica.",
                    "Preço anormalmente baixo:",
                    "- Aplica-se o regime legal em vigor.",
                ]
            )
        )

        result = AwardReader().extract(classified, sections)

        self.assertEqual(result.fields["award_criterion"].status.value, "confirmed")
        self.assertEqual(result.fields["price_weight"].normalized_value, 30.0)
        self.assertEqual(result.fields["technical_weight"].normalized_value, 70.0)
        self.assertEqual(len(result.fields["factors"].value), 4)
        self.assertEqual(len(result.fields["subfactors"].value), 2)
        self.assertEqual(result.fields["maximum_score_requirements"].status.value, "confirmed")
        self.assertEqual(result.fields["tie_break_rules"].status.value, "confirmed")
        self.assertEqual(
            result.fields["abnormally_low_price_rule"].status.value,
            "confirmed",
        )
        self.assertFalse(result.warnings)

    def test_warns_when_percentages_do_not_sum_to_hundred(self) -> None:
        classified, sections = self._build_document(
            "\n".join(
                [
                    "ARTIGO 17.º",
                    "Critério de adjudicação: preço e qualidade técnica.",
                    "Fatores:",
                    "- Qualidade 60%",
                    "- Preço 20%",
                    "- Sustentabilidade 10%",
                ]
            )
        )

        result = AwardReader().extract(classified, sections)

        self.assertTrue(any("100%" in warning for warning in result.warnings))


class FinancialReaderTests(unittest.TestCase):
    def _build_document(self, text: str) -> tuple[ClassifiedDocument, list]:
        source = SourceDocument(
            document_id="financial-doc",
            filename="Condições_Financeiras.pdf",
            origin="manual",
            source_role="official_document",
            text=text,
        )
        classified = ClassifiedDocument(
            source=source,
            document_type=DocumentType.SPECIFICATIONS,
            title=source.filename,
            confidence=1.0,
            reasons=["test"],
        )
        return classified, extract_sections(classified)

    def test_separates_prizes_services_value_and_obra_cost(self) -> None:
        classified, sections = self._build_document(
            "\n".join(
                [
                    "ARTIGO 5.º",
                    "Prémios:",
                    "1.º prémio: 15 000 €",
                    "2.º prémio: 10 000 €",
                    "3.º prémio: 5 000 €",
                    "Preço dos serviços: 1 221 957 €",
                    "Valor do procedimento: 26 000 €",
                    "Custo estimado da obra: 24 439 134 €",
                    "Pagamentos por fase:",
                    "- Fase 1: 25%",
                    "- Fase 2: 35%",
                    "- Fase 3: 40%",
                    "Caução: 12 500 €",
                    "Seguro de responsabilidade civil obrigatório.",
                    "Penalização por atraso: 1% por dia.",
                    "Revisão de preços: não aplicável.",
                ]
            )
        )

        result = FinancialReader().extract(classified, sections)

        self.assertEqual(len(result.fields["competition_prizes"].value), 3)
        self.assertEqual(result.fields["procedure_value"].normalized_value, 26000.0)
        self.assertEqual(result.fields["design_services_value"].normalized_value, 1221957.0)
        self.assertEqual(
            result.fields["estimated_construction_cost"].normalized_value,
            24439134.0,
        )
        self.assertEqual(len(result.fields["payments_by_phase"].value), 3)
        self.assertEqual(result.fields["bond"].normalized_value, 12500.0)
        self.assertTrue(result.fields["insurance"].value)
        self.assertTrue(result.fields["penalties"].value)
        self.assertTrue(result.fields["price_revision"].value)
        self.assertTrue(result.fields["notes"].value)

    def test_does_not_confuse_prizes_with_procedure_value(self) -> None:
        classified, sections = self._build_document(
            "\n".join(
                [
                    "ARTIGO 5.º",
                    "Prémio único: 5 000 €",
                    "Valor do procedimento: 20 000 €",
                    "Preço dos serviços: 1 000 €",
                ]
            )
        )

        result = FinancialReader().extract(classified, sections)

        self.assertNotEqual(
            result.fields["competition_prizes"].value[0]["value"],
            result.fields["procedure_value"].normalized_value,
        )


class TeamReaderTests(unittest.TestCase):
    def _build_document(self, text: str) -> tuple[ClassifiedDocument, list]:
        source = SourceDocument(
            document_id="team-doc",
            filename="Equipa_Tecnica.pdf",
            origin="manual",
            source_role="official_document",
            text=text,
        )
        classified = ClassifiedDocument(
            source=source,
            document_type=DocumentType.TERMS_OF_REFERENCE,
            title=source.filename,
            confidence=1.0,
            reasons=["test"],
        )
        return classified, extract_sections(classified)

    def test_extracts_coordinator_specializations_and_requirements(self) -> None:
        classified, sections = self._build_document(
            "\n".join(
                [
                    "ARTIGO 8.º",
                    "Coordenador: arquiteto com 5 anos de experiência e inscrição válida na Ordem dos Arquitetos.",
                    "Equipa mínima:",
                    "- Coordenador",
                    "- Arquiteto",
                    "- Engenheiro",
                    "- Arquiteto",
                    "Especialidades obrigatórias:",
                    "- Arquitetura",
                    "- Estruturas",
                    "- Instalações",
                    "- Estruturas",
                    "Requisitos profissionais:",
                    "- inscrição na Ordem dos Arquitetos",
                    "- inscrição na Ordem dos Engenheiros",
                    "Certificações:",
                    "- BIM",
                    "- ISO 19650",
                    "Consultores:",
                    "- consultor BIM",
                    "- consultor de acessibilidade",
                    "Sob pena de exclusão: falta de coordenador.",
                    "Critérios da equipa:",
                    "- fator experiência 30%",
                    "- fator coordenação 20%",
                ]
            )
        )

        result = TeamReader().extract(classified, sections)

        self.assertEqual(result.fields["coordinator"].status.value, "confirmed")
        self.assertEqual(result.fields["coordinator"].value["minimum_years"], 5)
        self.assertEqual(len(result.fields["required_specializations"].value), 3)
        self.assertTrue(result.fields["professional_requirements"].value)
        self.assertEqual(
            result.fields["experience_requirements"].value[0]["minimum_years"],
            5,
        )
        self.assertTrue(result.fields["certifications"].value)
        self.assertTrue(result.fields["consultants"].value)
        self.assertTrue(result.fields["exclusionary_team_requirements"].value)
        self.assertTrue(result.fields["scored_team_requirements"].value)

    def test_marks_missing_team_data_as_not_found(self) -> None:
        classified, sections = self._build_document(
            "ARTIGO 1.º\nObjeto do procedimento sem requisitos de equipa."
        )

        result = TeamReader().extract(classified, sections)

        self.assertEqual(result.fields["coordinator"].status.value, "not_found")
        self.assertTrue(result.warnings)


class DeliverablesReaderTests(unittest.TestCase):
    def _build_document(self, text: str) -> tuple[ClassifiedDocument, list]:
        source = SourceDocument(
            document_id="deliverables-doc",
            filename="Programa_Concurso.pdf",
            origin="manual",
            source_role="official_document",
            text=text,
        )
        classified = ClassifiedDocument(
            source=source,
            document_type=DocumentType.PROCEDURE_PROGRAM,
            title=source.filename,
            confidence=1.0,
            reasons=["test"],
        )
        return classified, extract_sections(classified)

    def test_groups_deliverables_by_phase_and_formats(self) -> None:
        classified, sections = self._build_document(
            "\n".join(
                [
                    "ARTIGO 12.º",
                    "Fase 1 - Estudo prévio: 30 dias",
                    "- Estudo prévio",
                    "- Peças escritas em PDF",
                    "- Peças desenhadas em DWG e IFC",
                    "Fase 2 - Anteprojeto: 45 dias",
                    "- Anteprojeto",
                    "- Maquete digital BIM",
                    "Fase 3 - Projeto de execução: 60 dias",
                    "- Projeto de execução",
                    "- Assistência técnica",
                    "- Telas finais",
                    "- Mapa de quantidades",
                    "Escala 1:100",
                    "2 exemplares físicos",
                    "Validação e aprovação do dono de obra.",
                ]
            )
        )

        result = DeliverablesReader().extract(classified, sections)

        self.assertTrue(result.fields["phases"].value)
        self.assertEqual(len(result.fields["deliverables_by_phase"].value), 3)
        self.assertTrue(result.fields["digital_formats"].value)
        self.assertTrue(result.fields["physical_formats"].value)
        self.assertTrue(result.fields["scale_requirements"].value)
        self.assertTrue(result.fields["validation_requirements"].value)
        self.assertTrue(result.fields["assistance_requirements"].value)
        self.assertTrue(result.fields["phases"].evidences)

    def test_marks_missing_deliverables_as_not_found(self) -> None:
        classified, sections = self._build_document(
            "ARTIGO 1.º\nSem informação sobre fases ou entregáveis."
        )

        result = DeliverablesReader().extract(classified, sections)

        self.assertEqual(result.fields["phases"].status.value, "not_found")


class SubmissionReaderTests(unittest.TestCase):
    def _build_document(self, text: str) -> tuple[ClassifiedDocument, list]:
        source = SourceDocument(
            document_id="submission-doc",
            filename="Programa_Concurso.pdf",
            origin="manual",
            source_role="official_document",
            text=text,
        )
        classified = ClassifiedDocument(
            source=source,
            document_type=DocumentType.PROCEDURE_PROGRAM,
            title=source.filename,
            confidence=1.0,
            reasons=["test"],
        )
        return classified, extract_sections(classified)

    def test_separates_submission_and_habilitation_rules(self) -> None:
        classified, sections = self._build_document(
            "\n".join(
                [
                    "ARTIGO 10.º",
                    "Documentos da proposta:",
                    "- Memória descritiva",
                    "- Declaração de aceitação",
                    "Documentos de habilitação:",
                    "- Certidão da Ordem",
                    "- Declaração de não impedimento",
                    "Assinatura digital qualificada obrigatória.",
                    "Proposta anónima em invólucro fechado.",
                    "Submissão na plataforma eletrónica AcinGov em PDF e ZIP.",
                    "Limite de 20 páginas e 3 ficheiros.",
                    "Nome do ficheiro sem acentos.",
                ]
            )
        )

        result = SubmissionReader().extract(classified, sections)

        self.assertTrue(result.fields["administrative_documents"].value)
        self.assertTrue(result.fields["post_award_documents"].value)
        self.assertTrue(result.fields["signature_requirements"].value)
        self.assertTrue(result.fields["anonymity_rules"].value)
        self.assertTrue(result.fields["submission_format_rules"].value)
        self.assertTrue(result.fields["naming_rules"].value)
        self.assertTrue(result.fields["page_limits"].value)
        self.assertTrue(result.fields["platform_requirements"].value)
        self.assertTrue(result.fields["signature_requirements"].evidences)

    def test_marks_missing_submission_data_as_not_found(self) -> None:
        classified, sections = self._build_document(
            "ARTIGO 1.º\nSem dados relevantes sobre submissão."
        )

        result = SubmissionReader().extract(classified, sections)

        self.assertEqual(result.fields["administrative_documents"].status.value, "not_found")


class RisksReaderTests(unittest.TestCase):
    def _build_document(self, text: str) -> tuple[ClassifiedDocument, list]:
        source = SourceDocument(
            document_id="risks-doc",
            filename="Caderno_Encargos.pdf",
            origin="manual",
            source_role="official_document",
            text=text,
        )
        classified = ClassifiedDocument(
            source=source,
            document_type=DocumentType.SPECIFICATIONS,
            title=source.filename,
            confidence=1.0,
            reasons=["test"],
        )
        return classified, extract_sections(classified)

    def test_classifies_risk_gravity_and_categories(self) -> None:
        classified, sections = self._build_document(
            "\n".join(
                [
                    "ARTIGO 20.º",
                    "Sob pena de exclusão, a proposta deve respeitar o anonimato.",
                    "Falta de documentos obrigatórios resulta em exclusão.",
                    "Assinatura inválida ou fora de prazo é motivo de exclusão.",
                    "Contradição entre peças e anexos deve ser esclarecida.",
                    "Retificação do procedimento poderá ser publicada.",
                    "Penalização contratual por atraso.",
                ]
            )
        )

        result = RisksReader().extract(classified, sections)

        self.assertTrue(result.fields["exclusion_risks"].value)
        self.assertTrue(result.fields["contractual_risks"].value)
        self.assertTrue(result.fields["submission_risks"].value)
        self.assertTrue(result.fields["contradictions"].value)
        self.assertTrue(result.fields["clarification_alerts"].value or result.fields["rectification_alerts"].value)
        self.assertIn(result.fields["exclusion_risks"].value[0]["severity"], {"critical", "warning", "info"})
        self.assertTrue(result.fields["exclusion_risks"].evidences)

    def test_marks_missing_risks_as_not_found(self) -> None:
        classified, sections = self._build_document(
            "ARTIGO 1.º\nSem riscos identificados."
        )

        result = RisksReader().extract(classified, sections)

        self.assertEqual(result.fields["exclusion_risks"].status.value, "not_found")
        self.assertTrue(result.warnings)


class ConsolidatorTests(unittest.TestCase):
    def _evidence(
        self,
        evidence_id: str,
        source_document_id: str,
        excerpt: str,
    ) -> Evidence:
        return Evidence(
            evidence_id=evidence_id,
            source_document_id=source_document_id,
            filename=f"{source_document_id}.pdf",
            page=1,
            section="artigo 1",
            excerpt=excerpt,
            confidence=0.9,
            status=EvidenceStatus.CONFIRMED,
        )

    def _field(
        self,
        field_name: str,
        value,
        normalized_value=None,
        evidences=None,
        confidence: float = 0.8,
        status: EvidenceStatus = EvidenceStatus.CONFIRMED,
    ) -> ExtractedField:
        return ExtractedField(
            field_name=field_name,
            value=value,
            normalized_value=normalized_value if normalized_value is not None else value,
            evidences=list(evidences or []),
            confidence=confidence,
            status=status,
        )

    def _reader_result(
        self,
        reader_name: str,
        document_id: str,
        fields: dict[str, ExtractedField],
        warnings: list[str] | None = None,
        confidence: float = 0.8,
    ) -> ReaderResult:
        evidences = []
        for field in fields.values():
            evidences.extend(field.evidences)
        return ReaderResult(
            reader_name=reader_name,
            document_ids=[document_id],
            fields=fields,
            evidences=evidences,
            warnings=list(warnings or []),
            confidence=confidence,
        )

    def test_merges_evidences_without_losing_any(self) -> None:
        result_a = self._reader_result(
            "procedure_reader",
            "doc-a",
            {
                "object": self._field(
                    "object",
                    "Requalificacao da escola",
                    evidences=[self._evidence("ev-a", "doc-a", "Objeto do procedimento")],
                    confidence=0.7,
                )
            },
            confidence=0.7,
        )
        result_b = self._reader_result(
            "procedure_reader",
            "doc-b",
            {
                "object": self._field(
                    "object",
                    "Requalificacao da escola",
                    evidences=[self._evidence("ev-b", "doc-b", "Objeto confirmado")],
                    confidence=0.9,
                )
            },
            confidence=0.9,
        )

        consolidated = consolidate_reader_results([result_a, result_b])

        object_field = consolidated.procedure_identity["object"]
        self.assertEqual(object_field["value"], "Requalificacao da escola")
        self.assertEqual(len(object_field["evidences"]), 2)
        self.assertFalse(object_field["conflict"])

    def test_conflicts_keep_alternatives_and_flags(self) -> None:
        result_a = self._reader_result(
            "procedure_reader",
            "doc-a",
            {
                "submission_deadline": self._field(
                    "submission_deadline",
                    "2026-09-01",
                    normalized_value="2026-09-01",
                    evidences=[self._evidence("ev-a", "doc-a", "Prazo A")],
                    confidence=0.8,
                )
            },
            confidence=0.8,
        )
        result_b = self._reader_result(
            "procedure_reader",
            "doc-b",
            {
                "submission_deadline": self._field(
                    "submission_deadline",
                    "2026-09-15",
                    normalized_value="2026-09-15",
                    evidences=[self._evidence("ev-b", "doc-b", "Prazo B")],
                    confidence=0.7,
                )
            },
            confidence=0.7,
        )

        consolidated = consolidate_reader_results([result_a, result_b])

        deadline_field = consolidated.procedure_identity["submission_deadline"]
        self.assertTrue(deadline_field["conflict"])
        self.assertEqual(len(deadline_field["alternatives"]), 1)
        self.assertEqual(len(deadline_field["evidences"]), 2)
        self.assertTrue(any("conflict" in warning.lower() for warning in consolidated.warnings))

    def test_prices_stay_separated(self) -> None:
        result = self._reader_result(
            "financial_reader",
            "doc-fin",
            {
                "competition_prizes": self._field(
                    "competition_prizes",
                    [
                        {"label": "1o premio", "value": 15000},
                        {"label": "2o premio", "value": 10000},
                    ],
                    evidences=[self._evidence("ev-fin-1", "doc-fin", "Premios")],
                    confidence=0.85,
                ),
                "procedure_value": self._field(
                    "procedure_value",
                    26000.0,
                    normalized_value=26000.0,
                    evidences=[self._evidence("ev-fin-2", "doc-fin", "Valor do procedimento")],
                    confidence=0.9,
                ),
                "design_services_value": self._field(
                    "design_services_value",
                    1221957.0,
                    normalized_value=1221957.0,
                    evidences=[self._evidence("ev-fin-3", "doc-fin", "Preco dos servicos")],
                    confidence=0.95,
                ),
                "estimated_construction_cost": self._field(
                    "estimated_construction_cost",
                    24439134.0,
                    normalized_value=24439134.0,
                    evidences=[self._evidence("ev-fin-4", "doc-fin", "Custo da obra")],
                    confidence=0.9,
                ),
            },
            confidence=0.9,
        )

        consolidated = consolidate_reader_results([result])

        prices = consolidated.prices
        self.assertIn("competition_prizes", prices)
        self.assertIn("procedure_value", prices)
        self.assertIn("design_services_value", prices)
        self.assertIn("estimated_construction_cost", prices)
        self.assertEqual(len(prices["competition_prizes"]["value"]), 2)
        self.assertEqual(prices["procedure_value"]["normalized_value"], 26000.0)
        self.assertEqual(prices["design_services_value"]["normalized_value"], 1221957.0)
        self.assertEqual(prices["estimated_construction_cost"]["normalized_value"], 24439134.0)


class ArchitectureIntelligenceExperimentTests(unittest.TestCase):
    def test_experiment_exports_artifacts_and_runs_matching(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        import app.architecture_intelligence.pipeline as pipeline_module

        pipeline_module.DEBUG_EXPORT_ROOT = Path(temp_dir.name) / "debug_exports"

        source = SourceDocument(
            document_id="exp-lumiar",
            filename="Caderno_Encargos_Lumiar.pdf",
            origin="local",
            source_role="official_document",
            text="\n".join(
                [
                    "ARTIGO 1.º",
                    "Objeto: Reabilitação da Escola Secundária do Lumiar.",
                    "Entidade adjudicante: Município de Lisboa.",
                    "Tipo de procedimento: Concurso de conceção.",
                    "CÓDIGO CPV: 71240000-2.",
                    "Prazo para apresentação das propostas: 2026-10-15.",
                    "ARTIGO 5.º",
                    "Preço dos serviços: 1 221 957 €.",
                    "Valor do procedimento: 26 000 €.",
                    "Custo estimado da obra: 24 439 134 €.",
                    "ARTIGO 8.º",
                    "Coordenador: arquiteto com 5 anos de experiência.",
                    "Equipa mínima:",
                    "- Arquiteto",
                    "- Engenheiro civil",
                    "ARTIGO 12.º",
                    "Fase 1 - Estudo prévio: 30 dias",
                    "- Estudo prévio",
                    "- Peças escritas em PDF",
                    "- Peças desenhadas em DWG e IFC",
                    "Fase 2 - Anteprojeto: 45 dias",
                    "- Anteprojeto",
                    "- Maquete digital BIM",
                    "Fase 3 - Projeto de execução: 60 dias",
                    "- Projeto de execução",
                    "- Assistência técnica",
                    "- Telas finais",
                    "- Mapa de quantidades",
                    "Documentos da proposta:",
                    "- Memória descritiva",
                    "- Declaração de aceitação",
                    "Documentos de habilitação:",
                    "- Certidão da Ordem",
                    "- Declaração de não impedimento",
                    "Assinatura digital qualificada obrigatória.",
                    "Proposta anónima em invólucro fechado.",
                    "Submissão na plataforma eletrónica AcinGov em PDF e ZIP.",
                    "Limite de 20 páginas e 3 ficheiros.",
                    "Sob pena de exclusão: falta de documentos, assinatura inválida e fora de prazo.",
                    "ARTIGO 17.º",
                    "Critério de adjudicação: qualidade 70% e preço 30%.",
                ]
            ),
        )

        company = CompanyProfile(
            company_id=99,
            identity=CompanyIdentity(
                company_name="Atelier Lumiar",
                location="Lisboa",
            ),
            services=["Projeto de arquitetura"],
            competences=["Arquitetura"],
            specializations=["Educacao"],
            project_experience=[
                CompanyProjectExperience(
                    name="Escola A",
                    typology="Escola Secundaria",
                    location="Lisboa",
                    skills_demonstrated=["Arquitetura"],
                )
            ],
            preferences=CompanyPreferences(
                typologies=["Educacao"],
                locations=["Lisboa"],
            ),
        )

        result = run_architecture_intelligence_experiment([source], company)

        output_dir = Path(result.output_dir)
        self.assertTrue(output_dir.exists())
        self.assertTrue((output_dir / "reader_results.json").exists())
        self.assertTrue((output_dir / "consolidated.json").exists())
        self.assertTrue((output_dir / "executive_analysis.json").exists())
        self.assertTrue((output_dir / "company_matching.json").exists())
        self.assertTrue((output_dir / "warnings.json").exists())

        self.assertTrue(result.reader_results)
        self.assertGreaterEqual(len(result.reader_results), 7)
        self.assertEqual(result.classified_documents[0]["document_type"], "specifications")
        self.assertIn("document_quality", result.consolidated)
        self.assertIsNotNone(result.company_matching)
        self.assertIn("compatibility_score", result.company_matching)
        self.assertTrue(result.consolidated["phases_and_deliverables"])
        self.assertTrue(result.consolidated["submission_checklist"])
        self.assertTrue(result.consolidated["exclusion_risks"])

    def test_experiment_discovers_children_from_nested_acingov_container(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        import app.architecture_intelligence.pipeline as pipeline_module

        pipeline_module.DEBUG_EXPORT_ROOT = Path(temp_dir.name) / "debug_exports"
        root = Path(temp_dir.name) / "lumiar"
        root.mkdir()
        cache = root / "jobs" / "52"
        cache.mkdir(parents=True)
        container = root / "01-OTMxNTc2.pdf"
        nested_bytes = root / "inner.zip"
        with zipfile.ZipFile(nested_bytes, "w") as nested:
            nested.writestr(
                "TERMOS DE REFERENCIA_ANEXOS_LUMIAR/CE_Anexos/CE_ES_Lumiar.pdf",
                b"%PDF-1.4 CE",
            )
            nested.writestr(
                "TERMOS DE REFERENCIA_ANEXOS_LUMIAR/TR_Anexos/ANEXO I - Programa Preliminar ES LUMIAR.pdf",
                b"%PDF-1.4 PROGRAMA",
            )
        with zipfile.ZipFile(container, "w") as outer:
            outer.write(
                nested_bytes,
                "Processo Concurso/1_TERMOS_DE_REFERENCIA_ANEXOS_LUMIAR.zip",
            )
        (cache / "textos.json").write_text(
            json.dumps(
                {
                    "Processo Concurso\\1_TERMOS_DE_REFERENCIA_ANEXOS_LUMIAR\\TERMOS DE REFERENCIA_ANEXOS_LUMIAR\\CE_Anexos\\CE_ES_Lumiar.pdf": "\n".join(
                        [
                            "ARTIGO 1.º",
                            "Objeto: Reabilitação da Escola Secundária do Lumiar.",
                            "Preço dos serviços: 1 221 957 EUR.",
                            "Critério de adjudicação: qualidade 70% e preço 30%.",
                            "Coordenador: arquiteto.",
                        ]
                    ),
                    "Processo Concurso\\1_TERMOS_DE_REFERENCIA_ANEXOS_LUMIAR\\TERMOS DE REFERENCIA_ANEXOS_LUMIAR\\TR_Anexos\\ANEXO I - Programa Preliminar ES LUMIAR.pdf": "\n".join(
                        [
                            "Programa preliminar.",
                            "Fase 1 - Estudo prévio: 30 dias.",
                            "Documentos da proposta: memória descritiva.",
                            "Sob pena de exclusão: proposta fora de prazo.",
                        ]
                    ),
                }
            ),
            encoding="utf-8",
        )

        source = SourceDocument(
            document_id="acingov-931576",
            concurso_id=435,
            filename="01-OTMxNTc2.pdf",
            path=container.as_posix(),
            origin="acingov",
            source_role="platform_document",
            content_type="application/pdf",
            text="",
            metadata={
                "experiment_case": "lumiar",
                "source_url": "https://www.acingov.pt/acingovprod/2/zonaPublica/zona_publica_c/donwloadProcedurePiece/OTMxNTc2",
                "text_cache_paths": [(cache / "textos.json").as_posix()],
            },
        )
        result = run_architecture_intelligence_experiment([source])
        filenames = {
            document["filename"] for document in result.classified_documents
        }
        reader_document_ids = {
            document_id
            for reader_result in result.reader_results
            for document_id in reader_result["document_ids"]
        }
        reader_counts: dict[str, int] = {}
        for reader_result in result.reader_results:
            reader_counts[reader_result["reader_name"]] = (
                reader_counts.get(reader_result["reader_name"], 0) + 1
            )
        manifest = json.loads(
            (Path(result.output_dir) / "experimental_source_manifest.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("CE_ES_Lumiar.pdf", filenames)
        self.assertIn("ANEXO I - Programa Preliminar ES LUMIAR.pdf", filenames)
        self.assertGreaterEqual(len(result.classified_documents), 2)
        self.assertNotIn("01-OTMxNTc2.pdf", filenames)
        self.assertGreaterEqual(len(reader_document_ids), 2)
        self.assertGreaterEqual(max(reader_counts.values()), 2)
        self.assertEqual(manifest["containers"][0]["status"], "expanded")
        self.assertFalse(manifest["containers"][0]["sent_to_reader"])
        self.assertEqual(manifest["summary"]["children_accepted"], 2)
        self.assertEqual(manifest["summary"]["children_with_text"], 2)

    def test_experiment_expands_nested_zip_with_wrong_pdf_extension(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        import app.architecture_intelligence.pipeline as pipeline_module

        pipeline_module.DEBUG_EXPORT_ROOT = Path(temp_dir.name) / "debug_exports"
        root = Path(temp_dir.name) / "lumiar"
        root.mkdir()
        cache = root / "jobs" / "52"
        cache.mkdir(parents=True)
        container = root / "01-OTMxNTc2.pdf"
        nested_zip = root / "nested-disguised.pdf"

        with zipfile.ZipFile(nested_zip, "w") as nested:
            nested.writestr(
                "TERMOS DE REFERENCIA_ANEXOS_LUMIAR/CE_Anexos/CE_ES_Lumiar.pdf",
                b"%PDF-1.4 CE",
            )
        with zipfile.ZipFile(container, "w") as outer:
            outer.write(
                nested_zip,
                "Processo Concurso/1_TERMOS_DE_REFERENCIA_ANEXOS_LUMIAR.pdf",
            )
        (cache / "textos.json").write_text(
            json.dumps(
                {
                    "Processo Concurso\\1_TERMOS_DE_REFERENCIA_ANEXOS_LUMIAR\\TERMOS DE REFERENCIA_ANEXOS_LUMIAR\\CE_Anexos\\CE_ES_Lumiar.pdf": "\n".join(
                        [
                            "Caderno de encargos.",
                            "ARTIGO 1.º",
                            "Objeto: Reabilitação da Escola Secundária do Lumiar.",
                            "Preço base: 60000 EUR.",
                        ]
                    )
                }
            ),
            encoding="utf-8",
        )

        source = SourceDocument(
            document_id="acingov-931576",
            concurso_id=435,
            filename="01-OTMxNTc2.pdf",
            path=container.as_posix(),
            origin="acingov",
            source_role="platform_document",
            content_type="application/pdf",
            text="",
            metadata={
                "experiment_case": "lumiar",
                "source_url": "https://www.acingov.pt/download/OTMxNTc2",
                "text_cache_paths": [(cache / "textos.json").as_posix()],
            },
        )

        result = run_architecture_intelligence_experiment([source])
        output_dir = Path(result.output_dir)
        filenames = {
            document["filename"] for document in result.classified_documents
        }
        manifest = json.loads(
            (output_dir / "archive_manifest.json").read_text(encoding="utf-8")
        )
        legacy_manifest = json.loads(
            (output_dir / "experimental_source_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        accepted_items = [
            item
            for item in manifest["items"]
            if item.get("status") == "accepted"
        ]

        self.assertIn("CE_ES_Lumiar.pdf", filenames)
        self.assertNotIn("01-OTMxNTc2.pdf", filenames)
        self.assertEqual(manifest, legacy_manifest)
        self.assertEqual(manifest["containers"][0]["status"], "expanded")
        self.assertFalse(manifest["containers"][0]["sent_to_reader"])
        self.assertTrue(
            any(
                item["filename"] == "1_TERMOS_DE_REFERENCIA_ANEXOS_LUMIAR.pdf"
                and item["content_type"] == "application/zip"
                and item["status"] == "expanded"
                for item in manifest["items"]
            )
        )
        self.assertEqual(len(accepted_items), 1)
        self.assertEqual(accepted_items[0]["origin"], "acingov")
        self.assertEqual(
            accepted_items[0]["source_url"],
            "https://www.acingov.pt/download/OTMxNTc2",
        )
        self.assertTrue(accepted_items[0]["sha256"])
        self.assertEqual(accepted_items[0]["read_status"], "text_reused")
        self.assertTrue(accepted_items[0]["readers_applied"])

    def test_experiment_keeps_consolidated_sections_from_consolidator_only(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        import app.architecture_intelligence.pipeline as pipeline_module

        pipeline_module.DEBUG_EXPORT_ROOT = Path(temp_dir.name) / "debug_exports"
        source = SourceDocument(
            document_id="exp-non-merged",
            filename="Caderno_Encargos.pdf",
            origin="manual",
            source_role="official_document",
            text="\n".join(
                [
                    "Caderno de encargos.",
                    "ARTIGO 12.º",
                    "Fase 1 - Estudo prévio: 30 dias",
                    "- Estudo prévio",
                    "- Peças desenhadas em DWG",
                    "Documentos da proposta:",
                    "- Memória descritiva",
                    "Sob pena de exclusão: falta de documentos.",
                ]
            ),
        )
        empty_consolidated = ConsolidatedCompetitionData(
            document_quality="partial",
            quality_report={
                "documents_official": 0,
                "documents_read": 0,
                "documents_ignored": 0,
                "conflicts": 0,
                "fields_filled": 0,
                "fields_empty": 0,
                "confidence_global": 0.0,
            },
        )

        with patch.object(
            pipeline_module.Consolidator,
            "consolidate",
            return_value=empty_consolidated,
        ):
            result = run_architecture_intelligence_experiment([source])

        self.assertEqual(result.consolidated["phases_and_deliverables"], [])
        self.assertEqual(result.consolidated["submission_checklist"]["administrative"], [])
        self.assertEqual(result.consolidated["exclusion_risks"], [])
        self.assertEqual(result.consolidated["document_alerts"], [])
        self.assertTrue(result.reader_results)

    def _evidence(
        self,
        evidence_id: str,
        source_document_id: str,
        excerpt: str,
    ) -> Evidence:
        return Evidence(
            evidence_id=evidence_id,
            source_document_id=source_document_id,
            filename=f"{source_document_id}.pdf",
            page=1,
            section="artigo 1",
            excerpt=excerpt,
            confidence=0.9,
            status=EvidenceStatus.CONFIRMED,
        )

    def _field(
        self,
        field_name: str,
        value,
        normalized_value=None,
        evidences=None,
        confidence: float = 0.8,
        status: EvidenceStatus = EvidenceStatus.CONFIRMED,
    ) -> ExtractedField:
        return ExtractedField(
            field_name=field_name,
            value=value,
            normalized_value=normalized_value if normalized_value is not None else value,
            evidences=list(evidences or []),
            confidence=confidence,
            status=status,
        )

    def _reader_result(
        self,
        reader_name: str,
        document_id: str,
        fields: dict[str, ExtractedField],
        warnings: list[str] | None = None,
        confidence: float = 0.8,
    ) -> ReaderResult:
        evidences = []
        for field in fields.values():
            evidences.extend(field.evidences)
        return ReaderResult(
            reader_name=reader_name,
            document_ids=[document_id],
            fields=fields,
            evidences=evidences,
            warnings=list(warnings or []),
            confidence=confidence,
        )

    def test_document_quality_and_quality_report(self) -> None:
        procedure = self._reader_result(
            "procedure_reader",
            "doc-proc",
            {
                "object": self._field("object", "Escola Secundaria do Lumiar", confidence=0.9),
                "contracting_entity": self._field("contracting_entity", "Municipio", confidence=0.9),
            },
            confidence=0.9,
        )
        award = self._reader_result(
            "award_reader",
            "doc-award",
            {
                "award_criterion": self._field("award_criterion", "Melhor proposta", confidence=0.8),
            },
            confidence=0.8,
        )
        financial = self._reader_result(
            "financial_reader",
            "doc-fin",
            {
                "procedure_value": self._field("procedure_value", 26000.0, normalized_value=26000.0, confidence=0.9),
            },
            confidence=0.9,
        )
        team = self._reader_result(
            "team_reader",
            "doc-team",
            {
                "coordinator": self._field("coordinator", {"role": "arquiteto"}, normalized_value={"role": "arquiteto"}, confidence=0.85),
            },
            confidence=0.85,
        )

        consolidated = consolidate_reader_results([procedure, award, financial, team])

        self.assertEqual(consolidated.document_quality, "complete")
        self.assertEqual(consolidated.quality_report["documents_official"], 4)
        self.assertEqual(consolidated.quality_report["documents_read"], 4)
        self.assertGreater(consolidated.quality_report["fields_filled"], 0)
        self.assertGreaterEqual(consolidated.quality_report["fields_empty"], 0)
        self.assertGreater(consolidated.quality_report["confidence_global"], 0)

    def test_deduplicates_identical_list_items(self) -> None:
        result_a = self._reader_result(
            "financial_reader",
            "doc-a",
            {
                "competition_prizes": self._field(
                    "competition_prizes",
                    [{"label": "1o premio", "value": 15000}],
                    evidences=[self._evidence("ev-a", "doc-a", "Premio")],
                    confidence=0.8,
                )
            },
            confidence=0.8,
        )
        result_b = self._reader_result(
            "financial_reader",
            "doc-b",
            {
                "competition_prizes": self._field(
                    "competition_prizes",
                    [{"label": "1o premio", "value": 15000}],
                    evidences=[self._evidence("ev-b", "doc-b", "Premio duplicado")],
                    confidence=0.75,
                )
            },
            confidence=0.75,
        )

        consolidated = consolidate_reader_results([result_a, result_b])

        prizes_field = consolidated.prices["competition_prizes"]
        self.assertEqual(len(prizes_field["value"]), 1)
        self.assertEqual(len(prizes_field["evidences"]), 2)
        self.assertFalse(prizes_field["conflict"])

    def test_consolidates_new_reader_sections_natively(self) -> None:
        deliverables_a = self._reader_result(
            "deliverables_reader",
            "doc-deliv-a",
            {
                "phases": self._field(
                    "phases",
                    [
                        {
                            "phase": "Fase 1",
                            "description": "Estudo prévio",
                            "deadline": "30 dias",
                            "deliverables": ["Estudo prévio", "PDF"],
                        }
                    ],
                    confidence=0.86,
                    evidences=[self._evidence("ev-deliv-a", "doc-deliv-a", "Fase 1")],
                ),
                "drawing_requirements": self._field(
                    "drawing_requirements",
                    [{"text": "Peças desenhadas em DWG"}],
                    confidence=0.8,
                    evidences=[self._evidence("ev-draw-a", "doc-deliv-a", "DWG")],
                ),
            },
            confidence=0.86,
        )
        deliverables_b = self._reader_result(
            "deliverables_reader",
            "doc-deliv-b",
            {
                "deliverables_by_phase": self._field(
                    "deliverables_by_phase",
                    [
                        {
                            "phase": "Fase 1",
                            "description": "Estudo prévio revisto",
                            "deadline": "45 dias",
                            "deliverables": ["Anteprojeto", "IFC"],
                        }
                    ],
                    confidence=0.83,
                    evidences=[self._evidence("ev-deliv-b", "doc-deliv-b", "Fase 1 revisto")],
                ),
            },
            confidence=0.83,
        )
        submission_a = self._reader_result(
            "submission_reader",
            "doc-sub-a",
            {
                "administrative_documents": self._field(
                    "administrative_documents",
                    [{"text": "Memória descritiva"}],
                    confidence=0.79,
                    evidences=[self._evidence("ev-sub-a", "doc-sub-a", "Memória descritiva")],
                )
            },
            confidence=0.79,
        )
        submission_b = self._reader_result(
            "submission_reader",
            "doc-sub-b",
            {
                "administrative_documents": self._field(
                    "administrative_documents",
                    [{"text": "Memória descritiva"}],
                    confidence=0.77,
                    evidences=[self._evidence("ev-sub-b", "doc-sub-b", "Memória descritiva duplicada")],
                )
            },
            confidence=0.77,
        )
        financial = self._reader_result(
            "financial_reader",
            "doc-fin",
            {
                "payments_by_phase": self._field(
                    "payments_by_phase",
                    [
                        {
                            "phase": "1",
                            "percentage": 20.0,
                            "description": "Fase 1 - 20%",
                        }
                    ],
                    confidence=0.81,
                    evidences=[self._evidence("ev-fin", "doc-fin", "Fase 1 - 20%")],
                )
            },
            confidence=0.81,
        )
        risks = self._reader_result(
            "risks_reader",
            "doc-risk",
            {
                "exclusion_risks": self._field(
                    "exclusion_risks",
                    [{"title": "Falta de documentos", "description": "Falta de documentos"}],
                    confidence=0.78,
                    evidences=[self._evidence("ev-risk", "doc-risk", "Falta de documentos")],
                ),
                "document_alerts": self._field(
                    "document_alerts",
                    [{"title": "Aviso documental", "description": "Aviso documental"}],
                    confidence=0.76,
                    evidences=[self._evidence("ev-alert", "doc-risk", "Aviso documental")],
                ),
            },
            confidence=0.77,
        )
        procedure = self._reader_result(
            "procedure_reader",
            "doc-proc",
            {
                "object": self._field("object", "Reabilitação da Escola", confidence=0.9),
            },
            confidence=0.9,
        )
        award = self._reader_result(
            "award_reader",
            "doc-award",
            {
                "award_criterion": self._field("award_criterion", "Proposta economicamente mais vantajosa", confidence=0.88),
            },
            confidence=0.88,
        )
        team = self._reader_result(
            "team_reader",
            "doc-team",
            {
                "coordinator": self._field("coordinator", {"role": "arquiteto"}, normalized_value={"role": "arquiteto"}, confidence=0.85),
            },
            confidence=0.85,
        )

        consolidated = consolidate_reader_results(
            [
                procedure,
                award,
                financial,
                team,
                deliverables_a,
                deliverables_b,
                submission_a,
                submission_b,
                risks,
            ]
        )

        phase = consolidated.phases_and_deliverables[0]
        self.assertEqual(phase["field"], "phases_and_deliverables")
        self.assertTrue(phase["conflict"])
        self.assertIn("deliverables_reader", phase["source_readers"])
        self.assertIn("financial_reader", phase["source_readers"])
        self.assertIn("doc-deliv-a", phase["document_ids"])
        self.assertIn("doc-deliv-b", phase["document_ids"])
        self.assertTrue(phase["payments"])
        self.assertTrue(phase["alternatives"])

        checklist = consolidated.submission_checklist["administrative"]
        self.assertEqual(len(checklist), 1)
        self.assertEqual(checklist[0]["field"], "administrative_documents")
        self.assertEqual(len(checklist[0]["evidences"]), 2)
        self.assertEqual(checklist[0]["source_readers"], ["submission_reader"])

        self.assertTrue(consolidated.drawing_rules)
        self.assertEqual(consolidated.drawing_rules[0]["source_readers"], ["deliverables_reader"])
        self.assertTrue(consolidated.exclusion_risks)
        self.assertEqual(consolidated.exclusion_risks[0]["source_readers"], ["risks_reader"])
        self.assertTrue(consolidated.document_alerts)

    def test_information_model_separates_submission_and_contract_contexts(self) -> None:
        prelim_document = SourceDocument(
            document_id="doc-prelim",
            concurso_id=435,
            filename="ANEXO I - Programa Preliminar ES LUMIAR.pdf",
            origin="acingov",
            source_role="platform_document",
            text="Programa preliminar com custo estimado da obra de 24 439 134 EUR.",
            metadata={"source_url": "https://example.com/prelim"},
        )
        ce_document = SourceDocument(
            document_id="doc-ce",
            concurso_id=435,
            filename="CE_ES_Lumiar.pdf",
            origin="acingov",
            source_role="platform_document",
            text="Caderno de encargos com preço base e condições de execução.",
            metadata={"source_url": "https://example.com/ce"},
        )
        prelim_financial = self._reader_result(
            "financial_reader",
            "doc-prelim",
            {
                "estimated_construction_cost": self._field(
                    "estimated_construction_cost",
                    24439134.0,
                    normalized_value=24439134.0,
                    confidence=0.92,
                    evidences=[
                        self._evidence(
                            "ev-prelim-cost",
                            "doc-prelim",
                            "Custo estimado da obra: 24 439 134 EUR.",
                        )
                    ],
                )
            },
            confidence=0.92,
        )
        ce_financial = self._reader_result(
            "financial_reader",
            "doc-ce",
            {
                "procedure_value": self._field(
                    "procedure_value",
                    1221957.0,
                    normalized_value=1221957.0,
                    confidence=0.84,
                    evidences=[
                        self._evidence(
                            "ev-ce-value",
                            "doc-ce",
                            "Preço base: 1 221 957 EUR.",
                        )
                    ],
                )
            },
            confidence=0.84,
        )
        award = self._reader_result(
            "award_reader",
            "doc-prelim",
            {
                "award_criterion": self._field(
                    "award_criterion",
                    "Qualidade 70% e preço 30%",
                    confidence=0.9,
                    evidences=[
                        self._evidence("ev-award", "doc-prelim", "Critério de adjudicação.")
                    ],
                )
            },
            confidence=0.9,
        )
        submission = self._reader_result(
            "submission_reader",
            "doc-prelim",
            {
                "administrative_documents": self._field(
                    "administrative_documents",
                    [{"text": "Memória descritiva"}, {"text": "Painéis A1"}],
                    confidence=0.88,
                    evidences=[
                        self._evidence("ev-sub", "doc-prelim", "Memória descritiva e painéis A1.")
                    ],
                )
            },
            confidence=0.88,
        )

        consolidated = consolidate_reader_results(
            [prelim_financial, ce_financial, award, submission],
            source_documents=[prelim_document, ce_document],
        )

        document_index = {}
        for item in consolidated.document_index:
            payload = item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            document_index[payload["document_id"]] = payload
        information_model = {}
        for item in consolidated.information_model:
            payload = item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            information_model[payload["field_name"]] = payload

        self.assertEqual(
            document_index["doc-prelim"]["document_category"],
            "Programa Preliminar",
        )
        self.assertEqual(
            document_index["doc-prelim"]["lifecycle_phase"],
            "submission",
        )
        self.assertGreater(
            document_index["doc-prelim"]["document_priority"],
            document_index["doc-ce"]["document_priority"],
        )

        self.assertIn("prices.estimated_construction_cost", information_model)
        self.assertEqual(
            information_model["prices.estimated_construction_cost"]["source_document"],
            "ANEXO I - Programa Preliminar ES LUMIAR.pdf",
        )
        self.assertEqual(
            information_model["prices.estimated_construction_cost"]["phase"],
            "submission",
        )
        self.assertEqual(
            information_model["prices.estimated_construction_cost"]["purpose"],
            "preparar candidatura",
        )
        self.assertEqual(
            information_model["prices.estimated_construction_cost"]["document_category"],
            "Programa Preliminar",
        )
        self.assertIn("prices.procedure_value", information_model)
        self.assertEqual(
            information_model["prices.procedure_value"]["phase"],
            "contract_execution",
        )
        self.assertEqual(
            information_model["prices.procedure_value"]["purpose"],
            "execução do contrato",
        )
        submission_items = information_model["administrative_documents"]["value"]
        submission_labels = {
            item["value"]["text"] if isinstance(item.get("value"), dict) else item.get("value")
            for item in submission_items
        }
        self.assertIn("Memória descritiva", submission_labels)
        self.assertIn("Painéis A1", submission_labels)


class LLMOrchestratorTests(unittest.TestCase):
    def _evidence(
        self,
        evidence_id: str,
        source_document_id: str,
        excerpt: str,
    ) -> Evidence:
        return Evidence(
            evidence_id=evidence_id,
            source_document_id=source_document_id,
            filename=f"{source_document_id}.pdf",
            page=2,
            section="artigo 1",
            excerpt=excerpt,
            confidence=0.9,
            status=EvidenceStatus.CONFIRMED,
        )

    def _competition(self, quality: str = "complete") -> ConsolidatedCompetitionData:
        procedure_evidence = self._evidence("ev-proc", "doc-proc", "Objeto e prazo")
        award_evidence = self._evidence("ev-award", "doc-award", "Critério de adjudicação")
        financial_evidence = self._evidence("ev-fin", "doc-fin", "Preço dos serviços")
        team_evidence = self._evidence("ev-team", "doc-team", "Equipa mínima")
        alert_evidence = self._evidence("ev-alert", "doc-alert", "Aviso documental")

        return ConsolidatedCompetitionData(
            document_quality=quality,
            quality_report={
                "documents_official": 4,
                "documents_read": 4,
                "documents_ignored": 0,
                "conflicts": 0,
                "fields_filled": 6,
                "fields_empty": 2,
                "confidence_global": 0.842,
            },
            procedure_identity={
                "object": {
                    "field": "object",
                    "kind": "scalar",
                    "value": "Requalificacao da Escola Secundaria do Lumiar",
                    "normalized_value": "Requalificacao da Escola Secundaria do Lumiar",
                    "confidence": 0.93,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [procedure_evidence],
                    "source_readers": ["procedure_reader"],
                    "document_ids": ["doc-proc"],
                },
                "contracting_entity": {
                    "field": "contracting_entity",
                    "kind": "scalar",
                    "value": "Municipio de Lisboa",
                    "normalized_value": "Municipio de Lisboa",
                    "confidence": 0.9,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [procedure_evidence],
                    "source_readers": ["procedure_reader"],
                    "document_ids": ["doc-proc"],
                },
                "submission_deadline": {
                    "field": "submission_deadline",
                    "kind": "scalar",
                    "value": "2026-09-01",
                    "normalized_value": "2026-09-01",
                    "confidence": 0.88,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [procedure_evidence],
                    "source_readers": ["procedure_reader"],
                    "document_ids": ["doc-proc"],
                },
                "execution_period": {
                    "field": "execution_period",
                    "kind": "scalar",
                    "value": "180 dias",
                    "normalized_value": "180 dias",
                    "confidence": 0.85,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [procedure_evidence],
                    "source_readers": ["procedure_reader"],
                    "document_ids": ["doc-proc"],
                },
            },
            prices={
                "design_services_value": {
                    "field": "design_services_value",
                    "kind": "scalar",
                    "value": 1221957.0,
                    "normalized_value": 1221957.0,
                    "confidence": 0.91,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [financial_evidence],
                    "source_readers": ["financial_reader"],
                    "document_ids": ["doc-fin"],
                },
                "estimated_construction_cost": {
                    "field": "estimated_construction_cost",
                    "kind": "scalar",
                    "value": 24439134.0,
                    "normalized_value": 24439134.0,
                    "confidence": 0.9,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [financial_evidence],
                    "source_readers": ["financial_reader"],
                    "document_ids": ["doc-fin"],
                },
            },
            award_strategy={
                "award_criterion": {
                    "field": "award_criterion",
                    "kind": "scalar",
                    "value": "Proposta economicamente mais vantajosa",
                    "normalized_value": "Proposta economicamente mais vantajosa",
                    "confidence": 0.89,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [award_evidence],
                    "source_readers": ["award_reader"],
                    "document_ids": ["doc-award"],
                },
                "factors": {
                    "field": "factors",
                    "kind": "list",
                    "value": [{"value": "Qualidade arquitetonica", "normalized_value": "qualidade"}],
                    "normalized_value": ["qualidade"],
                    "confidence": 0.87,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [award_evidence],
                    "source_readers": ["award_reader"],
                    "document_ids": ["doc-award"],
                },
            },
            required_team=[
                {
                    "field": "coordinator",
                    "kind": "scalar",
                    "value": {
                        "role": "arquiteto",
                        "minimum_years": 5,
                    },
                    "normalized_value": {
                        "role": "arquiteto",
                        "minimum_years": 5,
                    },
                    "confidence": 0.92,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [team_evidence],
                    "source_readers": ["team_reader"],
                    "document_ids": ["doc-team"],
                }
            ],
            phases_and_deliverables=[],
            submission_checklist={"administrative": [], "technical": [], "financial": [], "team": [], "post_award": []},
            drawing_rules=[],
            financial_conditions={
                "insurance": {
                    "field": "insurance",
                    "kind": "scalar",
                    "value": True,
                    "normalized_value": True,
                    "confidence": 0.8,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [financial_evidence],
                    "source_readers": ["financial_reader"],
                    "document_ids": ["doc-fin"],
                },
                "penalties": {
                    "field": "penalties",
                    "kind": "scalar",
                    "value": "1% por dia",
                    "normalized_value": "1% por dia",
                    "confidence": 0.8,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [financial_evidence],
                    "source_readers": ["financial_reader"],
                    "document_ids": ["doc-fin"],
                },
            },
            technical_constraints=[],
            exclusion_risks=[
                {
                    "field": "exclusion_risks",
                    "kind": "list",
                    "value": [{"value": "Falta de coordenador"}],
                    "normalized_value": ["falta de coordenador"],
                    "confidence": 0.77,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [team_evidence],
                    "source_readers": ["team_reader"],
                    "document_ids": ["doc-team"],
                }
            ],
            document_alerts=[
                {
                    "field": "document_alerts",
                    "kind": "list",
                    "value": [{"value": "Aviso documental"}],
                    "normalized_value": ["aviso documental"],
                    "confidence": 0.7,
                    "conflict": False,
                    "alternatives": [],
                    "evidences": [alert_evidence],
                    "source_readers": ["procedure_reader"],
                    "document_ids": ["doc-alert"],
                }
            ],
            evidences=[procedure_evidence, award_evidence, financial_evidence, team_evidence, alert_evidence],
            sources=[{"reader_name": "procedure_reader", "document_ids": ["doc-proc"]}],
            warnings=["Aviso documental"],
        )

    def test_orchestrates_short_cards_with_evidence_refs(self) -> None:
        competition = self._competition()

        result = orchestrate_competition(competition)

        self.assertIn("Requalificacao da Escola Secundaria do Lumiar", result.executive_summary)
        self.assertGreaterEqual(len(result.cards), 4)
        self.assertTrue(all(card.text for card in result.cards))
        self.assertTrue(all("..." not in card.text for card in result.cards))
        self.assertTrue(all(card.evidence_refs for card in result.cards))
        self.assertEqual(result.document_confidence["document_quality"], "complete")
        self.assertEqual(result.document_confidence["global_confidence"], 0.842)

    def test_uses_not_found_when_information_is_missing(self) -> None:
        competition = ConsolidatedCompetitionData(
            document_quality="insufficient",
            quality_report={
                "documents_official": 0,
                "documents_read": 0,
                "documents_ignored": 0,
                "conflicts": 0,
                "fields_filled": 0,
                "fields_empty": 0,
                "confidence_global": 0.0,
            },
        )

        result = LLMOrchestrator().orchestrate(competition)

        self.assertEqual(result.executive_summary, "Not Found")
        self.assertEqual(result.go_no_go.decision, "no_go")
        self.assertEqual(result.cards[0].text, "Not Found")

    def test_go_no_go_changes_with_document_quality(self) -> None:
        complete = self._competition("complete")
        partial = self._competition("partial")

        complete_result = LLMOrchestrator().orchestrate(complete)
        partial_result = LLMOrchestrator().orchestrate(partial)

        self.assertEqual(complete_result.go_no_go.decision, "go")
        self.assertEqual(partial_result.go_no_go.decision, "review")


if __name__ == "__main__":
    unittest.main()
