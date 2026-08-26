"""Adaptador conservador para a pesquisa pública da Ordem dos Arquitectos.

Esta fonte começa em modo complementar: não cria cartões novos. Apenas associa
uma notícia/página da OA a um concurso já conhecido quando existe uma
correspondência forte.
"""

from __future__ import annotations

import re
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


SOURCE = "ordem_arquitectos"
SOURCE_LABEL = "Ordem dos Arquitectos"
SEARCH_URL = "https://www.ordemdosarquitectos.org/pesquisa/CONCURSO"
SOURCE_HOST = "ordemdosarquitectos.org"

SOURCE_NEGATIVE_PATTERNS = (
    r"\bemprego\b",
    r"\bestagio\b",
    r"procedimento\s+concursal\s+comum",
    r"recrutamento",
    r"\bpremio\b",
    r"\bwebinar\b",
    r"\bworkshop\b",
    r"\bexposicao\b",
    r"\bopen\s+day\b",
)


def _card_for_link(anchor: Tag) -> Tag:
    current = anchor
    for _ in range(7):
        parent = current.parent
        if not isinstance(parent, Tag):
            break
        current = parent
        if current.find(["h2", "h3", "h4", "h5"]):
            return current
    return anchor


def parse_search_results(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        label = normalize(anchor.get_text(" ", strip=True))
        if label not in {"ver mais", "saiba mais"}:
            continue
        href = urljoin(SEARCH_URL, compact(anchor.get("href")))
        parsed = urlparse(href)
        if SOURCE_HOST not in parsed.netloc.casefold() or href in seen:
            continue
        seen.add(href)

        card = _card_for_link(anchor)
        heading = card.find(["h2", "h3", "h4", "h5"])
        title = compact(heading.get_text(" ", strip=True)) if heading else ""
        text = compact(card.get_text(" ", strip=True))
        if not title or "concurso" not in normalize(f"{title} {text}"):
            continue
        items.append({"title": title, "url": href, "search_text": text})
    return items


def _extract_title(soup: BeautifulSoup, fallback: str) -> str:
    for selector in ("h1", "main h2", "article h2", "h2"):
        node = soup.select_one(selector)
        if node:
            title = compact(node.get_text(" ", strip=True))
            if title and normalize(title) not in {"pesquisa", "noticias"}:
                return title
    return fallback


def _extract_publication_date(text: str) -> str:
    patterns = (
        r"publicado\s+em\s+([^\.;|]{4,60})",
        r"(\d{1,2}\s+de\s+[a-zç]+\s+de\s+20\d{2})",
        r"(\d{1,2}[/-]\d{1,2}[/-]20\d{2})",
    )
    for pattern in patterns:
        match = re.search(pattern, normalize(text), flags=re.I)
        if match:
            parsed = parse_portuguese_date(match.group(1))
            if parsed:
                return parsed.isoformat()
    return ""


def _extract_deadline(text: str) -> str:
    patterns = (
        r"entrega\s+de\s+propostas[^\d]*(\d{1,2}[/-]\d{1,2}[/-]20\d{2})",
        r"candidaturas?\s+ate[^\d]*(\d{1,2}[/-]\d{1,2}[/-]20\d{2})",
        r"prazo[^\d]*(\d{1,2}[/-]\d{1,2}[/-]20\d{2})",
    )
    normalized = normalize(text)
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.I)
        if match:
            parsed = parse_portuguese_date(match.group(1))
            if parsed:
                return parsed.isoformat()
    return ""


def _external_official_link(soup: BeautifulSoup, page_url: str) -> str:
    preferred: list[str] = []
    other: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(page_url, compact(anchor.get("href")))
        parsed = urlparse(href)
        host = parsed.netloc.casefold()
        if not href.startswith("http") or SOURCE_HOST in host:
            continue
        if any(token in host for token in ("base.gov", "acingov", "vortal", "saphety", "gov.pt", "cm-")):
            preferred.append(href)
        else:
            other.append(href)
    return (preferred or other or [""])[0]


def parse_detail(
    html: str,
    *,
    page_url: str,
    fallback_title: str,
    search_text: str,
) -> ExternalProcedure:
    soup = BeautifulSoup(html, "html.parser")
    body_text = compact(soup.get_text(" ", strip=True))
    combined = compact(f"{search_text} {body_text}")
    title = _extract_title(soup, fallback_title)
    official = _external_official_link(soup, page_url)
    deadline = _extract_deadline(combined)

    procedure = ExternalProcedure(
        source=SOURCE,
        source_label=SOURCE_LABEL,
        reference=stable_reference(SOURCE, page_url),
        title=title,
        page_url=page_url,
        status="em_curso" if deadline else "desconhecido",
        raw_text=combined,
        documents_url=official,
        official_url=official or page_url,
        publication_date=_extract_publication_date(combined),
        deadline=deadline,
        procedure_type=infer_procedure_type(title, combined),
        complement_only=True,
        metadata={"complement_only_reason": "Pesquisa geral da OA mistura notícias e outros conteúdos."},
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
        html = fetch_html(
            SEARCH_URL,
            session=client,
            request_kind="listing",
        )
        items = parse_search_results(html)
        procedures: list[ExternalProcedure] = []
        for item in items[:MAX_DETAILS]:
            try:
                detail_html = fetch_html(
                    item["url"],
                    session=client,
                    request_kind="detail",
                )
                procedure = parse_detail(
                    detail_html,
                    page_url=item["url"],
                    fallback_title=item["title"],
                    search_text=item["search_text"],
                )
            except Exception:
                procedure = ExternalProcedure(
                    source=SOURCE,
                    source_label=SOURCE_LABEL,
                    reference=stable_reference(SOURCE, item["url"]),
                    title=item["title"],
                    page_url=item["url"],
                    status="desconhecido",
                    raw_text=item["search_text"],
                    official_url=item["url"],
                    procedure_type=infer_procedure_type(item["title"], item["search_text"]),
                    complement_only=True,
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
