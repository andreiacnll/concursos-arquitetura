"""Adaptador para a Plataforma de Encomenda da OA-SRS/OA-SRLVT."""

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
)


SOURCE = "oasrs_encomenda"
SOURCE_LABEL = "Plataforma Encomenda OA-SRS"
LIST_URL = "https://encomenda.oasrs.org/concursos"
ACTIVE_LIST_URLS = (
    "https://encomenda.oasrs.org/concursos/oasrs",
    "https://encomenda.oasrs.org/concursos/outros",
)
DETAIL_FRAGMENT = "/concursos/detalhe/"

DATE_ISO_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def _nearest_card_text(anchor: Tag) -> str:
    current: Tag | None = anchor
    best = compact(anchor.get_text(" ", strip=True))
    for _ in range(6):
        current = current.parent if isinstance(current, Tag) else None
        if current is None:
            break
        text = compact(current.get_text(" ", strip=True))
        if len(text) > len(best):
            best = text
        if "a decorrer" in normalize(text) or "concurso" in normalize(text):
            if len(text) <= 1200:
                return text
    return best


def parse_listing(
    html: str,
    *,
    base_url: str = LIST_URL,
    forced_status: str = "",
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, compact(anchor.get("href")))
        if DETAIL_FRAGMENT not in urlparse(href).path:
            continue
        if href in seen:
            continue
        seen.add(href)

        card_text = _nearest_card_text(anchor)
        title = compact(anchor.get_text(" ", strip=True))
        if not title or normalize(title) in {"ver mais", "saiba mais"}:
            heading = anchor.find(["h1", "h2", "h3", "h4", "h5"])
            title = compact(heading.get_text(" ", strip=True)) if heading else ""
        if not title:
            continue

        date_match = DATE_ISO_RE.search(card_text)
        status = (
            forced_status
            or (
                "em_curso"
                if "a decorrer" in normalize(card_text)
                else "desconhecido"
            )
        )
        items.append(
            {
                "title": title,
                "url": href,
                "listing_text": card_text,
                "publication_date": date_match.group(1) if date_match else "",
                "status": status,
            }
        )
    return items


def _label_value(soup: BeautifulSoup, labels: tuple[str, ...]) -> str:
    for text_node in soup.find_all(string=True):
        label = normalize(text_node)
        if label not in labels:
            continue
        parent = text_node.parent
        if not isinstance(parent, Tag):
            continue
        for candidate in (
            parent.find_next_sibling(),
            parent.parent.find_next_sibling() if isinstance(parent.parent, Tag) else None,
            parent.find_next(),
        ):
            if not isinstance(candidate, Tag):
                continue
            value = compact(candidate.get_text(" ", strip=True))
            if value and normalize(value) not in labels and len(value) < 300:
                return value
    return ""


def _extract_title(soup: BeautifulSoup, fallback: str) -> str:
    for selector in ("h1", "main h2", "article h2", "h2"):
        heading = soup.select_one(selector)
        if heading:
            title = compact(heading.get_text(" ", strip=True))
            if title and normalize(title) not in {"concursos", "concurso"}:
                return title
    return fallback


def _extract_deadline(text: str) -> str:
    patterns = (
        r"propostas\s+ate\s+([^\n|]+)",
        r"data[- ]limite\s+para\s+entrega\s+de\s+propostas\s*:?\s*([^\n|]+)",
        r"data[- ]limite\s+para\s+apresentacao\s+de\s+propostas\s*:?\s*([^\n|]+)",
    )
    normalized = normalize(text)
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.I)
        if not match:
            continue
        parsed = parse_portuguese_date(match.group(1))
        if parsed:
            return parsed.isoformat()
    return ""


def _best_documents_url(soup: BeautifulSoup, detail_url: str) -> str:
    preferred: list[str] = []
    fallback: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(detail_url, compact(anchor.get("href")))
        host = urlparse(href).netloc.casefold()
        label = normalize(anchor.get_text(" ", strip=True))
        if not href.startswith("http"):
            continue
        if any(value in host for value in ("acingov", "vortal", "saphety", "base.gov")):
            preferred.append(href)
        elif href.lower().endswith(".pdf") or "document" in label or "termos" in label:
            fallback.append(href)
    return (preferred or fallback or [""])[0]


def parse_detail(
    html: str,
    *,
    detail_url: str,
    fallback_title: str,
    listing_text: str,
    publication_date: str,
    listing_status: str,
) -> ExternalProcedure:
    soup = BeautifulSoup(html, "html.parser")
    body_text = compact(soup.get_text(" ", strip=True))
    title = _extract_title(soup, fallback_title)
    entity = _label_value(soup, ("promotor", "entidade promotora"))
    location = _label_value(soup, ("localizacao", "local"))
    program = _label_value(soup, ("programa",))

    normalized = normalize(body_text)
    status = listing_status

    # Quando a página de listagem é uma secção oficial "em curso",
    # essa classificação prevalece. O texto completo da página de detalhe
    # pode conter referências a concursos concluídos, resultados ou arquivo
    # no menu e não deve transformar um concurso ativo em concluído.
    if listing_status != "em_curso":
        if "concluido" in normalized and "a decorrer" not in normalized:
            status = "concluido"
        elif "a decorrer" in normalized:
            status = "em_curso"

    path_parts = [part for part in urlparse(detail_url).path.split("/") if part]
    try:
        detail_index = path_parts.index("detalhe")
        token = path_parts[detail_index + 1]
    except (ValueError, IndexError):
        token = detail_url

    procedure = ExternalProcedure(
        source=SOURCE,
        source_label=SOURCE_LABEL,
        reference=f"OASRS:{token}",
        title=title,
        page_url=detail_url,
        status=status,
        raw_text=compact(f"{listing_text} {body_text}"),
        entity=entity,
        documents_url=_best_documents_url(soup, detail_url),
        official_url=detail_url,
        publication_date=publication_date,
        deadline=_extract_deadline(body_text),
        location=location,
        procedure_type=infer_procedure_type(title, body_text),
        metadata={"program": program or None},
    )
    procedure.relevant, procedure.relevance_reason = evaluate_relevance(procedure)
    return procedure


def collect(session: requests.Session | None = None) -> list[ExternalProcedure]:
    own_session = session is None
    client = session or requests.Session()
    try:
        listing_items: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        errors: list[str] = []

        # Estas duas páginas são os filtros oficiais de concursos em curso.
        # Assim, a atividade não depende de encontrar a expressão
        # "A decorrer" dentro da estrutura HTML de cada cartão.
        for active_url in ACTIVE_LIST_URLS:
            try:
                listing_html = fetch_html(
                    active_url,
                    session=client,
                    request_kind="listing",
                )
                items = parse_listing(
                    listing_html,
                    base_url=active_url,
                    forced_status="em_curso",
                )
            except Exception as exc:
                errors.append(
                    f"{active_url}: {type(exc).__name__}: {exc}"
                )
                continue

            for item in items:
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                listing_items.append(item)

        # Fallback compatível com a listagem geral, caso o site volte
        # a alterar os filtros ou os dois endereços deixem de responder.
        if not listing_items:
            try:
                listing_html = fetch_html(
                    LIST_URL,
                    session=client,
                    request_kind="listing",
                )
                listing_items = parse_listing(
                    listing_html,
                    base_url=LIST_URL,
                )
            except Exception as exc:
                errors.append(
                    f"{LIST_URL}: {type(exc).__name__}: {exc}"
                )

        if not listing_items and errors:
            raise RuntimeError(
                "Não foi possível obter concursos da OA-SRS. "
                + " | ".join(errors)
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
                    publication_date=item["publication_date"],
                    listing_status=item["status"],
                )
            except Exception:
                procedure = ExternalProcedure(
                    source=SOURCE,
                    source_label=SOURCE_LABEL,
                    reference=f"OASRS:{item['url']}",
                    title=item["title"],
                    page_url=item["url"],
                    status=item["status"],
                    raw_text=item["listing_text"],
                    official_url=item["url"],
                    publication_date=item["publication_date"],
                    procedure_type=infer_procedure_type(
                        item["title"],
                        item["listing_text"],
                    ),
                )
                procedure.relevant, procedure.relevance_reason = (
                    evaluate_relevance(procedure)
                )
            procedures.append(procedure)
        return procedures
    finally:
        if own_session:
            client.close()
