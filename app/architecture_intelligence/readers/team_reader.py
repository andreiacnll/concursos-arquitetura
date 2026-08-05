from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Any

from ..evidence import create_evidence
from ..schemas import (
    ClassifiedDocument,
    DocumentSection,
    DocumentType,
    EvidenceStatus,
    ExtractedField,
    ReaderResult,
)
from .base import SpecializedReader


class TeamReader(SpecializedReader):
    reader_name = "team_reader"
    supported_topics = ("team",)

    _SUPPORTED_DOCUMENT_TYPES = {
        DocumentType.ANNOUNCEMENT,
        DocumentType.TERMS_OF_REFERENCE,
        DocumentType.PROCEDURE_PROGRAM,
        DocumentType.SPECIFICATIONS,
        DocumentType.PRELIMINARY_PROGRAM,
        DocumentType.CONTRACT_DRAFT,
        DocumentType.AWARD_CRITERIA,
    }

    def supports(self, document: ClassifiedDocument) -> bool:
        return document.document_type in self._SUPPORTED_DOCUMENT_TYPES

    def extract(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
    ) -> ReaderResult:
        relevant_sections = self.relevant_sections(sections) or list(sections)
        text = self._join_text(document, relevant_sections)
        lines = self._lines(text)

        fields = {
            "coordinator": self._extract_coordinator(document, relevant_sections, lines),
            "minimum_team": self._extract_block_list(
                document,
                relevant_sections,
                lines,
                field_name="minimum_team",
                headings=("equipa minima", "composicao da equipa"),
            ),
            "required_specializations": self._extract_block_list(
                document,
                relevant_sections,
                lines,
                field_name="required_specializations",
                headings=("especialidades obrigatorias", "especialidades"),
            ),
            "professional_requirements": self._extract_block_list(
                document,
                relevant_sections,
                lines,
                field_name="professional_requirements",
                headings=("requisitos profissionais", "habilitacoes", "inscricao"),
            ),
            "experience_requirements": self._extract_experience_requirements(
                document,
                relevant_sections,
                lines,
            ),
            "certifications": self._extract_block_list(
                document,
                relevant_sections,
                lines,
                field_name="certifications",
                headings=("certificacoes", "certificacao", "certificados"),
            ),
            "consultants": self._extract_block_list(
                document,
                relevant_sections,
                lines,
                field_name="consultants",
                headings=("consultores",),
            ),
            "exclusionary_team_requirements": self._extract_inline_or_block(
                document,
                relevant_sections,
                lines,
                field_name="exclusionary_team_requirements",
                markers=("sob pena de exclusao", "exclusao", "nao admissao"),
            ),
            "scored_team_requirements": self._extract_block_list(
                document,
                relevant_sections,
                lines,
                field_name="scored_team_requirements",
                headings=("criterios da equipa", "criterios", "fatores", "subfatores", "pontuacao"),
            ),
        }

        found = [field for field in fields.values() if field.status != EvidenceStatus.NOT_FOUND]
        confidence = (
            sum(field.confidence for field in found) / len(found)
            if found
            else 0.0
        )
        warnings = [] if found else ["Não foram encontrados requisitos de equipa."]

        return ReaderResult(
            reader_name=self.reader_name,
            document_ids=[document.source.document_id],
            fields=fields,
            evidences=self._collect_evidences(fields),
            warnings=warnings,
            confidence=confidence,
        )

    def _extract_coordinator(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
    ) -> ExtractedField:
        for section in sections or []:
            for line in self._lines(section.text):
                if not self._contains_marker(line, ("coordenador", "coordenacao")):
                    continue
                value = self._parse_coordinator_line(line)
                evidence = create_evidence(
                    source_document_id=document.source.document_id,
                    filename=document.source.filename,
                    excerpt=line,
                    page=section.page_start,
                    section=section.title,
                    confidence=0.86,
                    status=EvidenceStatus.CONFIRMED,
                )
                return ExtractedField(
                    field_name="coordinator",
                    value=value,
                    normalized_value=value,
                    evidences=[evidence],
                    confidence=0.86,
                    status=EvidenceStatus.CONFIRMED,
                )
        for line in lines:
            if not self._contains_marker(line, ("coordenador", "coordenacao")):
                continue
            value = self._parse_coordinator_line(line)
            evidence = create_evidence(
                source_document_id=document.source.document_id,
                filename=document.source.filename,
                excerpt=line,
                confidence=0.82,
                status=EvidenceStatus.CONFIRMED,
            )
            return ExtractedField(
                field_name="coordinator",
                value=value,
                normalized_value=value,
                evidences=[evidence],
                confidence=0.82,
                status=EvidenceStatus.CONFIRMED,
            )
        return ExtractedField(
            field_name="coordinator",
            value=None,
            normalized_value=None,
            evidences=[],
            confidence=0.0,
            status=EvidenceStatus.NOT_FOUND,
        )

    def _extract_experience_requirements(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
    ) -> ExtractedField:
        items: list[dict[str, Any]] = []
        evidences = []
        pattern = re.compile(r"(?i)(\d+)\s+anos?|experiencia")
        for section in sections or []:
            for line in self._lines(section.text):
                if not pattern.search(line):
                    continue
                item = {
                    "description": self._clean_line(line),
                    "minimum_years": self._extract_years(line),
                }
                items.append(item)
                evidences.append(
                    create_evidence(
                        source_document_id=document.source.document_id,
                        filename=document.source.filename,
                        excerpt=line,
                        page=section.page_start,
                        section=section.title,
                        confidence=0.82,
                        status=EvidenceStatus.CONFIRMED,
                    )
                )
        if not items:
            for line in lines:
                if not pattern.search(line):
                    continue
                item = {
                    "description": self._clean_line(line),
                    "minimum_years": self._extract_years(line),
                }
                items.append(item)
                evidences.append(
                    create_evidence(
                        source_document_id=document.source.document_id,
                        filename=document.source.filename,
                        excerpt=line,
                        confidence=0.8,
                        status=EvidenceStatus.CONFIRMED,
                    )
                )
        return self._field_from_items("experience_requirements", items, evidences)

    def _extract_block_list(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        *,
        field_name: str,
        headings: tuple[str, ...],
    ) -> ExtractedField:
        items: list[str] = []
        evidences = []
        for section in sections or []:
            for value, excerpt in self._collect_heading_block(section.text, headings):
                cleaned = self._clean_line(value)
                if cleaned and cleaned not in items:
                    items.append(cleaned)
                    evidences.append(
                        create_evidence(
                            source_document_id=document.source.document_id,
                            filename=document.source.filename,
                            excerpt=excerpt,
                            page=section.page_start,
                            section=section.title,
                            confidence=0.8,
                            status=EvidenceStatus.CONFIRMED,
                        )
                    )
        if not items:
            for value, excerpt in self._collect_heading_block("\n".join(lines), headings):
                cleaned = self._clean_line(value)
                if cleaned and cleaned not in items:
                    items.append(cleaned)
                    evidences.append(
                        create_evidence(
                            source_document_id=document.source.document_id,
                            filename=document.source.filename,
                            excerpt=excerpt,
                            confidence=0.78,
                            status=EvidenceStatus.CONFIRMED,
                        )
                    )
        return self._field_from_items(field_name, items, evidences)

    def _extract_inline_or_block(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        *,
        field_name: str,
        markers: tuple[str, ...],
    ) -> ExtractedField:
        items: list[str] = []
        evidences = []
        for section in sections or []:
            for line in self._lines(section.text):
                if not self._contains_marker(line, markers):
                    continue
                inline = self._inline_after_colon(line)
                if inline:
                    items.append(inline)
                else:
                    items.append(self._clean_line(line))
                evidences.append(
                    create_evidence(
                        source_document_id=document.source.document_id,
                        filename=document.source.filename,
                        excerpt=line,
                        page=section.page_start,
                        section=section.title,
                        confidence=0.8,
                        status=EvidenceStatus.CONFIRMED,
                    )
                )
        if not items:
            for line in lines:
                if not self._contains_marker(line, markers):
                    continue
                inline = self._inline_after_colon(line)
                items.append(inline or self._clean_line(line))
                evidences.append(
                    create_evidence(
                        source_document_id=document.source.document_id,
                        filename=document.source.filename,
                        excerpt=line,
                        confidence=0.78,
                        status=EvidenceStatus.CONFIRMED,
                    )
                )
        return self._field_from_items(field_name, items, evidences)

    def _collect_heading_block(
        self,
        text: str,
        headings: tuple[str, ...],
    ) -> list[tuple[str, str]]:
        lines = self._lines(text)
        collected: list[tuple[str, str]] = []
        for index, line in enumerate(lines):
            if not self._contains_marker(line, headings):
                continue
            inline = self._inline_after_colon(line)
            if inline:
                collected.append((inline, line))
            for next_line in lines[index + 1 :]:
                if self._is_heading(next_line):
                    break
                if not self._looks_like_item(next_line):
                    continue
                collected.append((next_line, next_line))
        return collected

    def _field_from_items(
        self,
        field_name: str,
        items: list[Any],
        evidences: list[Any],
    ) -> ExtractedField:
        if not items:
            return ExtractedField(
                field_name=field_name,
                value=[],
                normalized_value=[],
                evidences=[],
                confidence=0.0,
                status=EvidenceStatus.NOT_FOUND,
            )
        deduped = self._dedupe(items)
        return ExtractedField(
            field_name=field_name,
            value=deduped,
            normalized_value=deduped,
            evidences=evidences,
            confidence=min(0.95, 0.72 + (0.03 * len(deduped))),
            status=EvidenceStatus.CONFIRMED,
        )

    @staticmethod
    def _dedupe(values: list[Any]) -> list[Any]:
        seen: set[str] = set()
        result: list[Any] = []
        for value in values:
            key = TeamReader._normalize(str(value))
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    @staticmethod
    def _clean_line(text: str) -> str:
        cleaned = re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", text or "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned.rstrip(" .;,:-")

    @staticmethod
    def _lines(text: str) -> list[str]:
        return [line.strip() for line in re.split(r"\r?\n", text or "") if line.strip()]

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", TeamReader._clean_line(text).casefold())
        return "".join(character for character in normalized if not unicodedata.combining(character))

    def _contains_marker(self, text: str, markers: tuple[str, ...]) -> bool:
        normalized = self._normalize(text)
        return any(self._normalize(marker) in normalized for marker in markers)

    @staticmethod
    def _inline_after_colon(text: str) -> str | None:
        cleaned = TeamReader._clean_line(text)
        if ":" not in cleaned:
            return None
        remainder = cleaned.split(":", 1)[1].strip()
        remainder = re.sub(r"^\s*[-–]\s*", "", remainder).strip()
        return remainder or None

    @staticmethod
    def _is_heading(text: str) -> bool:
        stripped = (text or "").strip()
        return bool(stripped and stripped.endswith(":"))

    @staticmethod
    def _looks_like_item(text: str) -> bool:
        stripped = text.strip()
        return bool(stripped and not stripped.endswith(":"))

    @staticmethod
    def _parse_coordinator_line(text: str) -> dict[str, Any]:
        cleaned = TeamReader._clean_line(text)
        return {
            "role": "coordinator",
            "description": cleaned,
            "minimum_years": TeamReader._extract_years(cleaned),
            "professional_registration": TeamReader._extract_registration(cleaned),
        }

    @staticmethod
    def _extract_years(text: str) -> int | None:
        match = re.search(r"(?i)\b(\d+)\s+anos?\b", text or "")
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_registration(text: str) -> str | None:
        normalized = TeamReader._normalize(text)
        for marker in ("ordem dos arquitetos", "ordem dos engenheiros", "inscricao"):
            if TeamReader._normalize(marker) in normalized:
                return marker
        return None

    @staticmethod
    def _join_text(
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
    ) -> str:
        if sections:
            return "\n".join(section.text for section in sections if section.text)
        return document.source.text or ""

    @staticmethod
    def _collect_evidences(fields: dict[str, ExtractedField]) -> list[Any]:
        evidences: list[Any] = []
        for field in fields.values():
            evidences.extend(field.evidences)
        return evidences
