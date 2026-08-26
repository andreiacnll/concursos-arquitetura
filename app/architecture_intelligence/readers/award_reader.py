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


class AwardReader(SpecializedReader):
    reader_name = "award_reader"
    supported_topics = ("award_criteria",)

    _SUPPORTED_DOCUMENT_TYPES = {
        DocumentType.AWARD_CRITERIA,
        DocumentType.TERMS_OF_REFERENCE,
        DocumentType.PROCEDURE_PROGRAM,
        DocumentType.SPECIFICATIONS,
    }

    _PERCENTAGE_PATTERN = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")

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
            "award_criterion": self._extract_text_field(
                document,
                relevant_sections,
                lines,
                field_name="award_criterion",
                markers=("criterio de adjudicacao", "critério de adjudicação", "modelo de avaliacao", "modelo de avaliação"),
            ),
            "evaluation_model": self._extract_text_field(
                document,
                relevant_sections,
                lines,
                field_name="evaluation_model",
                markers=("modelo de avaliacao", "modelo de avaliação", "modelo de julgamento", "metodo de avaliacao", "método de avaliação"),
            ),
            "price_weight": self._extract_weight_field(
                document,
                relevant_sections,
                lines,
                field_name="price_weight",
                markers=("preco", "preço"),
                prefer_last=False,
            ),
            "technical_weight": self._extract_weight_field(
                document,
                relevant_sections,
                lines,
                field_name="technical_weight",
                markers=("tecnica", "técnica", "qualidade", "merito", "mérito"),
                prefer_last=True,
            ),
            "factors": self._extract_block_list(
                document,
                relevant_sections,
                lines,
                field_name="factors",
                headings=("fatores",),
                stop_headings=("subfatores", "pontuacao maxima", "pontuação máxima", "desempate", "preco anormalmente baixo", "preço anormalmente baixo"),
            ),
            "subfactors": self._extract_block_list(
                document,
                relevant_sections,
                lines,
                field_name="subfactors",
                headings=("subfatores",),
                stop_headings=("pontuacao maxima", "pontuação máxima", "desempate", "preco anormalmente baixo", "preço anormalmente baixo"),
            ),
            "maximum_score_requirements": self._extract_block_list(
                document,
                relevant_sections,
                lines,
                field_name="maximum_score_requirements",
                headings=("pontuacao maxima", "pontuação máxima", "requisitos para pontuacao maxima", "requisitos para pontuação máxima"),
            ),
            "tie_break_rules": self._extract_block_list(
                document,
                relevant_sections,
                lines,
                field_name="tie_break_rules",
                headings=("desempate", "criterios de desempate", "critérios de desempate"),
            ),
            "abnormally_low_price_rule": self._extract_text_field(
                document,
                relevant_sections,
                lines,
                field_name="abnormally_low_price_rule",
                markers=("preco anormalmente baixo", "preço anormalmente baixo", "oferta anormalmente baixa"),
            ),
        }

        found = [field for field in fields.values() if field.status != EvidenceStatus.NOT_FOUND]
        confidence = (
            sum(field.confidence for field in found) / len(found)
            if found
            else 0.0
        )

        warnings: list[str] = []
        factor_weights = [
            float(item["weight"])
            for item in (fields["factors"].value or [])
            if isinstance(item, dict) and isinstance(item.get("weight"), (int, float))
        ]
        if factor_weights and abs(sum(factor_weights) - 100.0) > 0.5:
            warnings.append("As percentagens dos fatores não somam 100%.")
        if not found:
            warnings.append("Não foram encontrados critérios de adjudicação.")

        return ReaderResult(
            reader_name=self.reader_name,
            document_ids=[document.source.document_id],
            fields=fields,
            evidences=self._collect_evidences(fields),
            warnings=warnings,
            confidence=confidence,
        )

    def _extract_text_field(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        *,
        field_name: str,
        markers: tuple[str, ...],
    ) -> ExtractedField:
        candidate = self._find_line(sections, lines, markers)
        if candidate is None:
            return ExtractedField(
                field_name=field_name,
                value=None,
                normalized_value=None,
                evidences=[],
                confidence=0.0,
                status=EvidenceStatus.NOT_FOUND,
            )
        value = self._inline_after_colon(candidate) or self._clean_line(candidate)
        evidence = create_evidence(
            source_document_id=document.source.document_id,
            filename=document.source.filename,
            excerpt=candidate,
            confidence=0.86,
            status=EvidenceStatus.CONFIRMED,
        )
        return ExtractedField(
            field_name=field_name,
            value=value,
            normalized_value=value,
            evidences=[evidence],
            confidence=0.86,
            status=EvidenceStatus.CONFIRMED,
        )

    def _extract_weight_field(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        *,
        field_name: str,
        markers: tuple[str, ...],
        prefer_last: bool,
    ) -> ExtractedField:
        candidate = self._find_line(sections, lines, markers, require_percent=True)
        if candidate is None:
            return ExtractedField(
                field_name=field_name,
                value=None,
                normalized_value=None,
                evidences=[],
                confidence=0.0,
                status=EvidenceStatus.NOT_FOUND,
            )
        values = self._extract_percentages(candidate)
        normalized = values[-1] if (values and prefer_last) else values[0] if values else None
        evidence = create_evidence(
            source_document_id=document.source.document_id,
            filename=document.source.filename,
            excerpt=candidate,
            confidence=0.84,
            status=EvidenceStatus.CONFIRMED,
        )
        return ExtractedField(
            field_name=field_name,
            value={"text": candidate, "percentages": values},
            normalized_value=normalized,
            evidences=[evidence],
            confidence=0.84,
            status=EvidenceStatus.CONFIRMED,
        )

    def _extract_block_list(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
        lines: list[str],
        *,
        field_name: str,
        headings: tuple[str, ...],
        stop_headings: tuple[str, ...] = (),
    ) -> ExtractedField:
        items: list[dict[str, Any]] = []
        evidences = []
        for section in sections or []:
            for value, excerpt in self._collect_block(section.text, headings, stop_headings):
                item = self._parse_block_item(value)
                if item is None:
                    continue
                items.append(item)
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
            for value, excerpt in self._collect_block("\n".join(lines), headings, stop_headings):
                item = self._parse_block_item(value)
                if item is None:
                    continue
                items.append(item)
                evidences.append(
                    create_evidence(
                        source_document_id=document.source.document_id,
                        filename=document.source.filename,
                        excerpt=excerpt,
                        confidence=0.78,
                        status=EvidenceStatus.CONFIRMED,
                    )
                )
        return self._field_from_items(field_name, items, evidences, confidence=0.76)

    def _collect_block(
        self,
        text: str,
        headings: tuple[str, ...],
        stop_headings: tuple[str, ...] = (),
    ) -> list[tuple[str, str]]:
        lines = self._lines(text)
        collected: list[tuple[str, str]] = []
        for index, line in enumerate(lines):
            normalized_line = self._normalize(line)
            if normalized_line not in {self._normalize(item) for item in headings}:
                continue
            inline = self._inline_after_colon(line)
            if inline:
                collected.append((inline, line))
            for next_line in lines[index + 1 :]:
                if self._is_heading(next_line):
                    normalized_next = self._normalize(next_line)
                    if stop_headings and normalized_next in {
                        self._normalize(item) for item in stop_headings
                    }:
                        break
                    if normalized_next in {self._normalize(item) for item in headings}:
                        continue
                    break
                if not self._looks_like_item(next_line):
                    continue
                collected.append((next_line, next_line))
        return collected

    def _parse_block_item(self, text: str) -> dict[str, Any] | None:
        cleaned = self._clean_line(text)
        if not cleaned:
            return None
        percentage = self._extract_percentages(cleaned)
        return {
            "name": cleaned,
            "weight": percentage[0] if percentage else None,
            "description": cleaned,
        }

    def _find_line(
        self,
        sections: Sequence[DocumentSection],
        lines: list[str],
        markers: tuple[str, ...],
        *,
        require_percent: bool = False,
    ) -> str | None:
        for section in sections:
            for line in self._lines(section.text):
                if self._contains_marker(line, markers) and (not require_percent or self._PERCENTAGE_PATTERN.search(line)):
                    return line
        for line in lines:
            if self._contains_marker(line, markers) and (not require_percent or self._PERCENTAGE_PATTERN.search(line)):
                return line
        return None

    def _extract_percentages(self, text: str) -> list[float]:
        values: list[float] = []
        for match in self._PERCENTAGE_PATTERN.finditer(text or ""):
            try:
                values.append(float(match.group(1).replace(",", ".")))
            except ValueError:
                continue
        return values

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
        normalized = unicodedata.normalize("NFKD", AwardReader._clean_line(text).casefold())
        return "".join(character for character in normalized if not unicodedata.combining(character))

    @staticmethod
    def _inline_after_colon(text: str) -> str | None:
        cleaned = AwardReader._clean_line(text)
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
