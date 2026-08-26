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


class RisksReader(SpecializedReader):
    reader_name = "risks_reader"
    supported_topics = ("risks", "submission", "financial", "team")

    _SUPPORTED_DOCUMENT_TYPES = {
        DocumentType.ANNOUNCEMENT,
        DocumentType.TERMS_OF_REFERENCE,
        DocumentType.PROCEDURE_PROGRAM,
        DocumentType.SPECIFICATIONS,
        DocumentType.PRELIMINARY_PROGRAM,
        DocumentType.CONTRACT_DRAFT,
        DocumentType.CLARIFICATION,
        DocumentType.RECTIFICATION,
    }

    _RISK_SPECS = (
        (
            "exclusion_risks",
            "critical",
            ("exclusão", "exclusao", "não admissão", "nao admissao", "sob pena de exclusão", "sob pena de exclusao", "fora de prazo", "assinatura inválida", "assinatura invalida", "documentos em falta"),
        ),
        (
            "contractual_risks",
            "warning",
            ("penalização", "penalizacao", "multa", "rescisão", "rescisao", "incumprimento", "prazo crítico", "prazo critico"),
        ),
        (
            "submission_risks",
            "critical",
            ("anonimato", "anónimo", "anonimo", "involucro", "documento ilegível", "documento ilegivel", "limite de páginas", "limite de paginas", "número de ficheiros", "numero de ficheiros", "formato inválido", "formato invalido"),
        ),
        (
            "document_alerts",
            "warning",
            ("ausente", "em falta", "esclarecimento", "retificação", "retificacao", "contradição", "contradicao", "dúvida", "duvida"),
        ),
        (
            "contradictions",
            "warning",
            ("contradição", "contradicao", "inconsistência", "inconsistencia", "difere", "conflito"),
        ),
        (
            "missing_annexes",
            "warning",
            ("anexo", "anexos", "faltam", "em falta", "ausente"),
        ),
        (
            "clarification_alerts",
            "info",
            ("esclarecimento", "questão", "questao", "pergunta"),
        ),
        (
            "rectification_alerts",
            "info",
            ("retificação", "retificacao", "rectificação", "rectificacao"),
        ),
    )

    def supports(self, document: ClassifiedDocument) -> bool:
        return document.document_type in self._SUPPORTED_DOCUMENT_TYPES

    def extract(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
    ) -> ReaderResult:
        relevant_sections = self.relevant_sections(sections) or list(sections)
        lines = self._lines(self._join_text(document, relevant_sections))

        fields = {
            field_name: self._extract_risk_field(
                document,
                relevant_sections,
                lines,
                field_name=field_name,
                severity=severity,
                markers=markers,
            )
            for field_name, severity, markers in self._RISK_SPECS
        }

        found = [field for field in fields.values() if field.status != EvidenceStatus.NOT_FOUND]
        warnings = [] if found else ["Não foram encontrados riscos relevantes."]
        confidence = sum(field.confidence for field in found) / len(found) if found else 0.0

        return ReaderResult(
            reader_name=self.reader_name,
            document_ids=[document.source.document_id],
            fields=fields,
            evidences=self._collect_evidences(fields),
            warnings=warnings,
            confidence=confidence,
        )

    def _extract_risk_field(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        *,
        field_name: str,
        severity: str,
        markers: tuple[str, ...],
    ) -> ExtractedField:
        items: list[dict[str, Any]] = []
        evidences = []
        for section in sections or []:
            for line in self._lines(section.text):
                if not self._contains_marker(line, markers):
                    continue
                item = self._risk_item(line, severity)
                if item not in items:
                    items.append(item)
                    evidences.append(
                        create_evidence(
                            source_document_id=document.source.document_id,
                            filename=document.source.filename,
                            excerpt=line,
                            page=section.page_start,
                            section=section.title,
                            confidence=item["confidence"],
                            status=EvidenceStatus.CONFIRMED,
                        )
                    )
        if not items:
            for line in lines:
                if not self._contains_marker(line, markers):
                    continue
                item = self._risk_item(line, severity)
                if item not in items:
                    items.append(item)
                    evidences.append(
                        create_evidence(
                            source_document_id=document.source.document_id,
                            filename=document.source.filename,
                            excerpt=line,
                            confidence=item["confidence"],
                            status=EvidenceStatus.CONFIRMED,
                        )
                    )
        return self._field_from_items(field_name, items, evidences)

    def _risk_item(self, text: str, severity: str) -> dict[str, Any]:
        cleaned = self._clean_line(text)
        title = self._risk_title(cleaned)
        return {
            "title": title,
            "description": cleaned,
            "severity": severity,
            "condition": cleaned,
            "confidence": 0.82 if severity == "critical" else 0.76 if severity == "warning" else 0.7,
            "status": "confirmed",
        }

    @staticmethod
    def _risk_title(text: str) -> str:
        normalized = RisksReader._normalize(text)
        mapping = (
            ("anonim", "Quebra de anonimato"),
            ("fora de prazo", "Prazo fora do prazo"),
            ("assinatura", "Assinatura inválida"),
            ("documentos em falta", "Falta de documentos"),
            ("limite de paginas", "Excesso de páginas"),
            ("formato invalido", "Formato inválido"),
            ("contradi", "Contradição documental"),
            ("esclarecimento", "Esclarecimento"),
            ("retifica", "Retificação"),
            ("penal", "Penalização contratual"),
            ("exclus", "Risco de exclusão"),
        )
        for marker, title in mapping:
            if marker in normalized:
                return title
        return "Risco identificado"

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
        normalized = unicodedata.normalize("NFKD", RisksReader._clean_line(text).casefold())
        return "".join(character for character in normalized if not unicodedata.combining(character))

    def _contains_marker(self, text: str, markers: tuple[str, ...]) -> bool:
        normalized = self._normalize(text)
        return any(self._normalize(marker) in normalized for marker in markers)

    @staticmethod
    def _field_from_items(
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
        return ExtractedField(
            field_name=field_name,
            value=items,
            normalized_value=items,
            evidences=evidences,
            confidence=min(0.95, max((item.get("confidence", 0.7) for item in items), default=0.7)),
            status=EvidenceStatus.CONFIRMED,
        )

    @staticmethod
    def _collect_evidences(fields: dict[str, ExtractedField]) -> list[Any]:
        evidences: list[Any] = []
        for field in fields.values():
            evidences.extend(field.evidences)
        return evidences
