from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from ..schemas import ClassifiedDocument, DocumentSection, ReaderResult


class SpecializedReader(ABC):
    reader_name = "base"
    supported_topics: tuple[str, ...] = ()

    @abstractmethod
    def supports(self, document: ClassifiedDocument) -> bool:
        """Indica se este leitor pode trabalhar com o documento."""

    @abstractmethod
    def extract(
        self,
        document: ClassifiedDocument,
        sections: Sequence[DocumentSection],
    ) -> ReaderResult:
        """Extrai apenas os campos da responsabilidade deste leitor."""

    def relevant_sections(
        self,
        sections: Sequence[DocumentSection],
    ) -> list[DocumentSection]:
        if not self.supported_topics:
            return list(sections)

        supported = {topic.casefold() for topic in self.supported_topics}

        return [
            section
            for section in sections
            if supported.intersection(topic.casefold() for topic in section.topics)
        ]