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


class DeliverablesReader(SpecializedReader):
    reader_name = "deliverables_reader"
    supported_topics = ("deliverables", "technical_constraints")

    _SUPPORTED_DOCUMENT_TYPES = {
        DocumentType.ANNOUNCEMENT,
        DocumentType.TERMS_OF_REFERENCE,
        DocumentType.PROCEDURE_PROGRAM,
        DocumentType.SPECIFICATIONS,
        DocumentType.PRELIMINARY_PROGRAM,
        DocumentType.CONTRACT_DRAFT,
    }

    _PHASE_PATTERN = re.compile(
        r"(?i)\b(?:fase|etapa)\s*([0-9ivxlcdm]+)\b(?:\s*[:-]?\s*(.*))?"
    )
    _DATE_PATTERN = re.compile(
        r"(?i)\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b"
    )
    _DIGITAL_FORMATS = ("bim", "ifc", "dwg", "dxf", "pdf", "rvt", "skp")
    _PHYSICAL_FORMATS = ("exemplar", "exemplares", "copia", "cópia", "papel", "fisico", "físico")
    _VALIDATION_TERMS = ("validacao", "validação", "aprovacao", "aprovação", "homologacao", "homologação", "visado", "conferência")
    _ASSISTANCE_TERMS = ("assistencia tecnica", "assistência técnica", "acompanhar obra", "telas finais", "as built", "esclarecimento")

    def supports(self, document: ClassifiedDocument) -> bool:
        return document.document_type in self._SUPPORTED_DOCUMENT_TYPES

    def extract(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
    ) -> ReaderResult:
        relevant_sections = self.relevant_sections(sections) or list(sections)
        lines = self._lines(self._join_text(document, relevant_sections))

        phases = self._extract_phases(document, relevant_sections, lines)
        fields = {
            "phases": self._field_from_items("phases", phases, self._collect_evidences_from_items(phases), confidence=0.82),
            "deliverables_by_phase": self._field_from_items(
                "deliverables_by_phase",
                self._deliverables_by_phase(phases, document, relevant_sections, lines),
                self._collect_evidences_from_phase_map(phases),
                confidence=0.8,
            ),
            "drawing_requirements": self._extract_list_field(document, relevant_sections, lines, "drawing_requirements", ("peças desenhadas", "pecas desenhadas", "desenhos", "plantas", "alçados", "cortes", "escala")),
            "digital_formats": self._extract_formats(document, relevant_sections, lines, "digital_formats", self._DIGITAL_FORMATS),
            "physical_formats": self._extract_formats(document, relevant_sections, lines, "physical_formats", self._PHYSICAL_FORMATS),
            "scale_requirements": self._extract_list_field(document, relevant_sections, lines, "scale_requirements", ("escala",)),
            "validation_requirements": self._extract_list_field(document, relevant_sections, lines, "validation_requirements", self._VALIDATION_TERMS),
            "assistance_requirements": self._extract_list_field(document, relevant_sections, lines, "assistance_requirements", self._ASSISTANCE_TERMS),
        }

        found = [field for field in fields.values() if field.status != EvidenceStatus.NOT_FOUND]
        warnings = [] if found else ["Não foram encontrados entregáveis relevantes."]
        confidence = sum(field.confidence for field in found) / len(found) if found else 0.0

        return ReaderResult(
            reader_name=self.reader_name,
            document_ids=[document.source.document_id],
            fields=fields,
            evidences=self._collect_evidences(fields),
            warnings=warnings,
            confidence=confidence,
        )

    def _extract_phases(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        current_phase: dict[str, Any] | None = None
        for section in sections or []:
            for line in self._lines(section.text):
                match = self._PHASE_PATTERN.search(line)
                if match:
                    phase_name = f"Fase {match.group(1).strip()}"
                    description = self._clean_line(match.group(2) or line)
                    evidence = create_evidence(
                        source_document_id=document.source.document_id,
                        filename=document.source.filename,
                        excerpt=line,
                        page=section.page_start,
                        section=section.title,
                        confidence=0.83,
                        status=EvidenceStatus.CONFIRMED,
                    )
                    current_phase = {
                        "phase": phase_name,
                        "description": description,
                        "deadline": self._first_date(description or line),
                        "deliverables": [],
                        "evidences": [evidence],
                    }
                    result.append(current_phase)
                    continue
                if current_phase is None:
                    continue
                deliverable = self._extract_deliverable_label(line)
                if deliverable:
                    current_phase["deliverables"].append(deliverable)
                    current_phase.setdefault("evidences", []).append(
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
        if not result:
            for line in lines:
                match = self._PHASE_PATTERN.search(line)
                if not match:
                    continue
                evidence = create_evidence(
                    source_document_id=document.source.document_id,
                    filename=document.source.filename,
                    excerpt=line,
                    confidence=0.8,
                    status=EvidenceStatus.CONFIRMED,
                )
                result.append(
                    {
                        "phase": f"Fase {match.group(1).strip()}",
                        "description": self._clean_line(match.group(2) or line),
                        "deadline": self._first_date(line),
                        "deliverables": [],
                        "evidences": [evidence],
                    }
                )
        for phase in result:
            phase["deliverables"] = self._dedupe_list(phase.get("deliverables") or [])
        return result

    def _deliverables_by_phase(
        self,
        phases: list[dict[str, Any]],
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
    ) -> list[dict[str, Any]]:
        if not phases:
            items = self._extract_deliverable_items(document, sections, lines)
            if not items:
                return []
            return [
                {
                    "phase": "Not Found",
                    "deliverables": items,
                    "deadline": None,
                }
            ]
        return [
            {
                "phase": phase.get("phase") or "Not Found",
                "deliverables": self._dedupe_list(phase.get("deliverables") or []),
                "deadline": phase.get("deadline"),
            }
            for phase in phases
        ]

    def _extract_deliverable_items(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
    ) -> list[str]:
        items: list[str] = []
        for section in sections or []:
            for line in self._lines(section.text):
                item = self._extract_deliverable_label(line)
                if item and item not in items:
                    items.append(item)
        if not items:
            for line in lines:
                item = self._extract_deliverable_label(line)
                if item and item not in items:
                    items.append(item)
        return items

    def _extract_list_field(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        field_name: str,
        markers: tuple[str, ...],
    ) -> ExtractedField:
        items: list[dict[str, Any]] = []
        evidences = []
        for section in sections or []:
            for line in self._lines(section.text):
                if not self._contains_marker(line, markers):
                    continue
                cleaned = self._clean_line(line)
                if not cleaned:
                    continue
                item = {"text": cleaned}
                if item not in items:
                    items.append(item)
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
                cleaned = self._clean_line(line)
                item = {"text": cleaned}
                if item not in items:
                    items.append(item)
                    evidences.append(
                        create_evidence(
                            source_document_id=document.source.document_id,
                            filename=document.source.filename,
                            excerpt=line,
                            confidence=0.78,
                            status=EvidenceStatus.CONFIRMED,
                        )
                    )
        return self._field_from_items(field_name, items, evidences, confidence=0.76)

    def _extract_formats(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        field_name: str,
        formats: tuple[str, ...],
    ) -> ExtractedField:
        items: list[dict[str, Any]] = []
        evidences = []
        for section in sections or []:
            for line in self._lines(section.text):
                lowered = self._normalize(line)
                if not any(fmt in lowered for fmt in formats):
                    continue
                tokens = [fmt.upper() for fmt in formats if fmt in lowered]
                cleaned = self._clean_line(line)
                item = {"text": cleaned, "formats": self._dedupe_list(tokens)}
                if item not in items:
                    items.append(item)
                    evidences.append(
                        create_evidence(
                            source_document_id=document.source.document_id,
                            filename=document.source.filename,
                            excerpt=line,
                            page=section.page_start,
                            section=section.title,
                            confidence=0.81,
                            status=EvidenceStatus.CONFIRMED,
                        )
                    )
        if not items:
            for line in lines:
                lowered = self._normalize(line)
                if not any(fmt in lowered for fmt in formats):
                    continue
                cleaned = self._clean_line(line)
                item = {"text": cleaned, "formats": self._dedupe_list([fmt.upper() for fmt in formats if fmt in lowered])}
                if item not in items:
                    items.append(item)
                    evidences.append(
                        create_evidence(
                            source_document_id=document.source.document_id,
                            filename=document.source.filename,
                            excerpt=line,
                            confidence=0.79,
                            status=EvidenceStatus.CONFIRMED,
                        )
                    )
        return self._field_from_items(field_name, items, evidences, confidence=0.77)

    def _extract_deliverable_label(self, text: str) -> str | None:
        cleaned = self._clean_line(text)
        if not cleaned:
            return None
        lowered = self._normalize(cleaned)
        keywords = (
            "estudo previo",
            "estudo prévio",
            "anteprojeto",
            "projeto de execucao",
            "projeto de execução",
            "assistencia tecnica",
            "assistência técnica",
            "telas finais",
            "mapa de quantidades",
            "estimativa",
            "memoria descritiva",
            "memória descritiva",
            "pecas escritas",
            "peças escritas",
            "pecas desenhadas",
            "peças desenhadas",
            "bim",
            "ifc",
            "dwg",
            "pdf",
        )
        if any(keyword in lowered for keyword in keywords):
            return cleaned
        return None

    @staticmethod
    def _first_date(text: str) -> str | None:
        match = DeliverablesReader._DATE_PATTERN.search(text or "")
        return match.group(1) if match else None

    @staticmethod
    def _join_text(document: ClassifiedDocument, sections: Sequence[DocumentSection]) -> str:
        if sections:
            return "\n".join(section.text for section in sections if section.text)
        return document.source.text or ""

    @staticmethod
    def _lines(text: str) -> list[str]:
        return [line.strip() for line in re.split(r"\r?\n", text or "") if line.strip()]

    @staticmethod
    def _clean_line(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip().rstrip(" .;,:-")

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", DeliverablesReader._clean_line(text).casefold())
        return "".join(character for character in normalized if not unicodedata.combining(character))

    def _contains_marker(self, text: str, markers: tuple[str, ...]) -> bool:
        normalized = self._normalize(text)
        return any(self._normalize(marker) in normalized for marker in markers)

    @staticmethod
    def _dedupe_list(values: list[Any]) -> list[Any]:
        seen: set[str] = set()
        result: list[Any] = []
        for value in values:
            key = DeliverablesReader._normalize(str(value))
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    def _field_from_items(
        self,
        field_name: str,
        items: list[Any],
        evidences: list[Any],
        *,
        confidence: float,
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
        return ExtractedField(
            field_name=field_name,
            value=items,
            normalized_value=items,
            evidences=evidences,
            confidence=min(0.95, confidence),
            status=EvidenceStatus.CONFIRMED,
        )

    @staticmethod
    def _collect_evidences_from_items(items: list[dict[str, Any]]) -> list[Any]:
        evidences: list[Any] = []
        for item in items:
            evidences.extend(item.get("evidences") or [])
        return evidences

    @staticmethod
    def _collect_evidences_from_phase_map(phases: list[dict[str, Any]]) -> list[Any]:
        evidences: list[Any] = []
        for phase in phases:
            evidences.extend(phase.get("evidences") or [])
        return evidences

    @staticmethod
    def _collect_evidences(fields: dict[str, ExtractedField]) -> list[Any]:
        evidences: list[Any] = []
        for field in fields.values():
            evidences.extend(field.evidences)
        return evidences
