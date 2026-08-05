from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ACCEPTED_READER_SOURCE_TYPES = {
    "official_document",
    "platform_document",
    "user_uploaded_official_document",
}

BLOCKED_NAMES = {
    "analise.json",
    "analise_ai.json",
    "ficha.json",
    "textos.json",
    "ficha_analise_existente.txt",
    "ficha_legado.json",
    "lumiar_expected_analysis.json",
    "metadata.json",
}

OFFICIAL_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".odt",
    ".zip",
    ".xlsx",
    ".xls",
    ".csv",
}

GENERATED_EXTENSIONS = {
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
}


@dataclass
class SourceManifestItem:
    path: str
    filename: str
    source_type: str
    source_role: str
    accepted_for_reader: bool
    accepted_for_metadata: bool = False
    sha256: str | None = None
    origin: str = ""
    read_status: str = "pending"
    collected_at: str | None = None
    reason: str = ""


@dataclass
class SourceManifest:
    job_id: int | None
    root: str
    items: list[SourceManifestItem] = field(default_factory=list)

    def accepted_paths(self, base: Path) -> list[Path]:
        result = []
        for item in self.items:
            if not item.accepted_for_reader:
                continue
            path = (base / item.path).resolve()
            if base.resolve() in path.parents and path.exists():
                result.append(path)
        return result

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "root": self.root,
            "accepted_source_types": sorted(ACCEPTED_READER_SOURCE_TYPES),
            "items": [asdict(item) for item in self.items],
        }


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_job_output(path: Path) -> bool:
    return "jobs" in {part.lower() for part in path.parts}


def classify_source(path: Path) -> tuple[str, bool, str]:
    name = path.name.lower()
    suffix = path.suffix.lower()
    path_text = path.as_posix().lower()

    if name == "base_announcement.json":
        return "official_announcement", False, "BASE announcement metadata can feed identity fields but is not a procedure piece."
    if name == "metadata.json":
        return "cache_metadata", False, "Cache metadata is not document evidence."
    if name in BLOCKED_NAMES or name.startswith(("analise", "ficha", "textos")):
        if name.startswith("textos"):
            return "extracted_text", False, "Extracted text needs a linked official source_document_id and SHA-256."
        if name.startswith("analise"):
            return "generated_analysis", False, "Generated analysis output must not be read again."
        if name.startswith("ficha"):
            return "legacy_analysis", False, "Legacy/final analysis output must not be read as official evidence."
        return "job_output", False, "Generated output is blocked."
    if _is_job_output(path):
        return "job_output", False, "Previous job outputs are blocked."
    if "plataforma_publica/downloads" in path_text and suffix in OFFICIAL_EXTENSIONS:
        return "platform_document", True, "Downloaded public platform document."
    if suffix in OFFICIAL_EXTENSIONS:
        return "official_document", True, "Procedure document extension accepted."
    if suffix in GENERATED_EXTENSIONS:
        return "generated_analysis", False, "Generated or non-document artefact."
    if suffix == ".txt":
        return "extracted_text", False, "Loose extracted text is blocked without official source linkage."
    return "unknown", False, "Unknown source type."


def _source_role(source_type: str) -> str:
    if source_type == "official_announcement":
        return "official_announcement"
    if source_type in ACCEPTED_READER_SOURCE_TYPES:
        return "procedure_piece"
    if source_type == "cache_metadata":
        return "cache_metadata"
    if source_type == "extracted_text":
        return "extracted_text"
    return "blocked_output"


def _origin(path: Path, source_type: str) -> str:
    path_text = path.as_posix().lower()
    if source_type == "official_announcement":
        return "base.gov.pt"
    if "plataforma_publica" in path_text:
        if "vortal" in path_text:
            return "vortal"
        if "acingov" in path_text:
            return "acingov"
        return "platform"
    return "local"


def _mtime_iso(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat().replace("+00:00", "Z")
    except OSError:
        return None


def create_source_manifest(
    root: Path,
    *,
    job_id: int | None = None,
    output_path: Path | None = None,
    paths: Iterable[Path] | None = None,
) -> SourceManifest:
    root = root.resolve()
    candidates = list(paths) if paths is not None else [
        path for path in root.rglob("*") if path.is_file()
    ]
    items = []
    for path in candidates:
        resolved = path.resolve()
        if root not in resolved.parents and resolved != root:
            continue
        source_type, accepted, reason = classify_source(resolved)
        sha256 = _sha256(resolved) if (accepted or source_type == "official_announcement") else None
        items.append(
            SourceManifestItem(
                path=resolved.relative_to(root).as_posix(),
                filename=resolved.name,
                source_type=source_type,
                source_role=_source_role(source_type),
                accepted_for_reader=accepted,
                accepted_for_metadata=source_type == "official_announcement",
                sha256=sha256,
                origin=_origin(resolved, source_type),
                read_status="accepted" if accepted else "metadata" if source_type == "official_announcement" else "blocked",
                collected_at=_mtime_iso(resolved),
                reason=reason,
            )
        )
    manifest = SourceManifest(
        job_id=job_id,
        root=root.as_posix(),
        items=items,
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return manifest
