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


class FinancialReader(SpecializedReader):
    reader_name = "financial_reader"
    supported_topics = ("financial",)

    _SUPPORTED_DOCUMENT_TYPES = {
        DocumentType.ANNOUNCEMENT,
        DocumentType.TERMS_OF_REFERENCE,
        DocumentType.PROCEDURE_PROGRAM,
        DocumentType.SPECIFICATIONS,
        DocumentType.PRELIMINARY_PROGRAM,
        DocumentType.CONTRACT_DRAFT,
        DocumentType.AWARD_CRITERIA,
    }

    _MONEY_PATTERN = re.compile(
        r"(?i)(\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*(?:€|eur)"
    )
    _PERCENT_PATTERN = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")

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
            "competition_prizes": self._extract_prizes(document, relevant_sections, lines),
            "procedure_value": self._extract_money_field(
                document,
                relevant_sections,
                lines,
                field_name="procedure_value",
                markers=("valor do procedimento", "preco base", "preço base", "valor base"),
            ),
            "design_services_value": self._extract_money_field(
                document,
                relevant_sections,
                lines,
                field_name="design_services_value",
                markers=("preco dos servicos", "preço dos serviços", "honorarios", "honorários"),
            ),
            "estimated_construction_cost": self._extract_money_field(
                document,
                relevant_sections,
                lines,
                field_name="estimated_construction_cost",
                markers=("custo da obra", "custo estimado da obra", "estimativa da obra", "valor estimado da obra"),
            ),
            "payments_by_phase": self._extract_payments(document, relevant_sections, lines),
            "bond": self._extract_money_field(
                document,
                relevant_sections,
                lines,
                field_name="bond",
                markers=("caucao", "caução"),
            ),
            "insurance": self._extract_text_list(
                document,
                relevant_sections,
                lines,
                field_name="insurance",
                markers=("seguro", "seguros"),
            ),
            "penalties": self._extract_text_list(
                document,
                relevant_sections,
                lines,
                field_name="penalties",
                markers=("penalizacao", "penalização", "multa", "multas"),
            ),
            "price_revision": self._extract_text_list(
                document,
                relevant_sections,
                lines,
                field_name="price_revision",
                markers=("revisao de precos", "revisão de preços", "atualização de preços", "actualização de preços"),
            ),
            "notes": self._extract_text_list(
                document,
                relevant_sections,
                lines,
                field_name="notes",
                markers=("premio", "prémio", "valor dos serviços", "valor da obra"),
            ),
        }

        found = [field for field in fields.values() if field.status != EvidenceStatus.NOT_FOUND]
        confidence = (
            sum(field.confidence for field in found) / len(found)
            if found
            else 0.0
        )
        warnings: list[str] = []
        if not found:
            warnings.append("Não foram encontrados dados financeiros relevantes.")
        if (
            fields["competition_prizes"].status != EvidenceStatus.NOT_FOUND
            and fields["procedure_value"].status != EvidenceStatus.NOT_FOUND
        ):
            warnings.append("Os prémios do concurso foram separados do valor do procedimento.")

        return ReaderResult(
            reader_name=self.reader_name,
            document_ids=[document.source.document_id],
            fields=fields,
            evidences=self._collect_evidences(fields),
            warnings=warnings,
            confidence=confidence,
        )

    def _extract_prizes(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
    ) -> ExtractedField:
        items: list[dict[str, Any]] = []
        evidences = []
        pattern = re.compile(
            r"(?i)([^:\n]{0,80}pr[ée]mio[^:\n]*)[:\-]?\s*(\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d+)?)\s*(?:€|eur)"
        )
        for section in sections or []:
            for line in self._lines(section.text):
                match = pattern.search(line)
                if not match:
                    continue
                item = {
                    "position": self._clean_line(match.group(1)),
                    "value": self._normalize_money(match.group(2)),
                    "normalized_value": self._normalize_money(match.group(2)),
                }
                items.append(item)
                evidences.append(
                    create_evidence(
                        source_document_id=document.source.document_id,
                        filename=document.source.filename,
                        excerpt=line,
                        page=section.page_start,
                        section=section.title,
                        confidence=0.84,
                        status=EvidenceStatus.CONFIRMED,
                    )
                )
        if not items:
            for line in lines:
                match = pattern.search(line)
                if not match:
                    continue
                item = {
                    "position": self._clean_line(match.group(1)),
                    "value": self._normalize_money(match.group(2)),
                    "normalized_value": self._normalize_money(match.group(2)),
                }
                items.append(item)
                evidences.append(
                    create_evidence(
                        source_document_id=document.source.document_id,
                        filename=document.source.filename,
                        excerpt=line,
                        confidence=0.82,
                        status=EvidenceStatus.CONFIRMED,
                    )
                )
        return self._field_from_items("competition_prizes", items, evidences, confidence=0.8)

    def _extract_money_field(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        *,
        field_name: str,
        markers: tuple[str, ...],
    ) -> ExtractedField:
        candidate = self._find_marked_line(sections, lines, markers)
        if candidate is None:
            return ExtractedField(
                field_name=field_name,
                value=None,
                normalized_value=None,
                evidences=[],
                confidence=0.0,
                status=EvidenceStatus.NOT_FOUND,
            )
        money = self._extract_money(candidate)
        evidence = create_evidence(
            source_document_id=document.source.document_id,
            filename=document.source.filename,
            excerpt=candidate,
            confidence=0.85,
            status=EvidenceStatus.CONFIRMED,
        )
        return ExtractedField(
            field_name=field_name,
            value={"text": candidate, "amount": money},
            normalized_value=money,
            evidences=[evidence],
            confidence=0.85,
            status=EvidenceStatus.CONFIRMED,
        )

    def _extract_text_list(
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
                cleaned = self._clean_line(line)
                if cleaned not in items:
                    items.append(cleaned)
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
                if cleaned not in items:
                    items.append(cleaned)
                    evidences.append(
                        create_evidence(
                            source_document_id=document.source.document_id,
                            filename=document.source.filename,
                            excerpt=line,
                            confidence=0.78,
                            status=EvidenceStatus.CONFIRMED,
                        )
                    )
        return self._field_from_items(field_name, items, evidences, confidence=0.74)

    def _extract_payments(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
    ) -> ExtractedField:
        items: list[dict[str, Any]] = []
        evidences = []
        pattern = re.compile(r"(?i)\b(?:fase|etapa)\s*([0-9ivxlcdm]+)\b.*?(\d{1,3}(?:[.,]\d+)?)\s*%")
        for section in sections or []:
            for line in self._lines(section.text):
                match = pattern.search(line)
                if not match:
                    continue
                items.append(
                    {
                        "phase": match.group(1).strip(),
                        "percentage": self._to_float(match.group(2)),
                        "description": self._clean_line(line),
                    }
                )
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
                match = pattern.search(line)
                if not match:
                    continue
                items.append(
                    {
                        "phase": match.group(1).strip(),
                        "percentage": self._to_float(match.group(2)),
                        "description": self._clean_line(line),
                    }
                )
                evidences.append(
                    create_evidence(
                        source_document_id=document.source.document_id,
                        filename=document.source.filename,
                        excerpt=line,
                        confidence=0.8,
                        status=EvidenceStatus.CONFIRMED,
                    )
                )
        return self._field_from_items("payments_by_phase", items, evidences, confidence=0.8)

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

    def _find_marked_line(
        self,
        sections: Sequence[DocumentSection],
        lines: list[str],
        markers: tuple[str, ...],
    ) -> str | None:
        for section in sections:
            for line in self._lines(section.text):
                if self._contains_marker(line, markers):
                    return line
        for line in lines:
            if self._contains_marker(line, markers):
                return line
        return None

    def _contains_marker(self, text: str, markers: tuple[str, ...]) -> bool:
        normalized = self._normalize(text)
        return any(self._normalize(marker) in normalized for marker in markers)

    @staticmethod
    def _join_text(
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
    ) -> str:
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
        normalized = unicodedata.normalize("NFKD", FinancialReader._clean_line(text).casefold())
        return "".join(character for character in normalized if not unicodedata.combining(character))

    @classmethod
    def _extract_money(cls, text: str) -> float | None:
        match = cls._MONEY_PATTERN.search(text or "")
        return cls._normalize_money(match.group(1)) if match else None

    @staticmethod
    def _normalize_money(value: str) -> float | None:
        cleaned = value.replace(" ", "").replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _to_float(value: str) -> float | None:
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _collect_evidences(fields: dict[str, ExtractedField]) -> list[Any]:
        evidences: list[Any] = []
        for field in fields.values():
            evidences.extend(field.evidences)
        return evidences
