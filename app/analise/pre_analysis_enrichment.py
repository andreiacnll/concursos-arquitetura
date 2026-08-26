"""Enriquecimento documental leve, anterior à análise AI.

Preenche os campos usados na Pesquisa sem criar uma análise: tipo normalizado,
preço base/honorários, publicação, prazo e critério de adjudicação. O módulo
reutiliza a cache documental pública e conserva evidências num JSON próprio.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from app.analise.common_project_extractor import extract_common_project_data
from app.analise.platform_documents import (
    discover_public_documents,
    download_public_documents,
    load_cached_platform_documents,
    save_platform_metadata,
)
from app.analise.procedure_analysis import extract_procedure_analysis
from app.database import abrir_conexao


VERSION = "pre-analysis-enrichment-v15.6"
GENERIC_TYPES = {
    "",
    "concurso público",
    "concurso publico",
    "concurso público internacional",
    "concurso publico internacional",
    "procedimento de contratação pública",
    "procedimento de contratacao publica",
    "concurso de arquitetura",
}


@dataclass
class EnrichmentReport:
    concurso_id: int
    status: str
    documents: int = 0
    updated_fields: tuple[str, ...] = ()
    family: str = ""
    warnings: tuple[str, ...] = ()
    evidence_path: str = ""


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _columns(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(concursos)").fetchall()
    }


def _load_concurso(concurso_id: int) -> dict[str, Any]:
    connection = abrir_conexao()
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            """
            SELECT c.*,
                   COALESCE(c.link_pecas, (
                       SELECT cf.documentos_url
                       FROM concurso_fontes AS cf
                       WHERE cf.concurso_id = c.id
                         AND cf.documentos_url IS NOT NULL
                         AND TRIM(cf.documentos_url) != ''
                       ORDER BY cf.principal DESC, cf.id DESC
                       LIMIT 1
                   )) AS enrichment_link_pecas
            FROM concursos AS c
            WHERE c.id = ?
            """,
            (concurso_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ValueError(f"Concurso {concurso_id} não encontrado.")
    item = dict(row)
    item["link_pecas"] = item.get("enrichment_link_pecas") or item.get("link_pecas")
    return item


def _cache_dir(root: Path, concurso_id: int) -> Path:
    analysis_cache = root / "analise_documentos" / str(concurso_id) / "plataforma_publica"
    if (analysis_cache / "metadata.json").exists():
        return analysis_cache
    return root / "analise_documentos" / str(concurso_id) / "pre_analise"


def _obtain_documents(
    concurso: dict[str, Any],
    cache_dir: Path,
    *,
    allow_download: bool,
) -> tuple[list[Any], list[str]]:
    warnings: list[str] = []
    cached = load_cached_platform_documents(cache_dir)
    if cached:
        return cached, warnings
    if not allow_download:
        return [], ["Sem documentos em cache e downloads desativados."]

    result = discover_public_documents(concurso, timeout=45)
    warnings.extend(result.warnings or [])
    public = result.public_documents or []
    if result.status != "success" or not public:
        return [], warnings or [f"Plataforma sem documentos públicos: {result.status}."]

    downloaded = download_public_documents(public, cache_dir, timeout=120)
    save_platform_metadata(cache_dir, result, downloaded)
    return downloaded, warnings


def _extract_texts(cache_dir: Path) -> dict[str, str]:
    # Reutiliza exatamente os leitores e a extração segura já usados pelo worker.
    from app.analise.worker import _extrair_archivos_recursivo, _extrair_textos

    downloads = cache_dir / "downloads"
    if not downloads.exists():
        return {}
    extracted = cache_dir / "extracted"
    extracted.mkdir(parents=True, exist_ok=True)
    _extrair_archivos_recursivo(downloads, extracted)

    texts = _extrair_textos(downloads)
    extracted_texts = _extrair_textos(extracted)
    for name, value in extracted_texts.items():
        if value and name not in texts:
            texts[name] = value
    return texts


def _normalised_type(procedure: dict[str, Any], concurso: dict[str, Any]) -> str:
    family = _clean(procedure.get("family"))
    if family == "design_competition":
        return "Concurso de conceção"
    if family == "design_build":
        return "Conceção-Construção"
    if family == "project_services":
        features = procedure.get("features") or {}
        if features.get("has_design_submission"):
            return "Prestação de serviços de projeto com proposta de conceção"
        return "Prestação de serviços de projeto"
    return _clean(concurso.get("tipo_procedimento"))


def _verified_criteria(procedure: dict[str, Any]) -> dict[str, Any]:
    criteria = procedure.get("award_criteria") or {}
    if not isinstance(criteria, dict):
        return {}
    factors = criteria.get("factors") or []
    verified = bool(criteria.get("verified_top_level_weights"))
    if factors and verified:
        return criteria
    # Não gravar ponderações inferidas a partir de subfatores ou frases soltas.
    return {}


def _build_updates(
    concurso: dict[str, Any],
    common: dict[str, Any],
    procedure: dict[str, Any],
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    current_type = _clean(concurso.get("tipo_procedimento"))
    normalised_type = _normalised_type(procedure, concurso)
    if normalised_type and (current_type.casefold() in {item.casefold() for item in GENERIC_TYPES} or current_type != normalised_type):
        updates["tipo_procedimento"] = normalised_type

    publication = common.get("publication_date") or {}
    deadline = common.get("submission_deadline") or {}
    price = common.get("base_price") or {}
    for metric in procedure.get("top_metrics") or []:
        if not isinstance(metric, dict):
            continue
        key = metric.get("key")
        if key == "procedure_value" and not _clean(price.get("value")):
            price = {"value": metric.get("value")}
        elif key == "submission_deadline" and not _clean(deadline.get("value")):
            if metric.get("status") in {"confirmed", "relative_confirmed"}:
                deadline = {
                    "value": metric.get("value"),
                    "status": metric.get("status"),
                }
    criteria = _verified_criteria(procedure)

    if _clean(publication.get("value")) and not _clean(concurso.get("data")):
        updates["data"] = publication["value"]
    if _clean(deadline.get("value")):
        if not _clean(concurso.get("data_entrega_propostas")):
            updates["data_entrega_propostas"] = deadline["value"]
        if not _clean(concurso.get("data_limite")):
            updates["data_limite"] = deadline["value"]
    if _clean(price.get("value")) and not _clean(concurso.get("preco_base")):
        updates["preco_base"] = price["value"]

    if criteria:
        updates["criterio_tipo"] = criteria.get("type") or None
        updates["criterio_resumo"] = criteria.get("summary") or None
        updates["criterio_detalhe"] = json.dumps(
            {
                "factors": criteria.get("factors") or [],
                "formula": criteria.get("formula") or "",
                "tie_breakers": criteria.get("tie_breakers") or [],
                "source_document": criteria.get("source_document") or "",
                "source_heading": criteria.get("source_heading") or "",
            },
            ensure_ascii=False,
        )
    return {key: value for key, value in updates.items() if value is not None}


def _persist_updates(concurso_id: int, updates: dict[str, Any]) -> tuple[str, ...]:
    if not updates:
        return ()
    connection = abrir_conexao()
    try:
        available = _columns(connection)
        safe = {key: value for key, value in updates.items() if key in available}
        if not safe:
            return ()
        assignments = ", ".join(f"{key} = ?" for key in safe)
        connection.execute(
            f"UPDATE concursos SET {assignments} WHERE id = ?",
            (*safe.values(), concurso_id),
        )
        connection.commit()
        return tuple(safe)
    finally:
        connection.close()


def enrich_concurso(
    concurso_id: int,
    *,
    root: Path | None = None,
    allow_download: bool = True,
) -> EnrichmentReport:
    project_root = (root or Path.cwd()).resolve()
    concurso = _load_concurso(concurso_id)
    cache = _cache_dir(project_root, concurso_id)
    warnings: list[str] = []

    try:
        documents, obtain_warnings = _obtain_documents(
            concurso,
            cache,
            allow_download=allow_download,
        )
        warnings.extend(obtain_warnings)
    except Exception as error:  # a recolha principal nunca deve falhar por isto
        return EnrichmentReport(
            concurso_id=concurso_id,
            status="document_error",
            warnings=(str(error),),
        )

    if not documents:
        # O tipo ainda pode ser normalizado apenas pelos dados estruturados.
        procedure = extract_procedure_analysis(
            ficha={},
            textos={},
            concurso=concurso,
        )
        updates = _build_updates(concurso, {}, procedure)
        fields = _persist_updates(concurso_id, updates)
        return EnrichmentReport(
            concurso_id=concurso_id,
            status="classified_without_documents",
            updated_fields=fields,
            family=_clean(procedure.get("family")),
            warnings=tuple(warnings),
        )

    texts = _extract_texts(cache)
    if not texts:
        return EnrichmentReport(
            concurso_id=concurso_id,
            status="no_readable_text",
            documents=len(documents),
            warnings=tuple(warnings),
        )

    common = extract_common_project_data(textos=texts, concurso=concurso)
    procedure = extract_procedure_analysis(
        ficha={"common_project_extraction": common},
        textos=texts,
        concurso=concurso,
    )
    updates = _build_updates(concurso, common, procedure)
    fields = _persist_updates(concurso_id, updates)

    evidence = {
        "version": VERSION,
        "concurso_id": concurso_id,
        "updates": updates,
        "common": common,
        "procedure": procedure,
        "documents": [asdict(document) for document in documents],
        "warnings": warnings,
    }
    evidence_path = cache / "pre_analysis_enrichment.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return EnrichmentReport(
        concurso_id=concurso_id,
        status="updated" if fields else "no_new_verified_fields",
        documents=len(documents),
        updated_fields=fields,
        family=_clean(procedure.get("family")),
        warnings=tuple(warnings),
        evidence_path=str(evidence_path.relative_to(project_root)),
    )


def enrich_many(
    concurso_ids: Iterable[int],
    *,
    root: Path | None = None,
    allow_download: bool = True,
) -> list[EnrichmentReport]:
    return [
        enrich_concurso(
            int(concurso_id),
            root=root,
            allow_download=allow_download,
        )
        for concurso_id in dict.fromkeys(int(value) for value in concurso_ids)
    ]


def source_concurso_ids(source: str = "lisboa_sru") -> list[int]:
    connection = abrir_conexao()
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT cf.concurso_id
            FROM concurso_fontes AS cf
            JOIN concursos AS c ON c.id = cf.concurso_id
            WHERE cf.fonte = ?
              AND COALESCE(cf.estado_fonte, '') != 'concluido'
            ORDER BY cf.concurso_id
            """,
            (source,),
        ).fetchall()
        return [int(row[0]) for row in rows]
    finally:
        connection.close()


def automatic_enabled() -> bool:
    return os.getenv("CNLL_PRE_ANALYSIS_ENRICHMENT", "1").strip().casefold() not in {
        "0", "false", "no", "off"
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Enriquece os cards de Pesquisa sem criar análises AI.",
    )
    parser.add_argument("ids", nargs="*", type=int)
    parser.add_argument("--source", default="lisboa_sru")
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args()

    ids = args.ids or source_concurso_ids(args.source)
    reports = enrich_many(
        ids,
        root=Path.cwd(),
        allow_download=not args.cache_only,
    )
    print("ENRIQUECIMENTO PRÉ-ANÁLISE")
    for report in reports:
        fields = ", ".join(report.updated_fields) or "sem novos campos confirmados"
        print(f"- {report.concurso_id}: {report.status} · {fields}")
        for warning in report.warnings:
            print(f"    aviso: {warning}")


if __name__ == "__main__":
    main()
