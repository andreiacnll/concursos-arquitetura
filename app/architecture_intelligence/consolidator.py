from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .schemas import (
    ClassifiedDocument,
    DocumentClassification,
    ConsolidatedCompetitionData,
    Evidence,
    EvidenceStatus,
    ExtractedField,
    InformationItem,
    ReaderResult,
    SourceDocument,
)
from .document_classifier import classify_document
from .knowledge_router import get_default_router


PROCEDURE_FIELDS = (
    "object",
    "contracting_entity",
    "procedure_type",
    "cpv",
    "submission_deadline",
    "execution_period",
    "location",
    "reference",
)

PRICES_FIELDS = (
    "competition_prizes",
    "procedure_value",
    "design_services_value",
    "estimated_construction_cost",
)

FINANCIAL_CONDITIONS_FIELDS = (
    "bond",
    "insurance",
    "penalties",
    "price_revision",
    "notes",
)

AWARD_FIELDS = (
    "award_criterion",
    "evaluation_model",
    "price_weight",
    "technical_weight",
    "factors",
    "subfactors",
    "maximum_score_requirements",
    "tie_break_rules",
    "abnormally_low_price_rule",
)

TEAM_FIELDS = (
    "coordinator",
    "minimum_team",
    "required_specializations",
    "professional_requirements",
    "experience_requirements",
    "certifications",
    "consultants",
    "exclusionary_team_requirements",
    "scored_team_requirements",
)

LIST_FIELDS = {
    "competition_prizes",
    "payments_by_phase",
    "phases",
    "deliverables_by_phase",
    "minimum_team",
    "required_specializations",
    "professional_requirements",
    "experience_requirements",
    "certifications",
    "consultants",
    "exclusionary_team_requirements",
    "scored_team_requirements",
    "administrative_documents",
    "technical_documents",
    "financial_documents",
    "team_documents",
    "post_award_documents",
    "drawing_requirements",
    "digital_formats",
    "physical_formats",
    "scale_requirements",
    "validation_requirements",
    "assistance_requirements",
    "insurance",
    "penalties",
    "price_revision",
    "notes",
    "factors",
    "subfactors",
    "maximum_score_requirements",
    "tie_break_rules",
    "drawing_rules",
    "technical_constraints",
    "exclusion_risks",
    "document_alerts",
}


@dataclass(slots=True)
class _FieldCandidate:
    field_name: str
    reader_name: str
    document_ids: list[str]
    value: Any
    normalized_value: Any
    confidence: float
    evidences: list[Evidence]
    specificity: int


class Consolidator:
    def consolidate(
        self,
        reader_results: list[ReaderResult],
        source_documents: list[SourceDocument] | None = None,
    ) -> ConsolidatedCompetitionData:
        results = list(reader_results or [])
        source_documents = list(source_documents or [])
        buckets: dict[str, dict[str, list[_FieldCandidate]]] = {
            "procedure_identity": defaultdict(list),
            "prices": defaultdict(list),
            "award_strategy": defaultdict(list),
            "required_team": defaultdict(list),
            "phases_and_deliverables": defaultdict(list),
            "submission_checklist": defaultdict(list),
            "financial_conditions": defaultdict(list),
            "drawing_rules": defaultdict(list),
            "technical_constraints": defaultdict(list),
            "exclusion_risks": defaultdict(list),
            "document_alerts": defaultdict(list),
        }
        warnings: list[str] = []
        sources: list[dict[str, Any]] = []
        all_evidences: list[Evidence] = []
        unique_docs: set[str] = set()
        document_index = self._build_document_index(source_documents)

        for result in results:
            unique_docs.update(result.document_ids)
            warnings.extend(result.warnings)
            sources.append(
                {
                    "reader_name": result.reader_name,
                    "document_ids": list(result.document_ids),
                    "fields": len(result.fields),
                    "confidence": result.confidence,
                    "warnings": list(result.warnings),
                    "evidence_count": len(result.evidences),
                }
            )
            all_evidences.extend(result.evidences)

            for field_name, field in result.fields.items():
                section = self._field_section(field_name)
                if section is None:
                    continue
                candidate = self._to_candidate(result, field_name, field)
                if candidate is None:
                    continue
                buckets[section][field_name].append(candidate)
                all_evidences.extend(field.evidences)

        procedure_identity = self._build_section_dict(
            buckets["procedure_identity"],
            PROCEDURE_FIELDS,
        )
        prices = self._build_prices_section(buckets["prices"])
        award_strategy = self._build_section_dict(
            buckets["award_strategy"],
            AWARD_FIELDS,
        )
        required_team = self._build_section_list(
            buckets["required_team"],
            TEAM_FIELDS,
        )
        phases_and_deliverables = self._build_phases_section(
            buckets["phases_and_deliverables"],
        )
        submission_checklist = self._build_submission_checklist(
            buckets["submission_checklist"],
        )
        drawing_rules = self._build_section_list(
            buckets["drawing_rules"],
        )
        financial_conditions = self._build_section_dict(
            buckets["financial_conditions"],
            FINANCIAL_CONDITIONS_FIELDS,
        )
        technical_constraints = self._build_section_list(
            buckets["technical_constraints"],
        )
        exclusion_risks = self._build_section_list(
            buckets["exclusion_risks"],
        )
        document_alerts = self._build_document_alerts(
            results=results,
            alert_candidates=buckets["document_alerts"],
        )

        conflict_count = sum(
            self._count_conflicts(section)
            for section in (
                procedure_identity,
                prices,
                award_strategy,
                required_team,
                phases_and_deliverables,
                submission_checklist,
                drawing_rules,
                financial_conditions,
                technical_constraints,
                exclusion_risks,
                document_alerts,
            )
        )

        quality_report = self._quality_report(
            unique_docs=unique_docs,
            conflict_count=conflict_count,
            procedure_identity=procedure_identity,
            prices=prices,
            award_strategy=award_strategy,
            required_team=required_team,
            phases_and_deliverables=phases_and_deliverables,
            submission_checklist=submission_checklist,
            drawing_rules=drawing_rules,
            financial_conditions=financial_conditions,
            technical_constraints=technical_constraints,
            exclusion_risks=exclusion_risks,
            document_alerts=document_alerts,
        )

        document_quality = self._document_quality(
            procedure_identity=procedure_identity,
            prices=prices,
            award_strategy=award_strategy,
            required_team=required_team,
            phases_and_deliverables=phases_and_deliverables,
            submission_checklist=submission_checklist,
            drawing_rules=drawing_rules,
            technical_constraints=technical_constraints,
            exclusion_risks=exclusion_risks,
            quality_report=quality_report,
        )
        information_model = self._build_information_model(
            procedure_identity=procedure_identity,
            prices=prices,
            award_strategy=award_strategy,
            required_team=required_team,
            phases_and_deliverables=phases_and_deliverables,
            submission_checklist=submission_checklist,
            drawing_rules=drawing_rules,
            financial_conditions=financial_conditions,
            technical_constraints=technical_constraints,
            exclusion_risks=exclusion_risks,
            document_alerts=document_alerts,
            document_index=document_index,
        )

        knowledge_intents = get_default_router().group_by_intent(
            information_model
        )

        return ConsolidatedCompetitionData(
            document_quality=document_quality,
            quality_report=quality_report,
            document_index=document_index,
            information_model=information_model,
            knowledge_intents=knowledge_intents,
            procedure_identity=procedure_identity,
            prices=prices,
            award_strategy=award_strategy,
            required_team=required_team,
            phases_and_deliverables=phases_and_deliverables,
            submission_checklist=submission_checklist,
            drawing_rules=drawing_rules,
            financial_conditions=financial_conditions,
            technical_constraints=technical_constraints,
            exclusion_risks=exclusion_risks,
            document_alerts=document_alerts,
            evidences=self._dedupe_evidences(all_evidences),
            sources=sources,
            warnings=self._dedupe_strings(
                warnings + self._conflict_warnings(conflict_count)
            ),
        )

    def _build_document_index(self, source_documents: list[SourceDocument]) -> list[dict[str, Any]]:
        index: list[dict[str, Any]] = []
        for source in source_documents:
            classified = classify_document(source)
            index.append(
                DocumentClassification(
                    document_id=source.document_id,
                    filename=source.filename,
                    document_category=classified.document_category,
                    lifecycle_phase=classified.lifecycle_phase,
                    lifecycle_purpose=classified.lifecycle_purpose,
                    document_type=classified.document_type.value,
                    confidence=classified.confidence,
                    document_priority=classified.document_priority,
                    reasons=list(classified.reasons),
                    source_role=source.source_role,
                    source_url=self._source_url(source),
                ).model_dump(mode="json")
            )
        index.sort(
            key=lambda item: (
                -int(item.get("document_priority") or 0),
                item.get("document_category") or "",
                item.get("filename") or "",
            )
        )
        return index

    def _build_information_model(
        self,
        *,
        procedure_identity: dict[str, Any],
        prices: dict[str, Any],
        award_strategy: dict[str, Any],
        required_team: list[dict[str, Any]],
        phases_and_deliverables: list[dict[str, Any]],
        submission_checklist: dict[str, list[dict[str, Any]]],
        drawing_rules: list[dict[str, Any]],
        financial_conditions: dict[str, Any],
        technical_constraints: list[dict[str, Any]],
        exclusion_risks: list[dict[str, Any]],
        document_alerts: list[dict[str, Any]],
        document_index: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        lookup = self._document_lookup(document_index)
        items: list[dict[str, Any]] = []
        sections = {
            "procedure_identity": procedure_identity,
            "prices": prices,
            "award_strategy": award_strategy,
            "required_team": required_team,
            "phases_and_deliverables": phases_and_deliverables,
            "submission_checklist": submission_checklist,
            "drawing_rules": drawing_rules,
            "financial_conditions": financial_conditions,
            "technical_constraints": technical_constraints,
            "exclusion_risks": exclusion_risks,
            "document_alerts": document_alerts,
        }
        for section_name, section_value in sections.items():
            items.extend(self._information_items_for_section(section_name, section_value, lookup))
        return self._dedupe_information_items(items)

    def _information_items_for_section(
        self,
        section_name: str,
        section_value: Any,
        document_lookup: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if isinstance(section_value, dict):
            return self._information_items_from_mapping(section_name, section_value, document_lookup)
        if isinstance(section_value, list):
            items: list[dict[str, Any]] = []
            for item in section_value:
                if isinstance(item, dict):
                    items.extend(self._information_items_from_mapping(section_name, item, document_lookup))
                else:
                    text = self._clean_text(item)
                    if text:
                        items.append(
                            self._information_item(
                                field_name=section_name,
                                value=text,
                                normalized_value=self._signature(item),
                                section_name=section_name,
                                evidence_source=item,
                                document_lookup=document_lookup,
                            )
                        )
            return items
        text = self._clean_text(section_value)
        if not text:
            return []
        return [
            self._information_item(
                field_name=section_name,
                value=text,
                normalized_value=self._signature(section_value),
                section_name=section_name,
                evidence_source=section_value,
                document_lookup=document_lookup,
            )
        ]

    def _information_items_from_mapping(
        self,
        section_name: str,
        mapping: dict[str, Any],
        document_lookup: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        metadata_keys = {
            "field",
            "kind",
            "confidence",
            "conflict",
            "alternatives",
            "evidences",
            "source_readers",
            "document_ids",
            "payments",
            "normalized_value",
            "value",
        }
        if mapping.get("field") and "value" in mapping:
            items.append(
                self._information_item(
                    field_name=str(mapping.get("field") or section_name),
                    value=mapping.get("value"),
                    normalized_value=mapping.get("normalized_value"),
                    section_name=section_name,
                    evidence_source=mapping,
                    document_lookup=document_lookup,
                )
            )
            return items
        for key, value in mapping.items():
            if key in metadata_keys:
                continue
            if isinstance(value, dict) and "value" in value and "confidence" in value:
                items.append(
                    self._information_item(
                        field_name=f"{section_name}.{key}",
                        value=value.get("value"),
                        normalized_value=value.get("normalized_value"),
                        section_name=section_name,
                        evidence_source=value,
                        document_lookup=document_lookup,
                    )
                )
                continue
            if isinstance(value, list):
                for index, child in enumerate(value):
                    if isinstance(child, dict):
                        items.extend(
                            self._information_items_from_mapping(
                                f"{section_name}.{key}",
                                child,
                                document_lookup,
                            )
                        )
                    else:
                        text = self._clean_text(child)
                        if text:
                            items.append(
                                self._information_item(
                                    field_name=f"{section_name}.{key}",
                                    value=text,
                                    normalized_value=self._signature(child),
                                    section_name=section_name,
                                    evidence_source=mapping,
                                    document_lookup=document_lookup,
                                )
                            )
                continue
            if self._has_content(value):
                items.append(
                    self._information_item(
                        field_name=f"{section_name}.{key}",
                        value=value,
                        normalized_value=self._signature(value),
                        section_name=section_name,
                        evidence_source=mapping,
                        document_lookup=document_lookup,
                    )
                )
        return items

    def _information_item(
        self,
        *,
        field_name: str,
        value: Any,
        normalized_value: Any,
        section_name: str,
        evidence_source: Any,
        document_lookup: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        evidence_refs = self._dedupe_evidences(self._extract_evidences(evidence_source))
        document = self._resolve_information_source(evidence_refs, evidence_source, document_lookup)
        phase, purpose = self._information_lifecycle(field_name, section_name, document)
        knowledge_block = self._knowledge_block(
            field_name,
            section_name,
            phase,
        )
        source_document = document.get("filename") or self._best_source_document_name(evidence_refs, evidence_source, document_lookup)
        source_document_id = document.get("document_id") or self._best_source_document_id(evidence_refs, evidence_source)
        confidence = self._information_confidence(evidence_source, evidence_refs, document)
        return InformationItem(
            field_name=field_name,
            value=value,
            normalized_value=normalized_value if normalized_value is not None else value,
            knowledge_block=knowledge_block,
            phase=phase,
            purpose=purpose,
            source_document=source_document,
            source_document_id=source_document_id,
            document_category=document.get("document_category") or "Outros",
            confidence=confidence,
            evidence_ids=[evidence.evidence_id for evidence in evidence_refs],
            document_priority=int(document.get("document_priority") or 0),
            reader_name=self._source_readers(evidence_source),
            section=section_name,
        ).model_dump(mode="json")

    def _information_lifecycle(
        self,
        field_name: str,
        section_name: str,
        document: dict[str, Any],
    ) -> tuple[str, str]:
        category = document.get("document_category") or "Outros"
        normalized = self._normalize_text(
            f"{section_name}.{field_name}"
        )

        submission_tokens = (
            "submission_deliverables",
            "drawing_requirements",
            "drawing_rules",
            "technical_documents",
            "panel",
            "painel",
            "memoria descritiva",
            "descriptive memory",
            "maquete",
            "model",
            "video",
            "anonymous",
            "anonimato",
            "proposal",
            "proposta tecnica",
        )

        evaluation_tokens = (
            "award_criterion",
            "evaluation_model",
            "factors",
            "subfactors",
            "price_weight",
            "technical_weight",
            "maximum_score",
            "tie_break",
            "jury",
            "juri",
        )

        administrative_tokens = (
            "administrative_documents",
            "financial_documents",
            "team_documents",
            "signature",
            "platform",
            "formulario",
            "formul",
            "habilitation",
            "habilitacao",
            "declaration",
            "declaracao",
            "document_alerts",
        )

        contract_tokens = (
            "contract_deliverables",
            "execution_project",
            "projeto de execucao",
            "anteprojeto",
            "estudo previo",
            "technical_assistance",
            "assistencia tecnica",
            "measurements",
            "medicoes",
            "final_drawings",
            "telas finais",
            "payments_by_phase",
            "financial_conditions",
            "contract_scope",
        )

        # O significado espec?fico do campo tem prioridade.
        if any(token in normalized for token in evaluation_tokens):
            return "evaluation", "avaliação do júri"

        if any(token in normalized for token in submission_tokens):
            return "submission", "preparar candidatura"

        if any(token in normalized for token in administrative_tokens):
            return "administrative", "obrigação administrativa"

        if any(token in normalized for token in contract_tokens):
            return "contract_execution", "execução do contrato"

        # S? depois usamos o papel geral do documento.
        if category in {
            "Caderno de Encargos",
            "Condições Técnicas",
            "Minuta do Contrato",
        }:
            return "contract_execution", "execução do contrato"

        if category in {
            "Programa Preliminar",
            "Programa do Concurso",
            "Regulamento",
        }:
            return "submission", "preparar candidatura"

        if section_name == "award_strategy":
            return "evaluation", "avaliação do júri"

        if section_name == "submission_checklist":
            return "administrative", "obrigação administrativa"

        return "submission", "preparar candidatura"

    def _knowledge_block(
        self,
        field_name: str,
        section_name: str,
        phase: str,
    ) -> str:
        normalized = self._normalize_text(
            f"{section_name}.{field_name}"
        )

        if (
            "competition_prizes" in normalized
            or "prize" in normalized
            or "premio" in normalized
        ):
            return "awards"

        if "jury" in normalized or "juri" in normalized:
            return "jury"

        if section_name == "award_strategy":
            return "evaluation"

        if "estimated_construction_cost" in normalized:
            return "financials"

        if section_name == "prices":
            return "financials"

        if section_name == "procedure_identity":
            return "competition_identity"

        if section_name == "required_team":
            return "team"

        if section_name == "exclusion_risks":
            return "risks"

        if section_name == "document_alerts":
            return "administrative"

        if section_name == "submission_checklist":
            if "technical" in normalized:
                return "submission_documents"
            return "administrative"

        submission_tokens = (
            "panel",
            "painel",
            "memoria descritiva",
            "drawing",
            "maquete",
            "video",
            "proposal",
            "proposta",
        )

        if any(token in normalized for token in submission_tokens):
            return "submission_deliverables"

        contract_tokens = (
            "execution_project",
            "projeto de execucao",
            "anteprojeto",
            "estudo previo",
            "technical_assistance",
            "assistencia tecnica",
            "measurements",
            "medicoes",
            "final_drawings",
            "telas finais",
        )

        if any(token in normalized for token in contract_tokens):
            return "contract_deliverables"

        if section_name == "phases_and_deliverables":
            if phase == "submission":
                return "submission_deliverables"
            return "contract_deliverables"

        if section_name == "financial_conditions":
            return "financials"

        if section_name == "technical_constraints":
            return "contract_scope"

        if section_name == "drawing_rules":
            if phase == "submission":
                return "submission_deliverables"
            return "contract_deliverables"

        return "other"

    def _information_confidence(self, evidence_source: Any, evidence_refs: list[Evidence], document: dict[str, Any]) -> float:
        values = []
        if isinstance(evidence_source, dict):
            for key in ("confidence",):
                if self._has_content(evidence_source.get(key)):
                    try:
                        values.append(float(evidence_source.get(key)))
                    except (TypeError, ValueError):
                        pass
        if evidence_refs:
            values.append(max(float(evidence.confidence or 0.0) for evidence in evidence_refs))
        if document.get("confidence") is not None:
            try:
                values.append(float(document.get("confidence")))
            except (TypeError, ValueError):
                pass
        return round(max(values) if values else 0.0, 3)

    def _resolve_information_source(
        self,
        evidence_refs: list[Evidence],
        evidence_source: Any,
        document_lookup: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        for evidence in evidence_refs:
            if evidence.source_document_id and evidence.source_document_id in document_lookup:
                return document_lookup[evidence.source_document_id]
            filename_key = self._normalize_text(evidence.filename)
            if filename_key and filename_key in document_lookup:
                return document_lookup[filename_key]
        document_id = self._best_source_document_id(evidence_refs, evidence_source)
        if document_id and document_id in document_lookup:
            return document_lookup[document_id]
        return {}

    def _best_source_document_id(self, evidence_refs: list[Evidence], evidence_source: Any) -> str:
        if isinstance(evidence_source, dict):
            document_ids = evidence_source.get("document_ids") or []
            if document_ids:
                return str(document_ids[0])
        for evidence in evidence_refs:
            if evidence.source_document_id:
                return evidence.source_document_id
        return ""

    def _best_source_document_name(self, evidence_refs: list[Evidence], evidence_source: Any, document_lookup: dict[str, dict[str, Any]]) -> str:
        document_id = self._best_source_document_id(evidence_refs, evidence_source)
        if document_id and document_id in document_lookup:
            return str(document_lookup[document_id].get("filename") or "")
        for evidence in evidence_refs:
            if evidence.filename:
                return evidence.filename
        return ""

    def _document_lookup(self, document_index: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for item in document_index:
            document_id = self._normalize_text(str(item.get("document_id") or ""))
            filename = self._normalize_text(str(item.get("filename") or ""))
            if document_id:
                lookup[document_id] = item
            if filename:
                lookup[filename] = item
        return lookup

    def _source_url(self, source: SourceDocument) -> str:
        for key in ("source_url", "platform_url", "url", "external_id"):
            value = source.metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _extract_evidences(self, value: Any) -> list[Evidence]:
        evidences: list[Evidence] = []
        if isinstance(value, dict):
            raw = value.get("evidences")
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, Evidence):
                        evidences.append(item)
                    elif isinstance(item, dict):
                        try:
                            evidences.append(Evidence.model_validate(item))
                        except Exception:
                            continue
            for child in value.values():
                evidences.extend(self._extract_evidences(child))
        elif isinstance(value, list):
            for child in value:
                evidences.extend(self._extract_evidences(child))
        elif isinstance(value, Evidence):
            evidences.append(value)
        return self._dedupe_evidences(evidences)

    def _source_readers(self, value: Any) -> str:
        if isinstance(value, dict):
            readers = value.get("source_readers")
            if isinstance(readers, list):
                return ", ".join(str(item) for item in self._dedupe_strings([str(item) for item in readers]))
        return ""

    def _dedupe_information_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for item in items:
            signature = self._normalize_text(
                f"{item.get('field_name')}::{item.get('source_document_id')}::{item.get('normalized_value')}"
            )
            if not signature or signature in seen:
                continue
            seen.add(signature)
            result.append(item)
        result.sort(
            key=lambda item: (
                self._phase_rank(str(item.get("phase") or "")),
                -int(item.get("document_priority") or 0),
                str(item.get("source_document") or ""),
                str(item.get("field_name") or ""),
            )
        )
        return result

    def _phase_rank(self, phase: str) -> int:
        order = {
            "submission": 0,
            "evaluation": 1,
            "contract_execution": 2,
            "administrative": 3,
        }
        return order.get(phase, 9)

    def _field_section(self, field_name: str) -> str | None:
        if field_name in PROCEDURE_FIELDS:
            return "procedure_identity"
        if field_name in PRICES_FIELDS:
            return "prices"
        if field_name in AWARD_FIELDS:
            return "award_strategy"
        if field_name in TEAM_FIELDS:
            return "required_team"
        if field_name in {"phases", "deliverables_by_phase", "payments_by_phase"}:
            return "phases_and_deliverables"
        if field_name in {
            "administrative_documents",
            "technical_documents",
            "financial_documents",
            "team_documents",
            "post_award_documents",
        }:
            return "submission_checklist"
        if field_name in {
            "drawing_requirements",
            "digital_formats",
            "physical_formats",
            "scale_requirements",
            "validation_requirements",
            "assistance_requirements",
            "drawing_rules",
        }:
            return "drawing_rules"
        if field_name in FINANCIAL_CONDITIONS_FIELDS:
            return "financial_conditions"
        if field_name == "technical_constraints":
            return "technical_constraints"
        if field_name == "exclusion_risks":
            return "exclusion_risks"
        if field_name == "document_alerts":
            return "document_alerts"
        return None

    def _to_candidate(
        self,
        result: ReaderResult,
        field_name: str,
        field: ExtractedField,
    ) -> _FieldCandidate | None:
        if field.status == EvidenceStatus.NOT_FOUND and field.value in (None, [], {}):
            return None
        return _FieldCandidate(
            field_name=field_name,
            reader_name=result.reader_name,
            document_ids=list(result.document_ids),
            value=field.value,
            normalized_value=field.normalized_value,
            confidence=float(field.confidence or 0.0),
            evidences=list(field.evidences),
            specificity=self._specificity(result.reader_name, field_name),
        )

    def _specificity(self, reader_name: str, field_name: str) -> int:
        mapping = {
            "procedure_reader": 4,
            "award_reader": 4,
            "financial_reader": 4,
            "team_reader": 4,
        }
        base = mapping.get(reader_name, 1)
        if field_name in PROCEDURE_FIELDS and reader_name == "procedure_reader":
            return base + 2
        if field_name in AWARD_FIELDS and reader_name == "award_reader":
            return base + 2
        if field_name in PRICES_FIELDS and reader_name == "financial_reader":
            return base + 2
        if field_name in TEAM_FIELDS and reader_name == "team_reader":
            return base + 2
        return base

    def _build_section_dict(
        self,
        section_candidates: dict[str, list[_FieldCandidate]],
        field_order: tuple[str, ...],
    ) -> dict[str, Any]:
        section: dict[str, Any] = {}
        for field_name in field_order:
            candidates = section_candidates.get(field_name, [])
            if candidates:
                section[field_name] = self._merge_candidates(field_name, candidates)
        for field_name in sorted(section_candidates):
            if field_name in section:
                continue
            candidates = section_candidates[field_name]
            if candidates:
                section[field_name] = self._merge_candidates(field_name, candidates)
        return section

    def _build_section_list(
        self,
        section_candidates: dict[str, list[_FieldCandidate]],
        field_order: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        ordered_fields = list(field_order or [])
        if not ordered_fields:
            ordered_fields = sorted(section_candidates)
        else:
            seen = set(ordered_fields)
            ordered_fields.extend(
                field_name
                for field_name in sorted(section_candidates)
                if field_name not in seen
            )
        for field_name in ordered_fields:
            candidates = section_candidates.get(field_name, [])
            if candidates:
                entries.append(self._merge_candidates(field_name, candidates))
        return entries

    def _build_prices_section(
        self,
        section_candidates: dict[str, list[_FieldCandidate]],
    ) -> dict[str, Any]:
        prices: dict[str, Any] = {}
        if "competition_prizes" in section_candidates:
            prices["competition_prizes"] = self._merge_candidates(
                "competition_prizes",
                section_candidates["competition_prizes"],
            )
        for field_name in ("procedure_value", "design_services_value", "estimated_construction_cost"):
            candidates = section_candidates.get(field_name, [])
            if candidates:
                prices[field_name] = self._merge_candidates(field_name, candidates)
        return prices

    def _build_phases_section(
        self,
        section_candidates: dict[str, list[_FieldCandidate]],
    ) -> list[dict[str, Any]]:
        variants_by_phase: dict[str, list[dict[str, Any]]] = defaultdict(list)
        ordered_phases: list[str] = []

        for field_name in ("phases", "deliverables_by_phase", "payments_by_phase"):
            for candidate in section_candidates.get(field_name, []):
                for item in self._as_list(candidate.value):
                    if not isinstance(item, dict):
                        item = {"phase": item}
                    phase = self._clean_text(
                        item.get("phase")
                        or item.get("fase")
                        or item.get("name")
                        or "Not Found"
                    )
                    phase_key = self._phase_group_key(phase or "Not Found")
                    if phase_key not in variants_by_phase:
                        ordered_phases.append(phase_key)
                    variants_by_phase[phase_key].append(
                        {
                            "phase": phase or "Not Found",
                            "description": self._clean_text(
                                item.get("description")
                                or item.get("text")
                                or item.get("title")
                                or ""
                            ),
                            "deadline": self._clean_text(item.get("deadline")),
                            "deliverables": self._as_list(item.get("deliverables")),
                            "percentage": self._clean_text(item.get("percentage")),
                            "candidate_confidence": candidate.confidence,
                            "reader_name": candidate.reader_name,
                            "document_ids": list(candidate.document_ids),
                            "evidences": list(candidate.evidences),
                        }
                    )

        phases: list[dict[str, Any]] = []
        for phase_key in ordered_phases:
            phases.append(self._merge_phase_group(variants_by_phase[phase_key]))
        return phases

    def _build_submission_checklist(
        self,
        section_candidates: dict[str, list[_FieldCandidate]],
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            "administrative": self._build_section_list(
                {"administrative_documents": section_candidates.get("administrative_documents", [])},
                ("administrative_documents",),
            ),
            "technical": self._build_section_list(
                {"technical_documents": section_candidates.get("technical_documents", [])},
                ("technical_documents",),
            ),
            "financial": self._build_section_list(
                {"financial_documents": section_candidates.get("financial_documents", [])},
                ("financial_documents",),
            ),
            "team": self._build_section_list(
                {"team_documents": section_candidates.get("team_documents", [])},
                ("team_documents",),
            ),
            "post_award": self._build_section_list(
                {"post_award_documents": section_candidates.get("post_award_documents", [])},
                ("post_award_documents",),
            ),
        }

    def _merge_candidates(
        self,
        field_name: str,
        candidates: list[_FieldCandidate],
    ) -> dict[str, Any]:
        grouped: dict[str, list[_FieldCandidate]] = defaultdict(list)
        for candidate in candidates:
            signature = self._signature(
                candidate.normalized_value if candidate.normalized_value is not None else candidate.value
            )
            grouped[signature].append(candidate)

        selected_group = self._best_group(list(grouped.values()))
        selected_candidate = self._best_candidate(selected_group)
        alternatives: list[dict[str, Any]] = []

        if field_name in LIST_FIELDS:
            merged_items, item_confidence, item_conflict = self._merge_list_items(candidates)
            return {
                "field": field_name,
                "kind": "list",
                "value": merged_items,
                "normalized_value": [item["normalized_value"] for item in merged_items],
                "confidence": item_confidence,
                "conflict": item_conflict or len(grouped) > 1,
                "alternatives": self._group_alternatives(grouped, selected_group),
                "evidences": self._dedupe_evidences(
                    evidence
                    for candidate in candidates
                    for evidence in candidate.evidences
                ),
                "source_readers": self._dedupe_strings(
                    [candidate.reader_name for candidate in candidates]
                ),
                "document_ids": self._dedupe_strings(
                    [doc for candidate in candidates for doc in candidate.document_ids]
                ),
            }

        for group in grouped.values():
            if group is selected_group:
                continue
            best = self._best_candidate(group)
            alternatives.append(
                {
                    "value": best.value,
                    "normalized_value": best.normalized_value,
                    "confidence": best.confidence,
                    "reader_name": best.reader_name,
                    "document_ids": list(best.document_ids),
                    "evidences": self._dedupe_evidences(best.evidences),
                }
            )

        return {
            "field": field_name,
            "kind": "scalar",
            "value": selected_candidate.value,
            "normalized_value": selected_candidate.normalized_value,
            "confidence": selected_candidate.confidence,
            "conflict": len(grouped) > 1,
            "alternatives": alternatives,
            "evidences": self._dedupe_evidences(
                evidence
                for candidate in candidates
                for evidence in candidate.evidences
            ),
            "source_readers": self._dedupe_strings(
                [candidate.reader_name for candidate in candidates]
            ),
            "document_ids": self._dedupe_strings(
                [doc for candidate in candidates for doc in candidate.document_ids]
            ),
        }

    def _merge_list_items(
        self,
        candidates: list[_FieldCandidate],
    ) -> tuple[list[dict[str, Any]], float, bool]:
        items: dict[str, dict[str, Any]] = {}
        item_confidences: dict[str, float] = {}
        item_evidences: dict[str, list[Evidence]] = defaultdict(list)
        item_readers: dict[str, list[str]] = defaultdict(list)
        item_documents: dict[str, list[str]] = defaultdict(list)

        for candidate in candidates:
            for item in self._as_list(candidate.value):
                signature = self._signature(item)
                if signature not in items:
                    items[signature] = {
                        "value": self._normalize_item(item),
                        "normalized_value": signature,
                        "confidence": candidate.confidence,
                    }
                item_confidences[signature] = max(
                    item_confidences.get(signature, 0.0),
                    candidate.confidence,
                )
                item_evidences[signature].extend(candidate.evidences)
                item_readers[signature].append(candidate.reader_name)
                item_documents[signature].extend(candidate.document_ids)

        merged_items: list[dict[str, Any]] = []
        for signature, item in items.items():
            merged_items.append(
                {
                    "value": item["value"],
                    "normalized_value": signature,
                    "confidence": item_confidences.get(signature, item["confidence"]),
                    "evidences": self._dedupe_evidences(item_evidences.get(signature, [])),
                    "source_readers": self._dedupe_strings(item_readers.get(signature, [])),
                    "document_ids": self._dedupe_strings(item_documents.get(signature, [])),
                }
            )

        selected_candidate = self._best_candidate(candidates)
        return merged_items, selected_candidate.confidence, len(candidates) > 1 and len(merged_items) > 1

    def _merge_phase_group(
        self,
        variants: list[dict[str, Any]],
    ) -> dict[str, Any]:
        selected_variant = max(
            variants,
            key=lambda variant: (
                variant.get("candidate_confidence", 0.0),
                len(self._dedupe_evidences(variant.get("evidences", []))),
                len(self._as_list(variant.get("deliverables"))),
            ),
        )
        all_evidences = self._dedupe_evidences(
            evidence
            for variant in variants
            for evidence in variant.get("evidences", [])
        )
        all_readers = self._dedupe_strings(
            [variant.get("reader_name", "") for variant in variants]
        )
        all_documents = self._dedupe_strings(
            [
                doc
                for variant in variants
                for doc in variant.get("document_ids", [])
            ]
        )
        merged_deliverables = self._dedupe_list(
            [
                deliverable
                for variant in variants
                for deliverable in self._as_list(variant.get("deliverables"))
            ]
        )
        merged_payments = self._dedupe_list(
            [
                payment
                for variant in variants
                if variant.get("percentage")
                for payment in [
                    {
                        "phase": variant.get("phase", "Not Found"),
                        "percentage": variant.get("percentage"),
                        "description": variant.get("description", ""),
                    }
                ]
            ]
        )
        deadlines = self._dedupe_strings(
            [variant.get("deadline", "") for variant in variants]
        )
        conflict = len(deadlines) > 1

        alternatives = []
        for variant in variants:
            if variant is selected_variant:
                continue
            alternative_deliverables = self._dedupe_list(
                self._as_list(variant.get("deliverables"))
            )
            alternatives.append(
                {
                    "value": {
                        "phase": variant.get("phase", "Not Found"),
                        "description": variant.get("description", ""),
                        "deadline": variant.get("deadline") or None,
                        "deliverables": alternative_deliverables,
                        "percentage": variant.get("percentage") or None,
                    },
                    "normalized_value": {
                        "phase": self._signature(variant.get("phase", "Not Found")),
                        "description": self._signature(variant.get("description", "")),
                        "deadline": self._signature(variant.get("deadline") or ""),
                        "deliverables": [
                            self._signature(item) for item in alternative_deliverables
                        ],
                        "percentage": self._signature(variant.get("percentage") or ""),
                    },
                    "confidence": variant.get("candidate_confidence", 0.0),
                    "reader_name": variant.get("reader_name", ""),
                    "document_ids": self._dedupe_strings(list(variant.get("document_ids", []))),
                    "evidences": self._dedupe_evidences(variant.get("evidences", [])),
                }
            )

        selected_deliverables = merged_deliverables
        selected_value = {
            "phase": selected_variant.get("phase", "Not Found"),
            "description": selected_variant.get("description", ""),
            "deadline": selected_variant.get("deadline") or None,
            "deliverables": selected_deliverables,
            "percentage": selected_variant.get("percentage") or None,
        }
        return {
            "field": "phases_and_deliverables",
            "kind": "list",
            "value": selected_value,
            "normalized_value": {
                "phase": self._signature(selected_value["phase"]),
                "description": self._signature(selected_value["description"]),
                "deadline": self._signature(selected_value["deadline"] or ""),
                "deliverables": [self._signature(item) for item in selected_deliverables],
                "percentage": self._signature(selected_value["percentage"] or ""),
            },
            "confidence": selected_variant.get("candidate_confidence", 0.0),
            "conflict": conflict,
            "alternatives": alternatives,
            "evidences": all_evidences,
            "source_readers": all_readers,
            "document_ids": all_documents,
            "payments": merged_payments,
        }

    def _group_alternatives(
        self,
        grouped: dict[str, list[_FieldCandidate]],
        selected_group: list[_FieldCandidate],
    ) -> list[dict[str, Any]]:
        alternatives: list[dict[str, Any]] = []
        for group in grouped.values():
            if group is selected_group:
                continue
            best = self._best_candidate(group)
            alternatives.append(
                {
                    "value": best.value,
                    "normalized_value": best.normalized_value,
                    "confidence": best.confidence,
                    "reader_name": best.reader_name,
                    "document_ids": list(best.document_ids),
                    "evidences": self._dedupe_evidences(best.evidences),
                }
            )
        return alternatives

    def _best_group(
        self,
        groups: list[list[_FieldCandidate]],
    ) -> list[_FieldCandidate]:
        return max(
            groups,
            key=lambda group: (
                self._best_candidate(group).confidence,
                len(self._dedupe_evidences(
                    evidence for candidate in group for evidence in candidate.evidences
                )),
                self._best_candidate(group).specificity,
            ),
        )

    def _best_candidate(self, candidates: list[_FieldCandidate]) -> _FieldCandidate:
        return max(
            candidates,
            key=lambda candidate: (
                candidate.confidence,
                len(self._dedupe_evidences(candidate.evidences)),
                candidate.specificity,
            ),
        )

    def _document_quality(
        self,
        *,
        procedure_identity: dict[str, Any],
        prices: dict[str, Any],
        award_strategy: dict[str, Any],
        required_team: list[dict[str, Any]],
        phases_and_deliverables: list[dict[str, Any]],
        submission_checklist: dict[str, list[dict[str, Any]]],
        drawing_rules: list[dict[str, Any]],
        technical_constraints: list[dict[str, Any]],
        exclusion_risks: list[dict[str, Any]],
        quality_report: dict[str, Any],
    ) -> str:
        has_procedure = bool(procedure_identity)
        has_prices = bool(prices)
        has_award = bool(award_strategy)
        has_team = bool(required_team)
        has_other_sections = any(
            section
            for section in (
                phases_and_deliverables,
                submission_checklist.values(),
                drawing_rules,
                technical_constraints,
                exclusion_risks,
                quality_report.get("document_alerts", []),
            )
        )

        if not any((has_procedure, has_prices, has_award, has_team, has_other_sections)):
            return "insufficient"
        if has_procedure and not any((has_prices, has_award, has_team, has_other_sections)):
            return "announcement_only"
        if has_procedure and has_prices and has_award and has_team and quality_report.get("conflicts", 0) == 0:
            return "complete"
        return "partial"

    def _quality_report(
        self,
        *,
        unique_docs: set[str],
        conflict_count: int,
        procedure_identity: dict[str, Any],
        prices: dict[str, Any],
        award_strategy: dict[str, Any],
        required_team: list[dict[str, Any]],
        phases_and_deliverables: list[dict[str, Any]],
        submission_checklist: dict[str, list[dict[str, Any]]],
        drawing_rules: list[dict[str, Any]],
        financial_conditions: dict[str, Any],
        technical_constraints: list[dict[str, Any]],
        exclusion_risks: list[dict[str, Any]],
        document_alerts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        slots = []
        slots.extend(procedure_identity.get(field) for field in PROCEDURE_FIELDS)
        slots.extend(prices.get(field) for field in PRICES_FIELDS)
        slots.extend(award_strategy.get(field) for field in AWARD_FIELDS)
        slots.extend(required_team)
        slots.append(phases_and_deliverables)
        slots.extend(submission_checklist.values())
        slots.append(drawing_rules)
        slots.extend(financial_conditions.get(field) for field in FINANCIAL_CONDITIONS_FIELDS)
        slots.append(technical_constraints)
        slots.append(exclusion_risks)
        slots.append(document_alerts)

        filled = sum(1 for value in slots if self._has_content(value))
        empty = sum(1 for value in slots if not self._has_content(value))
        confidences = [
            item["confidence"]
            for item in self._iterate_entries(
                procedure_identity,
                prices,
                award_strategy,
                required_team,
                phases_and_deliverables,
                submission_checklist,
                financial_conditions,
                drawing_rules,
                technical_constraints,
                exclusion_risks,
                document_alerts,
            )
            if "confidence" in item
        ]
        confidence_global = round(sum(confidences) / len(confidences), 3) if confidences else 0.0
        return {
            "documents_official": len(unique_docs),
            "documents_read": len(unique_docs),
            "documents_ignored": 0,
            "conflicts": conflict_count,
            "fields_filled": filled,
            "fields_empty": empty,
            "confidence_global": confidence_global,
        }

    def _build_document_alerts(
        self,
        *,
        results: list[ReaderResult],
        alert_candidates: dict[str, list[_FieldCandidate]],
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        for result in results:
            for warning in result.warnings:
                alerts.append(
                    {
                        "kind": "warning",
                        "reader_name": result.reader_name,
                        "document_ids": list(result.document_ids),
                        "message": warning,
                    }
                )

        for entry in self._build_section_list(alert_candidates):
            alerts.append(
                {
                    **entry,
                    "kind": "document_alert",
                }
            )

        return self._dedupe_dicts(alerts)

    def _count_conflicts(self, value: Any) -> int:
        if isinstance(value, dict):
            total = 1 if value.get("conflict") else 0
            for child in value.values():
                total += self._count_conflicts(child)
            return total
        if isinstance(value, list):
            return sum(self._count_conflicts(item) for item in value)
        return 0

    def _iterate_entries(self, *sections: Any) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for section in sections:
            if isinstance(section, dict):
                for value in section.values():
                    entries.extend(self._iterate_entries(value))
                if "confidence" in section:
                    entries.append(section)
            elif isinstance(section, list):
                for item in section:
                    entries.extend(self._iterate_entries(item))
        return entries

    def _has_content(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (int, float, bool)):
            return True
        if isinstance(value, list):
            return any(self._has_content(item) for item in value)
        if isinstance(value, dict):
            if "value" in value:
                return self._has_content(value.get("value"))
            return any(self._has_content(item) for item in value.values())
        return bool(value)

    def _as_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return list(value)
        return [value]

    def _clean_text(self, value: Any) -> str:
        return self._normalize_text(str(value or ""))

    def _phase_group_key(self, value: Any) -> str:
        normalized = self._clean_text(value)
        normalized = normalized.replace("fase ", "").replace("etapa ", "")
        normalized = normalized.replace("fase", "").replace("etapa", "")
        normalized = normalized.strip(" .,:;-")
        if not normalized:
            return "not-found"
        match = unicodedata.normalize("NFKD", normalized)
        compact = "".join(
            character
            for character in match
            if not unicodedata.combining(character)
        )
        compact = compact.strip().casefold()
        return compact or "not-found"

    def _dedupe_list(self, values: list[Any]) -> list[Any]:
        seen: set[str] = set()
        result: list[Any] = []
        for value in values:
            signature = self._signature(value)
            if not signature or signature in seen:
                continue
            seen.add(signature)
            result.append(value)
        return result

    def _normalize_item(self, item: Any) -> Any:
        if isinstance(item, dict):
            return dict(item)
        return item

    def _signature(self, value: Any) -> str:
        if isinstance(value, dict):
            return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
        if isinstance(value, list):
            normalized = [self._signature(item) for item in value]
            return json.dumps(normalized, ensure_ascii=False)
        return self._normalize_text(str(value))

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", (value or "").casefold())
        return "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        ).strip()

    def _dedupe_evidences(self, evidences: Any) -> list[Evidence]:
        seen: set[str] = set()
        result: list[Evidence] = []
        for evidence in evidences:
            if not isinstance(evidence, Evidence):
                continue
            if evidence.evidence_id in seen:
                continue
            seen.add(evidence.evidence_id)
            result.append(evidence)
        return result

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = self._normalize_text(str(value))
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(str(value))
        return result

    def _dedupe_dicts(self, values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for value in values:
            signature = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
            if signature in seen:
                continue
            seen.add(signature)
            result.append(value)
        return result

    def _empty_submission_checklist(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "administrative": [],
            "technical": [],
            "financial": [],
            "team": [],
            "post_award": [],
        }

    def _conflict_warnings(self, conflict_count: int) -> list[str]:
        if conflict_count <= 0:
            return []
        return [f"Consolidation detected {conflict_count} conflict(s)."]


def consolidate_reader_results(
    reader_results: list[ReaderResult],
    source_documents: list[SourceDocument] | None = None,
) -> ConsolidatedCompetitionData:
    return Consolidator().consolidate(
        reader_results,
        source_documents=source_documents,
    )
