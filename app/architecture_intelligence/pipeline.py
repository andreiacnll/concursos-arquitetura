from __future__ import annotations

import json
import re
import hashlib
import tempfile
import unicodedata
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from xml.etree import ElementTree

from .consolidator import Consolidator
from .document_classifier import classify_document
from .llm_orchestrator import orchestrate_competition
from .semantic_enrichment import enrich_consolidated_semantics
from .readers import (
    AwardReader,
    DeliverablesReader,
    FinancialReader,
    ProcedureReader,
    RisksReader,
    SubmissionReader,
    TeamReader,
)
from .schemas import ClassifiedDocument, ConsolidatedCompetitionData, SourceDocument


DEBUG_EXPORT_ROOT = Path("debug_exports") / "architecture_intelligence"


@dataclass(slots=True)
class ArchitectureIntelligenceExperimentResult:
    case_slug: str
    output_dir: str
    reader_results: list[dict[str, Any]]
    consolidated: dict[str, Any]
    executive_analysis: dict[str, Any]
    company_matching: dict[str, Any] | None
    warnings: list[str]
    classified_documents: list[dict[str, Any]]


@dataclass(slots=True)
class MaterializedSources:
    documents: list[SourceDocument]
    manifest: dict[str, Any]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split()).strip()


def _slugify(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    return slug.strip("-")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_prefix(path: Path, size: int = 8) -> bytes:
    try:
        with path.open("rb") as handle:
            return handle.read(size)
    except OSError:
        return b""


def _is_zip_signature(prefix: bytes) -> bool:
    return prefix.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))


def _path_is_zip_container(path: Path) -> bool:
    return _is_zip_signature(_read_prefix(path)) or zipfile.is_zipfile(path)


def _content_type_from_signature(
    *,
    filename: str,
    prefix: bytes,
) -> str:
    suffix = Path(filename).suffix.lower()
    if _is_zip_signature(prefix):
        if suffix == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return "application/zip"
    if prefix.startswith(b"%PDF") or suffix == ".pdf":
        return "application/pdf"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if suffix == ".txt":
        return "text/plain"
    return "application/octet-stream"


def _source_url_from_metadata(metadata: dict[str, Any]) -> str:
    for key in ("source_url", "platform_url", "url", "external_id"):
        value = _clean(metadata.get(key))
        if value:
            return value
    return ""


def _safe_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return _safe_jsonable(value.model_dump())
    if hasattr(value, "dict") and callable(value.dict):  # pragma: no cover - legacy fallback
        try:
            return value.dict()
        except Exception:
            return str(value)
    if isinstance(value, dict):
        return {str(key): _safe_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_safe_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_safe_jsonable(item) for item in sorted(value, key=lambda item: _clean(item))]
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return value.as_posix()
    if hasattr(value, "__dict__"):
        return {
            key: _safe_jsonable(item)
            for key, item in value.__dict__.items()
            if not key.startswith("_")
        }
    return str(value)


def _read_text_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if _path_is_zip_container(path):
        texts: list[str] = []
        try:
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.endswith("/"):
                        continue
                    inner_suffix = Path(name).suffix.lower()
                    data = archive.read(name)
                    if inner_suffix == ".pdf":
                        from pypdf import PdfReader

                        try:
                            reader = PdfReader(BytesIO(data))
                            texts.extend(
                                page.extract_text() or ""
                                for page in reader.pages
                            )
                        except Exception:
                            continue
                    elif inner_suffix in {".txt", ".json"}:
                        texts.append(data.decode("utf-8", errors="ignore"))
        except Exception:
            texts = []
        combined = "\n".join(texts).strip()
        if combined:
            return combined
    if suffix == ".pdf":
        from app.analise.extrair_texto_pdf import extrair_pdf

        return extrair_pdf(path)
    if suffix in {".txt", ".json"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def _extract_pdf_text(path: Path) -> str:
    try:
        from app.analise.extrair_texto_pdf import extrair_pdf

        return extrair_pdf(path)
    except Exception:
        return ""


def _extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            names = [
                "word/document.xml",
                *[
                    name
                    for name in archive.namelist()
                    if name.startswith("word/header") or name.startswith("word/footer")
                ],
            ]
            parts: list[str] = []
            for name in names:
                try:
                    xml = archive.read(name)
                except KeyError:
                    continue
                root = ElementTree.fromstring(xml)
                parts.extend(
                    node.text or ""
                    for node in root.iter()
                    if node.tag.endswith("}t") and node.text
                )
            return " ".join(part.strip() for part in parts if part.strip())
    except Exception:
        return ""


def _normalize_match_key(value: Any) -> str:
    text = str(value or "").replace("\\", "/")
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9./_-]+", "", ascii_text).strip("/")


def _candidate_text_cache_paths(source: SourceDocument) -> list[Path]:
    metadata = dict(source.metadata or {})
    configured = metadata.get("text_cache_paths") or metadata.get("textos_paths") or []
    if isinstance(configured, (str, Path)):
        configured = [configured]

    result: list[Path] = []
    for item in configured:
        path = Path(item)
        if path.exists():
            result.append(path)

    source_path = Path(source.path) if source.path else None
    if source_path and source_path.exists():
        parts = list(source_path.resolve().parts)
        for index, part in enumerate(parts):
            if part == "analise_documentos" and index + 1 < len(parts):
                concurso_root = Path(*parts[: index + 2])
                jobs_root = concurso_root / "jobs"
                if jobs_root.exists():
                    for textos in sorted(
                        jobs_root.glob("*/textos.json"),
                        key=lambda item: int(item.parent.name)
                        if item.parent.name.isdigit()
                        else -1,
                        reverse=True,
                    ):
                        result.append(textos)
                break

    unique: list[Path] = []
    seen: set[str] = set()
    for path in result:
        resolved = path.resolve().as_posix().casefold()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _load_text_cache(source: SourceDocument) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for path in _candidate_text_cache_paths(source):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for key, text in data.items():
            clean_text = str(text or "").strip()
            if not clean_text:
                continue
            entries.append((_normalize_match_key(key), str(key), clean_text))
    return entries


def _find_preserved_text(
    text_cache: list[tuple[str, str, str]],
    *,
    archive_member_path: str,
    filename: str,
    sha256: str | None,
) -> tuple[str, str | None]:
    if not text_cache:
        return "", None

    normalized_path = _normalize_match_key(archive_member_path)
    normalized_name = _normalize_match_key(filename)
    sha_key = _normalize_match_key(sha256 or "")
    for key, raw_key, text in text_cache:
        if normalized_path and (key == normalized_path or key.endswith(normalized_path)):
            return text, raw_key
    name_matches = [
        (raw_key, text)
        for key, raw_key, text in text_cache
        if normalized_name and key.endswith(normalized_name)
    ]
    if len(name_matches) == 1:
        return name_matches[0][1], name_matches[0][0]
    if sha_key:
        for key, raw_key, text in text_cache:
            if sha_key and sha_key in key:
                return text, raw_key
    return "", None


def _archive_parent_prefix(member_name: str) -> str:
    path = PurePosixPath(member_name)
    stem = path.name[: -len(path.suffix)] if path.suffix else path.name
    parent = path.parent.as_posix()
    return f"{parent}/{stem}" if parent != "." else stem


def _blocked_archive_member(name: str) -> str | None:
    path = PurePosixPath(name)
    filename = path.name
    lowered = filename.casefold()
    if not filename or filename.startswith("~$") or "__macosx" in name.casefold():
        return "temporary_or_system_file"
    if lowered in {
        ".ds_store",
        "thumbs.db",
        "metadata.json",
        "analise.json",
        "analise_ai.json",
        "ficha.json",
        "textos.json",
        "lumiar_expected_analysis.json",
    }:
        return "generated_or_metadata_output"
    if lowered.startswith(("analise", "ficha", "textos")):
        return "generated_or_metadata_output"
    return None


def _official_name_hint(name: str) -> bool:
    normalized = _normalize_match_key(name)
    hints = (
        "caderno",
        "encargos",
        "termos",
        "referencia",
        "programa",
        "anexo",
        "convite",
        "anuncio",
        "procedimento",
        "concurso",
    )
    return any(hint in normalized for hint in hints)


def _accept_archive_member(
    *,
    filename: str,
    content_type: str,
    prefix: bytes,
) -> tuple[bool, str]:
    suffix = Path(filename).suffix.lower()
    if suffix in {".pdf", ".docx"}:
        return True, f"accepted_extension:{suffix}"
    if suffix in {".doc", ".odt"}:
        return True, f"accepted_extension:{suffix}"
    if not suffix and (
        content_type == "application/pdf"
        or _official_name_hint(filename)
        or prefix.startswith(b"%PDF")
    ):
        return True, "accepted_no_extension_official_piece"
    return False, "unsupported_archive_member_type"


def _copy_zip_entry_to_temp(
    entry: zipfile.ZipInfo,
    archive: zipfile.ZipFile,
    tmp_dir: Path,
) -> tuple[Path, str, bytes]:
    temporary = tempfile.NamedTemporaryFile(
        delete=False,
        dir=tmp_dir,
        suffix=".bin",
    )
    target = Path(temporary.name)
    temporary.close()
    digest = hashlib.sha256()
    with archive.open(entry) as source, target.open("wb") as destination:
        prefix = source.read(8)
        if prefix:
            destination.write(prefix)
            digest.update(prefix)
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            destination.write(chunk)
            digest.update(chunk)
    return target, digest.hexdigest(), prefix


def _text_from_materialized_file(path: Path, content_type: str) -> str:
    if content_type == "application/pdf":
        return _extract_pdf_text(path)
    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx_text(path)
    if content_type == "text/plain":
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def _extract_source_metadata(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item.get("metadata") or {})
    metadata = getattr(item, "metadata", None)
    if isinstance(metadata, dict):
        return dict(metadata)
    return {}


def _source_document_file_path(source: SourceDocument) -> Path | None:
    if not source.path:
        return None
    path = Path(source.path)
    return path if path.exists() else None


def _container_manifest_entry(source: SourceDocument, expanded: bool) -> dict[str, Any]:
    metadata = dict(source.metadata or {})
    return {
        "document_id": source.document_id,
        "filename": source.filename,
        "path": source.path,
        "origin": source.origin,
        "source_role": source.source_role,
        "source_url": _source_url_from_metadata(metadata),
        "sha256": source.sha256,
        "content_type": source.content_type,
        "status": "expanded" if expanded else "not_expanded",
        "sent_to_reader": not expanded,
        "reason": "zip_container_expanded" if expanded else "not_a_zip_container_or_expansion_failed",
    }


def _materialize_archive_children(
    *,
    archive_path: Path,
    parent: SourceDocument,
    parent_sha256: str | None,
    text_cache: list[tuple[str, str, str]],
    tmp_dir: Path,
    archive_member_prefix: str = "",
    parent_archive_entry: str | None = None,
    seen_child_hashes: set[str] | None = None,
) -> tuple[list[SourceDocument], list[dict[str, Any]]]:
    seen_child_hashes = seen_child_hashes if seen_child_hashes is not None else set()
    children: list[SourceDocument] = []
    manifest_items: list[dict[str, Any]] = []
    metadata = dict(parent.metadata or {})
    source_url = _source_url_from_metadata(metadata)

    try:
        archive = zipfile.ZipFile(archive_path)
    except Exception as error:
        return [], [
            {
                "filename": archive_path.name,
                "archive_member_path": archive_member_prefix,
                "status": "rejected",
                "reason": f"zip_open_failed:{error}",
                "sent_to_reader": False,
            }
        ]

    with archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            blocked_reason = _blocked_archive_member(entry.filename)
            logical_path = (
                f"{archive_member_prefix}/{entry.filename}"
                if archive_member_prefix
                else entry.filename
            )
            filename = PurePosixPath(entry.filename).name
            if blocked_reason:
                manifest_items.append(
                    {
                        "filename": filename,
                        "archive_member_path": logical_path,
                        "parent_document_id": parent.document_id,
                        "parent_sha256": parent_sha256,
                        "origin": parent.origin,
                        "source_url": source_url,
                        "status": "rejected",
                        "reason": blocked_reason,
                        "sent_to_reader": False,
                    }
                )
                continue

            temp_path, child_sha256, prefix = _copy_zip_entry_to_temp(
                entry,
                archive,
                tmp_dir,
            )
            content_type = _content_type_from_signature(
                filename=filename,
                prefix=prefix,
            )
            if content_type == "application/zip":
                nested_prefix = (
                    f"{archive_member_prefix}/{_archive_parent_prefix(entry.filename)}"
                    if archive_member_prefix
                    else _archive_parent_prefix(entry.filename)
                )
                nested_children, nested_manifest = _materialize_archive_children(
                    archive_path=temp_path,
                    parent=parent,
                    parent_sha256=parent_sha256,
                    text_cache=text_cache,
                    tmp_dir=tmp_dir,
                    archive_member_prefix=nested_prefix,
                    parent_archive_entry=logical_path,
                    seen_child_hashes=seen_child_hashes,
                )
                children.extend(nested_children)
                manifest_items.append(
                    {
                        "filename": filename,
                        "archive_member_path": logical_path,
                        "parent_document_id": parent.document_id,
                        "parent_sha256": parent_sha256,
                        "sha256": child_sha256,
                        "origin": parent.origin,
                        "source_url": source_url,
                        "content_type": content_type,
                        "status": "expanded",
                        "reason": "nested_zip_container",
                        "sent_to_reader": False,
                        "children_count": len(nested_children),
                    }
                )
                manifest_items.extend(nested_manifest)
                continue

            accepted, reason = _accept_archive_member(
                filename=filename,
                content_type=content_type,
                prefix=prefix,
            )
            if not accepted:
                manifest_items.append(
                    {
                        "filename": filename,
                        "archive_member_path": logical_path,
                        "parent_document_id": parent.document_id,
                        "parent_sha256": parent_sha256,
                        "sha256": child_sha256,
                        "origin": parent.origin,
                        "source_url": source_url,
                        "content_type": content_type,
                        "status": "rejected",
                        "reason": reason,
                        "sent_to_reader": False,
                    }
                )
                continue
            if child_sha256 in seen_child_hashes:
                manifest_items.append(
                    {
                        "filename": filename,
                        "archive_member_path": logical_path,
                        "parent_document_id": parent.document_id,
                        "parent_sha256": parent_sha256,
                        "sha256": child_sha256,
                        "origin": parent.origin,
                        "source_url": source_url,
                        "content_type": content_type,
                        "status": "rejected",
                        "reason": "duplicate_sha256",
                        "sent_to_reader": False,
                    }
                )
                continue
            seen_child_hashes.add(child_sha256)

            preserved_text, preserved_key = _find_preserved_text(
                text_cache,
                archive_member_path=logical_path,
                filename=filename,
                sha256=child_sha256,
            )
            text = preserved_text or _text_from_materialized_file(temp_path, content_type)
            read_status = (
                "text_reused"
                if preserved_text
                else "text_extracted"
                if text.strip()
                else "text_unavailable"
            )
            child_id = "-".join(
                value
                for value in (
                    parent.document_id,
                    _slugify(logical_path)[:80],
                    child_sha256[:12],
                )
                if value
            )
            child_metadata = {
                **metadata,
                "archive_member_path": logical_path,
                "archive_filename": filename,
                "parent_document_id": parent.document_id,
                "parent_sha256": parent_sha256,
                "parent_archive_entry": parent_archive_entry,
                "source_url": source_url,
                "text_cache_key": preserved_key,
                "read_status": read_status,
            }
            child = SourceDocument(
                document_id=child_id,
                concurso_id=parent.concurso_id,
                filename=filename,
                path=logical_path,
                origin=parent.origin,
                source_role="official_document",
                content_type=content_type,
                sha256=child_sha256,
                text=text,
                metadata=child_metadata,
            )
            children.append(child)
            manifest_items.append(
                {
                    "document_id": child.document_id,
                    "filename": child.filename,
                    "archive_member_path": logical_path,
                    "parent_document_id": parent.document_id,
                    "parent_sha256": parent_sha256,
                    "sha256": child_sha256,
                    "origin": child.origin,
                    "source_role": child.source_role,
                    "source_url": source_url,
                    "content_type": content_type,
                    "status": "accepted",
                    "reason": reason,
                    "read_status": read_status,
                    "text_available": bool(text.strip()),
                    "text_cache_key": preserved_key,
                    "sent_to_reader": bool(text.strip()),
                    "readers_applied": [],
                }
            )
    return children, manifest_items


def materialize_experimental_source_documents(
    source_documents: Iterable[SourceDocument],
) -> MaterializedSources:
    documents: list[SourceDocument] = []
    containers: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="architecture-intelligence-zip-") as tmp:
        tmp_dir = Path(tmp)
        for source in source_documents:
            path = _source_document_file_path(source)
            source_sha256 = source.sha256 or (_sha256_file(path) if path else None)
            if path is None or not _path_is_zip_container(path):
                documents.append(source)
                containers.append(_container_manifest_entry(source, expanded=False))
                continue

            text_cache = _load_text_cache(source)
            children, child_items = _materialize_archive_children(
                archive_path=path,
                parent=source,
                parent_sha256=source_sha256,
                text_cache=text_cache,
                tmp_dir=tmp_dir,
            )
            expanded = bool(children)
            containers.append(
                _container_manifest_entry(
                    source.model_copy(update={"sha256": source_sha256}),
                    expanded=expanded,
                )
            )
            items.extend(child_items)
            if expanded:
                documents.extend(children)
            else:
                documents.append(source)

    accepted = [item for item in items if item.get("status") == "accepted"]
    rejected = [item for item in items if item.get("status") == "rejected"]
    text_available = [
        item
        for item in accepted
        if item.get("text_available")
    ]
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "containers": containers,
        "items": items,
        "summary": {
            "containers": len(containers),
            "children_found": len(items),
            "children_accepted": len(accepted),
            "children_with_text": len(text_available),
            "children_rejected": len(rejected),
            "documents_sent_to_readers": len(
                [document for document in documents if document.text.strip()]
            ),
        },
    }
    return MaterializedSources(documents=documents, manifest=manifest)


def _looks_like_blocked_output(item: Any) -> bool:
    name = ""
    path_text = ""
    source_role = ""

    if isinstance(item, Path):
        name = item.name
        path_text = item.as_posix()
    elif isinstance(item, str):
        name = Path(item).name
        path_text = item
    elif isinstance(item, dict):
        name = _clean(item.get("filename") or item.get("name") or item.get("path"))
        path_text = _clean(item.get("path") or item.get("filename") or item.get("name"))
        source_role = _clean(item.get("source_role") or item.get("source_type"))
    else:
        name = _clean(getattr(item, "filename", ""))
        path = getattr(item, "path", "")
        path_text = _clean(path or name)
        source_role = _clean(getattr(item, "source_role", ""))

    lowered = f"{name} {path_text} {source_role}".casefold()
    blocked_tokens = (
        "analise.json",
        "analise_ai.json",
        "ficha.json",
        "textos.json",
        "ficha_analise_existente.txt",
        "ficha_legado.json",
        "lumiar_expected_analysis.json",
        "metadata.json",
        "generated_analysis",
        "legacy_analysis",
        "job_output",
        "cache_metadata",
        "extracted_text",
    )
    return any(token in lowered for token in blocked_tokens)


def _coerce_source_document(item: Any, index: int) -> SourceDocument:
    if isinstance(item, SourceDocument):
        return item
    if isinstance(item, ClassifiedDocument):
        return item.source

    if isinstance(item, Path):
        path = item
        prefix = _read_prefix(path)
        is_zip_container = _path_is_zip_container(path)
        text = "" if is_zip_container else _read_text_source(path)
        metadata = {"path": path.as_posix()}
        path_text = path.as_posix().casefold()
        origin = (
            "acingov"
            if "acingov" in path_text
            else "vortal"
            if "vortal" in path_text
            else "local"
        )
        content_type = (
            "application/zip"
            if is_zip_container
            else _content_type_from_signature(filename=path.name, prefix=prefix)
        )
        return SourceDocument(
            document_id=_slugify(path.stem) or f"document-{index + 1}",
            filename=path.name,
            path=path.as_posix(),
            origin=origin,
            source_role="platform_document" if "plataforma_publica" in path_text else "official_document",
            content_type=content_type,
            sha256=_sha256_file(path),
            text=text,
            metadata=metadata,
        )

    if isinstance(item, str):
        path = Path(item)
        if path.exists():
            return _coerce_source_document(path, index)
        return SourceDocument(
            document_id=_slugify(item) or f"document-{index + 1}",
            filename=item,
            origin="local",
            source_role="official_document",
            text="",
            metadata={},
        )

    if isinstance(item, dict):
        metadata = dict(item.get("metadata") or {})
        path_value = _clean(item.get("path") or item.get("filename") or metadata.get("path"))
        path = Path(path_value) if path_value else None
        text = _clean(item.get("text"))
        if not text and path and path.exists():
            text = _read_text_source(path)
        document_id = _clean(
            item.get("document_id")
            or item.get("id")
            or metadata.get("document_id")
            or metadata.get("id")
        )
        return SourceDocument(
            document_id=document_id or _slugify(path.stem if path else path_value) or f"document-{index + 1}",
            concurso_id=item.get("concurso_id") or metadata.get("concurso_id"),
            filename=_clean(item.get("filename") or (path.name if path else "") or f"document-{index + 1}"),
            path=path.as_posix() if path else _clean(item.get("path") or metadata.get("path")) or None,
            origin=_clean(item.get("origin") or metadata.get("origin") or "local"),
            source_role=_clean(item.get("source_role") or metadata.get("source_role") or "official_document"),
            content_type=_clean(item.get("content_type") or metadata.get("content_type")) or None,
            sha256=_clean(item.get("sha256") or metadata.get("sha256")) or None,
            text=text,
            metadata={**metadata, **{key: value for key, value in item.items() if key not in {"metadata", "text"}}},
        )

    raise TypeError(f"Unsupported source document type: {type(item)!r}")


def _derive_case_slug(source_documents: list[SourceDocument]) -> str:
    for source in source_documents:
        metadata = _extract_source_metadata(source)
        candidates = [
            metadata.get("experiment_case"),
            metadata.get("case_name"),
            metadata.get("slug"),
            metadata.get("competition_slug"),
            metadata.get("competition_id"),
            metadata.get("concurso_id"),
            source.concurso_id,
            source.document_id,
            Path(source.filename).stem,
        ]
        for candidate in candidates:
            slug = _slugify(candidate)
            if slug:
                return slug
    return "architecture-intelligence-experiment"


def _available_readers() -> list[Any]:
    return [
        reader
        for reader in (
            ProcedureReader(),
            AwardReader(),
            FinancialReader(),
            TeamReader(),
            DeliverablesReader(),
            SubmissionReader(),
            RisksReader(),
        )
    ]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe_jsonable(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_architecture_intelligence_experiment(
    source_documents: Iterable[Any],
    company_profile: Any = None,
    *,
    write_debug_exports: bool = True,
) -> ArchitectureIntelligenceExperimentResult:
    coerced_documents = [
        _coerce_source_document(item, index)
        for index, item in enumerate(source_documents or [])
    ]
    materialized_sources = materialize_experimental_source_documents(coerced_documents)
    accepted_documents = [
        document
        for document in materialized_sources.documents
        if document.text.strip() and not _looks_like_blocked_output(document)
    ]

    case_slug = _derive_case_slug(accepted_documents or materialized_sources.documents or coerced_documents)
    output_dir = DEBUG_EXPORT_ROOT / case_slug
    if write_debug_exports:
        output_dir.mkdir(parents=True, exist_ok=True)

    classified_documents = []
    reader_results = []
    warnings: list[str] = []

    for document in accepted_documents:
        classified = classify_document(document)
        sections = []
        if classified.document_type.name != "UNKNOWN":
            from .section_extractor import extract_sections

            sections = extract_sections(classified)
        else:
            from .section_extractor import extract_sections

            sections = extract_sections(classified)
            warnings.append(
                f"{document.filename}: classificado como desconhecido."
            )

        classified_documents.append(
            {
                "document_id": document.document_id,
                "filename": document.filename,
                "path": document.path,
                "source_role": document.source_role,
                "origin": document.origin,
                "sha256": document.sha256,
                "parent_document_id": document.metadata.get("parent_document_id"),
                "archive_member_path": document.metadata.get("archive_member_path"),
                "document_type": classified.document_type.value,
                "confidence": classified.confidence,
                "reasons": list(classified.reasons),
                "section_count": len(sections),
            }
        )

        for reader in _available_readers():
            if not reader.supports(classified):
                continue
            result = reader.extract(classified, sections)
            reader_results.append(result)
            warnings.extend(result.warnings)

    readers_by_document: dict[str, list[str]] = {}
    for result in reader_results:
        for document_id in result.document_ids:
            readers_by_document.setdefault(document_id, [])
            if result.reader_name not in readers_by_document[document_id]:
                readers_by_document[document_id].append(result.reader_name)
    for item in materialized_sources.manifest.get("items", []):
        document_id = item.get("document_id")
        if document_id:
            item["readers_applied"] = readers_by_document.get(document_id, [])

    consolidator = Consolidator()
    consolidated = consolidator.consolidate(
        reader_results,
        source_documents=accepted_documents,
    )
    consolidated, semantic_enrichment = (
        enrich_consolidated_semantics(consolidated)
    )
    executive_analysis = orchestrate_competition(consolidated)

    company_matching: dict[str, Any] | None = None
    if company_profile is not None:
        from app.company_ai.company_matching_v2 import analyze_company_match_v2

        company_matching = analyze_company_match_v2(consolidated, company_profile).model_dump(
            mode="json"
        )

    payloads = {
        "reader_results.json": [
            result.model_dump(mode="json") for result in reader_results
        ],
        "consolidated.json": consolidated.model_dump(mode="json"),
        "semantic_enrichment.json": semantic_enrichment,
        "executive_analysis.json": executive_analysis.model_dump(mode="json"),
        "company_matching.json": company_matching
        if company_matching is not None
        else {
            "status": "not_run",
            "reason": "company_profile_missing",
        },
        "warnings.json": {
            "warnings": consolidated.warnings + warnings,
            "case_slug": case_slug,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "classified_documents.json": classified_documents,
        "archive_manifest.json": materialized_sources.manifest,
        "experimental_source_manifest.json": materialized_sources.manifest,
    }

    if write_debug_exports:
        for filename, payload in payloads.items():
            _write_json(output_dir / filename, payload)

    return ArchitectureIntelligenceExperimentResult(
        case_slug=case_slug,
        output_dir=output_dir.as_posix(),
        reader_results=[result.model_dump(mode="json") for result in reader_results],
        consolidated=consolidated.model_dump(mode="json"),
        executive_analysis=executive_analysis.model_dump(mode="json"),
        company_matching=company_matching,
        warnings=_safe_jsonable(consolidated.warnings + warnings),
        classified_documents=classified_documents,
    )
