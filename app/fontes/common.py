"""Infraestrutura comum para fontes externas de concursos de arquitetura.

A BASE.gov continua a ser recolhida exclusivamente por ``app.coletor``.
Este módulo apenas normaliza, filtra, associa e guarda fontes complementares
na mesma base de dados e na tabela ``concurso_fontes`` criada pelo adaptador
Lisboa SRU.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sqlite3
import tempfile
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from app.coletor import parece_relevante
from app.database import abrir_conexao, criar_base_dados, guardar_concurso


PORTUGAL_TZ = ZoneInfo("Europe/Lisbon")
DEFAULT_DAYS = 7
MAX_DAYS = 31
DAYS_WINDOW = max(
    1,
    min(
        int(os.getenv("FONTES_EXTERNAS_DIAS_PESQUISA", str(DEFAULT_DAYS))),
        MAX_DAYS,
    ),
)
REQUEST_TIMEOUT = int(os.getenv("FONTES_EXTERNAS_TIMEOUT_SEGUNDOS", "35"))
MAX_RETRIES = max(
    1,
    min(
        int(os.getenv("FONTES_EXTERNAS_MAX_TENTATIVAS", "3")),
        5,
    ),
)
LISTING_INTERVAL = max(
    0.0,
    float(os.getenv("FONTES_EXTERNAS_INTERVALO_LISTAGEM", "5")),
)
DETAIL_INTERVAL = max(
    0.0,
    float(os.getenv("FONTES_EXTERNAS_INTERVALO_DETALHES", "8")),
)
JITTER_MAX = max(
    0.0,
    float(os.getenv("FONTES_EXTERNAS_JITTER_MAXIMO", "4")),
)
BACKOFF_BASE = max(
    1.0,
    float(os.getenv("FONTES_EXTERNAS_BACKOFF_BASE", "15")),
)
BACKOFF_MAX = max(
    BACKOFF_BASE,
    float(os.getenv("FONTES_EXTERNAS_BACKOFF_MAX", "120")),
)
MAX_DETAILS = max(
    1,
    min(
        int(os.getenv("FONTES_EXTERNAS_MAX_DETALHES", "25")),
        60,
    ),
)
CIRCUIT_FAILURES = max(
    2,
    int(os.getenv("FONTES_EXTERNAS_FALHAS_CIRCUITO", "3")),
)
SUSPENSION_HOURS = max(
    1.0,
    float(os.getenv("FONTES_EXTERNAS_SUSPENSAO_HORAS", "12")),
)
USER_AGENT = os.getenv(
    "FONTES_EXTERNAS_USER_AGENT",
    "CNLL-Arquitetura/1.0 (recolha pública de concursos)",
)
CHECKPOINT_PATH = Path(
    os.getenv("FONTES_EXTERNAS_CHECKPOINT", "fontes_externas_checkpoint.json")
)
TRANSPORT_STATE_PATH = Path(
    os.getenv(
        "FONTES_EXTERNAS_ESTADO_TRANSPORTE",
        "fontes_externas_transport_state.json",
    )
)
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
_LAST_REQUEST_AT: dict[str, float] = {}

BASE_PRIORITY_HOSTS = ("base.gov.pt",)

STRONG_POSITIVE_PATTERNS = (
    r"\barquitetura\b",
    r"\barquitectura\b",
    r"arquitetura\s+paisagista",
    r"\bpaisagismo\b",
    r"\burbanismo\b",
    r"planeamento\s+urbano",
    r"ordenamento\s+do\s+territorio",
    r"projeto\s+de\s+execucao",
    r"elaboracao\s+de\s+projeto",
    r"projeto\s+e\s+especialidades",
    r"concurso\s+(publico\s+)?de\s+concecao",
    r"concurso\s+de\s+ideias",
    r"\bparque\s+urbano\b",
    r"\bespaco\s+publico\b",
    r"obras?\s+de\s+urbanizacao",
    r"reabilitacao\s+urbana",
    r"reabilitacao\s+de\s+edific",
    r"ampliacao\s+de\s+edific",
    r"equipamento\s+publico",
    r"levantamento\s+arquitetonico",
    r"levantamento\s+topografico",
    r"nuvem\s+de\s+pontos",
    r"plano\s+de\s+pormenor",
    r"plano\s+de\s+urbanizacao",
)

NEGATIVE_PATTERNS = (
    r"\blimpeza\b",
    r"\bvigilancia\b",
    r"\bseguros?\b",
    r"\binformatica\b",
    r"fornecimento\s+de",
    r"compra\s+de\s+equipamentos?",
    r"aquisicao\s+de\s+equipamentos?",
    r"manutencao\s+corrente",
    r"servicos?\s+juridicos?",
    r"recursos?\s+humanos?",
    r"servicos?\s+administrativos?",
    r"licenciamento\s+de\s+software",
)

PROJECT_COMPONENT_PATTERNS = (
    r"\bprojeto\b",
    r"\bprojecto\b",
    r"\bconcecao\b",
    r"\bconcepcao\b",
    r"arquitetura",
    r"arquitectura",
    r"especialidades",
    r"levantamento",
    r"planeamento",
    r"urbanismo",
    r"paisag",
)


@dataclass(slots=True)
class ExternalProcedure:
    source: str
    source_label: str
    reference: str
    title: str
    page_url: str
    status: str
    raw_text: str
    entity: str = ""
    documents_url: str = ""
    official_url: str = ""
    publication_date: str = ""
    deadline: str = ""
    location: str = ""
    procedure_type: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    relevant: bool = False
    relevance_reason: str = ""
    relevance_method: str = "deterministic"
    complement_only: bool = False
    allow_new_without_official_date: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SourceReport:
    source: str
    discovered: int = 0
    active: int = 0
    relevant: int = 0
    rejected: int = 0
    inserted: int = 0
    associated: int = 0
    already_known: int = 0
    source_state_updated: int = 0
    outside_window: int = 0
    complement_only_unmatched: int = 0
    errors: list[str] = field(default_factory=list)


def now_portugal() -> datetime:
    return datetime.now(PORTUGAL_TZ)


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    ).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def compact(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_reference(source: str, url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return f"{source}:{digest}"


def parse_iso_date(value: object) -> date | None:
    text = compact(value)
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], pattern).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None



PORTUGUESE_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def parse_portuguese_date(value: object) -> date | None:
    original = compact(value)
    numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", original)
    if numeric:
        day, month, year = map(int, numeric.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
    iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", original)
    if iso:
        year, month, day = map(int, iso.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
    text = normalize(original)
    written = re.search(
        r"\b(\d{1,2})\s+de\s+([a-z]+)(?:\s+de|[, ])+\s*(\d{4})\b",
        text,
    )
    if written:
        day = int(written.group(1))
        month = PORTUGUESE_MONTHS.get(written.group(2))
        year = int(written.group(3))
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                return None
    return None

def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def load_checkpoint(path: Path = CHECKPOINT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "sources": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"version": 1, "sources": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "sources": {}}
    payload["version"] = 1
    payload.setdefault("sources", {})
    return payload


def save_checkpoint(payload: dict[str, Any], path: Path = CHECKPOINT_PATH) -> None:
    payload["updated_at"] = now_portugal().isoformat()
    atomic_write_json(path, payload)


def _load_transport_state(
    path: Path | None = None,
) -> dict[str, Any]:
    path = path or TRANSPORT_STATE_PATH
    if not path.exists():
        return {"version": 1, "hosts": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"version": 1, "hosts": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "hosts": {}}
    payload["version"] = 1
    payload.setdefault("hosts", {})
    return payload


def _save_transport_state(
    payload: dict[str, Any],
    path: Path | None = None,
) -> None:
    path = path or TRANSPORT_STATE_PATH
    payload["updated_at"] = now_portugal().isoformat()
    atomic_write_json(path, payload)


def _host_transport_state(
    payload: dict[str, Any],
    host: str,
) -> dict[str, Any]:
    hosts = payload.setdefault("hosts", {})
    state = hosts.setdefault(
        host,
        {
            "consecutive_failures": 0,
            "suspended_until": "",
            "last_failure_at": "",
            "last_success_at": "",
            "last_status": None,
        },
    )
    return state


def _suspended_until(
    state: dict[str, Any],
) -> datetime | None:
    value = compact(state.get("suspended_until"))
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PORTUGAL_TZ)
    return parsed.astimezone(PORTUGAL_TZ)


def _ensure_host_available(
    host: str,
    transport: dict[str, Any],
) -> None:
    state = _host_transport_state(transport, host)
    until = _suspended_until(state)
    current = now_portugal()

    if until is None:
        return

    if until <= current:
        state["suspended_until"] = ""
        state["consecutive_failures"] = 0
        _save_transport_state(transport)
        return

    raise RuntimeError(
        f"Fonte {host} temporariamente suspensa até "
        f"{until.isoformat()} após falhas consecutivas."
    )


def _record_transport_success(
    host: str,
    transport: dict[str, Any],
) -> None:
    state = _host_transport_state(transport, host)
    state["consecutive_failures"] = 0
    state["suspended_until"] = ""
    state["last_success_at"] = now_portugal().isoformat()
    state["last_status"] = 200
    _save_transport_state(transport)


def _record_transport_failure(
    host: str,
    transport: dict[str, Any],
    *,
    status: int | None,
) -> None:
    state = _host_transport_state(transport, host)
    failures = int(state.get("consecutive_failures") or 0) + 1
    state["consecutive_failures"] = failures
    state["last_failure_at"] = now_portugal().isoformat()
    state["last_status"] = status

    if failures >= CIRCUIT_FAILURES:
        state["suspended_until"] = (
            now_portugal() + timedelta(hours=SUSPENSION_HOURS)
        ).isoformat()

    _save_transport_state(transport)


def _request_interval(request_kind: str) -> float:
    return (
        LISTING_INTERVAL
        if request_kind == "listing"
        else DETAIL_INTERVAL
    )


def _wait_for_request_slot(
    host: str,
    request_kind: str,
) -> None:
    interval = _request_interval(request_kind)
    jitter = random.uniform(0.0, JITTER_MAX)
    target = interval + jitter
    previous = _LAST_REQUEST_AT.get(host)

    if previous is not None:
        elapsed = time.monotonic() - previous
        remaining = target - elapsed
        if remaining > 0:
            time.sleep(remaining)

    _LAST_REQUEST_AT[host] = time.monotonic()


def _retry_after_seconds(value: object) -> float:
    text = compact(value)
    if not text:
        return 0.0

    try:
        return max(0.0, float(text))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        return 0.0

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)

    return max(
        0.0,
        (
            retry_at.astimezone(timezone.utc)
            - datetime.now(timezone.utc)
        ).total_seconds(),
    )


def _backoff_seconds(
    attempt: int,
    *,
    retry_after: float = 0.0,
) -> float:
    exponential = min(
        BACKOFF_BASE * (2 ** max(0, attempt - 1)),
        BACKOFF_MAX,
    )
    jitter = random.uniform(0.0, JITTER_MAX)
    return min(
        max(retry_after, exponential + jitter),
        BACKOFF_MAX,
    )


def fetch_html(
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: int = REQUEST_TIMEOUT,
    request_kind: str = "detail",
) -> str:
    own_session = session is None
    client = session or requests.Session()
    client.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.5",
        }
    )

    host = urlparse(url).netloc.casefold()
    transport = _load_transport_state()
    _ensure_host_available(host, transport)

    last_error: Exception | None = None

    try:
        for attempt in range(1, MAX_RETRIES + 1):
            _wait_for_request_slot(host, request_kind)

            try:
                response = client.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                last_error = error
                _record_transport_failure(
                    host,
                    transport,
                    status=None,
                )
            else:
                status = int(response.status_code)

                if status not in RETRYABLE_HTTP_STATUS:
                    try:
                        response.raise_for_status()
                    except requests.RequestException as error:
                        raise RuntimeError(
                            f"HTTP {status} ao consultar {url}: {error}"
                        ) from error

                    content_type = response.headers.get(
                        "content-type",
                        "",
                    ).casefold()
                    if "html" not in content_type and "xml" not in content_type:
                        raise RuntimeError(
                            "A fonte devolveu conteúdo não HTML: "
                            f"{content_type or 'desconhecido'}"
                        )

                    _record_transport_success(
                        host,
                        transport,
                    )
                    return response.text

                last_error = RuntimeError(
                    f"HTTP {status}: {response.reason}"
                )
                _record_transport_failure(
                    host,
                    transport,
                    status=status,
                )

                retry_after = _retry_after_seconds(
                    response.headers.get("Retry-After")
                )

                state = _host_transport_state(
                    transport,
                    host,
                )
                until = _suspended_until(state)
                if until is not None and until > now_portugal():
                    break

                if attempt < MAX_RETRIES:
                    delay = _backoff_seconds(
                        attempt,
                        retry_after=retry_after,
                    )
                    print(
                        f"[fontes externas] {host} devolveu "
                        f"HTTP {status}; nova tentativa em "
                        f"{delay:.1f}s."
                    )
                    time.sleep(delay)
                    continue

            state = _host_transport_state(transport, host)
            until = _suspended_until(state)
            if until is not None and until > now_portugal():
                break

            if attempt < MAX_RETRIES:
                delay = _backoff_seconds(attempt)
                print(
                    f"[fontes externas] falha temporária em "
                    f"{host}; nova tentativa em {delay:.1f}s."
                )
                time.sleep(delay)

    finally:
        if own_session:
            client.close()

    state = _host_transport_state(transport, host)
    until = _suspended_until(state)
    if until is not None and until > now_portugal():
        raise RuntimeError(
            f"Fonte {host} suspensa até {until.isoformat()} "
            "após falhas consecutivas."
        )

    raise RuntimeError(
        f"Não foi possível consultar {url}: {last_error}"
    )


def infer_procedure_type(title: str, raw_text: str = "") -> str:
    text = normalize(f"{title} {raw_text}")
    if "concurso publico internacional de concecao" in text:
        return "Concurso Público Internacional de Conceção"
    if "concurso publico de concecao" in text or "concurso de concecao" in text:
        return "Concurso de Conceção"
    if "concurso de ideias" in text:
        return "Concurso de Ideias"
    if "concurso publico internacional" in text:
        return "Concurso Público Internacional"
    if "concurso publico" in text:
        return "Concurso Público"
    if "aquisicao de servicos" in text:
        return "Aquisição de Serviços"
    return "Concurso de Arquitetura"


def evaluate_relevance(
    procedure: ExternalProcedure,
    *,
    source_negative_patterns: Iterable[str] = (),
    source_positive_patterns: Iterable[str] = (),
) -> tuple[bool, str]:
    title = normalize(procedure.title)
    text = normalize(f"{procedure.title} {procedure.raw_text}")

    for pattern in tuple(source_negative_patterns) + NEGATIVE_PATTERNS:
        if re.search(pattern, title if pattern in source_negative_patterns else text):
            procedure.relevance_method = "deterministic_negative"
            return False, "Rejeitado por categoria explicitamente irrelevante."

    has_project_component = any(
        re.search(pattern, text) for pattern in PROJECT_COMPONENT_PATTERNS
    )
    if "empreitada" in text and not has_project_component:
        procedure.relevance_method = "deterministic_pure_works"
        return False, "Rejeitado por ser uma empreitada sem elaboração de projeto."

    if any(re.search(pattern, text) for pattern in tuple(source_positive_patterns)):
        procedure.relevance_method = "source_positive"
        return True, "Aceite por regra explícita da fonte."

    if any(re.search(pattern, text) for pattern in STRONG_POSITIVE_PATTERNS):
        procedure.relevance_method = "deterministic_positive"
        return True, "Aceite por regra arquitetónica explícita."

    payload = {
        "contractDesignation": procedure.title,
        "description": procedure.raw_text,
        "contractingEntity": procedure.entity,
        "contractingProcedureType": procedure.procedure_type,
        "contractType": (
            "Aquisição de serviços" if has_project_component else ""
        ),
        "modelType": procedure.source_label,
        "type": "Fonte profissional complementar",
    }
    if parece_relevante(payload):
        procedure.relevance_method = "base_filter"
        return True, "Aceite pelas regras determinísticas do coletor BASE.gov."

    procedure.relevance_method = "deterministic_reject"
    return False, "Rejeitado pelas regras determinísticas de pertinência."


def ensure_source_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS concurso_fontes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concurso_id INTEGER NOT NULL,
            fonte TEXT NOT NULL,
            referencia TEXT NOT NULL,
            pagina_url TEXT,
            documentos_url TEXT,
            estado_fonte TEXT,
            titulo_origem TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            principal INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT,
            UNIQUE(fonte, referencia),
            FOREIGN KEY(concurso_id)
                REFERENCES concursos(id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_concurso_fontes_concurso "
        "ON concurso_fontes(concurso_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_concurso_fontes_fonte_estado "
        "ON concurso_fontes(fonte, estado_fonte)"
    )


def normalized_entity(value: object) -> str:
    text = normalize(value)
    aliases = {
        "lisboa sru": "lisboa ocidental sru",
        "lisboa ocidental sru em sa": "lisboa ocidental sru",
        "lisboa ocidental sru em s a": "lisboa ocidental sru",
        "camara municipal de lisboa": "municipio de lisboa",
        "c m lisboa": "municipio de lisboa",
    }
    return aliases.get(text, text)


def title_signature(value: object) -> str:
    boilerplate = {
        "concurso", "publico", "internacional", "para", "a", "o", "de",
        "da", "do", "das", "dos", "e", "em", "por", "aquisicao",
        "servicos", "elaboracao", "empreitada", "analise", "projeto",
        "projecto",
    }
    return " ".join(
        token for token in normalize(value).split()
        if token not in boilerplate and len(token) > 1
    )


def title_similarity(left: object, right: object) -> float:
    first = title_signature(left)
    second = title_signature(right)
    if not first or not second:
        return 0.0
    sequence = SequenceMatcher(None, first, second).ratio()
    set_a = set(first.split())
    set_b = set(second.split())
    intersection = set_a & set_b
    jaccard = len(intersection) / max(1, len(set_a | set_b))
    containment = len(intersection) / max(1, min(len(set_a), len(set_b)))
    return max(sequence, (jaccard * 0.55) + (containment * 0.45))


def is_base_link(value: object) -> bool:
    host = urlparse(compact(value)).netloc.casefold()
    return any(priority in host for priority in BASE_PRIORITY_HOSTS)


def find_existing_source(
    connection: sqlite3.Connection,
    source: str,
    reference: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT cf.*, c.link, c.titulo, c.entidade
        FROM concurso_fontes AS cf
        JOIN concursos AS c ON c.id = cf.concurso_id
        WHERE cf.fonte = ? AND cf.referencia = ?
        """,
        (source, reference),
    ).fetchone()


def _exact_url_match(
    connection: sqlite3.Connection,
    procedure: ExternalProcedure,
) -> sqlite3.Row | None:
    urls = {
        compact(value)
        for value in (
            procedure.page_url,
            procedure.documents_url,
            procedure.official_url,
        )
        if compact(value)
    }
    for url in urls:
        rows = connection.execute(
            """
            SELECT DISTINCT c.*
            FROM concursos AS c
            LEFT JOIN concurso_fontes AS cf ON cf.concurso_id = c.id
            WHERE c.link = ?
               OR c.link_pecas = ?
               OR cf.pagina_url = ?
               OR cf.documentos_url = ?
            LIMIT 3
            """,
            (url, url, url, url),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]
    return None


def find_existing_match(
    connection: sqlite3.Connection,
    procedure: ExternalProcedure,
) -> sqlite3.Row | None:
    exact = _exact_url_match(connection, procedure)
    if exact is not None:
        return exact

    candidates = connection.execute(
        """
        SELECT DISTINCT c.*
        FROM concursos AS c
        LEFT JOIN concurso_fontes AS cf ON cf.concurso_id = c.id
        ORDER BY CASE
            WHEN LOWER(COALESCE(c.link, '')) LIKE '%base.gov.pt%' THEN 0
            ELSE 1
        END, c.id DESC
        """
    ).fetchall()

    source_entity = normalized_entity(procedure.entity)
    matches: list[tuple[float, sqlite3.Row]] = []
    for row in candidates:
        candidate_entity = normalized_entity(row["entidade"])
        entity_known = bool(
            source_entity
            and source_entity not in {"por confirmar", "entidade por confirmar"}
        )
        if entity_known and candidate_entity and source_entity != candidate_entity:
            continue
        score = title_similarity(procedure.title, row["titulo"])
        threshold = 0.89 if entity_known else 0.94
        if score >= threshold:
            matches.append((score, row))

    matches.sort(key=lambda item: item[0], reverse=True)
    if not matches:
        return None
    if len(matches) > 1 and matches[0][0] - matches[1][0] < 0.04:
        return None
    return matches[0][1]


def associate_source(
    connection: sqlite3.Connection,
    concurso_id: int,
    procedure: ExternalProcedure,
    *,
    principal: bool,
) -> None:
    metadata = dict(procedure.metadata)
    metadata.update(
        {
            "raw_text": procedure.raw_text,
            "relevance_reason": procedure.relevance_reason,
            "relevance_method": procedure.relevance_method,
            "publication_date": procedure.publication_date or None,
            "publication_date_is_official": bool(procedure.publication_date),
            "deadline": procedure.deadline or None,
            "entity": procedure.entity or None,
            "location": procedure.location or None,
            "official_url": procedure.official_url or None,
        }
    )
    connection.execute(
        """
        INSERT INTO concurso_fontes (
            concurso_id, fonte, referencia, pagina_url, documentos_url,
            estado_fonte, titulo_origem, first_seen_at, last_seen_at,
            principal, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fonte, referencia) DO UPDATE SET
            concurso_id = excluded.concurso_id,
            pagina_url = excluded.pagina_url,
            documentos_url = COALESCE(excluded.documentos_url, concurso_fontes.documentos_url),
            estado_fonte = excluded.estado_fonte,
            titulo_origem = excluded.titulo_origem,
            last_seen_at = excluded.last_seen_at,
            principal = excluded.principal,
            metadata_json = excluded.metadata_json
        """,
        (
            concurso_id,
            procedure.source,
            procedure.reference,
            procedure.page_url,
            procedure.documents_url or None,
            procedure.status,
            procedure.title,
            procedure.first_seen_at,
            procedure.last_seen_at,
            1 if principal else 0,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )


def update_checkpoint_entries(
    procedures: list[ExternalProcedure],
    checkpoint: dict[str, Any],
    current: datetime,
) -> None:
    sources = checkpoint.setdefault("sources", {})
    timestamp = current.isoformat()

    grouped: dict[str, list[ExternalProcedure]] = {}
    for procedure in procedures:
        grouped.setdefault(procedure.source, []).append(procedure)

    for source, source_items in grouped.items():
        source_checkpoint = sources.setdefault(source, {"procedures": {}})
        entries = source_checkpoint.setdefault("procedures", {})
        seen = {item.reference for item in source_items}

        for item in source_items:
            previous = entries.get(item.reference, {})
            first_seen = compact(previous.get("first_seen_at")) or timestamp
            item.first_seen_at = first_seen
            item.last_seen_at = timestamp
            entries[item.reference] = {
                "title": item.title,
                "status": item.status,
                "page_url": item.page_url,
                "documents_url": item.documents_url,
                "publication_date": item.publication_date,
                "deadline": item.deadline,
                "first_seen_at": first_seen,
                "last_seen_at": timestamp,
                "relevant": item.relevant,
                "relevance_reason": item.relevance_reason,
                "relevance_method": item.relevance_method,
                "present_on_latest_page": True,
            }

        for reference, previous in entries.items():
            if reference not in seen:
                previous["present_on_latest_page"] = False


def is_within_window(procedure: ExternalProcedure, today: date) -> bool:
    official = parse_iso_date(procedure.publication_date)
    if official is not None:
        return official >= today - timedelta(days=DAYS_WINDOW)
    if not procedure.allow_new_without_official_date:
        return False
    first_seen = parse_iso_date(procedure.first_seen_at)
    if first_seen is None:
        return True
    return first_seen >= today - timedelta(days=DAYS_WINDOW)


def _new_concurso_link(procedure: ExternalProcedure) -> str:
    return compact(procedure.official_url) or procedure.page_url


def _insert_new(procedure: ExternalProcedure) -> int:
    new_id = guardar_concurso(
        titulo=procedure.title,
        entidade=procedure.entity or "Entidade por confirmar",
        link=_new_concurso_link(procedure),
        data=procedure.publication_date or None,
        data_limite=procedure.deadline or None,
        preco_base=None,
        cpv=None,
        tipo_procedimento=(
            procedure.procedure_type
            or infer_procedure_type(procedure.title, procedure.raw_text)
        ),
        link_pecas=procedure.documents_url or None,
        municipio=procedure.location or None,
        localizacao_contexto=(
            f"Descoberto em {procedure.source_label}. "
            "Quando não existe data oficial, first_seen_at é apenas data de deteção."
        ),
    )
    if new_id:
        return int(new_id)

    connection = abrir_conexao()
    try:
        row = connection.execute(
            "SELECT id FROM concursos WHERE link = ?",
            (_new_concurso_link(procedure),),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Não foi possível guardar {procedure.reference}.")
        return int(row["id"])
    finally:
        connection.close()


def persist_procedure(procedure: ExternalProcedure) -> str:
    criar_base_dados()
    connection = abrir_conexao()
    try:
        ensure_source_table(connection)
        existing_source = find_existing_source(
            connection,
            procedure.source,
            procedure.reference,
        )
        if existing_source is not None:
            principal = not is_base_link(existing_source["link"])
            associate_source(
                connection,
                int(existing_source["concurso_id"]),
                procedure,
                principal=principal,
            )
            connection.commit()
            return "already_known"

        existing_match = find_existing_match(connection, procedure)
        if existing_match is not None:
            principal = not is_base_link(existing_match["link"])
            associate_source(
                connection,
                int(existing_match["id"]),
                procedure,
                principal=False if is_base_link(existing_match["link"]) else principal,
            )
            connection.commit()
            return "associated"
    finally:
        connection.close()

    if procedure.complement_only:
        return "complement_only_unmatched"

    concurso_id = _insert_new(procedure)
    connection = abrir_conexao()
    try:
        ensure_source_table(connection)
        associate_source(connection, concurso_id, procedure, principal=True)
        connection.commit()
    finally:
        connection.close()
    return "inserted"


def update_known_source_state(procedure: ExternalProcedure) -> bool:
    connection = abrir_conexao()
    try:
        ensure_source_table(connection)
        existing = find_existing_source(
            connection,
            procedure.source,
            procedure.reference,
        )
        if existing is None:
            return False
        associate_source(
            connection,
            int(existing["concurso_id"]),
            procedure,
            principal=not is_base_link(existing["link"]),
        )
        connection.commit()
        return True
    finally:
        connection.close()


def process_source_items(
    procedures: list[ExternalProcedure],
    *,
    dry_run: bool,
    checkpoint: dict[str, Any],
) -> tuple[list[ExternalProcedure], SourceReport]:
    source_name = procedures[0].source if procedures else "unknown"
    report = SourceReport(source=source_name, discovered=len(procedures))
    current = now_portugal()

    update_checkpoint_entries(procedures, checkpoint, current)
    selected: list[ExternalProcedure] = []

    for procedure in procedures:
        if not dry_run and update_known_source_state(procedure):
            report.source_state_updated += 1

        active = procedure.status in {"em_curso", "ativo", "aberto"}
        if not active and not procedure.complement_only:
            continue
        report.active += 1

        if not procedure.relevant:
            report.rejected += 1
            continue

        connection = abrir_conexao()
        try:
            ensure_source_table(connection)
            known_source = find_existing_source(
                connection,
                procedure.source,
                procedure.reference,
            ) is not None
            existing_match = find_existing_match(connection, procedure)
        finally:
            connection.close()

        can_complement = existing_match is not None
        if not known_source and not can_complement and not is_within_window(
            procedure,
            current.date(),
        ):
            report.outside_window += 1
            continue

        if procedure.complement_only and not known_source and not can_complement:
            report.complement_only_unmatched += 1
            continue

        report.relevant += 1
        selected.append(procedure)
        if dry_run:
            continue

        result = persist_procedure(procedure)
        if result == "inserted":
            report.inserted += 1
        elif result == "associated":
            report.associated += 1
        elif result == "already_known":
            report.already_known += 1
        elif result == "complement_only_unmatched":
            report.complement_only_unmatched += 1

    return selected, report


def procedure_to_dict(procedure: ExternalProcedure) -> dict[str, Any]:
    return asdict(procedure)
