from __future__ import annotations

import re
import unicodedata
from typing import Protocol

from app.architecture_intelligence.llm.ollama_provider import OllamaProvider
from app.architecture_intelligence.llm.provider import LLMProviderError


class TitleTextProvider(Protocol):
    def generate_text(self, system: str, user: str) -> str:
        raise NotImplementedError


_SPACE_RE = re.compile(r"\s+")
_OBJECT_START_RE = re.compile(
    r"\b(?:escola|parque|mercado|unidade\s+de\s+saude|biblioteca|"
    r"habitacao|bairro|praca|centro|hospital|pavilhao|edificio|"
    r"infraestrutura|jardim|largo|avenida|rua)\b",
    re.IGNORECASE,
)
_ADMIN_RE = re.compile(
    r"\b(?:aquisic[a\u00e3]o|presta[c\u00e7][a\u00e3]o)\s+de\s+servicos\b|"
    r"\bconcurso\s+(?:p[u\u00fa]blico|de\s+conce[c\u00e7][a\u00e3]o|internacional)\b|"
    r"\bprocedimento\s+para\b|\bprocesso\s*(?:n\.?|no|numero)?\s*[\w./-]+|"
    r"\b(?:projeto\s+de\s+execu[c\u00e7][a\u00e3]o|elabora[c\u00e7][a\u00e3]o\s+de\s+projeto)\b",
    re.IGNORECASE,
)
_EXPLANATORY_RE = re.compile(
    r"^(?:o\s+)?(?:titulo|t[i\u00ed]tulo)\s+(?:resumido|e)\s*(?:[eé]|:)|"
    r"^(?:a\s+)?resposta\s*(?:[eé]|:)",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos",
    "e", "em", "na", "nas", "no", "nos", "o", "os", "para", "por",
}


def _texto(value: object) -> str:
    return _SPACE_RE.sub(" ", str(value or "")).strip(" \t\r\n-,:;.")


def _normalizar(value: object) -> str:
    decomposed = unicodedata.normalize("NFD", _texto(value))
    without_marks = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return without_marks.casefold()


def _tokens(value: object) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(_normalizar(value))
        if token not in _STOPWORDS and len(token) > 1
    }


def _formatar_capitalizacao(title: str) -> str:
    if not title.isupper():
        return title
    connectors = {"a", "as", "da", "das", "de", "do", "dos", "e", "em", "na", "nas", "no", "nos"}
    return " ".join(
        word.lower() if _normalizar(word) in connectors else word.capitalize()
        for word in title.split()
    )


def _limpar_final(value: object) -> str:
    title = _texto(value)
    title = re.split(
        r"\s+(?:-|\u2013|\u2014)\s+|\s*,\s*(?:processo|proc\.?|ref\.?|codigo)\b",
        title,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    if "," in title:
        main, suffix = title.split(",", 1)
        if _tokens(suffix).issubset(_tokens(main)):
            title = main
    return _formatar_capitalizacao(_texto(title))


def limpar_titulo_deterministico(titulo: object) -> str:
    """Extrai o objeto reconhecivel sem alterar o titulo oficial persistido."""
    official = _texto(titulo)
    if not official:
        return ""

    object_match = _OBJECT_START_RE.search(official)
    if object_match:
        return _limpar_final(official[object_match.start():])

    cleaned = re.sub(
        r"^(?:\s*(?:aquisic[a\u00e3]o|presta[c\u00e7][a\u00e3]o)\s+de\s+servicos(?:\s+n[.o\u00ba]*\s*[\w./-]+)?\s*[-:]*\s*)",
        "",
        official,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(?:\s*concurso\s+(?:p[u\u00fa]blico|de\s+conce[c\u00e7][a\u00e3]o|internacional)\s*(?:para)?\s*)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(?:\s*(?:a\s+)?elabora[c\u00e7][a\u00e3]o\s+de\s+(?:projeto|projeto\s+de\s+execu[c\u00e7][a\u00e3]o)\s+(?:para|de)\s*)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return _limpar_final(cleaned) or official


def titulo_e_humano(candidate: object) -> bool:
    title = _texto(candidate)
    words = title.split()
    return (
        3 <= len(words) <= 10
        and len(title) <= 110
        and not _ADMIN_RE.search(_normalizar(title))
    )


def validar_titulo_resumido(
    candidate: object,
    *,
    titulo_oficial: object,
    entidade: object = None,
    localizacao: object = None,
    objeto: object = None,
) -> str | None:
    """Aceita apenas um titulo curto, fiel e sem formato ou explicacoes."""
    raw = str(candidate or "").strip()
    title = _texto(raw)
    if not title or raw != title:
        return None
    if len(title) > 110 or not 2 <= len(title.split()) <= 12:
        return None
    if any(marker in title for marker in ("{", "}", "[", "]", "`", "\n")):
        return None
    if title.startswith(("\"", "'")) or title.endswith(("\"", "'", ".", ":")):
        return None
    if _EXPLANATORY_RE.search(title) or _ADMIN_RE.search(_normalizar(title)):
        return None

    allowed = _tokens(titulo_oficial) | _tokens(entidade) | _tokens(localizacao) | _tokens(objeto)
    candidate_tokens = _tokens(title)
    if not candidate_tokens or not candidate_tokens.issubset(allowed):
        return None
    return title


def _ollama_prompt(
    *,
    titulo_oficial: str,
    entidade: str,
    localizacao: str,
    objeto: str,
) -> tuple[str, str]:
    system = (
        "Identifica apenas o nome humano principal do objeto do concurso. "
        "Responde somente com o titulo, entre 3 e 10 palavras, sem Markdown, "
        "JSON, aspas, explicacoes, prefixos administrativos ou ponto final. "
        "Nao inventes nomes ou informacao que nao conste no contexto."
    )
    user = "\n".join(
        value
        for value in (
            f"Titulo oficial: {titulo_oficial}",
            f"Entidade: {entidade}" if entidade else "",
            f"Localizacao: {localizacao}" if localizacao else "",
            f"Objeto: {objeto}" if objeto else "",
        )
        if value
    )
    return system, user


def gerar_titulo_resumido(
    titulo_oficial: object,
    *,
    entidade: object = None,
    localizacao: object = None,
    objeto: object = None,
    provider: TitleTextProvider | None = None,
) -> str:
    """Gera um titulo de apresentacao; qualquer falha usa fallback seguro."""
    official = _texto(titulo_oficial)
    deterministic = limpar_titulo_deterministico(official)
    if titulo_e_humano(deterministic):
        return deterministic

    active_provider = provider
    if active_provider is None:
        candidate_provider = OllamaProvider()
        if candidate_provider.enabled:
            active_provider = candidate_provider

    if active_provider is not None and official:
        try:
            system, user = _ollama_prompt(
                titulo_oficial=official,
                entidade=_texto(entidade),
                localizacao=_texto(localizacao),
                objeto=_texto(objeto),
            )
            validated = validar_titulo_resumido(
                active_provider.generate_text(system, user),
                titulo_oficial=official,
                entidade=entidade,
                localizacao=localizacao,
                objeto=objeto,
            )
            if validated:
                return validated
        except (LLMProviderError, OSError, TimeoutError, ValueError):
            pass
        except Exception:
            # A sintese nunca pode interromper a recolha ou o upsert principal.
            pass
    return deterministic or official
