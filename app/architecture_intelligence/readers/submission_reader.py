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


class SubmissionReader(SpecializedReader):
    reader_name = "submission_reader"
    supported_topics = ("submission", "procedure_identity")

    _SUPPORTED_DOCUMENT_TYPES = {
        DocumentType.ANNOUNCEMENT,
        DocumentType.TERMS_OF_REFERENCE,
        DocumentType.PROCEDURE_PROGRAM,
        DocumentType.SPECIFICATIONS,
        DocumentType.PRELIMINARY_PROGRAM,
        DocumentType.CONTRACT_DRAFT,
    }

    _CATEGORY_MARKERS = {
        "administrative_documents": ("documentos administrativos", "documentos da proposta", "documentos da candidatura", "declaração", "declaracao", "certidão", "certidao"),
        "technical_documents": ("documentos técnicos", "documentos tecnicos", "memória descritiva", "memoria descritiva", "peças desenhadas", "pecas desenhadas", "projeto de execução", "projeto de execucao"),
        "financial_documents": ("documentos financeiros", "proposta financeira", "preço", "preco", "mapa de preços", "mapa de precos", "orçamento", "orcamento"),
        "team_documents": ("documentos da equipa", "equipa", "curriculum", "currículo", "termo de responsabilidade", "responsabilidade"),
        "post_award_documents": ("documentos de habilitação", "documentos de habilitacao", "habilitação", "habilitacao", "adjudicação", "adjudicacao"),
    }

    _SIGNATURE_TERMS = ("assinatura digital", "assinatura eletrónica", "assinatura electronica", "qualificada", "certificado")
    _ANONYMITY_TERMS = ("anonimato", "anónimo", "anonimo", "sem identificação", "sem identificacao", "involucro", "envelope")
    _FORMAT_TERMS = ("plataforma", "ficheiro", "ficheiros", "pdf", "zip", "formato", "submissão", "submissao")
    _NAMING_TERMS = ("nome do ficheiro", "nomenclatura", "nomeação", "nomeacao", "sem acentos", "sem espaços", "sem espacos")
    _LIMIT_TERMS = ("página", "pagina", "páginas", "paginas", "folhas", "número de ficheiros", "numero de ficheiros")

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
            "administrative_documents": self._extract_categories(document, relevant_sections, lines, "administrative_documents"),
            "technical_documents": self._extract_categories(document, relevant_sections, lines, "technical_documents"),
            "financial_documents": self._extract_categories(document, relevant_sections, lines, "financial_documents"),
            "team_documents": self._extract_categories(document, relevant_sections, lines, "team_documents"),
            "post_award_documents": self._extract_categories(document, relevant_sections, lines, "post_award_documents"),
            "signature_requirements": self._extract_terms(document, relevant_sections, lines, "signature_requirements", self._SIGNATURE_TERMS, severity="critical"),
            "anonymity_rules": self._extract_terms(document, relevant_sections, lines, "anonymity_rules", self._ANONYMITY_TERMS, severity="critical"),
            "submission_format_rules": self._extract_terms(document, relevant_sections, lines, "submission_format_rules", self._FORMAT_TERMS, severity="warning"),
            "naming_rules": self._extract_terms(document, relevant_sections, lines, "naming_rules", self._NAMING_TERMS, severity="warning"),
            "page_limits": self._extract_terms(document, relevant_sections, lines, "page_limits", self._LIMIT_TERMS, severity="warning"),
            "platform_requirements": self._extract_terms(document, relevant_sections, lines, "platform_requirements", ("acingov", "vortal", "base", "plataforma eletrónica", "plataforma eletronica"), severity="info"),
        }

        found = [field for field in fields.values() if field.status != EvidenceStatus.NOT_FOUND]
        warnings = [] if found else ["Não foram encontrados requisitos de submissão."]
        confidence = sum(field.confidence for field in found) / len(found) if found else 0.0

        return ReaderResult(
            reader_name=self.reader_name,
            document_ids=[document.source.document_id],
            fields=fields,
            evidences=self._collect_evidences(fields),
            warnings=warnings,
            confidence=confidence,
        )

    def _extract_categories(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        field_name: str,
    ) -> ExtractedField:
        markers = self._CATEGORY_MARKERS[field_name]
        items: list[dict[str, Any]] = []
        evidences = []
        for section in sections or []:
            for line in self._lines(section.text):
                if not self._contains_marker(line, markers):
                    continue
                cleaned = self._clean_line(line)
                if not cleaned:
                    continue
                item = {
                    "text": cleaned,
                    "category": field_name.replace("_", " "),
                    "mandatory": self._is_mandatory(cleaned),
                }
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
                item = {
                    "text": cleaned,
                    "category": field_name.replace("_", " "),
                    "mandatory": self._is_mandatory(cleaned),
                }
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
        return self._field_from_items(field_name, items, evidences, confidence=0.75)

    def _extract_terms(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        field_name: str,
        markers: tuple[str, ...],
        *,
        severity: str,
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
                item = {
                    "text": cleaned,
                    "mandatory": self._is_mandatory(cleaned),
                    "severity": severity,
                }
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
                item = {
                    "text": cleaned,
                    "mandatory": self._is_mandatory(cleaned),
                    "severity": severity,
                }
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
        return self._field_from_items(field_name, items, evidences, confidence=0.78)

    @staticmethod
    def _is_mandatory(text: str) -> bool:
        normalized = SubmissionReader._normalize(text)
        return any(token in normalized for token in ("obrigatorio", "obrigatória", "obrigatorio", "sob pena", "deve", "devera", "deverá"))

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
        normalized = unicodedata.normalize("NFKD", SubmissionReader._clean_line(text).casefold())
        return "".join(character for character in normalized if not unicodedata.combining(character))

    def _contains_marker(self, text: str, markers: tuple[str, ...]) -> bool:
        normalized = self._normalize(text)
        return any(self._normalize(marker) in normalized for marker in markers)

    @staticmethod
    def _field_from_items(
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
    def _collect_evidences(fields: dict[str, ExtractedField]) -> list[Any]:
        evidences: list[Any] = []
        for field in fields.values():
            evidences.extend(field.evidences)
        return evidences
