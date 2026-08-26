from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from pathlib import Path
from typing import Any

from .ollama_provider import OllamaProvider
from .presentation_prompt import PROMPT_VERSION, build_prompt
from .presentation_schema import (
    Presentation,
    PresentationCard,
    PresentationEvidence,
    PresentationItem,
    PresentationRisk,
    presentation_json_schema,
)
from .provider import LLMProviderError

logger = logging.getLogger(__name__)

SECTION_ORDER_TEMPLATES: dict[str, list[str]] = {
    "design_competition": [
        "competition_model",
        "awards",
        "financial_conditions",
        "jury",
        "award_criteria",
        "submission_deliverables",
        "anonymity",
        "calendar",
        "program",
        "risks",
    ],
    "ideas_competition": [
        "competition_model",
        "jury",
        "awards",
        "financial_conditions",
        "award_criteria",
        "submission_deliverables",
        "anonymity",
        "evaluation",
        "risks",
    ],
    "execution_project": [
        "competition_model",
        "financial_conditions",
        "required_team",
        "technical_specialties",
        "phases_and_deliverables",
        "award_criteria",
        "submission_checklist",
        "calendar",
        "risks",
    ],
    "architectural_services": [
        "competition_model",
        "contract_scope",
        "financial_conditions",
        "required_team",
        "technical_specialties",
        "award_criteria",
        "submission_checklist",
        "calendar",
        "risks",
    ],
    "rehabilitation_project": [
        "competition_model",
        "contract_scope",
        "financial_conditions",
        "required_team",
        "phases_and_deliverables",
        "award_criteria",
        "submission_checklist",
        "calendar",
        "risks",
    ],
    "urban_planning": [
        "competition_model",
        "contract_scope",
        "program",
        "award_criteria",
        "submission_deliverables",
        "calendar",
        "risks",
    ],
    "landscape_architecture": [
        "competition_model",
        "program",
        "award_criteria",
        "submission_deliverables",
        "calendar",
        "risks",
    ],
    "public_equipment": [
        "competition_model",
        "contract_scope",
        "program",
        "financial_conditions",
        "award_criteria",
        "submission_checklist",
        "calendar",
        "risks",
    ],
    "framework_agreement": [
        "competition_model",
        "contract_scope",
        "financial_conditions",
        "required_team",
        "award_criteria",
        "submission_checklist",
        "calendar",
        "risks",
    ],
    "works_contract": [
        "competition_model",
        "contract_scope",
        "financial_conditions",
        "required_team",
        "technical_specialties",
        "phases_and_deliverables",
        "submission_checklist",
        "calendar",
        "risks",
    ],
    "generic_services": [
        "competition_model",
        "contract_scope",
        "financial_conditions",
        "required_team",
        "submission_checklist",
        "calendar",
        "risks",
    ],
    "unknown": [
        "competition_model",
        "awards",
        "context_location",
        "financial_conditions",
        "award_criteria",
        "required_team",
        "deliverables",
        "submission_checklist",
        "risks",
    ],
}

CARD_SPECS: dict[str, dict[str, Any]] = {
    "competition_model": {
        "title": "Modelo e condições do concurso",
        "summary": "O modelo e as condições identificadas nas peças disponíveis.",
        "source": lambda data: {
            "Objeto": _pick(data.get("procedure_identity"), "object", "title", "summary"),
            "Tipo de procedimento": _pick(data.get("procedure_identity"), "procedure_type", "model", "competition_model"),
            "Entidade adjudicante": _pick(data.get("procedure_identity"), "contracting_entity", "entity"),
            "Localização": _pick(data.get("procedure_identity"), "location"),
            "Língua": _pick(data.get("procedure_identity"), "language"),
            "Plataforma": _pick(data.get("procedure_identity"), "platform"),
            "Trabalhos selecionados": _pick(data.get("procedure_identity"), "works_selected", "selected_works"),
            "Número de vencedores": _pick(data.get("procedure_identity"), "winners", "number_of_winners"),
            "Fase posterior": _pick(data.get("procedure_identity"), "post_award_phase", "phase_after"),
            "Anonimato": _pick(data.get("procedure_identity"), "anonymity", "anonymous_submission"),
            "Júri": _pick(data.get("procedure_identity"), "jury", "jury_composition"),
        },
    },
    "awards": {
        "title": "Prémios",
        "summary": "Os prémios e distinções confirmados nas peças analisadas.",
        "source": lambda data: {
            "Prémios do concurso": _pick(data.get("prices"), "competition_prizes", "prizes", "prize_table"),
            "Menções honrosas": _pick(data.get("prices"), "honourable_mentions", "honorable_mentions"),
        },
    },
    "jury": {
        "title": "Júri",
        "summary": "A composição do júri e os elementos de avaliação identificados.",
        "source": lambda data: _pick_many(data.get("award_strategy"), "jury", "jury_composition", "panel", "members", "composition"),
    },
    "award_criteria": {
        "title": "Critérios de adjudicação",
        "summary": "Os critérios e regras de avaliação identificados na documentação disponível.",
        "source": lambda data: _pick_many(
            data.get("award_strategy"),
            "award_criterion",
            "evaluation_model",
            "factors",
            "subfactors",
            "price_weight",
            "technical_weight",
            "maximum_score_requirements",
            "tie_break_rules",
            "criteria",
        ),
    },
    "financial_conditions": {
        "title": "Condições financeiras",
        "summary": "Os valores, pagamentos e garantias confirmados nas peças analisadas.",
        "source": lambda data: {
            "Preço dos serviços": _pick(data.get("prices"), "design_services_value", "service_price", "fee"),
            "Valor do procedimento": _pick(data.get("prices"), "procedure_value", "base_price"),
            "Custo estimado da obra": _pick(data.get("prices"), "estimated_construction_cost"),
            "Pagamentos por fase": _pick(data.get("financial_conditions"), "payments_by_phase", "payments"),
            "Caução": _pick(data.get("financial_conditions"), "bond", "guarantee"),
            "Seguros": _pick(data.get("financial_conditions"), "insurance"),
            "Penalidades": _pick(data.get("financial_conditions"), "penalties"),
            "Revisão de preços": _pick(data.get("financial_conditions"), "price_revision"),
        },
    },
    "required_team": {
        "title": "Equipa exigida",
        "summary": "Os perfis, especialidades e requisitos mínimos de equipa identificados.",
        "source": lambda data: data.get("required_team") or [],
    },
    "technical_specialties": {
        "title": "Especialidades técnicas",
        "summary": "As especialidades técnicas e competências explicitamente referidas nas peças.",
        "source": lambda data: _pick_many(data.get("technical_constraints"), "specializations", "specialties", "consultants", "disciplines"),
    },
    "phases_and_deliverables": {
        "title": "Fases e entregáveis contratuais",
        "summary": "As fases e entregáveis após contratação que foram identificados.",
        "source": lambda data: _contract_deliverables(data),
    },
    "submission_deliverables": {
        "title": "Entregas para participar no concurso",
        "summary": "Os elementos de candidatura e submissão identificados nas peças disponíveis.",
        "source": lambda data: _submission_deliverables(data),
    },
    "submission_checklist": {
        "title": "Documentos da candidatura",
        "summary": "Os documentos e requisitos formais de candidatura identificados.",
        "source": lambda data: data.get("submission_checklist") or {},
    },
    "anonymity": {
        "title": "Anonimato e formato de entrega",
        "summary": "As regras de anonimato, formato e apresentação encontradas nas peças.",
        "source": lambda data: _pick_many(
            data.get("procedure_identity"),
            "anonymity",
            "anonymous_submission",
            "anonymous",
            "panel_format",
            "panel_number",
            "memory",
            "descriptive_memory",
            "page_limit",
            "video",
            "mockup",
        ),
    },
    "calendar": {
        "title": "Calendário e prazos",
        "summary": "As datas e prazos úteis identificados na documentação disponível.",
        "source": lambda data: _pick_many(
            data.get("procedure_identity"),
            "submission_deadline",
            "clarification_deadline",
            "site_visit",
            "jury_decision",
            "award_date",
            "execution_period",
            "start_date",
            "end_date",
        ),
    },
    "program": {
        "title": "Programa e intervenção",
        "summary": "Os requisitos técnicos, de programa e de representação identificados.",
        "source": lambda data: {
            "Objeto": _pick(data.get("procedure_identity"), "object", "summary"),
            "Requisitos técnicos": data.get("technical_constraints") or [],
            "Regras de desenho": data.get("drawing_rules") or [],
        },
    },
    "contract_scope": {
        "title": "Âmbito do contrato",
        "summary": "O objeto do contrato e as condições principais de prestação identificadas.",
        "source": lambda data: {
            "Objeto": _pick(data.get("procedure_identity"), "object", "summary"),
            "Tipo de procedimento": _pick(data.get("procedure_identity"), "procedure_type", "model"),
            "Entidade adjudicante": _pick(data.get("procedure_identity"), "contracting_entity"),
            "Localização": _pick(data.get("procedure_identity"), "location"),
        },
    },
    "context_location": {
        "title": "Contexto e localização",
        "summary": "Os elementos de contexto territorial e funcional referidos nas peças.",
        "source": lambda data: {
            "Localização": _pick(data.get("procedure_identity"), "location"),
            "Objeto": _pick(data.get("procedure_identity"), "object", "summary"),
        },
    },
    "deliverables": {
        "title": "Entregáveis",
        "summary": "Os entregáveis relevantes encontrados na documentação disponível.",
        "source": lambda data: data.get("phases_and_deliverables") or [],
    },
    "risks": {
        "title": "Riscos e requisitos eliminatórios",
        "summary": "Os riscos e requisitos que podem condicionar a participação no concurso.",
        "source": lambda data: (data.get("exclusion_risks") or []) + (data.get("document_alerts") or []),
    },
    "evaluation": {
        "title": "Avaliação",
        "summary": "Os elementos de avaliação identificados para o concurso.",
        "source": lambda data: _pick_many(data.get("award_strategy"), "evaluation_model", "award_criterion", "criteria", "factors"),
    },
}


class PresentationBuilder:
    def __init__(self, cache_dir: Path | None = None, provider: OllamaProvider | None = None) -> None:
        self.cache_dir = cache_dir or (Path(__file__).resolve().parents[3] / "analise_documentos" / ".presentation_cache")
        self.provider = provider or OllamaProvider()

    def build(self, consolidated: Any, *, force: bool = False) -> Presentation:
        data = consolidated.model_dump(mode="json") if hasattr(consolidated, "model_dump") else dict(consolidated)
        key = self.cache_key(data)
        cached = self._read_cache(key) if not force else None
        if cached is not None:
            return cached
        try:
            result = self.provider.generate(build_prompt(data), presentation_json_schema())
            presentation = Presentation.model_validate(result)
            logger.info("presentation_provider=ollama result=valid")
        except (LLMProviderError, ValueError, TypeError) as exc:
            logger.warning("presentation_provider=fallback reason=%s", exc)
            presentation = self.deterministic(data)
        self._write_cache(key, presentation)
        return presentation

    def cached(self, consolidated: Any) -> Presentation | None:
        data = consolidated.model_dump(mode="json") if hasattr(consolidated, "model_dump") else dict(consolidated)
        return self._read_cache(self.cache_key(data))

    def cache_key(self, data: dict[str, Any]) -> str:
        material = {key: data.get(key) for key in (
            "procedure_identity",
            "prices",
            "award_strategy",
            "required_team",
            "phases_and_deliverables",
            "submission_checklist",
            "drawing_rules",
            "financial_conditions",
            "technical_constraints",
            "exclusion_risks",
            "document_alerts",
            "document_quality",
            "quality_report",
            "evidences",
        )}
        raw = json.dumps(material, ensure_ascii=False, sort_keys=True, default=str)
        model = getattr(self.provider, "model", "deterministic")
        return hashlib.sha256(f"{raw}|{PROMPT_VERSION}|{model}".encode("utf-8")).hexdigest()

    def deterministic(self, data: dict[str, Any]) -> Presentation:
        quality = str(data.get("document_quality") or "insufficient")
        classification = _classify_competition(data)
        cards = _build_cards(data, classification)

        risks = []
        for entry in (data.get("exclusion_risks") or []) + (data.get("document_alerts") or []):
            value = _text(entry)
            if value:
                risks.append(
                    PresentationRisk(
                        title="Risco documental",
                        summary=value,
                        severity="warning",
                        status="partial",
                        evidence_ids=_evidence_ids(entry),
                    )
                )

        opportunities = []
        if _has_value(data.get("award_strategy")):
            opportunities.append(
                PresentationRisk(
                    title="Critérios de avaliação",
                    summary="Os critérios de avaliação estão identificados na documentação disponível.",
                    severity="info",
                    status="confirmed",
                    evidence_ids=_evidence_ids(data.get("award_strategy")),
                )
            )

        checklist = []
        for category, items in (data.get("submission_checklist") or {}).items():
            for item in items or []:
                value = _text(item)
                if value:
                    checklist.append(
                        PresentationRisk(
                            title=_display_label(str(category), item),
                            summary=value,
                            severity="info",
                            status="confirmed",
                            evidence_ids=_evidence_ids(item),
                        )
                    )

        visibility = {key: bool(item.get("items")) for key, item in cards}
        return Presentation(
            document_status=quality if quality in {"complete", "partial", "insufficient", "announcement_only"} else "insufficient",
            executive_summary=_executive_summary(data, quality, classification),
            cards=[item for _, item in cards if item.get("items")],
            risks=_dedupe_insights(risks),
            opportunities=_dedupe_insights(opportunities),
            checklist=_dedupe_insights(checklist),
            missing_information=_missing(data),
            warnings=[],
            evidence=_presentation_evidence(data.get("evidences")),
            competition_type=classification["competition_type"],
            competition_subtype=classification["competition_subtype"],
            classification_confidence=classification["classification_confidence"],
            classification_reasons=classification["classification_reasons"],
            recommended_section_order=classification["recommended_section_order"],
            section_visibility=visibility,
            section_priority=classification["section_priority"],
            special_features=classification["special_features"],
        )

    def _read_cache(self, key: str) -> Presentation | None:
        path = self.cache_dir / f"{key}.json"
        try:
            return Presentation.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None
        except (OSError, ValueError):
            return None

    def _write_cache(self, key: str, presentation: Presentation) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{key}.json").write_text(presentation.model_dump_json(ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.warning("presentation_cache_write_failed: %s", exc)


def _build_cards(data: dict[str, Any], classification: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    order = classification["recommended_section_order"]
    cards: list[tuple[str, dict[str, Any]]] = []
    for section in order:
        spec = CARD_SPECS.get(section)
        if not spec:
            continue
        source = spec["source"](data)
        items = _items_from_source(source)
        if not items:
            continue
        cards.append(
            (
                section,
                {
                    "type": section,
                    "title": spec["title"],
                    "summary": spec["summary"],
                    "items": items,
                    "confidence": "confirmed",
                    "evidence_ids": _evidence_ids(source),
                },
            )
        )
    return cards


def _classify_competition(data: dict[str, Any]) -> dict[str, Any]:
    procedure = data.get("procedure_identity") or {}
    blobs = [
        _text(procedure),
        _text(data.get("award_strategy")),
        _text(data.get("prices")),
        _text(data.get("financial_conditions")),
        _text(data.get("required_team")),
        _text(data.get("phases_and_deliverables")),
        _text(data.get("submission_checklist")),
        _text(data.get("technical_constraints")),
        _text(data.get("drawing_rules")),
    ]
    haystack = " | ".join(part.lower() for part in blobs if part)
    classification_type = "unknown"
    reasons: list[str] = []
    confidence = 0.45

    if _contains_any(haystack, ("concurso de concep", "concurso de ideias", "concepc", "conceçao", "concecao", "ideias")):
        if "ideias" in haystack:
            classification_type = "ideas_competition"
            reasons.append("A documentação refere um concurso de ideias.")
            confidence = 0.88
        else:
            classification_type = "design_competition"
            reasons.append("A documentação aponta para um concurso de conceção.")
            confidence = 0.9
    elif _contains_any(haystack, ("projeto de exec", "assistencia tecnica", "assistência técnica", "especialidad", "bim", "ifc", "dwg")):
        classification_type = "execution_project"
        reasons.append("A documentação tem foco em projeto de execução e entrega técnica.")
        confidence = 0.84
    elif _contains_any(haystack, ("reabilita", "rehabilit")):
        classification_type = "rehabilitation_project"
        reasons.append("O objeto do procedimento remete para reabilitação.")
        confidence = 0.82
    elif _contains_any(haystack, ("paisag", "landscape")):
        classification_type = "landscape_architecture"
        reasons.append("O objeto do procedimento remete para arquitetura paisagista.")
        confidence = 0.8
    elif _contains_any(haystack, ("urban", "plano de urban", "loteamento")):
        classification_type = "urban_planning"
        reasons.append("O objeto do procedimento remete para urbanismo ou planeamento urbano.")
        confidence = 0.8
    elif _contains_any(haystack, ("equipamento", "public equipment")):
        classification_type = "public_equipment"
        reasons.append("O objeto do procedimento remete para equipamento público.")
        confidence = 0.78
    elif _contains_any(haystack, ("acordo quadro", "framework", "quadro")):
        classification_type = "framework_agreement"
        reasons.append("A documentação indica acordo quadro.")
        confidence = 0.78
    elif _contains_any(haystack, ("empreitada", "obra", "works contract")):
        classification_type = "works_contract"
        reasons.append("A documentação aponta para contrato de empreitada ou obra.")
        confidence = 0.76
    elif _contains_any(haystack, ("servi", "services")):
        classification_type = "generic_services"
        reasons.append("A documentação destaca prestação de serviços.")
        confidence = 0.7

    subtype = _subtype_for(data, classification_type, haystack)
    features = _special_features(data, haystack)
    order = SECTION_ORDER_TEMPLATES.get(classification_type, SECTION_ORDER_TEMPLATES["unknown"])
    visibility = {section: _section_has_content(section, data) for section in order}
    priority = {section: index + 1 for index, section in enumerate(order)}
    return {
        "competition_type": classification_type,
        "competition_subtype": subtype,
        "classification_confidence": confidence,
        "classification_reasons": reasons or ["Classificação inferida a partir dos campos estruturados disponíveis."],
        "recommended_section_order": order,
        "section_visibility": visibility,
        "section_priority": priority,
        "special_features": features,
    }


def _subtype_for(data: dict[str, Any], classification_type: str, haystack: str) -> str:
    text = " ".join(
        part.lower()
        for part in (
            _text(data.get("procedure_identity")),
            _text(data.get("award_strategy")),
            _text(data.get("technical_constraints")),
            _text(data.get("phases_and_deliverables")),
        )
        if part
    )
    if classification_type == "design_competition":
        if _contains_any(text, ("arquitet", "architecture")):
            return "architecture"
        if _contains_any(text, ("paisag", "landscape")):
            return "landscape_architecture"
        if _contains_any(text, ("urban", "planeamento")):
            return "urban_planning"
        return "generic_design"
    if classification_type == "execution_project":
        if _contains_any(text, ("reabilita", "rehabilit")):
            return "rehabilitation_project"
        if _contains_any(text, ("arquitet", "architecture")):
            return "architectural_services"
        return "generic_execution"
    if classification_type == "ideas_competition":
        return "architecture_school" if _contains_any(text, ("arquitet", "school", "escola")) else "generic_ideas"
    if classification_type == "public_equipment":
        return "equipment"
    if classification_type == "urban_planning":
        return "urban_plan"
    if classification_type == "landscape_architecture":
        return "landscape"
    if classification_type == "framework_agreement":
        return "framework"
    if classification_type == "works_contract":
        return "construction"
    if classification_type == "generic_services":
        return "services"
    return "unknown"


def _special_features(data: dict[str, Any], haystack: str) -> list[str]:
    features: list[str] = []
    if _contains_any(haystack, ("anonym", "anonymous")):
        features.append("anonymous_submission")
    if _contains_any(haystack, ("a1", "painel", "panels")):
        features.append("a1_panels")
    if _contains_any(haystack, ("memória descritiva", "memoria descritiva", "descriptive memory")):
        features.append("descriptive_memory")
    if _contains_any(haystack, ("prémio", "premio", "prize")):
        features.append("multiple_prizes")
    if _contains_any(haystack, ("júri", "jury")):
        features.append("jury")
    if _contains_any(haystack, ("fase posterior", "post-award", "após adjudicação", "apos adjudicacao")):
        features.append("post_award_phase")
    if _contains_any(haystack, ("bim",)):
        features.append("bim")
    if _contains_any(haystack, ("ifc",)):
        features.append("ifc")
    if _contains_any(haystack, ("dwg",)):
        features.append("dwg")
    if _contains_any(haystack, ("habilitação", "habilitacao", "qualification")):
        features.append("habilitation_documents")
    if _contains_any(haystack, ("proposta", "submission")):
        features.append("proposal_documents")
    return list(dict.fromkeys(features))


def _section_has_content(section: str, data: dict[str, Any]) -> bool:
    spec = CARD_SPECS.get(section)
    if not spec:
        return False
    return bool(_items_from_source(spec["source"](data)))


def _build_from_groups(groups: dict[str, Any]) -> list[PresentationItem]:
    items: list[PresentationItem] = []
    for label, value in groups.items():
        if isinstance(value, list):
            for child in value:
                text = _text(child)
                if text:
                    items.append(PresentationItem(label=_display_label(str(label), child), value=text, status="confirmed"))
        else:
            text = _text(value)
            if text:
                items.append(PresentationItem(label=_display_label(str(label), value), value=text, status="confirmed"))
    return _dedupe_items(items)


def _items_from_source(source: Any) -> list[PresentationItem]:
    if isinstance(source, dict):
        return _build_from_groups(source)
    if isinstance(source, list):
        result: list[PresentationItem] = []
        for value in source:
            if isinstance(value, dict):
                if value.get("phase") and value.get("items"):
                    phase_label = _display_label("phase", value)
                    for child in value.get("items") or []:
                        child_text = _text(child)
                        if child_text:
                            result.append(PresentationItem(label=phase_label, value=child_text, status="confirmed"))
                elif value.get("group") and value.get("items"):
                    group_label = _display_label(str(value.get("group")), value)
                    for child in value.get("items") or []:
                        child_text = _text(child)
                        if child_text:
                            result.append(PresentationItem(label=group_label, value=child_text, status="confirmed"))
                else:
                    text = _text(value)
                    if text:
                        result.append(PresentationItem(label=_display_label("", value), value=text, status="confirmed"))
            else:
                text = _text(value)
                if text:
                    result.append(PresentationItem(label="Requisito", value=text, status="confirmed"))
        return _dedupe_items(result)[:12]
    text = _text(source)
    return [PresentationItem(label="Requisito", value=text, status="confirmed")] if text else []


def _contract_deliverables(data: dict[str, Any]) -> dict[str, list[Any]]:
    submission, contract, fallback = _split_deliverables(data.get("phases_and_deliverables") or [])
    groups: dict[str, list[Any]] = {}
    if contract:
        groups["Entregáveis contratuais"] = contract
    if fallback:
        groups["Outros entregáveis"] = fallback
    if data.get("submission_checklist"):
        groups["Documentos da candidatura"] = _flatten_checklist(data.get("submission_checklist"))
    if not groups and submission:
        groups["Entregas para participar"] = submission
    return groups


def _submission_deliverables(data: dict[str, Any]) -> dict[str, list[Any]]:
    submission, contract, fallback = _split_deliverables(data.get("phases_and_deliverables") or [])
    groups: dict[str, list[Any]] = {}
    if submission:
        groups["Entregas para participar"] = submission
    if data.get("submission_checklist"):
        groups["Documentos da candidatura"] = _flatten_checklist(data.get("submission_checklist"))
    if fallback and not groups:
        groups["Outros elementos"] = fallback
    return groups


def _split_deliverables(values: list[Any]) -> tuple[list[Any], list[Any], list[Any]]:
    submission: list[Any] = []
    contract: list[Any] = []
    fallback: list[Any] = []
    for value in values or []:
        text = _text(value)
        if not text:
            continue
        normalized = _normalize(text)
        if _contains_any(normalized, ("painel", "memoria descritiva", "maquete", "video", "anonim", "a1", "candidatura", "proposta")):
            submission.append(value)
        elif _contains_any(normalized, ("estudo previo", "anteprojeto", "projeto de execucao", "assistencia tecnica", "telas finais", "medicoes", "bim", "ifc", "dwg")):
            contract.append(value)
        else:
            fallback.append(value)
    return submission, contract, fallback


def _flatten_checklist(checklist: dict[str, list[Any]]) -> list[Any]:
    values: list[Any] = []
    for items in checklist.values():
        values.extend(items or [])
    return values


def _pick(container: Any, *keys: str) -> Any:
    if not isinstance(container, dict):
        return None
    for key in keys:
        value = container.get(key)
        if _has_value(value):
            return value
    return None


def _pick_many(container: Any, *keys: str) -> dict[str, Any]:
    if not isinstance(container, dict):
        return {}
    result = {}
    for key in keys:
        value = container.get(key)
        if _has_value(value):
            result[key] = value
    return result


def _build_from_entries(entries: dict[str, Any]) -> list[PresentationItem]:
    return [PresentationItem(label=_display_label(label, value), value=_text(value), status="confirmed") for label, value in entries.items() if _has_value(value) and _text(value)]


def _build_from_source(source: Any) -> list[PresentationItem]:
    if isinstance(source, dict):
        return _build_from_entries(source)
    if isinstance(source, list):
        return _items_from_source(source)
    text = _text(source)
    return [PresentationItem(label="Requisito", value=text, status="confirmed")] if text else []


def _executive_summary(data: dict[str, Any], quality: str, classification: dict[str, Any]) -> str:
    identity = data.get("procedure_identity") or {}
    facts = []
    for field in ("object", "procedure_type", "contracting_entity", "location", "submission_deadline"):
        value = identity.get(field) if isinstance(identity, dict) else None
        value_text = _text(value)
        if value_text:
            facts.append(value_text)
    if not facts:
        intro = "A apresentação resume os factos confirmados na documentação disponível."
    else:
        intro = f"{'; '.join(facts[:5])}."
    suffix = " Alguns pontos permanecem por confirmar." if quality != "complete" else ""
    subtype = classification.get("competition_subtype") or classification.get("competition_type")
    if subtype and subtype != "unknown":
        return f"{intro} {suffix}".strip()
    return f"{intro}{suffix}".strip()


def _presentation_evidence(values: Any) -> list[PresentationEvidence]:
    result: list[PresentationEvidence] = []
    for value in values or []:
        if not isinstance(value, dict) or not value.get("evidence_id"):
            continue
        result.append(
            PresentationEvidence(
                evidence_id=str(value["evidence_id"]),
                source_document=str(value.get("filename") or ""),
                page=value.get("page"),
                section=str(value.get("section") or ""),
                excerpt=str(value.get("excerpt") or ""),
                confidence=value.get("confidence"),
            )
        )
    return result


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {}, "Not Found")


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    return "".join(char for char in text if not unicodedata.combining(char)).lower()

def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    normalized = _normalize(haystack)
    return any(_normalize(needle) in normalized for needle in needles)


def _text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("value", "label", "name", "text", "description"):
            if _has_value(value.get(key)):
                return _text(value[key])
        parts = []
        for key, child in value.items():
            if key in {"evidences", "evidence_ids"} or not _has_value(child):
                continue
            child_text = _text(child)
            if child_text:
                parts.append(f"{_display_label(str(key), child)}: {child_text}")
        return "; ".join(parts)
    if isinstance(value, list):
        return "; ".join(_text(item) for item in value if _has_value(item))
    return str(value).strip() if _has_value(value) else ""


def _evidence_ids(value: Any) -> list[str]:
    ids: list[str] = []
    if isinstance(value, dict):
        if value.get("evidence_id"):
            ids.append(str(value["evidence_id"]))
        for child in value.values():
            ids.extend(_evidence_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.extend(_evidence_ids(child))
    return list(dict.fromkeys(ids))


def _display_label(label: str, value: Any) -> str:
    if isinstance(value, dict):
        label = str(value.get("field_name") or value.get("label") or value.get("name") or value.get("category") or value.get("phase") or label)
    labels = {
        "object": "Objeto",
        "contracting_entity": "Entidade adjudicante",
        "procedure_type": "Tipo de procedimento",
        "submission_deadline": "Entrega de propostas",
        "clarification_deadline": "Esclarecimentos",
        "execution_period": "Prazo de execução",
        "location": "Localização",
        "competition_prizes": "Prémios",
        "procedure_value": "Valor do procedimento",
        "design_services_value": "Preço dos serviços",
        "estimated_construction_cost": "Custo estimado da obra",
        "award_criterion": "Critério geral",
        "evaluation_model": "Modelo de avaliação",
        "price_weight": "Peso do preço",
        "technical_weight": "Peso técnico",
        "minimum_team": "Equipa mínima",
        "required_specializations": "Especialidades",
        "professional_requirements": "Requisitos profissionais",
        "experience_requirements": "Experiência",
        "certifications": "Certificações",
        "consultants": "Consultores",
        "administrative": "Documentos administrativos",
        "technical": "Documentos técnicos",
        "financial": "Documentos financeiros",
        "team": "Documentos da equipa",
        "post_award": "Documentos pós-adjudicação",
        "phase": "Fase",
        "deliverables": "Entregáveis",
        "description": "Descrição",
        "deadline": "Prazo",
        "jury": "Júri",
        "members": "Membros",
        "panel": "Painel",
        "anonymous_submission": "Entrega anónima",
        "anonymity": "Anonimato",
        "page_limit": "Limite de páginas",
        "mockup": "Maquete",
    }
    if label in labels:
        return labels[label]
    if not label:
        return "Requisito"
    return label.replace("_", " ").strip().capitalize()


def _dedupe_items(items: list[PresentationItem]) -> list[PresentationItem]:
    seen: set[tuple[str, str]] = set()
    result: list[PresentationItem] = []
    for item in items:
        key = (" ".join(item.label.lower().split()), " ".join(item.value.lower().split()))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _missing(data: dict[str, Any]) -> list[str]:
    return [key for key in ("prices", "award_strategy", "required_team", "phases_and_deliverables", "submission_checklist", "technical_constraints") if not _has_value(data.get(key))]


def _dedupe_insights(items: list[PresentationRisk]) -> list[PresentationRisk]:
    seen: set[str] = set()
    result = []
    for item in items:
        key = " ".join(item.summary.lower().split())
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result
