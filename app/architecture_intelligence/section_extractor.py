from __future__ import annotations

import hashlib
import re
import unicodedata

from .schemas import ClassifiedDocument, DocumentSection


_TOPIC_RULES: dict[str, tuple[str, ...]] = {
    "procedure_identity": (
        "objeto",
        "entidade adjudicante",
        "tipo de procedimento",
        "codigo cpv",
        "cpv",
        "prazo para apresentacao",
    ),
    "award_criteria": (
        "criterio de adjudicacao",
        "criterios de adjudicacao",
        "fatores de avaliacao",
        "subfatores",
        "ponderacao",
        "modelo de avaliacao",
        "descritores",
        "desempate",
    ),
    "team": (
        "equipa tecnica",
        "equipa minima",
        "coordenador",
        "especialidades",
        "experiencia profissional",
        "habilitacoes",
        "ordem dos arquitectos",
        "ordem dos arquitetos",
        "ordem dos engenheiros",
    ),
    "financial": (
        "preco base",
        "preco contratual",
        "valor da obra",
        "estimativa da obra",
        "pagamento",
        "pagamentos",
        "premio",
        "premios",
        "caucao",
        "seguro",
        "penalizacao",
        "multa",
    ),
    "deliverables": (
        "entregaveis",
        "elementos a entregar",
        "estudo previo",
        "anteprojeto",
        "projeto de execucao",
        "assistencia tecnica",
        "telas finais",
        "pecas escritas",
        "pecas desenhadas",
        "memoria descritiva",
        "mapa de quantidades",
    ),
    "submission": (
        "documentos que constituem a proposta",
        "documentos da proposta",
        "documentos de habilitacao",
        "assinatura digital",
        "modo de apresentacao",
        "submissao",
        "involucro",
        "anonimato",
    ),
    "risks": (
        "exclusao",
        "motivo de exclusao",
        "nao admissao",
        "incumprimento",
        "prazo maximo",
        "sob pena de exclusao",
        "quebra de anonimato",
    ),
    "technical_constraints": (
        "condicionantes",
        "acessibilidade",
        "sustentabilidade",
        "eficiencia energetica",
        "vulnerabilidade sismica",
        "patrimonio",
        "edificio existente",
        "funcionamento durante a obra",
        "materiais reciclados",
        "bim",
    ),
}


_HEADING_PATTERN = re.compile(
    r"(?im)^[ \t]*(?:"
    r"(?:artigo|clausula)\s+\d+(?:[.]\s*)?[oa??]?"
    r"|(?:capitulo|seccao|secao)\s+(?:[ivxlcdm]+|\d+)(?:[.]\s*)?[oa??]?"
    r"|anexo\s+[ivxlcdm\d]+(?:[.\-][a-z0-9]+)*"
    r")[ \t]*$"
)


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def _normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _normalize_for_matching(value: str) -> str:
    value = _strip_accents(value.casefold())
    return re.sub(r"\s+", " ", value).strip()


def _build_section_id(
    document_id: str,
    index: int,
    title: str | None,
) -> str:
    raw = f"{document_id}|{index}|{title or ''}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"section-{digest}"


def detect_topics(text: str) -> list[str]:
    normalized = _normalize_for_matching(text)
    topics: list[str] = []

    for topic, keywords in _TOPIC_RULES.items():
        if any(
            _normalize_for_matching(keyword) in normalized
            for keyword in keywords
        ):
            topics.append(topic)

    return topics


def _extract_article(title: str | None) -> str | None:
    if not title:
        return None

    normalized_title = _strip_accents(title)

    match = re.search(
        r"(?i)\b(?:artigo|clausula)\s+\d+(?:[.]\s*)?[oa??]?",
        normalized_title,
    )

    return title.strip() if match else None


def extract_sections(
    document: ClassifiedDocument,
) -> list[DocumentSection]:
    text = _normalize_text(document.source.text)

    if not text:
        return []

    searchable_text = _strip_accents(text)
    headings = list(_HEADING_PATTERN.finditer(searchable_text))
    sections: list[DocumentSection] = []

    if not headings:
        return [
            DocumentSection(
                section_id=_build_section_id(
                    document.source.document_id,
                    0,
                    document.title,
                ),
                document_id=document.source.document_id,
                title=document.title,
                article=None,
                text=text,
                topics=detect_topics(text),
            )
        ]

    if headings[0].start() > 0:
        introduction = text[:headings[0].start()].strip()

        if introduction:
            sections.append(
                DocumentSection(
                    section_id=_build_section_id(
                        document.source.document_id,
                        0,
                        "Introducao",
                    ),
                    document_id=document.source.document_id,
                    title="Introdu??o",
                    article=None,
                    text=introduction,
                    topics=detect_topics(introduction),
                )
            )

    for index, heading in enumerate(headings):
        original_title = text[heading.start():heading.end()].strip()
        content_start = heading.end()
        content_end = (
            headings[index + 1].start()
            if index + 1 < len(headings)
            else len(text)
        )

        content_text = text[content_start:content_end].strip()
        combined_text = f"{original_title}\n{content_text}".strip()

        sections.append(
            DocumentSection(
                section_id=_build_section_id(
                    document.source.document_id,
                    index + 1,
                    original_title,
                ),
                document_id=document.source.document_id,
                title=original_title,
                article=_extract_article(original_title),
                text=combined_text,
                topics=detect_topics(combined_text),
            )
        )

    return sections
