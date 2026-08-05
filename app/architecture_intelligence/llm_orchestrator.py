from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from .schemas import ConsolidatedCompetitionData, Evidence


class OrchestratedCard(BaseModel):
    title: str
    text: str
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)


class OrchestratedInsight(BaseModel):
    text: str
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)


class GoNoGoDecision(BaseModel):
    decision: str
    reason: str
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)


class LLMOrchestrationResult(BaseModel):
    executive_summary: str
    executive_risks: list[OrchestratedInsight] = Field(default_factory=list)
    executive_opportunities: list[OrchestratedInsight] = Field(default_factory=list)
    executive_checklist: list[OrchestratedInsight] = Field(default_factory=list)
    go_no_go: GoNoGoDecision
    cards: list[OrchestratedCard] = Field(default_factory=list)
    document_confidence: dict[str, Any] = Field(default_factory=dict)


class LLMOrchestrator:
    def orchestrate(
        self,
        competition: ConsolidatedCompetitionData,
    ) -> LLMOrchestrationResult:
        summary = self._build_summary(competition)
        risks = self._build_risks(competition)
        opportunities = self._build_opportunities(competition)
        checklist = self._build_checklist(competition)
        go_no_go = self._build_go_no_go(competition, risks)
        cards = self._build_cards(summary, risks, opportunities, checklist, competition)
        document_confidence = self._build_document_confidence(competition)

        return LLMOrchestrationResult(
            executive_summary=summary["text"],
            executive_risks=risks,
            executive_opportunities=opportunities,
            executive_checklist=checklist,
            go_no_go=go_no_go,
            cards=cards,
            document_confidence=document_confidence,
        )

    def _build_summary(self, competition: ConsolidatedCompetitionData) -> dict[str, Any]:
        procedure = competition.procedure_identity or {}
        prices = competition.prices or {}
        award = competition.award_strategy or {}

        object_text = self._scalar_text(procedure.get("object"))
        entity_text = self._scalar_text(procedure.get("contracting_entity"))
        deadline_text = self._scalar_text(procedure.get("submission_deadline"))
        execution_text = self._scalar_text(procedure.get("execution_period"))
        criterion_text = self._scalar_text(award.get("award_criterion"))
        services_text = self._scalar_text(prices.get("design_services_value"))

        text = (
            f"O concurso incide sobre {object_text}, promovido por {entity_text}, com prazo {deadline_text} "
            f"e execução {execution_text}. O critério de adjudicação é {criterion_text} e o valor dos serviços é {services_text}."
        )
        if self._is_all_not_found([object_text, entity_text, deadline_text, execution_text, criterion_text, services_text]):
            text = "Not Found"

        return {"text": text, "evidence_refs": self._collect_refs(procedure, prices, award)}

    def _build_risks(self, competition: ConsolidatedCompetitionData) -> list[OrchestratedInsight]:
        insights: list[OrchestratedInsight] = []
        alerts = competition.document_alerts or []
        risks = competition.exclusion_risks or []
        financial = competition.financial_conditions or {}

        for entry in risks[:3]:
            text = self._entry_text(entry)
            if text != "Not Found":
                insights.append(
                    OrchestratedInsight(
                        text=text,
                        evidence_refs=self._refs_from_entry(entry),
                    )
                )

        for entry in alerts[:2]:
            text = self._entry_text(entry)
            if text != "Not Found":
                insights.append(
                    OrchestratedInsight(
                        text=text,
                        evidence_refs=self._refs_from_entry(entry),
                    )
                )

        for field_name in ("bond", "insurance", "penalties", "price_revision"):
            field = financial.get(field_name)
            if field and self._has_content(field.get("value")):
                text = self._sentence_from_value(field_name, field.get("value"))
                insights.append(
                    OrchestratedInsight(
                        text=text,
                        evidence_refs=self._refs_from_entry(field),
                    )
                )

        if not insights:
            insights.append(
                OrchestratedInsight(text="Not Found", evidence_refs=self._collect_refs(competition))
            )
        return self._dedupe_insights(insights)

    def _build_opportunities(self, competition: ConsolidatedCompetitionData) -> list[OrchestratedInsight]:
        insights: list[OrchestratedInsight] = []
        award = competition.award_strategy or {}
        team = competition.required_team or []
        prices = competition.prices or {}
        procedure = competition.procedure_identity or {}

        if self._has_content(award.get("award_criterion")) or self._has_content(award.get("factors")):
            insights.append(
                OrchestratedInsight(
                    text="O modelo de avaliação está definido e permite alinhar a proposta com os fatores indicados.",
                    evidence_refs=self._collect_refs(award),
                )
            )
        if team:
            insights.append(
                OrchestratedInsight(
                    text="A equipa exigida está explícita, o que ajuda a validar capacidade antes da submissão.",
                    evidence_refs=self._collect_refs(team),
                )
            )
        if any(self._has_content(prices.get(name, {}).get("value")) for name in ("procedure_value", "design_services_value", "estimated_construction_cost")):
            insights.append(
                OrchestratedInsight(
                    text="Os valores financeiros estão definidos, o que ajuda a estimar esforço e risco.",
                    evidence_refs=self._collect_refs(prices),
                )
            )
        if self._has_content(procedure.get("submission_deadline")):
            insights.append(
                OrchestratedInsight(
                    text="O prazo está identificado, o que permite estruturar a resposta com antecedência.",
                    evidence_refs=self._collect_refs(procedure),
                )
            )

        if not insights:
            insights.append(
                OrchestratedInsight(text="Not Found", evidence_refs=self._collect_refs(competition))
            )
        return self._dedupe_insights(insights)

    def _build_checklist(self, competition: ConsolidatedCompetitionData) -> list[OrchestratedInsight]:
        insights: list[OrchestratedInsight] = []
        procedure = competition.procedure_identity or {}
        team = competition.required_team or []
        financial = competition.financial_conditions or {}
        checklist = competition.submission_checklist or {}
        drawing_rules = competition.drawing_rules or []

        if self._has_content(procedure.get("submission_deadline")):
            insights.append(
                OrchestratedInsight(
                    text="Confirmar a data limite de submissão antes de preparar o envio.",
                    evidence_refs=self._collect_refs(procedure),
                )
            )
        if team:
            insights.append(
                OrchestratedInsight(
                    text="Validar a equipa mínima e as especialidades obrigatórias.",
                    evidence_refs=self._collect_refs(team),
                )
            )
        if any(self._has_content(financial.get(name, {}).get("value")) for name in ("bond", "insurance", "penalties", "price_revision")):
            insights.append(
                OrchestratedInsight(
                    text="Confirmar as condições financeiras e os encargos associados.",
                    evidence_refs=self._collect_refs(financial),
                )
            )
        if any(self._has_content(items) for items in checklist.values()):
            insights.append(
                OrchestratedInsight(
                    text="Verificar a checklist documental consolidada antes da submissão.",
                    evidence_refs=self._collect_refs(checklist),
                )
            )
        if drawing_rules:
            insights.append(
                OrchestratedInsight(
                    text="Rever as regras de peças desenhadas e os requisitos formais.",
                    evidence_refs=self._collect_refs(drawing_rules),
                )
            )

        if not insights:
            insights.append(
                OrchestratedInsight(text="Not Found", evidence_refs=self._collect_refs(competition))
            )
        return self._dedupe_insights(insights)

    def _build_go_no_go(
        self,
        competition: ConsolidatedCompetitionData,
        risks: list[OrchestratedInsight],
    ) -> GoNoGoDecision:
        quality = (competition.document_quality or "insufficient").lower()
        conflict_count = int((competition.quality_report or {}).get("conflicts", 0) or 0)

        if quality == "complete" and conflict_count == 0:
            return GoNoGoDecision(
                decision="go",
                reason="A documentação consolidada está completa e sem conflitos relevantes.",
                evidence_refs=self._collect_refs(competition.procedure_identity, competition.prices, competition.award_strategy, competition.required_team),
            )
        if quality in {"partial", "announcement_only"}:
            return GoNoGoDecision(
                decision="review",
                reason="A documentação consolidada é parcial e requer validação adicional.",
                evidence_refs=self._collect_refs(competition),
            )
        if risks:
            return GoNoGoDecision(
                decision="no_go",
                reason="A informação disponível é insuficiente para uma decisão segura.",
                evidence_refs=self._collect_refs(competition),
            )
        return GoNoGoDecision(
            decision="no_go",
            reason="Not Found",
            evidence_refs=self._collect_refs(competition),
        )

    def _build_cards(
        self,
        summary: dict[str, Any],
        risks: list[OrchestratedInsight],
        opportunities: list[OrchestratedInsight],
        checklist: list[OrchestratedInsight],
        competition: ConsolidatedCompetitionData,
    ) -> list[OrchestratedCard]:
        cards = [
            OrchestratedCard(
                title="Resumo executivo",
                text=summary["text"],
                evidence_refs=summary["evidence_refs"][:3],
            )
        ]

        risk_text = self._join_insights(risks[:2]) or "Not Found"
        cards.append(
            OrchestratedCard(
                title="Riscos executivos",
                text=risk_text,
                evidence_refs=self._merge_refs(risks[:2]),
            )
        )

        opportunity_text = self._join_insights(opportunities[:2]) or "Not Found"
        cards.append(
            OrchestratedCard(
                title="Oportunidades executivas",
                text=opportunity_text,
                evidence_refs=self._merge_refs(opportunities[:2]),
            )
        )

        checklist_text = self._join_insights(checklist[:3]) or "Not Found"
        cards.append(
            OrchestratedCard(
                title="Checklist executivo",
                text=checklist_text,
                evidence_refs=self._merge_refs(checklist[:3]),
            )
        )

        cards.append(
            OrchestratedCard(
                title="Confiança documental",
                text=self._confidence_sentence(competition),
                evidence_refs=self._collect_refs(competition),
            )
        )
        return cards

    def _build_document_confidence(self, competition: ConsolidatedCompetitionData) -> dict[str, Any]:
        quality_report = competition.quality_report or {}
        return {
            "document_quality": competition.document_quality or "insufficient",
            "global_confidence": quality_report.get("confidence_global", 0.0),
            "documents_official": quality_report.get("documents_official", 0),
            "documents_read": quality_report.get("documents_read", 0),
            "documents_ignored": quality_report.get("documents_ignored", 0),
            "conflicts": quality_report.get("conflicts", 0),
            "fields_filled": quality_report.get("fields_filled", 0),
            "fields_empty": quality_report.get("fields_empty", 0),
        }

    def _confidence_sentence(self, competition: ConsolidatedCompetitionData) -> str:
        quality_report = competition.quality_report or {}
        confidence = quality_report.get("confidence_global", 0.0)
        if confidence == 0:
            return "Not Found"
        return f"A confiança documental global é {confidence:.3f}."

    def _join_insights(self, insights: list[OrchestratedInsight]) -> str:
        texts = [insight.text for insight in insights if insight.text and insight.text != "Not Found"]
        return " ".join(texts) if texts else ""

    def _dedupe_insights(self, insights: list[OrchestratedInsight]) -> list[OrchestratedInsight]:
        seen: set[str] = set()
        result: list[OrchestratedInsight] = []
        for insight in insights:
            key = self._normalize_text(insight.text)
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(insight)
        return result

    def _merge_refs(self, insights: list[OrchestratedInsight]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for insight in insights:
            refs.extend(insight.evidence_refs)
        return self._dedupe_refs(refs)[:3]

    def _collect_refs(self, *values: Any) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for value in values:
            refs.extend(self._collect_refs_from_value(value))
        return self._dedupe_refs(refs)[:3]

    def _collect_refs_from_value(self, value: Any) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        if isinstance(value, Evidence):
            refs.append(self._evidence_ref(value))
            return refs
        if isinstance(value, BaseModel):
            return self._collect_refs_from_value(value.model_dump())
        if isinstance(value, dict):
            evidences = value.get("evidences", [])
            for evidence in evidences:
                if isinstance(evidence, Evidence):
                    refs.append(self._evidence_ref(evidence))
                elif isinstance(evidence, dict):
                    refs.append(self._evidence_ref_dict(evidence))
            for child in value.values():
                refs.extend(self._collect_refs_from_value(child))
            return refs
        if isinstance(value, list):
            for item in value:
                refs.extend(self._collect_refs_from_value(item))
        return refs

    def _refs_from_entry(self, entry: Any) -> list[dict[str, Any]]:
        return self._dedupe_refs(self._collect_refs_from_value(entry))[:3]

    def _evidence_ref(self, evidence: Evidence) -> dict[str, Any]:
        return {
            "evidence_id": evidence.evidence_id,
            "source_document_id": evidence.source_document_id,
            "filename": evidence.filename,
            "page": evidence.page,
            "section": evidence.section,
            "excerpt": evidence.excerpt,
        }

    def _evidence_ref_dict(self, evidence: dict[str, Any]) -> dict[str, Any]:
        return {
            "evidence_id": evidence.get("evidence_id", "Not Found"),
            "source_document_id": evidence.get("source_document_id", "Not Found"),
            "filename": evidence.get("filename", "Not Found"),
            "page": evidence.get("page"),
            "section": evidence.get("section"),
            "excerpt": evidence.get("excerpt", "Not Found"),
        }

    def _dedupe_refs(self, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for ref in refs:
            key = self._normalize_text(
                f"{ref.get('evidence_id')}::{ref.get('source_document_id')}::{ref.get('excerpt')}"
            )
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(ref)
        return result

    def _scalar_text(self, field: Any) -> str:
        if isinstance(field, dict):
            value = field.get("value")
            if self._has_content(value):
                return self._value_text(value)
        if self._has_content(field):
            return self._value_text(field)
        return "Not Found"

    def _entry_text(self, entry: Any) -> str:
        if isinstance(entry, dict):
            value = entry.get("value")
            if self._has_content(value):
                return self._value_text(value)
            if self._has_content(entry.get("text")):
                return self._value_text(entry.get("text"))
        if self._has_content(entry):
            return self._value_text(entry)
        return "Not Found"

    def _sentence_from_value(self, field_name: str, value: Any) -> str:
        text = self._value_text(value)
        if text == "Not Found":
            return "Not Found"
        labels = {
            "bond": "A caução é",
            "insurance": "O seguro obrigatório está definido.",
            "penalties": "As penalizações estão definidas.",
            "price_revision": "A revisão de preços está indicada.",
        }
        if field_name == "insurance":
            return "O seguro obrigatório está definido."
        if field_name == "penalties":
            return f"As penalizações são {text}."
        if field_name == "price_revision":
            return f"A revisão de preços é {text}."
        return f"{labels.get(field_name, field_name)} {text}."

    def _value_text(self, value: Any) -> str:
        if value is None:
            return "Not Found"
        if isinstance(value, str):
            return value.strip() or "Not Found"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, dict):
            parts: list[str] = []
            for key in ("value", "label", "name", "text", "description"):
                if self._has_content(value.get(key)):
                    parts.append(self._value_text(value.get(key)))
                    break
            if not parts:
                for child in value.values():
                    if self._has_content(child):
                        parts.append(self._value_text(child))
                        break
            return " ".join(part for part in parts if part).strip() or "Not Found"
        if isinstance(value, list):
            parts = [self._value_text(item) for item in value[:3] if self._has_content(item)]
            return ", ".join(part for part in parts if part) or "Not Found"
        return str(value).strip() or "Not Found"

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

    def _normalize_text(self, value: str) -> str:
        return "".join(ch for ch in value.casefold().strip() if not ch.isspace())

    def _is_all_not_found(self, values: list[str]) -> bool:
        return all(value == "Not Found" for value in values)


def orchestrate_competition(
    competition: ConsolidatedCompetitionData,
) -> LLMOrchestrationResult:
    return LLMOrchestrator().orchestrate(competition)
