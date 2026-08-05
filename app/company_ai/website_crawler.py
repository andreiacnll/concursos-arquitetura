from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

try:  # pragma: no cover - optional dependency
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional dependency
    sync_playwright = None


logger = logging.getLogger(__name__)

_IRRELEVANT_EXTENSIONS = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".zip",
    ".rar",
    ".7z",
    ".mp4",
    ".mp3",
    ".avi",
    ".mov",
    ".wmv",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".xml",
    ".json",
    ".csv",
    ".txt",
)

_GENERIC_LINK_TEXTS = {
    "",
    "read more",
    "more",
    "ver mais",
    "saiba mais",
    "continue reading",
    "details",
    "detail",
    "view project",
    "project",
    "projects",
    "> find more",
    "more on architecture...",
}

_PROJECT_HINTS = (
    "/portfolio-item/",
    "/works/",
    "/project/",
    "/projects/",
)

_GENERIC_PROJECT_TITLES = {
    "works",
    "work",
    "go",
    "office",
    "about",
    "contact",
    "contacts",
    "news",
    "publications",
    "services",
    "home",
    "homepage",
    "portfolio",
    "> find more",
    "more on architecture...",
}


@dataclass
class CrawledPage:
    url: str
    depth: int
    title: str = ""
    h1: str = ""
    text: str = ""
    links: list[str] = field(default_factory=list)
    project_names: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    competences: list[str] = field(default_factory=list)
    typologies: list[str] = field(default_factory=list)


@dataclass
class WebsiteCrawlResult:
    start_url: str
    final_url: str
    pages_visited: int = 0
    pages: list[CrawledPage] = field(default_factory=list)
    combined_text: str = ""
    project_names: list[str] = field(default_factory=list)
    services_found: list[str] = field(default_factory=list)
    competences_found: list[str] = field(default_factory=list)
    typologies_found: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _normalizar_url(url: str) -> str:
    texto = str(url or "").strip()
    if not texto:
        raise ValueError("URL vazia.")
    if not texto.startswith(("http://", "https://")):
        texto = f"https://{texto}"
    return texto


def _canonizar_url(url: str) -> str:
    url_sem_fragmento, _ = urldefrag(url)
    partes = urlparse(url_sem_fragmento)
    path = partes.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse(
        (
            partes.scheme.lower(),
            partes.netloc.lower(),
            path,
            "",
            partes.query,
            "",
        )
    )


def _mesmo_dominio(url: str, dominio_base: str) -> bool:
    return urlparse(url).netloc.lower() == dominio_base.lower()


def _e_link_util(url: str) -> bool:
    url_normalizado = url.lower().split("?", 1)[0]
    return not any(url_normalizado.endswith(ext) for ext in _IRRELEVANT_EXTENSIONS)


def _limpar_texto(valor: Any) -> str:
    return " ".join(str(valor or "").split())


def _normalizar_texto(valor: Any) -> str:
    return _limpar_texto(valor).lower()


def _dedupe(valores: list[str]) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []
    for valor in valores:
        texto = _limpar_texto(valor)
        if not texto:
            continue
        chave = texto.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(texto)
    return resultado


def _extrair_palavras_chave(texto: str) -> dict[str, list[str]]:
    base = _normalizar_texto(texto)
    services: list[str] = []
    competences: list[str] = []
    typologies: list[str] = []

    service_rules = {
        "architecture": "Architecture",
        "arquitetura": "Architecture",
        "urbanism": "Urbanism",
        "urbanismo": "Urbanism",
        "landscape": "Landscape",
        "paisagismo": "Landscape",
        "interior design": "Interior Design",
        "interiores": "Interior Design",
        "consulting": "Consulting",
        "consultoria": "Consulting",
        "research": "Research & Innovation",
        "sustainability": "Sustainability",
    }
    competence_rules = {
        "bim": "BIM",
        "computational design": "Computational Design",
        "coordenação": "Coordination",
        "coordenacao": "Coordination",
        "engineering": "Engineering",
        "engenharia": "Engineering",
        "branding": "Branding",
        "graphic design": "Graphic Design",
    }
    typology_rules = {
        "school": "Schools & Education",
        "escola": "Schools & Education",
        "hospital": "Health & Mental Care",
        "saude": "Health & Mental Care",
        "housing": "Housing",
        "habitacao": "Housing",
        "housing complex": "Housing",
        "hotel": "Hospitality",
        "heritage": "Heritage Buildings",
        "cultural": "Cultural Buildings",
        "institutional": "Institutional Buildings",
        "sports": "Sports Centre",
        "stadium": "Sports Centre",
        "refurbishment": "Refurbishment",
        "retail": "Commercial & Retail",
        "commercial": "Commercial & Retail",
        "public space": "Public Space",
    }

    for chave, valor in service_rules.items():
        if chave in base:
            services.append(valor)
    for chave, valor in competence_rules.items():
        if chave in base:
            competences.append(valor)
    for chave, valor in typology_rules.items():
        if chave in base:
            typologies.append(valor)

    return {
        "services": _dedupe(services),
        "competences": _dedupe(competences),
        "typologies": _dedupe(typologies),
    }


def _extrair_texto_e_links(
    html: str,
    base_url: str,
) -> tuple[str, str, str, list[tuple[str, str]], list[str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = _limpar_texto(soup.title.get_text(" ")) if soup.title else ""
    h1 = ""
    h1_tag = soup.find("h1")
    if h1_tag is not None:
        h1 = _limpar_texto(h1_tag.get_text(" "))

    links: list[tuple[str, str]] = []
    project_names: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href") or ""
        destino = urljoin(base_url, href)
        texto = _limpar_texto(anchor.get_text(" "))
        card = anchor.find_parent(class_="qodef-pl-item-inner")
        if card is not None:
            titulo_card = card.select_one(".qodef-pli-title")
            if titulo_card is not None:
                texto_card = _limpar_texto(titulo_card.get_text(" "))
                texto_card = texto_card.lstrip("—").strip()
                if texto_card:
                    texto = texto_card
        links.append((destino, texto))
        texto_normalizado = _normalizar_texto(texto)
        if (
            texto_normalizado
            and texto_normalizado not in _GENERIC_LINK_TEXTS
            and "/portfolio-item/" in destino.lower()
        ):
            project_names.append(texto)

    linhas_texto: list[str] = []
    if title:
        linhas_texto.append(title)
    if h1 and h1 != title:
        linhas_texto.append(h1)
    for tag in soup.find_all(["h2", "h3", "p", "li"]):
        texto = _limpar_texto(tag.get_text(" "))
        if texto:
            linhas_texto.append(texto)

    texto = "\n".join(linhas_texto).strip()
    return texto, title, h1, links, project_names


def _fetch_html_requests(url: str, timeout_seconds: int) -> tuple[str, str]:
    resposta = requests.get(
        url,
        timeout=timeout_seconds,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
        },
    )
    resposta.raise_for_status()
    return resposta.url or url, resposta.text


def _fetch_html_playwright(url: str, timeout_seconds: int) -> tuple[str, str]:
    if sync_playwright is None:
        raise RuntimeError("Playwright indisponivel neste ambiente.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        try:
            context = browser.new_context(
                locale="pt-PT",
                timezone_id="Europe/Lisbon",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 1000},
            )
            try:
                page = context.new_page()
                page.set_default_timeout(timeout_seconds * 1000)
                resposta = page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=timeout_seconds * 1000,
                )
                if resposta is not None and resposta.status >= 400:
                    raise RuntimeError(
                        f"HTTP {resposta.status} no carregamento renderizado."
                    )
                return page.url or url, page.content()
            finally:
                context.close()
        finally:
            browser.close()


def _fetch_html(url: str, timeout_seconds: int) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    try:
        final_url, html = _fetch_html_requests(url, timeout_seconds)
        texto, _, _, _, _ = _extrair_texto_e_links(html, final_url)
        if len(texto) < 400:
            warnings.append("requests_text_too_small")
            final_url, html = _fetch_html_playwright(url, timeout_seconds)
        return final_url, html, warnings
    except Exception as erro:
        warnings.append(f"requests_failed:{type(erro).__name__}")
        final_url, html = _fetch_html_playwright(url, timeout_seconds)
        return final_url, html, warnings


def _adicionar_unicos(destino: list[str], novos: list[str]) -> None:
    vistos = {item.lower() for item in destino}
    for item in novos:
        texto = _limpar_texto(item)
        if not texto:
            continue
        chave = texto.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        destino.append(texto)


def _nome_projeto_valido(texto: str, url: str) -> bool:
    nome = _normalizar_texto(texto)
    if not nome or nome in _GENERIC_PROJECT_TITLES:
        return False
    if len(nome) < 3:
        return False
    if any(hint in url.lower() for hint in _PROJECT_HINTS):
        return True
    return True


def crawl_website(
    start_url: str,
    *,
    max_pages: int = 12,
    max_depth: int = 2,
    timeout_seconds: int = 15,
) -> WebsiteCrawlResult:
    inicial = _normalizar_url(start_url)
    logger.info("[website-ingest] URL inicial %s", inicial)

    fila: deque[tuple[str, int]] = deque([(inicial, 0)])
    visitados: set[str] = set()
    paginas: list[CrawledPage] = []
    textos_aggregados: list[str] = []
    project_names: list[str] = []
    services: list[str] = []
    competences: list[str] = []
    typologies: list[str] = []
    warnings: list[str] = []

    dominio_base = urlparse(inicial).netloc
    final_url = inicial

    while fila and len(paginas) < max_pages:
        url_atual, depth = fila.popleft()
        url_canonica = _canonizar_url(url_atual)
        if url_canonica in visitados:
            continue
        visitados.add(url_canonica)

        if depth > max_depth:
            continue
        if not _mesmo_dominio(url_canonica, dominio_base):
            continue
        if not _e_link_util(url_canonica):
            continue

        try:
            final_url, html, avisos_fetch = _fetch_html(url_canonica, timeout_seconds)
            warnings.extend(avisos_fetch)
            for aviso_fetch in avisos_fetch:
                logger.warning("[website-ingest] erro ou aviso %s", aviso_fetch)
            texto, title, h1, links, nomes_projeto = _extrair_texto_e_links(
                html,
                final_url,
            )
            keyword_sets = _extrair_palavras_chave(texto)
            pagina = CrawledPage(
                url=final_url,
                depth=depth,
                title=title,
                h1=h1,
                text=texto,
                links=[link for link, _ in links],
                project_names=nomes_projeto,
                services=keyword_sets["services"],
                competences=keyword_sets["competences"],
                typologies=keyword_sets["typologies"],
            )
            paginas.append(pagina)

            logger.info("[website-ingest] pagina visitada %s", final_url)
            logger.info("[website-ingest] links descobertos %s", len(links))
            logger.info(
                "[website-ingest] caracteres extraidos %s",
                len(texto),
            )

            textos_aggregados.append(texto)
            nomes_candidatos = [*nomes_projeto]
            if "/portfolio-item/" in final_url.lower():
                if _nome_projeto_valido(title, final_url):
                    nomes_candidatos.append(title)
                if _nome_projeto_valido(h1, final_url):
                    nomes_candidatos.append(h1)
            _adicionar_unicos(project_names, nomes_candidatos)
            _adicionar_unicos(services, keyword_sets["services"])
            _adicionar_unicos(competences, keyword_sets["competences"])
            _adicionar_unicos(typologies, keyword_sets["typologies"])

            for destino, texto_link in links:
                destino_canonico = _canonizar_url(destino)
                if destino_canonico in visitados:
                    continue
                if not _mesmo_dominio(destino_canonico, dominio_base):
                    continue
                if not _e_link_util(destino_canonico):
                    continue
                texto_normalizado = _normalizar_texto(texto_link)
                if any(
                    hint in destino_canonico.lower()
                    for hint in _PROJECT_HINTS
                ) or texto_normalizado not in _GENERIC_LINK_TEXTS:
                    fila.append((destino_canonico, depth + 1))

            logger.info(
                "[website-ingest] projetos encontrados %s",
                len(project_names),
            )
        except Exception as erro:
            aviso = f"erro:{type(erro).__name__}"
            warnings.append(aviso)
            logger.warning("[website-ingest] erro ou aviso %s", aviso)

    combined_text = "\n\n".join(textos_aggregados).strip()
    if len(combined_text) > 200000:
        combined_text = combined_text[:200000]

    return WebsiteCrawlResult(
        start_url=inicial,
        final_url=final_url,
        pages_visited=len(paginas),
        pages=paginas,
        combined_text=combined_text,
        project_names=project_names,
        services_found=services,
        competences_found=competences,
        typologies_found=typologies,
        warnings=warnings,
    )
