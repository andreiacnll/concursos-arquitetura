from __future__ import annotations

from typing import Any
import unicodedata


TYPOLOGY_TAXONOMY: dict[str, tuple[str, ...]] = {
    "Educacao": (
        "educacao",
        "escola",
        "escolar",
        "centro escolar",
        "ensino",
        "agrupamento",
        "school",
        "education",
        "campus",
        "college",
        "university",
    ),
    "Saude": (
        "saude",
        "hospital",
        "clinica",
        "clinic",
        "health",
        "centro de saude",
        "hospital center",
    ),
    "Habitacao": (
        "habitacao",
        "housing",
        "residential",
        "house",
        "houses",
        "home",
        "residence",
        "residences",
        "senior residence",
        "senior residences",
        "housing complex",
        "social housing",
        "moradia",
        "apartamento",
        "dwelling",
    ),
    "Mercados": (
        "mercado",
        "market",
        "municipal market",
    ),
    "Mobiliario": (
        "mobiliario",
        "furniture",
        "chair",
        "cadeira",
    ),
    "Escritorios": (
        "escritorio",
        "office",
        "office building",
        "workplace",
    ),
    "Industria": (
        "industria",
        "industrial",
        "factory",
        "warehousing",
    ),
    "Paisagismo": (
        "paisagismo",
        "landscape",
        "garden",
        "jardim",
    ),
    "Espaco Publico": (
        "espaco publico",
        "public space",
        "square",
        "plaza",
    ),
    "Urbanismo": (
        "urbanismo",
        "urban planning",
        "planeamento urbano",
        "urban design",
    ),
    "Comercio": (
        "comercio",
        "retail",
        "shop",
        "store",
    ),
    "Turismo": (
        "turismo",
        "hotel",
        "hospitality",
        "lodging",
    ),
    "Patrimonio": (
        "patrimonio",
        "heritage",
        "monument",
        "historic",
        "chapel",
        "chapels",
        "mortuary chapel",
        "mortuary chapels",
        "funerary chapel",
        "funerary chapels",
    ),
    "Cultura": (
        "cultura",
        "museum",
        "theatre",
        "theater",
        "church",
        "igreja",
        "capela",
        "cultural building",
        "cultural center",
        "biblioteca",
        "auditorio",
    ),
    "Desporto": (
        "desporto",
        "sport",
        "stadium",
        "pavilhao",
    ),
    "Infraestruturas": (
        "infraestrutura",
        "infrastructure",
        "roads",
        "utilities",
    ),
    "Reabilitacao": (
        "reabilitacao",
        "requalificacao",
        "rehabilitation",
        "refurbishment",
        "renovation",
        "modernization",
    ),
}

SERVICE_TAXONOMY: dict[str, tuple[str, ...]] = {
    "Arquitetura": (
        "arquitetura",
        "architecture",
        "projecto de arquitetura",
        "projeto de arquitetura",
        "arquiteto",
        "arquitecto",
        "concecao",
        "concepcao",
    ),
    "Coordenacao": (
        "coordenacao",
        "coordination",
        "coordenacao tecnica",
        "coordenacao de projeto",
    ),
    "Fiscalizacao": (
        "fiscalizacao",
        "supervisao",
        "inspection",
    ),
    "BIM": (
        "bim",
        "building information modeling",
        "building information management",
        "modelacao da informacao",
    ),
    "Planeamento": (
        "planeamento",
        "planning",
        "urban planning",
        "planeamento urbano",
    ),
    "Reabilitacao": (
        "reabilitacao",
        "requalificacao",
        "rehabilitation",
        "refurbishment",
    ),
    "Paisagismo": (
        "paisagismo",
        "landscape",
    ),
    "Especialidades": (
        "especialidades",
        "engineering",
        "structures",
        "instalacoes",
    ),
    "Gestao de Projeto": (
        "gestao de projeto",
        "project management",
    ),
    "Estudo Previo": (
        "estudo previo",
        "preliminary study",
    ),
}


TYPOLOGY_SERVICE_HINTS: dict[str, tuple[str, ...]] = {
    "Educacao": ("Arquitetura", "Coordenacao", "BIM", "Especialidades"),
    "Saude": ("Arquitetura", "Coordenacao", "BIM", "Especialidades"),
    "Habitacao": ("Arquitetura", "Coordenacao", "BIM", "Reabilitacao"),
    "Mercados": ("Arquitetura", "Coordenacao", "BIM"),
    "Mobiliario": ("Arquitetura", "Estudo Previo", "Gestao de Projeto"),
    "Escritorios": ("Arquitetura", "Coordenacao", "BIM"),
    "Industria": ("Arquitetura", "Coordenacao", "Especialidades"),
    "Paisagismo": ("Paisagismo", "Arquitetura", "Coordenacao"),
    "Espaco Publico": ("Arquitetura", "Paisagismo", "Coordenacao"),
    "Urbanismo": ("Planeamento", "Arquitetura", "Coordenacao"),
    "Comercio": ("Arquitetura", "Coordenacao", "BIM"),
    "Turismo": ("Arquitetura", "Coordenacao", "BIM"),
    "Cultura": ("Arquitetura", "Coordenacao", "BIM"),
    "Desporto": ("Arquitetura", "Coordenacao", "BIM"),
    "Infraestruturas": ("Especialidades", "Coordenacao"),
    "Reabilitacao": ("Arquitetura", "Reabilitacao", "Coordenacao", "BIM"),
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _norm_text(value: Any) -> str:
    text = _clean_text(value).casefold()
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        key = _norm_text(text)
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def normalize_concept(value: Any, taxonomy: dict[str, tuple[str, ...]]) -> str:
    text = _norm_text(value)
    if not text:
        return ""
    for canonical, aliases in taxonomy.items():
        canonical_norm = _norm_text(canonical)
        if text == canonical_norm or text in canonical_norm or canonical_norm in text:
            return canonical
        for alias in aliases:
            alias_norm = _norm_text(alias)
            if not alias_norm:
                continue
            if text == alias_norm or text in alias_norm or alias_norm in text:
                return canonical
    return _clean_text(value)


def canonicalize_many(values: list[Any], taxonomy: dict[str, tuple[str, ...]]) -> list[str]:
    return _unique([normalize_concept(value, taxonomy) for value in values if _clean_text(value)])


def gather_texts(value: Any) -> list[str]:
    texts: list[str] = []
    if value is None:
        return texts
    if hasattr(value, "model_dump"):
        return gather_texts(value.model_dump())
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"value", "normalized_value", "label", "name", "text", "description", "title", "excerpt"}:
                texts.extend(gather_texts(item))
            else:
                texts.extend(gather_texts(item))
        return _unique(texts)
    if isinstance(value, (list, tuple, set)):
        for item in value:
            texts.extend(gather_texts(item))
        return _unique(texts)
    text = _clean_text(value)
    return [text] if text else []


def collect_concepts(value: Any, taxonomy: dict[str, tuple[str, ...]]) -> list[str]:
    return canonicalize_many(gather_texts(value), taxonomy)


def infer_service_hints(typologies: list[str]) -> list[str]:
    hints: list[str] = []
    for typology in typologies:
        hints.extend(TYPOLOGY_SERVICE_HINTS.get(typology, ()))
    return _unique(hints)
