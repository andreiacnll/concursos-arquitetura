"""Adaptador conservador para os concursos do Espaço de Arquitetura."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from app.fontes.common import (
    ExternalProcedure,
    MAX_DETAILS,
    compact,
    evaluate_relevance,
    fetch_html,
    infer_procedure_type,
    normalize,
    parse_portuguese_date,
    stable_reference,
)


SOURCE = "espaco_arquitetura"
SOURCE_LABEL = "Espaço de Arquitetura"
LIST_URL = "https://espacodearquitetura.com/concursos/"
ARCHIVE_URL_TEMPLATE = (
    "https://espacodearquitetura.com/categoria-concurso/{year}/"
)
SOURCE_HOST = "espacodearquitetura.com"

SOURCE_NEGATIVE_PATTERNS = (
    r"\bpremio\b",
    r"\bopen\s+call\b",
    r"\bvoluntariado\b",
    r"concurso\s+de\s+fotografia",
    r"design\s+de\s+produto",
    r"concurso\s+para\s+estudantes",
    r"\bworkshop\b",
    r"\bexposicao\b",
    r"\bbolsa\b",
    r"\blogotipo\b",
)


def _nearest_card_text(anchor: Tag) -> str:
    current: Tag | None = anchor
    best = compact(anchor.get_text(" ", strip=True))
    for _ in range(7):
        current = current.parent if isinstance(current, Tag) else None
        if current is None:
            break
        text = compact(current.get_text(" ", strip=True))
        if len(text) > len(best):
            best = text
        if (
            "publicado em" in normalize(text)
            or "inicio em" in normalize(text)
            or current.name == "article"
        ) and len(text) <= 1800:
            return text
    return best


def _is_detail_url(url: str) -> bool:
    parsed = urlparse(url)
    if SOURCE_HOST not in parsed.netloc.casefold():
        return False
    path = parsed.path.rstrip("/")
    if not path.startswith("/concursos/"):
        return False
    excluded = {
        "/concursos",
        "/concursos/page",
    }
    return path not in excluded and "/page/" not in path


def parse_listing(
    html: str,
    *,
    base_url: str = LIST_URL,
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, compact(anchor.get("href")))
        if not _is_detail_url(href) or href in seen:
            continue
        seen.add(href)
        title = compact(anchor.get_text(" ", strip=True))
        card_text = _nearest_card_text(anchor)
        if not title or len(title) < 6:
            heading = anchor.find(["h1", "h2", "h3", "h4", "h5"])
            title = compact(heading.get_text(" ", strip=True)) if heading else ""
        if not title:
            continue
        items.append({"title": title, "url": href, "listing_text": card_text})
    return items


def _extract_title(soup: BeautifulSoup, fallback: str) -> str:
    heading = soup.find("h1")
    if heading:
        title = compact(heading.get_text(" ", strip=True))
        if title:
            return title
    return fallback


def _publication_date(text: str) -> str:
    match = re.search(
        r"publicado\s+em\s+(.{3,60}?)(?:\s+por\s+|\.|\||$)",
        text,
        flags=re.I,
    )
    parsed = parse_portuguese_date(match.group(1) if match else text)
    return parsed.isoformat() if parsed else ""


def _date_range(text: str) -> tuple[str, str]:
    match = re.search(
        r"in[ií]cio\s+em\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s+at[eé]\s+"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        text,
        flags=re.I,
    )
    if not match:
        return "", ""
    start = parse_portuguese_date(match.group(1))
    end = parse_portuguese_date(match.group(2))
    return (
        start.isoformat() if start else "",
        end.isoformat() if end else "",
    )


def _extract_author(text: str) -> str:
    match = re.search(r"\(\s*por\s+([^\)]+)\)", text, flags=re.I)
    return compact(match.group(1)) if match else ""


def _extract_promoter(text: str) -> str:
    patterns = (
        r"promovid[oa]\s+pela?\s+([^\.;]{3,180})",
        r"entidade\s+promotora\s*:?\s*([^\.;]{3,180})",
        r"organizado\s+pela?\s+([^\.;]{3,180})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return compact(match.group(1))
    return ""


def _best_official_url(soup: BeautifulSoup, detail_url: str) -> str:
    preferred: list[str] = []
    other: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(detail_url, compact(anchor.get("href")))
        parsed = urlparse(href)
        host = parsed.netloc.casefold()
        if not href.startswith("http") or SOURCE_HOST in host:
            continue
        if any(token in host for token in ("base.gov", "acingov", "vortal", "saphety", "gov.pt", "cm-")):
            preferred.append(href)
        else:
            other.append(href)
    return (preferred or other or [detail_url])[0]


def parse_detail(
    html: str,
    *,
    detail_url: str,
    fallback_title: str,
    listing_text: str,
) -> ExternalProcedure:
    soup = BeautifulSoup(html, "html.parser")
    body_text = compact(soup.get_text(" ", strip=True))
    combined = compact(f"{listing_text} {body_text}")
    title = _extract_title(soup, fallback_title)
    publication_date = _publication_date(combined)
    _start, deadline = _date_range(combined)

    end_date = parse_portuguese_date(deadline)
    status = "em_curso" if end_date and end_date >= date.today() else "concluido"
    if not deadline:
        status = "desconhecido"

    entity = _extract_promoter(body_text) or _extract_author(listing_text)
    official_url = _best_official_url(soup, detail_url)

    procedure = ExternalProcedure(
        source=SOURCE,
        source_label=SOURCE_LABEL,
        reference=stable_reference(SOURCE, detail_url),
        title=title,
        page_url=detail_url,
        status=status,
        raw_text=combined,
        entity=entity,
        documents_url=official_url if official_url != detail_url else "",
        official_url=official_url,
        publication_date=publication_date,
        deadline=deadline,
        procedure_type=infer_procedure_type(title, combined),
        metadata={"source_page_is_editorial": True},
    )
    procedure.relevant, procedure.relevance_reason = evaluate_relevance(
        procedure,
        source_negative_patterns=SOURCE_NEGATIVE_PATTERNS,
    )
    return procedure


def collect(session: requests.Session | None = None) -> list[ExternalProcedure]:
    own_session = session is None
    client = session or requests.Session()
    try:
        current_year = date.today().year
        candidate_urls = (
            LIST_URL,
            ARCHIVE_URL_TEMPLATE.format(year=current_year),
        )

        listing_items: list[dict[str, str]] = []
        listing_errors: list[str] = []

        for listing_url in candidate_urls:
            try:
                listing_html = fetch_html(
                    listing_url,
                    session=client,
                    request_kind="listing",
                )
                listing_items = parse_listing(
                    listing_html,
                    base_url=listing_url,
                )
            except Exception as exc:
                listing_errors.append(
                    f"{listing_url}: {type(exc).__name__}: {exc}"
                )
                continue

            if listing_items:
                break

        if not listing_items and listing_errors:
            raise RuntimeError(
                "Nenhuma listagem do Espaço de Arquitetura "
                "ficou disponível. " + " | ".join(listing_errors)
            )

        procedures: list[ExternalProcedure] = []
        for item in listing_items[:MAX_DETAILS]:
            try:
                detail_html = fetch_html(
                    item["url"],
                    session=client,
                    request_kind="detail",
                )
                procedure = parse_detail(
                    detail_html,
                    detail_url=item["url"],
                    fallback_title=item["title"],
                    listing_text=item["listing_text"],
                )
            except Exception:
                procedure = ExternalProcedure(
                    source=SOURCE,
                    source_label=SOURCE_LABEL,
                    reference=stable_reference(SOURCE, item["url"]),
                    title=item["title"],
                    page_url=item["url"],
                    status="desconhecido",
                    raw_text=item["listing_text"],
                    official_url=item["url"],
                    publication_date=_publication_date(item["listing_text"]),
                    procedure_type=infer_procedure_type(
                        item["title"],
                        item["listing_text"],
                    ),
                )
                procedure.relevant, procedure.relevance_reason = evaluate_relevance(
                    procedure,
                    source_negative_patterns=SOURCE_NEGATIVE_PATTERNS,
                )
            procedures.append(procedure)
        return procedures
    finally:
        if own_session:
            client.close()
