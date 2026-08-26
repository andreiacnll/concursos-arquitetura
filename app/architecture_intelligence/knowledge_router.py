from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_VOCABULARY_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "apim"
    / "semantic_types_v0.1.json"
)

INTENT_PRIORITY = {
    "prepare_submission": 100,
    "understand_evaluation": 95,
    "understand_project": 90,
    "understand_contract": 85,
    "understand_financials": 85,
    "understand_team": 80,
    "understand_schedule": 80,
    "evaluate_opportunity": 75,
    "other": 0,
}

BLOCK_TO_INTENT = {
    "competition_identity": "understand_project",
    "competition_model": "understand_project",
    "context": "understand_project",
    "programme": "understand_project",
    "submission_deliverables": "prepare_submission",
    "submission_documents": "prepare_submission",
    "administrative": "prepare_submission",
    "evaluation": "understand_evaluation",
    "jury": "understand_evaluation",
    "awards": "understand_financials",
    "financials": "understand_financials",
    "contract_scope": "understand_contract",
    "contract_deliverables": "understand_contract",
    "team": "understand_team",
    "calendar": "understand_schedule",
    "risks": "evaluate_opportunity",
}

FIELD_ALIASES = {
    "object": "competition_object",
    "procedure_type": "competition_type",
    "location": "competition_location",
    "competition_prizes": "competition_prize",
    "prizes": "competition_prize",
    "prize_amount": "competition_prize",
    "base_price": "procedure_value",
    "procedure_price": "procedure_value",
    "design_fee": "design_services_value",
    "design_fees": "design_services_value",
    "estimated_work_cost": "estimated_construction_cost",
    "estimated_works_cost": "estimated_construction_cost",
    "estimated_construction_value": "estimated_construction_cost",
    "estimated_cost_of_works": "estimated_construction_cost",
    "construction_cost_estimate": "estimated_construction_cost",
    "work_cost_estimate": "estimated_construction_cost",
    "estimated_works_budget": "estimated_construction_cost",
    "bond": "bond_requirement",
    "insurance": "insurance_requirement",
    "penalties": "penalty_condition",
    "award_criterion": "evaluation_factor",
    "evaluation_model": "evaluation_method",
    "price_weight": "evaluation_weight",
    "technical_weight": "evaluation_weight",
    "factors": "evaluation_factor",
    "subfactors": "evaluation_subfactor",
    "tie_break_rules": "tie_break_rule",
    "jury": "jury_member",
    "coordinator": "coordinator_requirement",
    "minimum_team": "minimum_team_requirement",
    "required_team": "minimum_team_requirement",
    "exclusionary_team_requirements": "minimum_team_requirement",
    "required_specializations": "specialization_requirement",
    "professional_requirements": "specialization_requirement",
    "experience_requirements": "experience_requirement",
    "certifications": "certification_requirement",
    "payments_by_phase": "payment_condition",
    "exclusion_risks": "exclusion_risk",
    "document_alerts": "document_gap",
    "technical_constraints": "site_constraint",
}

FIELD_ROUTE_OVERRIDES = {
    "phases_and_deliverables": (
        "understand_contract",
        "contract_deliverables",
    ),
    "phases": ("understand_contract", "contract_scope"),
    "deliverables_by_phase": (
        "understand_contract",
        "contract_deliverables",
    ),
    "assistance_requirements": (
        "understand_contract",
        "contract_deliverables",
    ),
    "validation_requirements": (
        "understand_contract",
        "contract_scope",
    ),
    "required_team": ("understand_team", "team"),
    "exclusionary_team_requirements": ("understand_team", "team"),
    "submission_checklist": (
        "prepare_submission",
        "submission_deliverables",
    ),
    "drawing_requirements": (
        "prepare_submission",
        "submission_deliverables",
    ),
    "drawing_rules": (
        "prepare_submission",
        "submission_deliverables",
    ),
    "administrative_documents": (
        "prepare_submission",
        "submission_documents",
    ),
    "technical_documents": (
        "prepare_submission",
        "submission_documents",
    ),
    "financial_conditions": (
        "understand_financials",
        "financials",
    ),
    "technical_constraints": ("understand_project", "programme"),
    "exclusion_risks": ("evaluate_opportunity", "risks"),
    "document_alerts": ("evaluate_opportunity", "risks"),
    "physical_formats": ("other", "other"),
    "digital_formats": ("other", "other"),
    "scale_requirements": ("other", "other"),
}

FIELD_CONTENT_RULES = {
    "deliverables_by_phase": (
        ("execution_project", ("projeto de execucao", "execution project")),
        ("technical_assistance", ("assistencia tecnica", "technical assistance")),
        ("measurements", ("medicoes", "mapa de quantidades", "measurements")),
        ("final_drawings", ("telas finais", "as built", "final drawings")),
        ("anteproject", ("anteprojeto", "ante-projecto", "anteproject")),
        ("preliminary_study", ("estudo previo", "preliminary study")),
        ("bim_requirement", ("bim", "building information modeling")),
    ),
    "phases": (
        ("execution_project", ("projeto de execucao", "execution project")),
        ("anteproject", ("anteprojeto", "ante-projecto", "anteproject")),
        ("preliminary_study", ("estudo previo", "preliminary study")),
    ),
    "assistance_requirements": (
        ("technical_assistance", ("assistencia tecnica", "technical assistance")),
    ),
    "validation_requirements": (
        (
            "approval_requirement",
            (
                "aprovacao",
                "parecer",
                "licenciamento",
                "entidade externa",
            ),
        ),
    ),
    "drawing_requirements": (
        ("submission_panel", ("painel", "paineis", "prancha", "board")),
    ),
    "drawing_rules": (
        ("submission_panel", ("painel", "paineis", "prancha", "board")),
    ),
    "scale_requirements": (
        (
            "submission_panel_format",
            (
                "formato a0",
                "formato a1",
                "formato a2",
                "escala grafica",
                "planta",
                "corte",
                "alcado",
                "painel",
            ),
        ),
    ),
    "technical_documents": (
        (
            "submission_descriptive_memory",
            (
                "memoria descritiva",
                "memoria justificativa",
                "descriptive memory",
            ),
        ),
    ),
}


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char for char in text if not unicodedata.combining(char)
    )
    text = text.lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _leaf_field_name(field_name: str) -> str:
    parts = re.split(r"[.\[\]/]+", str(field_name or ""))
    return _normalize(parts[-1] if parts else field_name)


def _item_to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump(mode="json"))
    raise TypeError(
        "KnowledgeRouter aceita InformationItem, modelos Pydantic "
        "ou dicionários."
    )


class KnowledgeRouter:
    "Encaminha factos do Information Model de forma determinística."

    def __init__(self, vocabulary_path: str | Path | None = None) -> None:
        self.vocabulary_path = Path(
            vocabulary_path or DEFAULT_VOCABULARY_PATH
        )
        payload = json.loads(
            self.vocabulary_path.read_text(encoding="utf-8")
        )
        semantic_types = payload.get("semantic_types") or []
        self._types = {
            str(item["id"]): dict(item)
            for item in semantic_types
            if item.get("id")
        }
        if not self._types:
            raise ValueError(
                f"Vocabulário sem semantic types: {self.vocabulary_path}"
            )

    @property
    def semantic_type_ids(self) -> frozenset[str]:
        return frozenset(self._types)

    def route_item(self, item: Any) -> dict[str, Any]:
        data = _item_to_dict(item)
        field_name = str(data.get("field_name") or "")
        leaf = _leaf_field_name(field_name)
        full = _normalize(field_name)

        semantic_type, confidence, reason = self._resolve_semantic_type(
            data=data,
            leaf=leaf,
            full=full,
        )

        route_override = (
            FIELD_ROUTE_OVERRIDES.get(leaf)
            or FIELD_ROUTE_OVERRIDES.get(full)
        )

        if semantic_type:
            definition = self._types[semantic_type]
            intent = str(definition.get("intent") or "other")
            knowledge_block = str(
                definition.get("knowledge_block")
                or data.get("knowledge_block")
                or "other"
            )
        elif route_override:
            intent, knowledge_block = route_override
            confidence = max(confidence, 0.75)
            reason = "field_route_override"
        else:
            knowledge_block = str(
                data.get("knowledge_block") or "other"
            )
            intent = BLOCK_TO_INTENT.get(knowledge_block, "other")

        routed = dict(data)
        routed["semantic_type"] = semantic_type
        routed["knowledge_intent"] = intent
        routed["knowledge_block"] = knowledge_block
        routed["intent_priority"] = INTENT_PRIORITY.get(intent, 0)
        routed["routing"] = {
            "confidence": confidence,
            "reason": reason,
            "vocabulary_version": "0.1",
            "router_version": "0.2",
            "deterministic": True,
        }
        return routed

    def route_items(self, items: Iterable[Any]) -> list[dict[str, Any]]:
        return [self.route_item(item) for item in items]

    def group_by_intent(
        self,
        items: Iterable[Any],
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for routed in self.route_items(items):
            grouped[routed["knowledge_intent"]].append(routed)

        for values in grouped.values():
            values.sort(
                key=lambda item: (
                    -int(item.get("intent_priority") or 0),
                    -float(
                        (item.get("routing") or {}).get("confidence") or 0
                    ),
                    str(item.get("field_name") or ""),
                )
            )
        return dict(grouped)

    def _resolve_semantic_type(
        self,
        *,
        data: dict[str, Any],
        leaf: str,
        full: str,
    ) -> tuple[str | None, float, str]:
        for candidate in (leaf, full):
            if candidate in self._types:
                return candidate, 1.0, "exact_semantic_type"

        content = self._routing_text(data)
        content_match = self._match_field_content(leaf, content)
        if content_match:
            return content_match, 0.90, "field_content_rule"

        alias = FIELD_ALIASES.get(leaf) or FIELD_ALIASES.get(full)
        if alias and alias in self._types:
            return alias, 0.95, "field_alias"

        return None, 0.35, "knowledge_block_fallback"

    def _routing_text(self, data: dict[str, Any]) -> str:
        values = (
            data.get("field_name"),
            data.get("section"),
            data.get("purpose"),
            data.get("value"),
            data.get("normalized_value"),
        )
        return _normalize(
            " ".join(str(value or "")[:3000] for value in values)
        )

    def _match_field_content(
        self,
        field_name: str,
        normalized_content: str,
    ) -> str | None:
        rules = FIELD_CONTENT_RULES.get(field_name, ())
        for semantic_type, phrases in rules:
            if semantic_type not in self._types:
                continue
            for phrase in phrases:
                token = _normalize(phrase)
                if token and token in normalized_content:
                    return semantic_type
        return None


_default_router: KnowledgeRouter | None = None


def get_default_router() -> KnowledgeRouter:
    global _default_router
    if _default_router is None:
        _default_router = KnowledgeRouter()
    return _default_router


def route_information_item(item: Any) -> dict[str, Any]:
    return get_default_router().route_item(item)


def route_information_items(
    items: Iterable[Any],
) -> list[dict[str, Any]]:
    return get_default_router().route_items(items)


def group_information_by_intent(
    items: Iterable[Any],
) -> dict[str, list[dict[str, Any]]]:
    return get_default_router().group_by_intent(items)
