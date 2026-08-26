from __future__ import annotations

import re
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


class ProcedureReader(SpecializedReader):
    reader_name = "procedure_reader"

    supported_topics = (
        "procedure_identity",
    )

    _SUPPORTED_DOCUMENT_TYPES = {
        DocumentType.ANNOUNCEMENT,
        DocumentType.TERMS_OF_REFERENCE,
        DocumentType.PROCEDURE_PROGRAM,
        DocumentType.SPECIFICATIONS,
        DocumentType.PRELIMINARY_PROGRAM,
    }

    _FIELD_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
        "object": (
            re.compile(
                r"(?is)\bobjeto\b\s*[:\-]?\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
            re.compile(
                r"(?is)\btem por objeto\b\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
        ),
        "contracting_entity": (
            re.compile(
                r"(?is)\bentidade adjudicante\b\s*[:\-]?\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
            re.compile(
                r"(?is)\ba entidade adjudicante é\b\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
        ),
        "procedure_type": (
            re.compile(
                r"(?is)\btipo de procedimento\b\s*[:\-]?\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
            re.compile(
                r"(?is)\b(concurso público|concurso limitado por prévia qualificação|concurso de conceção|ajuste direto|consulta prévia)\b"
            ),
        ),
        "cpv": (
            re.compile(
                r"(?i)\bcpv\b\s*[:\-]?\s*([0-9]{8}(?:-[0-9])?)"
            ),
            re.compile(
                r"(?i)\bcódigo cpv\b\s*[:\-]?\s*([0-9]{8}(?:-[0-9])?)"
            ),
        ),
        "submission_deadline": (
            re.compile(
                r"(?is)\bprazo para apresentação (?:das propostas|da proposta|dos trabalhos)\b\s*[:\-]?\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
            re.compile(
                r"(?is)\bdata limite\b\s*[:\-]?\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
        ),
        "execution_period": (
            re.compile(
                r"(?is)\bprazo de execução\b\s*[:\-]?\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
            re.compile(
                r"(?is)\bprazo contratual\b\s*[:\-]?\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
        ),
        "location": (
            re.compile(
                r"(?is)\blocal(?:ização)?\b\s*[:\-]?\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
        ),
        "reference": (
            re.compile(
                r"(?is)\breferência do procedimento\b\s*[:\-]?\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
            re.compile(
                r"(?is)\bn[.ºo]?\s*(?:do procedimento|do concurso)\b\s*[:\-]?\s*(.+?)(?=\n{2,}|artigo|cláusula|$)"
            ),
        ),
    }

    def supports(self, document: ClassifiedDocument) -> bool:
        return document.document_type in self._SUPPORTED_DOCUMENT_TYPES

    def extract(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
    ) -> ReaderResult:
        relevant_sections = self.relevant_sections(sections)

        if not relevant_sections:
            relevant_sections = list(sections)

        fields: dict[str, ExtractedField] = {}
        all_evidences = []
        warnings: list[str] = []

        for field_name, patterns in self._FIELD_PATTERNS.items():
            extracted = self._extract_field(
                field_name=field_name,
                document=document,
                sections=relevant_sections,
                patterns=patterns,
            )

            fields[field_name] = extracted
            all_evidences.extend(extracted.evidences)

        found_fields = [
            field
            for field in fields.values()
            if field.status != EvidenceStatus.NOT_FOUND
        ]

        confidence = (
            sum(field.confidence for field in found_fields) / len(found_fields)
            if found_fields
            else 0.0
        )

        if not found_fields:
            warnings.append(
                "Não foram encontrados campos de identificação do procedimento."
            )

        return ReaderResult(
            reader_name=self.reader_name,
            document_ids=[document.source.document_id],
            fields=fields,
            evidences=all_evidences,
            warnings=warnings,
            confidence=confidence,
        )

    def _extract_field(
        self,
        *,
        field_name: str,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        patterns: Sequence[re.Pattern[str]],
    ) -> ExtractedField:
        for section in sections:
            for pattern in patterns:
                match = pattern.search(section.text)

                if not match:
                    continue

                value = self._clean_value(match.group(1))
                if not value:
                    continue

                evidence = create_evidence(
                    source_document_id=document.source.document_id,
                    filename=document.source.filename,
                    excerpt=match.group(0),
                    page=section.page_start,
                    section=section.title,
                    confidence=0.88,
                    status=EvidenceStatus.CONFIRMED,
                )

                return ExtractedField(
                    field_name=field_name,
                    value=value,
                    normalized_value=self._normalize_value(
                        field_name,
                        value,
                    ),
                    evidences=[evidence],
                    confidence=0.88,
                    status=EvidenceStatus.CONFIRMED,
                )

        return ExtractedField(
            field_name=field_name,
            value=None,
            normalized_value=None,
            evidences=[],
            confidence=0.0,
            status=EvidenceStatus.NOT_FOUND,
        )

    @staticmethod
    def _clean_value(value: str) -> str:
        cleaned = re.sub(r"\s+", " ", value or "").strip()

        stop_tokens = [
            "C?digo CPV",
            "Codigo CPV",
            "C?digo CPV",
            "CPV",
            "Entidade adjudicante",
            "Objeto",
            "Prazo",
            "Tipo de procedimento",
            "Artigo",
            "Cl?usula",
            "Clausula",
        ]

        cleaned_casefold = cleaned.casefold()

        for token in stop_tokens:
            position = cleaned_casefold.find(token.casefold())

            if position > 0:
                cleaned = cleaned[:position].strip()
                break

        cleaned = cleaned.rstrip(" .;,:-")

        return cleaned

    @staticmethod
    def _normalize_value(
        field_name: str,
        value: str,
    ) -> Any:
        if field_name == "cpv":
            return value.replace(" ", "")

        return value
