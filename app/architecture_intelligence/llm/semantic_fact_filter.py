from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping

from .ollama_provider import OllamaProvider
from .provider import LLMProvider, LLMProviderError
from .semantic_filter_prompt import (
    PROMPT_VERSION,
    build_semantic_filter_prompt,
)
from .semantic_filter_schema import (
    SemanticFact,
    SemanticFilterResponse,
    semantic_filter_json_schema,
)


DEFAULT_VOCABULARY_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "apim"
    / "semantic_types_v0.1.json"
)

IGNORED_FIELDS = {
    "document_alerts.message",
    "document_alerts.reader_name",
}

FIELD_TYPE_ALLOWLISTS = {
    "phases_and_deliverables": {
        "contract_scope",
        "preliminary_study",
        "anteproject",
        "execution_project",
        "technical_assistance",
        "measurements",
        "final_drawings",
        "approval_requirement",
        "bim_requirement",
        "payment_condition",
        "execution_period",
    },
    "assistance_requirements": {
        "technical_assistance",
        "final_drawings",
        "approval_requirement",
        "execution_project",
    },
    "technical_documents": {
        "execution_project",
        "technical_assistance",
        "measurements",
        "final_drawings",
        "approval_requirement",
        "bim_requirement",
    },
    "financial_documents": {
        "competition_prize",
        "procedure_value",
        "design_services_value",
        "contract_value",
        "estimated_construction_cost",
        "payment_condition",
        "bond_requirement",
        "insurance_requirement",
        "penalty_condition",
        "measurements",
    },
    "physical_formats": {
        "submission_panel",
        "submission_panel_format",
        "submission_panel_quantity",
        "submission_model",
        "submission_digital_format",
        "contract_scope",
        "execution_project",
    },
    "scale_requirements": {
        "submission_panel_format",
    },
    "administrative_documents": {
        "submission_digital_format",
        "submission_platform",
        "submission_anonymity",
        "certification_requirement",
    },
    "certifications": {
        "certification_requirement",
    },
    "required_specializations": {
        "specialization_requirement",
    },
    "exclusionary_team_requirements": {
        "minimum_team_requirement",
        "experience_requirement",
        "specialization_requirement",
        "certification_requirement",
        "exclusion_risk",
    },
    "validation_requirements": {
        "approval_requirement",
        "submission_anonymity",
    },
}

FIELD_ANCHORS = {
    "phases_and_deliverables": (
        "fase",
        "estudo previo",
        "anteprojeto",
        "projeto de exec",
        "assist",
        "medic",
        "mapa de quantidades",
        "telas finais",
        "bim",
        "aprov",
        "pagamento",
        "prazo",
    ),
    "assistance_requirements": (
        "assist",
        "obra",
        "esclarec",
        "telas finais",
        "projeto de exec",
    ),
    "technical_documents": (
        "projeto de exec",
        "assist",
        "medic",
        "mapa de quantidades",
        "telas finais",
        "bim",
        "aprov",
    ),
    "financial_documents": (
        "preco",
        "valor",
        "custo",
        "estimativa",
        "pagamento",
        "caucao",
        "seguro",
        "penal",
        "medic",
        "orcamento",
    ),
    "physical_formats": (
        "painel",
        "prancha",
        "formato a0",
        "formato a1",
        "formato a2",
        "maquete",
        "papel",
        "exemplar",
        "suporte digital",
    ),
    "scale_requirements": (
        "escala",
        "painel",
        "prancha",
        "a0",
        "a1",
        "a2",
    ),
    "administrative_documents": (
        "ficheiro",
        "pdf",
        "plataforma",
        "anonim",
        "assinatura",
        "declaracao",
        "certific",
    ),
    "certifications": (
        "certific",
        "ordem profissional",
        "habilit",
    ),
    "required_specializations": (
        "especialidade",
        "arquitet",
        "engenhe",
        "coorden",
        "paisag",
    ),
    "exclusionary_team_requirements": (
        "equipa",
        "experiencia",
        "especialidade",
        "certific",
        "exclusao",
    ),
    "validation_requirements": (
        "aprov",
        "validacao",
        "entidade externa",
        "anonim",
    ),
}


def _item_to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)

    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump(mode="json"))

    raise TypeError(
        "SemanticFactFilter aceita modelos Pydantic ou dicionários."
    )


def _raw_value(item: dict[str, Any]) -> Any:
    value = item.get("normalized_value")
    if value in (None, "", [], {}):
        value = item.get("value")
    return value


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _value_text(item: dict[str, Any]) -> str:
    value = _raw_value(item)

    if isinstance(value, str):
        return value

    return json.dumps(value, ensure_ascii=False, default=str)


def _flatten_strings(value: Any) -> Iterable[str]:
    if value is None:
        return

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return

        if stripped[:1] in {"{", "["}:
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                yield stripped
            else:
                yield from _flatten_strings(parsed)
            return

        yield stripped
        return

    if isinstance(value, Mapping):
        for child in value.values():
            yield from _flatten_strings(child)
        return

    if isinstance(value, (list, tuple, set)):
        for child in value:
            yield from _flatten_strings(child)
        return

    yield str(value)


class SemanticFactFilter:
    """Extrai factos semânticos de itens ambíguos usando um provider LLM."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        vocabulary_path: str | Path | None = None,
        *,
        max_chars: int = 6000,
        max_fragments: int = 30,
    ) -> None:
        self.provider = provider or OllamaProvider()
        self.vocabulary_path = Path(
            vocabulary_path or DEFAULT_VOCABULARY_PATH
        )
        self.max_chars = max_chars
        self.max_fragments = max_fragments
        self.allowed_semantic_types = self._load_semantic_types()

    def should_filter(self, item: Any) -> bool:
        data = _item_to_dict(item)
        field_name = str(data.get("field_name") or "")

        if field_name in IGNORED_FIELDS:
            return False

        leaf = self._leaf_field(field_name)
        return leaf in FIELD_TYPE_ALLOWLISTS

    def filter_item(self, item: Any) -> dict[str, Any]:
        data = _item_to_dict(item)
        field_name = str(data.get("field_name") or "")

        if field_name in IGNORED_FIELDS:
            return {
                "status": "ignored_metadata",
                "facts": [],
                "warnings": [],
                "prompt_version": PROMPT_VERSION,
            }

        if not self.should_filter(data):
            return {
                "status": "not_required",
                "facts": [],
                "warnings": [],
                "prompt_version": PROMPT_VERSION,
            }

        source_text = _value_text(data)
        if not source_text.strip():
            return {
                "status": "insufficient_evidence",
                "facts": [],
                "warnings": ["empty_source_value"],
                "prompt_version": PROMPT_VERSION,
            }

        leaf = self._leaf_field(field_name)
        allowed_types = sorted(
            FIELD_TYPE_ALLOWLISTS[leaf]
            & self.allowed_semantic_types
        )
        fragments = self._compact_fragments(
            leaf,
            _raw_value(data),
        )

        if not fragments:
            return {
                "status": "insufficient_evidence",
                "facts": [],
                "warnings": ["no_relevant_fragments"],
                "prompt_version": PROMPT_VERSION,
            }

        prompt_item = {
            "field_name": field_name,
            "knowledge_block": data.get("knowledge_block"),
            "source_document": data.get("source_document"),
            "value": fragments,
        }
        payload = build_semantic_filter_prompt(
            prompt_item,
            allowed_types,
            max_chars=self.max_chars,
        )

        try:
            raw = self.provider.generate(
                payload,
                semantic_filter_json_schema(),
            )
            response = SemanticFilterResponse.model_validate(raw)
        except (LLMProviderError, ValueError, TypeError) as exc:
            return {
                "status": "provider_unavailable",
                "facts": [],
                "warnings": [str(exc)],
                "prompt_version": PROMPT_VERSION,
            }

        valid_facts: list[SemanticFact] = []
        warnings: list[str] = []

        for fact in response.facts:
            if fact.semantic_type not in allowed_types:
                warnings.append(
                    f"semantic_type_not_allowed_for_field:"
                    f"{fact.semantic_type}"
                )
                continue

            if not self._excerpt_is_grounded(
                fact.source_excerpt,
                source_text,
            ):
                warnings.append(
                    f"ungrounded_excerpt:{fact.semantic_type}"
                )
                continue

            valid_facts.append(fact)

        status = response.status
        if valid_facts:
            status = "ok"
        elif response.facts:
            status = "insufficient_evidence"

        return {
            "status": status,
            "facts": [
                fact.model_dump(mode="json")
                for fact in valid_facts
            ],
            "discarded_fragments": response.discarded_fragments,
            "warnings": warnings,
            "prompt_version": PROMPT_VERSION,
            "allowed_semantic_types": allowed_types,
            "fragments_sent": fragments,
        }

    def _leaf_field(self, field_name: str) -> str:
        return re.split(r"[.\[\]/]+", field_name)[-1]

    def _compact_fragments(
        self,
        leaf: str,
        value: Any,
    ) -> list[str]:
        anchors = tuple(
            _normalize_text(anchor)
            for anchor in FIELD_ANCHORS.get(leaf, ())
        )

        relevant: list[str] = []
        fallback: list[str] = []
        seen: set[str] = set()
        used_chars = 0

        for fragment in _flatten_strings(value):
            normalized = _normalize_text(fragment)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)

            if len(fragment) < 8:
                continue

            fallback.append(fragment)
            if anchors and not any(
                anchor in normalized
                for anchor in anchors
            ):
                continue

            if used_chars + len(fragment) > self.max_chars:
                continue

            relevant.append(fragment)
            used_chars += len(fragment)
            if len(relevant) >= self.max_fragments:
                break

        selected = relevant or fallback[: min(10, self.max_fragments)]
        return selected

    def _load_semantic_types(self) -> frozenset[str]:
        payload = json.loads(
            self.vocabulary_path.read_text(encoding="utf-8")
        )
        semantic_types = payload.get("semantic_types") or []
        result = frozenset(
            str(item["id"])
            for item in semantic_types
            if item.get("id")
        )
        if not result:
            raise ValueError(
                f"Vocabulário sem semantic types: "
                f"{self.vocabulary_path}"
            )
        return result

    def _excerpt_is_grounded(
        self,
        excerpt: str,
        source_text: str,
    ) -> bool:
        normalized_excerpt = _normalize_text(excerpt)
        normalized_source = _normalize_text(source_text)

        if len(normalized_excerpt) < 12:
            return False

        return normalized_excerpt in normalized_source
