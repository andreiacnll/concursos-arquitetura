from __future__ import annotations

from app.analise.design_competition_extractor import apply_design_competition_extraction

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.architecture_intelligence.knowledge_router import get_default_router
from app.architecture_intelligence.llm.presentation_builder import PresentationBuilder
from app.architecture_intelligence.pipeline import run_architecture_intelligence_experiment
from app.architecture_intelligence.schemas import ConsolidatedCompetitionData
from app.architecture_intelligence.semantic_enrichment import enrich_consolidated_semantics


TRUE_VALUES = {"1", "true", "yes", "on"}
PRODUCT_VERSION = "semantic-product-v0.1"


def semantic_product_enabled() -> bool:
    return (
        os.getenv("SEMANTIC_PRODUCT_ENABLED", "0").strip().lower()
        in TRUE_VALUES
    )


def attach_semantic_product_data(
    *,
    textos: dict[str, str],
    ficha: dict[str, Any],
    enabled: bool | None = None,
    runner: Callable[..., Any] | None = None,
    enricher: Callable[..., Any] | None = None,
    presentation_builder: PresentationBuilder | None = None,
) -> dict[str, Any]:
    active = semantic_product_enabled() if enabled is None else enabled
    if not active:
        return {"status": "disabled", "version": PRODUCT_VERSION}

    sources = _sources_from_texts(textos)
    if not sources:
        return {
            "status": "insufficient_documents",
            "version": PRODUCT_VERSION,
            "warnings": ["no_usable_document_text"],
        }

    enrich = enricher or enrich_consolidated_semantics

    try:
        if runner is None:
            base = _build_fast_source_consolidated(textos)
        else:
            experiment = runner(
                sources,
                write_debug_exports=False,
            )
            base = ConsolidatedCompetitionData.model_validate(
                experiment.consolidated
            )
            base = _augment_with_source_evidences(base, textos)

        enriched, enrichment_report = enrich(base, enabled=True)
        enriched = _repair_design_competition_financials(
            enriched,
            textos,
        )
        enriched = apply_design_competition_extraction(
            ficha,
            enriched,
            textos,
        )
        compact = build_compact_consolidated(enriched)
        compact_payload = compact.model_dump(mode="json")
        presentation = _cache_deterministic_presentation(
            compact_payload,
            builder=presentation_builder,
        )
    except Exception as exc:
        return {
            "status": "fallback",
            "version": PRODUCT_VERSION,
            "warnings": [f"{type(exc).__name__}: {exc}"],
        }

    semantic_summary = _semantic_summary(compact)
    ficha["architecture_intelligence"] = {
        "status": "ok",
        "version": PRODUCT_VERSION,
        "generated_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "consolidated": compact_payload,
        "semantic_enrichment": _compact_report(enrichment_report),
        "presentation": presentation,
    }
    ficha.setdefault("document_insights", {})[
        "semantic_summary"
    ] = semantic_summary

    return {
        "status": "ok",
        "version": PRODUCT_VERSION,
        "facts_total": len(compact.information_model),
        "financial_items": len(semantic_summary["financials"]),
        "submission_items": len(semantic_summary["submission"]),
        "contract_items": len(semantic_summary["contract"]),
        "warnings": list(enrichment_report.get("warnings") or []),
    }


def build_compact_consolidated(
    enriched: ConsolidatedCompetitionData,
) -> ConsolidatedCompetitionData:
    semantic_items = [
        item.model_dump(mode="json")
        for item in enriched.information_model
        if item.reader_name == "semantic_evidence_filter"
    ]
    referenced_evidence_ids = {
        evidence_id
        for item in semantic_items
        for evidence_id in item.get("evidence_ids") or []
    }
    evidences = [
        evidence.model_dump(mode="json")
        for evidence in enriched.evidences
        if evidence.evidence_id in referenced_evidence_ids
    ]

    submission_items = [
        _deliverable_entry(item)
        for item in semantic_items
        if item.get("phase") == "submission"
    ]
    contract_items = [
        _deliverable_entry(item)
        for item in semantic_items
        if item.get("phase") == "contract_execution"
    ]

    prices = {
        key: _cap(value)
        for key, value in enriched.prices.items()
        if key
        in {
            "competition_prizes",
            "procedure_value",
            "design_services_value",
            "estimated_construction_cost",
        }
    }

    compact_items = _cap(semantic_items)
    knowledge_intents = (
        get_default_router().group_by_intent(compact_items)
        if compact_items
        else {}
    )

    return ConsolidatedCompetitionData(
        schema_version=enriched.schema_version,
        document_quality=enriched.document_quality,
        quality_report=_cap(enriched.quality_report),
        document_index=[
            item.model_dump(mode="json")
            for item in enriched.document_index
        ],
        information_model=compact_items,
        knowledge_intents=knowledge_intents,
        procedure_identity=_cap(enriched.procedure_identity),
        prices=prices,
        award_strategy=_cap(enriched.award_strategy),
        required_team=_cap(enriched.required_team),
        phases_and_deliverables=submission_items + contract_items,
        submission_checklist={
            "administrative": [],
            "technical": submission_items,
            "financial": [],
            "team": [],
            "post_award": [],
        },
        drawing_rules=[],
        financial_conditions=_cap(enriched.financial_conditions),
        technical_constraints=_cap(enriched.technical_constraints),
        exclusion_risks=_cap(enriched.exclusion_risks),
        document_alerts=_cap(enriched.document_alerts),
        evidences=evidences,
        sources=_cap(enriched.sources),
        warnings=list(enriched.warnings)[:20],
    )


def _sources_from_texts(
    textos: dict[str, str],
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    blocked = {
        "analise.json",
        "ficha.json",
        "textos.json",
        "analise_ai.json",
    }

    for index, (filename, raw_text) in enumerate(
        (textos or {}).items(),
        start=1,
    ):
        text = str(raw_text or "").strip()
        name = Path(str(filename or f"documento-{index}.txt")).name
        if not text or name.casefold() in blocked:
            continue
        digest = hashlib.sha256(
            f"{name}\0{text}".encode("utf-8")
        ).hexdigest()
        sources.append(
            {
                "document_id": f"worker-{digest[:20]}",
                "filename": name,
                "text": text,
                "origin": "analysis_worker",
                "source_role": (
                    "official_announcement"
                    if name.casefold() == "dados_concurso.txt"
                    else "official_document"
                ),
                "content_type": "text/plain",
                "sha256": digest,
                "metadata": {
                    "collection_method": "analysis_worker_texts",
                },
            }
        )
    return sources



_SOURCE_TOPIC_PATTERNS = {
    "financial_core": (
        r"\bmontante global dos premios\b",
        r"\bpreco base do procedimento\b",
        r"\bvalor do preco base do procedimento\b",
        r"\bvalor de obra\b",
        r"\bcusto estimado da obra\b",
        r"\bestimativa de custo de obra\b",
        r"\bpreco base da empreitada\b",
        r"\bhonorarios?\b",
        r"\bremuneracao do projetista\b",
        r"\bvalor dos servicos de projeto\b",
        r"\bvalor maximo dos servicos\b",
        r"\bpreco base da aquisicao de servicos\b",
        r"\bvalor do contrato de projeto\b",
        r"\bpreco contratual\b",
        r"\bformula de calculo dos honorarios\b",
        r"\b24 439 134\b",
        r"\b26 000 00\b",
    ),
    "submission_panels": (
        r"\bpaineis? a1\b",
        r"\bmodo de apresentacao dos paineis\b",
        r"\bmemoria descritiva\b",
        r"\bficheiros? jpg\b",
        r"\bformato fisico\b",
        r"\banonim",
        r"\bplataforma eletronica\b",
    ),
    "contract_deliverables": (
        r"\bprojeto de execucao\b",
        r"\banteprojeto\b",
        r"\bestudo previo\b",
        r"\bassistencia tecnica\b",
        r"\btelas finais\b",
        r"\bmapa de medicoes\b",
        r"\bmapa de quantidades\b",
        r"\bestimativa orcamental\b",
        r"\bprojeto de especialidades\b",
        r"\bbim\b",
    ),
}


def _normalize_source_window(value: object) -> str:
    import re
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _source_evidence_candidates(
    textos: dict[str, str],
) -> list[dict[str, Any]]:
    import re

    blocked = {
        "analise.json",
        "ficha.json",
        "textos.json",
        "analise_ai.json",
    }
    compiled = {
        topic: tuple(re.compile(pattern) for pattern in patterns)
        for topic, patterns in _SOURCE_TOPIC_PATTERNS.items()
    }
    limits = {
        "financial_core": 36,
        "submission_panels": 28,
        "contract_deliverables": 36,
    }
    counts = {key: 0 for key in limits}
    seen: set[str] = set()
    evidences: list[dict[str, Any]] = []

    for index, (raw_filename, raw_text) in enumerate(
        (textos or {}).items(),
        start=1,
    ):
        filename = Path(
            str(raw_filename or f"documento-{index}.txt")
        ).name
        if filename.casefold() in blocked:
            continue

        text = str(raw_text or "").replace("\x00", " ").strip()
        if not text:
            continue

        lines = [
            " ".join(line.split())
            for line in text.splitlines()
            if " ".join(line.split())
        ]
        if not lines:
            lines = [" ".join(text.split())]

        source_digest = hashlib.sha256(
            filename.encode("utf-8")
        ).hexdigest()[:16]
        source_document_id = f"worker-source-{source_digest}"

        for line_index in range(len(lines)):
            start = max(0, line_index - 2)
            end = min(len(lines), line_index + 3)
            excerpt = " ".join(lines[start:end]).strip()
            if not excerpt:
                continue
            if len(excerpt) > 850:
                excerpt = excerpt[:850].rsplit(" ", 1)[0]

            normalized = _normalize_source_window(excerpt)
            matched = [
                topic
                for topic, patterns in compiled.items()
                if counts[topic] < limits[topic]
                and any(pattern.search(normalized) for pattern in patterns)
            ]
            if not matched:
                continue

            signature = hashlib.sha256(
                f"{filename}\0{normalized}".encode("utf-8")
            ).hexdigest()[:20]
            if signature in seen:
                continue
            seen.add(signature)

            for topic in matched:
                counts[topic] += 1

            evidences.append(
                {
                    "evidence_id": signature,
                    "source_document_id": source_document_id,
                    "filename": filename,
                    "page": None,
                    "section": "worker_text_window",
                    "excerpt": excerpt,
                    "confidence": 0.90,
                    "status": "confirmed",
                    "metadata": {
                        "semantic_source": "worker_text_window",
                        "topics": matched,
                    },
                }
            )

    return evidences


def _augment_with_source_evidences(
    consolidated: ConsolidatedCompetitionData,
    textos: dict[str, str],
) -> ConsolidatedCompetitionData:
    payload = consolidated.model_dump(mode="json")
    existing = list(payload.get("evidences") or [])
    known = {
        str(item.get("evidence_id") or "")
        for item in existing
        if isinstance(item, dict)
    }
    for evidence in _source_evidence_candidates(textos):
        if evidence["evidence_id"] not in known:
            known.add(evidence["evidence_id"])
            existing.append(evidence)
    payload["evidences"] = existing
    return ConsolidatedCompetitionData.model_validate(payload)


def _build_fast_source_consolidated(
    textos: dict[str, str],
) -> ConsolidatedCompetitionData:
    sources = _sources_from_texts(textos)
    evidences = _source_evidence_candidates(textos)
    return ConsolidatedCompetitionData.model_validate(
        {
            "schema_version": "1.0",
            "document_quality": (
                "partial" if evidences else "insufficient"
            ),
            "quality_report": {
                "documents_read": len(sources),
                "semantic_source_evidences": len(evidences),
                "fast_path": True,
            },
            "document_index": [],
            "information_model": [],
            "knowledge_intents": {},
            "evidences": evidences,
            "sources": [
                {
                    "document_id": item.get("document_id"),
                    "filename": item.get("filename"),
                    "source_role": item.get("source_role"),
                    "origin": item.get("origin"),
                    "sha256": item.get("sha256"),
                }
                for item in sources
            ],
            "warnings": [],
        }
    )


_FINANCIAL_REPAIR_FIELDS = {
    "procedure_value",
    "estimated_construction_cost",
    "design_services_value",
}


def _financial_repair_normalize(value: object) -> str:
    import re
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = text.lower()
    text = re.sub(r"[^a-z0-9.,\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _financial_repair_amounts(
    text: str,
) -> list[tuple[int, int, str, float]]:
    import re

    pattern = re.compile(
        r"(?<!\d)"
        r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})?"
        r"|\d{4,}(?:,\d{2})?)"
        r"(?!\d)"
    )
    output: list[tuple[int, int, str, float]] = []
    for match in pattern.finditer(text):
        raw = match.group(1).strip()
        numeric_text = (
            raw.replace(" ", "")
            .replace(".", "")
            .replace(",", ".")
        )
        try:
            number = float(numeric_text)
        except ValueError:
            continue
        if number < 1000:
            continue
        output.append(
            (match.start(), match.end(), raw, number)
        )
    return output


def _financial_repair_format(raw: str) -> str:
    value = " ".join(
        raw.replace(".", " ").split()
    )
    return f"{value} EUR"


def _financial_repair_nearest(
    normalized: str,
    phrase_pattern: str,
    *,
    radius: int,
) -> tuple[str, float] | None:
    import re

    best: tuple[float, str, float] | None = None
    for phrase in re.finditer(
        phrase_pattern,
        normalized,
        re.IGNORECASE,
    ):
        start = max(0, phrase.start() - radius)
        end = min(len(normalized), phrase.end() + radius)
        window = normalized[start:end]

        for amount_start, amount_end, raw, number in (
            _financial_repair_amounts(window)
        ):
            absolute_start = start + amount_start
            absolute_end = start + amount_end

            if absolute_end < phrase.start():
                distance = phrase.start() - absolute_end
            elif absolute_start > phrase.end():
                distance = absolute_start - phrase.end()
            else:
                distance = 0

            score = float(distance)
            if "," in raw:
                score -= 6
            if "." in raw or " " in raw:
                score -= 3

            candidate = (score, raw, number)
            if best is None or candidate[0] < best[0]:
                best = candidate

    if best is None:
        return None

    return _financial_repair_format(best[1]), best[2]


def _explicit_financial_facts(
    textos: dict[str, str],
) -> dict[str, tuple[str, str, float]]:
    from pathlib import Path

    rules = {
        "procedure_value": (
            r"\bpreco base do procedimento\b"
            r"|\bvalor do preco base do procedimento\b"
            r"|\bvalor do procedimento\b",
            180,
        ),
        "estimated_construction_cost": (
            r"\bvalor estimado da obra\b"
            r"|\bcusto estimado da obra\b"
            r"|\bestimativa de custo da obra\b"
            r"|\bestimativa de custo de obra\b"
            r"|\bvalor de obra\b"
            r"|\bpreco base da empreitada\b"
            r"|\bcusto da obra\b",
            260,
        ),
        "design_services_value": (
            r"\bhonorarios?\b"
            r"|\bremuneracao do projetista\b"
            r"|\bvalor dos servicos de projeto\b"
            r"|\bvalor maximo dos servicos\b"
            r"|\bpreco base da aquisicao de servicos\b"
            r"|\bvalor do contrato de projeto\b"
            r"|\bpreco contratual dos servicos\b",
            240,
        ),
    }

    found: dict[str, tuple[str, str, float]] = {}

    for raw_filename, raw_text in (textos or {}).items():
        filename = Path(
            str(raw_filename or "documento.txt")
        ).name
        if filename.casefold() in {
            "ficha.json",
            "analise.json",
            "textos.json",
            "analise_ai.json",
        }:
            continue

        normalized = _financial_repair_normalize(raw_text)
        if not normalized:
            continue

        for field_name, (pattern, radius) in rules.items():
            result = _financial_repair_nearest(
                normalized,
                pattern,
                radius=radius,
            )
            if result is None:
                continue

            value, number = result
            current = found.get(field_name)

            if current is None:
                found[field_name] = (
                    value,
                    filename,
                    number,
                )
                continue

            if (
                field_name == "estimated_construction_cost"
                and number > current[2]
            ):
                found[field_name] = (
                    value,
                    filename,
                    number,
                )
            elif (
                field_name == "design_services_value"
                and number < current[2]
            ):
                found[field_name] = (
                    value,
                    filename,
                    number,
                )

    procedure = found.get("procedure_value")
    procedure_number = procedure[2] if procedure else None

    for field_name in (
        "estimated_construction_cost",
        "design_services_value",
    ):
        candidate = found.get(field_name)
        if (
            candidate is not None
            and procedure_number is not None
            and abs(candidate[2] - procedure_number) < 0.01
        ):
            del found[field_name]

    return found


def _repair_design_competition_financials(
    consolidated: ConsolidatedCompetitionData,
    textos: dict[str, str],
) -> ConsolidatedCompetitionData:
    payload = consolidated.model_dump(mode="json")
    items = list(payload.get("information_model") or [])
    explicit = _explicit_financial_facts(textos)

    existing_by_field = {
        str(item.get("field_name") or ""): item
        for item in items
        if isinstance(item, dict)
    }

    repaired: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        field_name = str(item.get("field_name") or "")
        if field_name not in _FINANCIAL_REPAIR_FIELDS:
            repaired.append(item)

    procedure_explicit = explicit.get("procedure_value")
    procedure_existing = existing_by_field.get(
        "procedure_value"
    )

    if procedure_explicit is not None:
        value, filename, _ = procedure_explicit
        repaired.append(
            _financial_repair_item(
                "procedure_value",
                value,
                filename,
            )
        )
    elif procedure_existing:
        repaired.append(procedure_existing)

    procedure_value = (
        procedure_explicit[2]
        if procedure_explicit is not None
        else _financial_repair_number_from_item(
            procedure_existing
        )
    )

    for field_name in (
        "estimated_construction_cost",
        "design_services_value",
    ):
        explicit_value = explicit.get(field_name)
        if explicit_value is not None:
            value, filename, number = explicit_value
            if (
                procedure_value is not None
                and abs(number - procedure_value) < 0.01
            ):
                continue
            repaired.append(
                _financial_repair_item(
                    field_name,
                    value,
                    filename,
                )
            )
            continue

        existing = existing_by_field.get(field_name)
        existing_number = _financial_repair_number_from_item(
            existing
        )
        if (
            existing
            and existing_number is not None
            and (
                procedure_value is None
                or abs(
                    existing_number - procedure_value
                ) >= 0.01
            )
        ):
            repaired.append(existing)

    payload["information_model"] = repaired
    return ConsolidatedCompetitionData.model_validate(
        payload
    )


def _financial_repair_number_from_item(
    item: dict[str, Any] | None,
) -> float | None:
    if not item:
        return None
    value = str(
        item.get("normalized_value")
        or item.get("value")
        or ""
    )
    amounts = _financial_repair_amounts(
        _financial_repair_normalize(value)
    )
    return amounts[0][3] if amounts else None


def _financial_repair_item(
    field_name: str,
    value: str,
    filename: str,
) -> dict[str, Any]:
    return {
        "field_name": field_name,
        "value": value,
        "normalized_value": value,
        "knowledge_block": "financials",
        "phase": "administrative",
        "purpose": "display",
        "source_document": filename,
        "source_document_id": f"worker-source-{filename}",
        "document_category": (
            "design_competition_source"
        ),
        "confidence": 0.99,
        "evidence_ids": [],
        "document_priority": 100,
        "reader_name": (
            "design_competition_financial_repair"
        ),
        "section": "explicit_document_fact",
    }

def _deliverable_entry(
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "field": item.get("field_name"),
        "value": item.get("value"),
        "normalized_value": item.get("normalized_value"),
        "confidence": item.get("confidence"),
        "evidence_ids": list(item.get("evidence_ids") or []),
        "source_document": item.get("source_document"),
        "phase": item.get("phase"),
    }


def _semantic_summary(
    compact: ConsolidatedCompetitionData,
) -> dict[str, list[dict[str, Any]]]:
    result = {
        "financials": [],
        "submission": [],
        "contract": [],
    }
    for item in compact.information_model:
        entry = {
            "semantic_type": item.field_name,
            "value": item.value,
            "confidence": item.confidence,
            "evidence_ids": list(item.evidence_ids),
            "source_document": item.source_document,
        }
        if item.knowledge_block == "financials":
            result["financials"].append(entry)
        elif item.phase == "submission":
            result["submission"].append(entry)
        elif item.phase == "contract_execution":
            result["contract"].append(entry)
    return result


def _cache_deterministic_presentation(
    consolidated: dict[str, Any],
    *,
    builder: PresentationBuilder | None = None,
) -> dict[str, Any]:
    presentation_builder = builder or PresentationBuilder()
    presentation = presentation_builder.deterministic(consolidated)
    cache_key = presentation_builder.cache_key(consolidated)
    cache_path = presentation_builder.cache_dir / f"{cache_key}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        presentation.model_dump_json(ensure_ascii=False),
        encoding="utf-8",
    )
    return presentation.model_dump(mode="json")


def _compact_report(
    report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": report.get("status"),
        "version": report.get("version"),
        "facts_total": report.get("facts_total"),
        "information_items_added": report.get(
            "information_items_added",
            0,
        ),
        "warnings": list(report.get("warnings") or [])[:20],
        "groups": [
            {
                "topic_id": group.get("topic_id"),
                "status": group.get("status"),
                "evidences_selected": group.get(
                    "evidences_selected"
                ),
                "facts_count": len(group.get("facts") or []),
                "warnings": list(group.get("warnings") or [])[:10],
            }
            for group in report.get("groups") or []
        ],
    }


def _cap(value: Any, *, depth: int = 0) -> Any:
    if depth >= 7:
        return None
    if isinstance(value, str):
        return value[:3000]
    if isinstance(value, dict):
        return {
            str(key): _cap(child, depth=depth + 1)
            for key, child in list(value.items())[:50]
        }
    if isinstance(value, list):
        return [
            _cap(child, depth=depth + 1)
            for child in value[:30]
        ]
    return value
