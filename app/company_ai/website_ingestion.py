from __future__ import annotations

import logging
from typing import Any

from .company_ingestion import ingest_company_information
from .knowledge_storage import save_company_source_raw_text
from .website_crawler import WebsiteCrawlResult, crawl_website
from .website_normalizer import normalize_website_content


logger = logging.getLogger(__name__)


def _dedupe(values: list[str]) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []
    for value in values:
        texto = str(value or "").strip()
        if not texto:
            continue
        chave = texto.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(texto)
    return resultado


def ingest_company_website(
    company_id: int,
    website_url: str,
    *,
    max_pages: int = 12,
    max_depth: int = 2,
    timeout_seconds: int = 15,
) -> dict[str, Any]:
    crawl_result: WebsiteCrawlResult = crawl_website(
        website_url,
        max_pages=max_pages,
        max_depth=max_depth,
        timeout_seconds=timeout_seconds,
    )
    normalized = normalize_website_content(crawl_result)
    source = f"website:{crawl_result.start_url}"
    save_company_source_raw_text(
        company_id,
        source=source,
        source_type="website",
        url=crawl_result.final_url,
        raw_text=crawl_result.combined_text,
    )

    ingestion_result = ingest_company_information(
        company_id,
        normalized.combined_text,
        source=source,
        project_names=normalized.project_names,
        section_urls=normalized.section_urls,
        section_evidence=normalized.section_evidence,
    )

    projects_found = _dedupe(normalized.project_names)
    services_found = _dedupe(crawl_result.services_found)
    extraction = ingestion_result.get("extraction")
    extraction_warnings = []
    if extraction is not None:
        extraction_warnings = [
            str(warning or "").strip()
            for warning in getattr(extraction, "warnings", [])
        ]
    warnings = _dedupe(
        [*crawl_result.warnings, *normalized.warnings, *extraction_warnings]
    )

    status = "success"
    if crawl_result.pages_visited <= 0:
        status = "failed"
        warnings.append("no_pages_visited")
    elif not projects_found:
        status = "partial"
        warnings.append("no_projects_found")
    elif ingestion_result.get("facts_created", 0) <= 0:
        status = "partial"
        warnings.append("no_facts_created")

    logger.info(
        "[website-ingest] factos guardados %s",
        ingestion_result.get("facts_created", 0),
    )

    return {
        "status": status,
        "source_url": crawl_result.final_url,
        "pages_visited": crawl_result.pages_visited,
        "facts_created": ingestion_result.get("facts_created", 0),
        "projects_found": projects_found,
        "services_found": services_found,
        "competences_found": _dedupe(crawl_result.competences_found),
        "normalization": {
            "removed_blocks": normalized.removed_blocks,
            "sections": [
                section
                for section, blocks in normalized.sections.items()
                if blocks
            ],
        },
        "warnings": warnings,
    }
