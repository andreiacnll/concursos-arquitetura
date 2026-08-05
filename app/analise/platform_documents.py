from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


@dataclass
class PlatformDocument:
    external_id: str
    source_url: str
    filename: str
    sha256: str = ""
    path: str = ""


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
    for key in ("link_pecas", "link_plataforma", "plataforma_url", "link"):
        url = _clean(concurso.get(key))
        if not url:
            continue
        if "vortal" in url.lower():
            return "vortal", url
        if "acingov" in url.lower():
            return "acingov", url
    return "unknown", ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        result.warnings.append("URL VORTAL publica sem identificador reconhecido.")
        return result

    api_url = (
        "https://community.vortal.biz/public/api/PublicTenderDocuments/"
        f"GetPublicTenderInformation?uniqueIdentifierEncrypted={key}&languageCode=pt-PT"
    )
    try:
        data = _request_json(api_url, platform_url, timeout)
    except Exception as error:
        result.status = "error"
        result.warnings.append(f"Erro da plataforma VORTAL: {error}")
        return result

    docs = data.get("documentList") or data.get("documents") or []
    if not docs:
        result.status = "no_documents"
        result.warnings.append("Nenhum documento publico encontrado.")
        return result

    base = f"{urlparse(platform_url).scheme}://{urlparse(platform_url).netloc}"
    for index, item in enumerate(docs):
        if not isinstance(item, dict):
            continue
        source_url = _document_url(item, base)
        if not source_url:
            continue
        filename = _clean(
            item.get("fileName")
            or item.get("name")
            or Path(urlparse(source_url).path).name
            or f"documento-{index + 1}.pdf"
        )
        result.public_documents.append(
            PlatformDocument(
                external_id=_clean(item.get("id") or item.get("documentId") or source_url),
                source_url=source_url,
                filename=filename,
            )
        )
    if not result.public_documents:
        result.status = "no_documents"
        result.warnings.append("Nenhum documento publico descarregavel encontrado.")
    else:
        result.status = "success"
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


def discover_public_documents(
    concurso: dict[str, Any],
    timeout: int = 20,
) -> PlatformDocumentResult:
    platform, platform_url = detect_platform(concurso)
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


def download_public_documents(
    documents: list[PlatformDocument],
    cache_dir: Path,
    timeout: int = 30,
) -> list[PlatformDocument]:
    downloads = cache_dir / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    saved: list[PlatformDocument] = []
    for index, document in enumerate(documents, start=1):
        request = Request(
            document.source_url,
            headers={"User-Agent": "CNLL/1.0", "Accept": "*/*"},
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                content = response.read()
        except Exception:
            continue
        suffix = Path(document.filename).suffix
        if content.startswith(b"PK"):
            suffix = ".zip"
        elif content.startswith(b"%PDF"):
            suffix = ".pdf"
        elif not suffix:
            suffix = ".bin"
        target = downloads / f"{index:02d}-{Path(document.filename).stem}{suffix}"
        target.write_bytes(content)
        document.sha256 = sha256_file(target)
        document.path = target.relative_to(cache_dir).as_posix()
        saved.append(document)
    return saved
