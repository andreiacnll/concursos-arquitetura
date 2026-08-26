from __future__ import annotations

import hashlib
import re

from .schemas import Evidence, EvidenceStatus


def normalize_excerpt(text: str) -> str:
    """Normaliza espaços e quebras de linha."""
    return re.sub(r"\s+", " ", text or "").strip()


def trim_at_sentence_boundary(
    text: str,
    max_chars: int = 420,
) -> str:
    """Encurta o texto sem cortar palavras arbitrariamente."""
    cleaned = normalize_excerpt(text)

    if len(cleaned) <= max_chars:
        return cleaned

    candidate = cleaned[:max_chars]

    for marker in (". ", "? ", "! ", "; "):
        position = candidate.rfind(marker)

        if position >= int(max_chars * 0.55):
            return candidate[: position + 1].strip()

    last_space = candidate.rfind(" ")

    if last_space > 0:
        candidate = candidate[:last_space]

    return f"{candidate.strip()}…"


def build_evidence_id(
    source_document_id: str,
    page: int | None,
    section: str | None,
    excerpt: str,
) -> str:
    """Cria um identificador estável para a evidência."""
    raw = "|".join(
        [
            source_document_id,
            str(page or ""),
            section or "",
            normalize_excerpt(excerpt),
        ]
    )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def create_evidence(
    *,
    source_document_id: str,
    filename: str,
    excerpt: str,
    page: int | None = None,
    section: str | None = None,
    confidence: float = 0.0,
    status: EvidenceStatus = EvidenceStatus.CONFIRMED,
) -> Evidence:
    """Cria uma evidência normalizada e validada."""
    normalized_excerpt = trim_at_sentence_boundary(excerpt)

    return Evidence(
        evidence_id=build_evidence_id(
            source_document_id=source_document_id,
            page=page,
            section=section,
            excerpt=normalized_excerpt,
        ),
        source_document_id=source_document_id,
        filename=filename,
        page=page,
        section=section,
        excerpt=normalized_excerpt,
        confidence=max(0.0, min(1.0, confidence)),
        status=status,
    )
