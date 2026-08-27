from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import requests

from app.analise.sharepoint_public import (
    SharePointDiscoveryError,
    discover_public_sharepoint_files,
    is_sharepoint_public_url,
)


logger = logging.getLogger(__name__)


@dataclass
class PlatformDocument:
    external_id: str
    source_url: str
    filename: str
    sha256: str = ""
    path: str = ""
    context_url: str = ""
    server_relative_url: str = ""
    etag: str = ""
    last_modified: str = ""
    content_length: str = ""


@dataclass
class PlatformDocumentResult:
    platform: str = "unknown"
    platform_url: str = ""
    status: str = "unsupported"
    requires_login: bool = False
    public_documents: list[PlatformDocument] | None = None
    warnings: list[str] | None = None
    used_playwright: bool = False


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())



def detect_platform(concurso: dict[str, Any]) -> tuple[str, str]:
    """
    Deteta a plataforma sem depender de uma única coluna histórica.

    Mantém a prioridade dos campos oficiais já usados e, como fallback,
    procura URLs de plataformas conhecidas noutros campos string do registo.
    Não tenta adivinhar uma plataforma quando não existe URL material.
    """
    preferred = (
        "link_pecas",
        "link_plataforma",
        "plataforma_url",
        "url_pecas",
        "link_documentos",
        "documentos_url",
        "contractingProcedureUrl",
        "contracting_procedure_url",
        "link",
    )

    def classify(url: str) -> tuple[str, str] | None:
        value = _clean(url)
        if not value:
            return None
        parsed = urlparse(value)
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
            return None
        lowered = value.casefold()
        if is_sharepoint_public_url(value):
            return "sharepoint", value
        if "vortal" in lowered:
            return "vortal", value
        if "acingov" in lowered:
            return "acingov", value
        return None

    for key in preferred:
        detected = classify(concurso.get(key))
        if detected:
            return detected

    # Registos antigos podem ter guardado o URL da plataforma noutro campo.
    # Só aceitamos URLs explícitos das plataformas suportadas.
    for value in concurso.values():
        if not isinstance(value, str):
            continue
        candidates: list[str] = []
        if re.match(r"(?i)^https?://", value.strip()):
            candidates.append(value.strip())
        candidates.extend(
            re.findall(r'https?://[^\s"\'<>]+', value, flags=re.IGNORECASE)
        )
        for candidate in candidates:
            detected = classify(candidate)
            if detected:
                return detected

    return "unknown", ""

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_public_document_versions(documents: list[PlatformDocument], timeout: int = 20) -> list[PlatformDocument]:
    """Obtém metadata HTTP leve; nunca lê o corpo do documento."""
    for document in documents:
        try:
            response = requests.head(document.source_url, timeout=timeout, allow_redirects=True, headers={"User-Agent": "CNLL/1.0"})
            if response.ok:
                document.etag = _clean(response.headers.get("ETag"))
                document.last_modified = _clean(response.headers.get("Last-Modified"))
                document.content_length = _clean(response.headers.get("Content-Length"))
        except requests.RequestException:
            continue
    return documents
def load_cached_platform_documents(cache_dir: Path) -> list[PlatformDocument]:
    metadata = cache_dir / "metadata.json"
    if not metadata.exists():
        return []
    try:
        data = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if data.get("stale"):
        return []

    documents: list[PlatformDocument] = []
    for item in data.get("documents") or []:
        if not isinstance(item, dict):
            continue
        document = PlatformDocument(
            external_id=_clean(item.get("external_id")),
            source_url=_clean(item.get("source_url")),
            filename=_clean(item.get("filename")),
            sha256=_clean(item.get("sha256")),
            path=_clean(item.get("path")),
            context_url=_clean(item.get("context_url")),
            server_relative_url=_clean(item.get("server_relative_url")),
            etag=_clean(item.get("etag")),
            last_modified=_clean(item.get("last_modified")),
            content_length=_clean(item.get("content_length")),
        )
        if not (document.external_id and document.source_url and document.sha256):
            continue
        file_path = (cache_dir / document.path).resolve()
        if cache_dir.resolve() not in file_path.parents or not file_path.exists():
            continue
        if sha256_file(file_path) != document.sha256:
            continue
        documents.append(document)
    return documents


def save_platform_metadata(
    cache_dir: Path,
    result: PlatformDocumentResult,
    documents: list[PlatformDocument],
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    data = {
        **asdict(result),
        "documents": [asdict(document) for document in documents],
        "stale": False,
    }
    data.pop("public_documents", None)
    (cache_dir / "metadata.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _request_json(url: str, referer: str, timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "User-Agent": "CNLL/1.0",
            "Accept": "application/json",
            "Referer": referer,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content = response.read()
    return json.loads(content.decode("utf-8", errors="ignore"))


def _vortal_key(platform_url: str) -> str:
    match = re.search(r"/public-tender-documents/([^/?#]+)", platform_url)
    return match.group(1) if match else ""


def _document_url(item: dict[str, Any], base_url: str) -> str:
    for key in (
        "documentUrl",
        "downloadUrl",
        "url",
        "fileUrl",
        "publicUrl",
    ):
        value = _clean(item.get(key))
        if value:
            return urljoin(base_url, value)
    return ""


# CNLL_DOCUMENT_ACQUISITION_V17_5
_VORTAL_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".odt",
    ".zip",
    ".7z",
    ".xlsx",
    ".xls",
    ".csv",
}


def _iter_vortal_document_dicts(
    value: Any,
    *,
    depth: int = 0,
):
    """Percorre respostas VORTAL sem assumir que documentList está na raiz."""
    if depth > 12:
        return

    if isinstance(value, dict):
        if any(
            _clean(value.get(key))
            for key in (
                "documentUrl",
                "downloadUrl",
                "url",
                "fileUrl",
                "publicUrl",
            )
        ):
            yield value

        for nested in value.values():
            yield from _iter_vortal_document_dicts(
                nested,
                depth=depth + 1,
            )

    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _iter_vortal_document_dicts(
                nested,
                depth=depth + 1,
            )


def _vortal_documents_from_payload(
    payload: Any,
    base_url: str,
) -> list[PlatformDocument]:
    """
    Converte respostas JSON VORTAL em documentos, mesmo quando a API muda
    ligeiramente a estrutura/envelope.
    """
    output: list[PlatformDocument] = []
    seen: set[str] = set()

    for index, item in enumerate(
        _iter_vortal_document_dicts(payload),
        start=1,
    ):
        if not isinstance(item, dict):
            continue

        source_url = _document_url(item, base_url)
        if not source_url:
            continue

        parsed = urlparse(source_url)
        if parsed.scheme.casefold() not in {"http", "https"}:
            continue

        signature = source_url.casefold()
        if signature in seen:
            continue

        filename = _clean(
            item.get("fileName")
            or item.get("filename")
            or item.get("documentName")
            or item.get("name")
            or item.get("title")
            or Path(parsed.path).name
            or f"documento-{index}.pdf"
        )

        output.append(
            PlatformDocument(
                external_id=_clean(
                    item.get("id")
                    or item.get("documentId")
                    or item.get("documentID")
                    or item.get("fileId")
                    or source_url
                ),
                source_url=source_url,
                filename=filename,
            )
        )
        seen.add(signature)

    return output


def _looks_like_public_document_link(
    href: str,
    text: str = "",
) -> bool:
    parsed = urlparse(href)
    suffix = Path(parsed.path).suffix.casefold()
    if suffix in _VORTAL_DOCUMENT_EXTENSIONS:
        return True

    probe = f"{href} {text}".casefold()
    return any(
        marker in probe
        for marker in (
            "download",
            "documento",
            "document",
            "ficheiro",
            "file",
            "programa",
            "caderno",
            "pecas",
            "peças",
            "anexo",
        )
    )


def _dedupe_platform_documents(
    documents: list[PlatformDocument],
) -> list[PlatformDocument]:
    output: list[PlatformDocument] = []
    seen: set[str] = set()

    for item in documents:
        source_url = _clean(item.source_url)
        if not source_url:
            continue
        key = source_url.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(item)

    return output


def _discover_vortal_with_playwright(
    platform_url: str,
    timeout: int,
) -> tuple[list[PlatformDocument], bool, list[str]]:
    """
    Fallback de browser apenas quando a API pública não devolve documentos.

    O browser serve para observar as chamadas JSON feitas pela própria página
    pública e os links de download materializados no DOM. Não faz login e não
    contorna autenticação.
    """
    warnings: list[str] = []
    captured_payloads: list[Any] = []
    anchor_rows: list[dict[str, Any]] = []
    used = False

    try:
        from playwright.sync_api import sync_playwright
    except Exception as error:
        return [], False, [
            f"Fallback Playwright VORTAL indisponível: {error}"
        ]

    browser = None
    context = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            used = True
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0 Safari/537.36"
                ),
                locale="pt-PT",
            )
            page = context.new_page()

            def capture_response(response) -> None:
                try:
                    response_url = str(response.url or "")
                    lowered = response_url.casefold()
                    if "vortal" not in lowered:
                        return

                    content_type = str(
                        response.headers.get("content-type", "")
                    ).casefold()
                    interesting = (
                        "json" in content_type
                        or "publictenderdocuments" in lowered
                        or "public-tender-documents" in lowered
                    )
                    if not interesting:
                        return

                    payload = response.json()
                    if isinstance(payload, (dict, list)):
                        captured_payloads.append(payload)
                except Exception:
                    return

            page.on("response", capture_response)

            try:
                page.goto(
                    platform_url,
                    wait_until="domcontentloaded",
                    timeout=max(8_000, int(timeout * 1000)),
                )
            except Exception as error:
                warnings.append(
                    f"A página pública VORTAL não terminou a navegação: {error}"
                )

            # Dá tempo às chamadas XHR/fetch da SPA sem transformar isto num
            # crawler lento.
            try:
                page.wait_for_timeout(
                    min(5_000, max(1_500, int(timeout * 150)))
                )
            except Exception:
                pass

            try:
                anchor_rows = page.locator("a[href]").evaluate_all(
                    """(nodes) => nodes.map((node) => ({
                      href: node.href || "",
                      text: (node.innerText || node.textContent || "").trim(),
                      download: node.getAttribute("download") || ""
                    }))"""
                )
            except Exception as error:
                warnings.append(
                    f"Não foi possível ler os links da página VORTAL: {error}"
                )

            if context is not None:
                context.close()
                context = None
            if browser is not None:
                browser.close()
                browser = None

    except Exception as error:
        warnings.append(
            f"Fallback Playwright VORTAL falhou: {error}"
        )
        try:
            if context is not None:
                context.close()
        except Exception:
            pass
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass

    parsed_platform = urlparse(platform_url)
    base_url = (
        f"{parsed_platform.scheme}://{parsed_platform.netloc}"
        if parsed_platform.scheme and parsed_platform.netloc
        else platform_url
    )

    documents: list[PlatformDocument] = []

    for payload in captured_payloads:
        documents.extend(
            _vortal_documents_from_payload(
                payload,
                base_url,
            )
        )

    for index, row in enumerate(anchor_rows, start=1):
        if not isinstance(row, dict):
            continue
        href = _clean(row.get("href"))
        label = _clean(row.get("text"))
        download_name = _clean(row.get("download"))
        if not href or not _looks_like_public_document_link(href, label):
            continue

        parsed = urlparse(href)
        if parsed.scheme.casefold() not in {"http", "https"}:
            continue

        filename = (
            download_name
            or Path(parsed.path).name
            or label
            or f"documento-browser-{index}.pdf"
        )
        documents.append(
            PlatformDocument(
                external_id=href,
                source_url=href,
                filename=filename,
            )
        )

    return _dedupe_platform_documents(documents), used, warnings


def discover_public_vortal_documents(
    platform_url: str,
    timeout: int = 20,
) -> PlatformDocumentResult:
    result = PlatformDocumentResult(
        platform="vortal",
        platform_url=platform_url,
        status="locating",
        public_documents=[],
        warnings=[],
    )

    key = _vortal_key(platform_url)
    if not key:
        result.status = "unsupported"
        result.warnings.append(
            "URL VORTAL pública sem identificador reconhecido."
        )
        return result

    parsed_platform = urlparse(platform_url)
    base_url = (
        f"{parsed_platform.scheme}://{parsed_platform.netloc}"
        if parsed_platform.scheme and parsed_platform.netloc
        else platform_url
    )

    api_url = (
        "https://community.vortal.biz/public/api/PublicTenderDocuments/"
        f"GetPublicTenderInformation?uniqueIdentifierEncrypted={key}"
        "&languageCode=pt-PT"
    )

    api_failed = False
    try:
        data = _request_json(
            api_url,
            platform_url,
            timeout,
        )
    except Exception as error:
        data = {}
        api_failed = True
        result.warnings.append(
            f"API pública VORTAL não devolveu informação utilizável: {error}"
        )

    api_documents = _vortal_documents_from_payload(
        data,
        base_url,
    )

    if api_documents:
        result.public_documents = api_documents
        result.status = "success"
        return result

    # A implementação anterior terminava aqui com no_documents/error.
    # Agora a página pública é usada como segunda fonte, via browser, apenas
    # quando a API não forneceu documentos.
    browser_documents, used_playwright, browser_warnings = (
        _discover_vortal_with_playwright(
            platform_url,
            timeout=max(timeout, 20),
        )
    )
    result.used_playwright = used_playwright
    result.warnings.extend(browser_warnings)

    if browser_documents:
        result.public_documents = browser_documents
        result.status = "success"
        if api_failed:
            result.warnings.append(
                "Documentos recuperados pela página pública VORTAL "
                "após falha da API."
            )
        else:
            result.warnings.append(
                "Documentos recuperados pela página pública VORTAL "
                "porque a API não os listou."
            )
        return result

    result.status = "error" if api_failed and not used_playwright else "no_documents"
    result.warnings.append(
        "Nenhum documento público descarregável foi encontrado na API "
        "nem na página pública VORTAL."
    )
    return result

def discover_public_acingov_documents(platform_url: str) -> PlatformDocumentResult:
    result = PlatformDocumentResult(
        platform="acingov",
        platform_url=platform_url,
        status="success",
        public_documents=[],
        warnings=[],
    )
    if not platform_url:
        result.status = "unsupported"
        result.warnings.append("URL acinGov em falta.")
        return result
    parsed = urlparse(platform_url)
    filename = Path(parsed.path).name or "pecas-procedimento.zip"
    result.public_documents.append(
        PlatformDocument(
            external_id=platform_url,
            source_url=platform_url,
            filename=filename,
        )
    )
    return result



def discover_public_sharepoint_documents(
    platform_url: str,
    timeout: int = 45,
) -> PlatformDocumentResult:
    result = PlatformDocumentResult(
        platform="sharepoint",
        platform_url=platform_url,
        status="locating",
        public_documents=[],
        warnings=[],
    )
    try:
        files = discover_public_sharepoint_files(
            platform_url,
            timeout=timeout,
        )
    except SharePointDiscoveryError as error:
        result.status = "error"
        result.warnings.append(
            f"Não foi possível inventariar a pasta pública SharePoint: {error}"
        )
        return result
    except Exception as error:
        result.status = "error"
        result.warnings.append(
            f"Erro ao consultar a pasta pública SharePoint: {error}"
        )
        return result

    for item in files:
        result.public_documents.append(
            PlatformDocument(
                external_id=item.external_id,
                source_url=item.source_url,
                filename=item.relative_path or item.filename,
                context_url=item.context_url,
                server_relative_url=item.server_relative_url,
            )
        )

    if not result.public_documents:
        result.status = "no_documents"
        result.warnings.append(
            "A pasta pública SharePoint não contém documentos suportados."
        )
    else:
        result.status = "success"
    return result


def discover_public_documents(
    concurso: dict[str, Any],
    timeout: int = 20,
) -> PlatformDocumentResult:
    platform, platform_url = detect_platform(concurso)
    if platform == "sharepoint":
        return discover_public_sharepoint_documents(
            platform_url,
            timeout=max(timeout, 45),
        )
    if platform == "vortal":
        return discover_public_vortal_documents(platform_url, timeout=timeout)
    if platform == "acingov":
        return discover_public_acingov_documents(platform_url)
    return PlatformDocumentResult(
        platform=platform,
        platform_url=platform_url,
        status="unsupported",
        public_documents=[],
        warnings=["Plataforma publica nao suportada automaticamente."],
    )


def _safe_download_name(value: str, index: int) -> str:
    basename = Path(
        _clean(value).replace("\\", "/")
    ).name
    stem = re.sub(
        r"[^A-Za-z0-9._() -]+",
        "_",
        Path(basename).stem,
    ).strip(" ._")
    suffix = Path(basename).suffix.casefold()
    return f"{index:03d}-{stem or 'documento'}{suffix}"


def _content_suffix(
    first_bytes: bytes,
    content_type: str,
    filename: str,
) -> str:
    lowered = content_type.casefold()
    declared_suffix = Path(filename).suffix.casefold()

    # DOCX/XLSX/PPTX são contentores ZIP por dentro. A assinatura PK não
    # significa que devam ser guardados como .zip, porque isso faria o worker
    # descompactar os XML internos e perder o documento lógico.
    ooxml_suffixes = {
        ".docx", ".docm",
        ".xlsx", ".xlsm",
        ".pptx", ".pptm",
    }
    if (
        declared_suffix in ooxml_suffixes
        and first_bytes.startswith(b"PK")
    ):
        return declared_suffix

    if first_bytes.startswith(b"7z\xbc\xaf'\x1c"):
        return ".7z"
    if (
        declared_suffix == ".zip"
        or first_bytes.startswith(b"PK")
        or "zip" in lowered
    ):
        return ".zip"
    if first_bytes.startswith(b"%PDF") or "pdf" in lowered:
        return ".pdf"
    return declared_suffix or ".bin"


def _sharepoint_site_url(final_url: str) -> str:
    parsed = urlparse(final_url)
    path = parsed.path
    for marker in ("/_layouts/", "/Documents/"):
        if marker in path:
            path = path.split(marker, 1)[0]
            break
    return f"{parsed.scheme}://{parsed.netloc}{path.rstrip('/')}"


def _prime_sharepoint_session(
    session: requests.Session,
    context_url: str,
    timeout: int,
) -> str:
    response = session.get(
        context_url,
        timeout=timeout,
        allow_redirects=True,
    )
    response.raise_for_status()
    return _sharepoint_site_url(response.url)


def _sharepoint_file_response(
    session: requests.Session,
    document: PlatformDocument,
    *,
    site_url: str,
    timeout: int,
) -> requests.Response:
    response = session.get(
        document.source_url,
        timeout=timeout,
        allow_redirects=True,
        stream=True,
        headers={"Accept": "*/*"},
    )
    content_type = response.headers.get("content-type", "").casefold()
    if response.ok and "html" not in content_type:
        return response
    response.close()

    if not document.server_relative_url:
        raise RuntimeError(
            "O SharePoint devolveu HTML em vez do ficheiro."
        )

    api_url = (
        f"{site_url}/_api/web/"
        "GetFileByServerRelativePath(decodedUrl=@file)/$value"
    )
    response = session.get(
        api_url,
        params={
            "@file": f"'{document.server_relative_url}'",
        },
        timeout=timeout,
        allow_redirects=True,
        stream=True,
        headers={
            "Accept": "application/octet-stream,*/*",
            "Referer": document.context_url,
        },
    )
    response.raise_for_status()
    return response


def _stream_response_to_file(
    response: requests.Response,
    target_base: Path,
    *,
    filename: str,
    max_bytes: int,
    max_archive_bytes: int | None = None,
) -> tuple[Path, int]:
    iterator = response.iter_content(
        chunk_size=1024 * 1024,
    )

    first = b""

    for chunk in iterator:
        if chunk:
            first = chunk
            break

    if not first:
        raise RuntimeError(
            "O download ficou vazio."
        )

    content_type = response.headers.get(
        "content-type",
        "",
    )

    suffix = _content_suffix(
        first[:16],
        content_type,
        filename,
    )

    if suffix == ".bin" and (
        "html" in content_type.casefold()
        or first.lstrip().startswith(b"<")
    ):
        raise RuntimeError(
            "O servidor devolveu uma pagina HTML em vez de um documento."
        )

    eh_arquivo = suffix in {
        ".zip",
        ".7z",
    }

    limite = max_bytes

    if (
        eh_arquivo
        and max_archive_bytes is not None
    ):
        limite = max_archive_bytes

    if limite <= 0:
        raise RuntimeError(
            "O limite disponivel para o download foi atingido."
        )

    declared_length_raw = response.headers.get(
        "content-length",
        "",
    ).strip()

    if declared_length_raw:
        try:
            declared_length = int(
                declared_length_raw
            )
        except (TypeError, ValueError):
            declared_length = 0

        if declared_length > limite:
            limite_mb = limite / (
                1024 * 1024
            )
            tamanho_mb = declared_length / (
                1024 * 1024
            )

            raise RuntimeError(
                "O ficheiro excede o limite configurado "
                f"({tamanho_mb:.1f} MB > {limite_mb:.1f} MB)."
            )

    target = target_base.with_suffix(
        suffix
    )

    total = 0

    try:
        with target.open("wb") as handle:
            total += len(first)

            if total > limite:
                raise RuntimeError(
                    "O ficheiro excede o limite configurado."
                )

            handle.write(first)

            for chunk in iterator:
                if not chunk:
                    continue

                total += len(chunk)

                if total > limite:
                    raise RuntimeError(
                        "O ficheiro excede o limite configurado."
                    )

                handle.write(chunk)

    except Exception:
        target.unlink(
            missing_ok=True,
        )
        raise

    return target, total


def download_public_documents(
    documents: list[PlatformDocument],
    cache_dir: Path,
    timeout: int = 90,
) -> list[PlatformDocument]:
    downloads = cache_dir / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)

    max_file_bytes = int(
        float(
            os.getenv(
                "CNLL_ANALISE_MAX_DOCUMENTO_MB",
                "550",
            )
        )
        * 1024
        * 1024
    )
    max_total_bytes = int(
        float(
            os.getenv(
                "CNLL_ANALISE_MAX_TOTAL_DOCUMENTOS_MB",
                "1600",
            )
        )
        * 1024
        * 1024
    )

    max_archive_bytes = int(
        float(
            os.getenv(
                "CNLL_ANALISE_MAX_PACOTE_MB",
                "4096",
            )
        )
        * 1024
        * 1024
    )

    max_total_archive_bytes = int(
        float(
            os.getenv(
                "CNLL_ANALISE_MAX_TOTAL_PACOTES_MB",
                "8192",
            )
        )
        * 1024
        * 1024
    )
    interval = max(
        0.0,
        float(
            os.getenv(
                "CNLL_ANALISE_PLATFORM_INTERVALO",
                "2.0",
            )
        ),
    )
    jitter = max(
        0.0,
        float(
            os.getenv(
                "CNLL_ANALISE_PLATFORM_JITTER",
                "1.0",
            )
        ),
    )

    saved: list[PlatformDocument] = []
    total_bytes = 0
    total_archive_bytes = 0
    sharepoint_sessions: dict[
        str,
        tuple[requests.Session, str],
    ] = {}

    try:
        for index, document in enumerate(
            documents,
            start=1,
        ):
            if interval > 0 and index > 1:
                time.sleep(
                    interval
                    + random.uniform(
                        0,
                        jitter,
                    )
                )

            safe_name = _safe_download_name(
                document.filename,
                index,
            )
            base_target = downloads / Path(
                safe_name
            ).with_suffix("")

            remaining_total_bytes = max(
                0,
                max_total_bytes - total_bytes,
            )

            remaining_archive_bytes = max(
                0,
                max_total_archive_bytes
                - total_archive_bytes,
            )

            effective_max_bytes = min(
                max_file_bytes,
                remaining_total_bytes,
            )

            effective_archive_max_bytes = min(
                max_archive_bytes,
                remaining_archive_bytes,
            )

            if (
                effective_max_bytes <= 0
                and effective_archive_max_bytes <= 0
            ):
                break

            try:
                if (
                    document.context_url
                    and is_sharepoint_public_url(
                        document.context_url
                    )
                ):
                    cached = sharepoint_sessions.get(
                        document.context_url
                    )
                    if cached is None:
                        session = requests.Session()
                        session.headers.update(
                            {
                                "User-Agent": "CNLL/1.0",
                                "Accept-Language": "pt-PT,pt;q=0.9",
                            }
                        )
                        site_url = _prime_sharepoint_session(
                            session,
                            document.context_url,
                            timeout,
                        )
                        cached = (session, site_url)
                        sharepoint_sessions[
                            document.context_url
                        ] = cached

                    session, site_url = cached
                    response = _sharepoint_file_response(
                        session,
                        document,
                        site_url=site_url,
                        timeout=timeout,
                    )
                    try:
                        target, size = _stream_response_to_file(
                            response,
                            base_target,
                            filename=document.filename,
                            max_bytes=effective_max_bytes,
                            max_archive_bytes=effective_archive_max_bytes,
                        )
                    finally:
                        response.close()
                else:
                    response = requests.get(
                        document.source_url,
                        timeout=timeout,
                        allow_redirects=True,
                        stream=True,
                        headers={
                            "User-Agent": "CNLL/1.0",
                            "Accept": "*/*",
                        },
                    )
                    try:
                        response.raise_for_status()
                        target, size = _stream_response_to_file(
                            response,
                            base_target,
                            filename=document.filename,
                            max_bytes=effective_max_bytes,
                            max_archive_bytes=effective_archive_max_bytes,
                        )
                    finally:
                        response.close()
            except Exception as erro:
                logger.warning(
                    "Falha ao descarregar documento publico %s (%s): %s",
                    document.filename,
                    document.source_url,
                    erro,
                )
                continue

            if target.suffix.casefold() in {".zip", ".7z"}:
                total_archive_bytes += size

                if total_archive_bytes > max_total_archive_bytes:
                    target.unlink(missing_ok=True)
                    break
            else:
                total_bytes += size

                if total_bytes > max_total_bytes:
                    target.unlink(missing_ok=True)
                    break

            document.sha256 = sha256_file(target)
            document.path = target.relative_to(
                cache_dir
            ).as_posix()
            saved.append(document)
    finally:
        for session, _ in sharepoint_sessions.values():
            session.close()

    return saved
