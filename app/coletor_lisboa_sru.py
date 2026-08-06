"""Adaptador controlado para os procedimentos da Lisboa SRU.

O módulo é independente de ``app.coletor`` e não substitui a recolha da
BASE.gov. Reutiliza apenas a função determinística ``parece_relevante`` e
guarda os resultados na mesma tabela ``concursos``.

A página da Lisboa SRU não publica uma data oficial fiável. ``first_seen_at``
é apenas a data de deteção local; ``last_seen_at`` e ``estado_fonte`` mantêm o
estado observado na fonte. Registos já conhecidos continuam a ser atualizados
mesmo depois da janela inicial de sete dias.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
import tempfile
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag

from app.coletor import parece_relevante
from app.database import abrir_conexao, criar_base_dados, guardar_concurso


SOURCE_NAME = "lisboa_sru"
SOURCE_LABEL = "Lisboa SRU"
SOURCE_URL = "https://www.lisboasru.pt/contratacao-publica"
ENTITY_NAME = "Lisboa Ocidental SRU, EM, S.A."
PORTUGAL_TZ = ZoneInfo("Europe/Lisbon")

DIAS_PADRAO = 7
DIAS_MAXIMOS = 31
DIAS_A_PESQUISAR = max(
    1,
    min(
        int(os.getenv("LISBOA_SRU_DIAS_PESQUISA", str(DIAS_PADRAO))),
        DIAS_MAXIMOS,
    ),
)
TIMEOUT_SEGUNDOS = int(os.getenv("LISBOA_SRU_TIMEOUT_SEGUNDOS", "35"))
MAXIMO_TENTATIVAS = int(os.getenv("LISBOA_SRU_MAX_TENTATIVAS", "3"))
INTERVALO_PEDIDOS = float(os.getenv("LISBOA_SRU_INTERVALO_PEDIDOS", "2.0"))
JITTER_MAXIMO = float(os.getenv("LISBOA_SRU_JITTER_MAXIMO", "0.8"))
CHECKPOINT_PATH = Path(
    os.getenv("LISBOA_SRU_CHECKPOINT", "lisboa_sru_checkpoint.json")
)
USER_AGENT = os.getenv(
    "LISBOA_SRU_USER_AGENT",
    "CNLL-Arquitetura/1.0 (+https://www.lisboasru.pt/contratacao-publica)",
)
OLLAMA_AMBIGUOS = os.getenv("LISBOA_SRU_OLLAMA_AMBIGUOS", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OLLAMA_URL = os.getenv("LISBOA_SRU_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("LISBOA_SRU_OLLAMA_MODEL", "qwen2.5:7b")

ACTIVE_SECTION = "em_concurso"
CONTRACTING_SECTION = "fase_contratacao"
CONCLUDED_SECTION = "concluido"

REFERENCE_RE = re.compile(r"\bSRU\d{7,}[A-Z0-9]*\b", re.I)

STRONG_ACCEPT_PATTERNS = (
    r"\barquitetura\b",
    r"\barquitectura\b",
    r"arquitetura\s+paisagista",
    r"\bpaisagismo\b",
    r"\burbanismo\b",
    r"planeamento\s+urbano",
    r"\bprojeto\s+de\s+execucao\b",
    r"elaboracao\s+de\s+projeto",
    r"projeto\s+e\s+especialidades",
    r"concurso\s+de\s+concecao",
    r"concurso\s+de\s+ideias",
    r"\bparque\s+urbano\b",
    r"\bespaco\s+publico\b",
    r"obras?\s+de\s+urbanizacao.*\bprojeto\b",
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
    r"\bconcecao\b",
    r"concecao\s+construcao",
    r"arquitetura",
    r"arquitectura",
    r"especialidades",
    r"levantamento",
    r"planeamento",
    r"urbanismo",
)


@dataclass(slots=True)
class SourceProcedure:
    title: str
    reference: str
    status: str
    page_url: str
    documents_url: str
    raw_text: str
    first_seen_at: str = ""
    last_seen_at: str = ""
    relevant: bool = False
    relevance_reason: str = ""
    relevance_method: str = "deterministic"


@dataclass(slots=True)
class CollectionReport:
    discovered: int = 0
    active: int = 0
    relevant: int = 0
    rejected: int = 0
    inserted: int = 0
    associated_to_base: int = 0
    already_known: int = 0
    source_state_updated: int = 0
    outside_window: int = 0


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
        return {"version": 2, "source": SOURCE_NAME, "procedures": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"version": 2, "source": SOURCE_NAME, "procedures": {}}
    if not isinstance(payload, dict):
        return {"version": 2, "source": SOURCE_NAME, "procedures": {}}
    payload["version"] = 2
    payload.setdefault("source", SOURCE_NAME)
    payload.setdefault("procedures", {})
    return payload


def save_checkpoint(payload: dict[str, Any], path: Path = CHECKPOINT_PATH) -> None:
    payload["updated_at"] = now_portugal().isoformat()
    atomic_write_json(path, payload)


def wait_controlled(base: float = INTERVALO_PEDIDOS) -> None:
    if base <= 0:
        return
    time.sleep(base + random.uniform(0, max(0.0, JITTER_MAXIMO)))


def fetch_page(session: requests.Session | None = None) -> str:
    own_session = session is None
    client = session or requests.Session()
    client.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.5",
        }
    )
    last_error: Exception | None = None
    try:
        for attempt in range(1, MAXIMO_TENTATIVAS + 1):
            try:
                response = client.get(SOURCE_URL, timeout=TIMEOUT_SEGUNDOS)
                response.raise_for_status()
                if "text/html" not in response.headers.get("content-type", ""):
                    raise RuntimeError("A Lisboa SRU não devolveu uma página HTML.")
                return response.text
            except (requests.RequestException, RuntimeError) as error:
                last_error = error
                if attempt >= MAXIMO_TENTATIVAS:
                    break
                wait_controlled(attempt * INTERVALO_PEDIDOS)
    finally:
        if own_session:
            client.close()
    raise RuntimeError(f"Não foi possível consultar a Lisboa SRU: {last_error}")


def section_from_heading(text: str) -> str | None:
    value = normalize(text)
    if value == "procedimentos em concurso":
        return ACTIVE_SECTION
    if value == "procedimentos em fase de contratacao":
        return CONTRACTING_SECTION
    if value == "procedimentos concluidos":
        return CONCLUDED_SECTION
    return None


def iter_until_next_h2(start: Tag) -> Iterable[Tag]:
    for element in start.next_elements:
        if element is start:
            continue
        if isinstance(element, Tag) and element.name == "h2":
            break
        if isinstance(element, Tag):
            yield element


def nearby_text_and_link(heading: Tag) -> tuple[str, str]:
    fragments: list[str] = []
    documents_url = ""
    visited: set[int] = set()
    for element in iter_until_next_h2(heading):
        identity = id(element)
        if identity in visited:
            continue
        visited.add(identity)
        text = compact(element.get_text(" ", strip=True))
        if text and text not in fragments:
            fragments.append(text)
        if element.name == "a":
            href = compact(element.get("href"))
            label = normalize(text)
            if href and (
                "pecas do procedimento" in label
                or "sharepoint" in href.casefold()
            ):
                documents_url = urljoin(SOURCE_URL, href)
        if len(" ".join(fragments)) > 2200:
            break
    return compact(" ".join(fragments)), documents_url


def parse_page(html: str) -> list[SourceProcedure]:
    soup = BeautifulSoup(html, "html.parser")
    procedures: list[SourceProcedure] = []
    current_section: str | None = None
    seen_references: set[str] = set()

    for heading in soup.find_all("h2"):
        title = compact(heading.get_text(" ", strip=True))
        section = section_from_heading(title)
        if section is not None:
            current_section = section
            continue
        if current_section is None:
            continue

        nearby, documents_url = nearby_text_and_link(heading)
        reference_match = REFERENCE_RE.search(f"{title} {nearby}")
        if not reference_match:
            continue
        reference = reference_match.group(0).upper()
        if reference in seen_references:
            continue
        seen_references.add(reference)

        title_without_reference = compact(
            REFERENCE_RE.sub("", title).strip(" -–—")
        ) or title

        procedures.append(
            SourceProcedure(
                title=title_without_reference,
                reference=reference,
                status=current_section,
                page_url=f"{SOURCE_URL}#{reference}",
                documents_url=documents_url,
                raw_text=compact(f"{title} {nearby}"),
            )
        )
    return procedures


def infer_procedure_type(title: str) -> str:
    text = normalize(title)
    if "concurso publico internacional" in text:
        return "Concurso Público Internacional"
    if "concurso de ideias" in text:
        return "Concurso de Ideias"
    if "concurso de concecao" in text or "concurso concecao" in text:
        return "Concurso de Conceção"
    if "concurso publico" in text:
        return "Concurso Público"
    if "aquisicao de servicos" in text:
        return "Aquisição de Serviços"
    if "empreitada" in text:
        return "Empreitada"
    return "Procedimento de contratação pública"


def as_base_filter_payload(procedure: SourceProcedure) -> dict[str, Any]:
    title = procedure.title
    normalized = normalize(f"{title} {procedure.raw_text}")
    contract_type = (
        "Aquisição de serviços"
        if any(re.search(pattern, normalized) for pattern in PROJECT_COMPONENT_PATTERNS)
        else "Empreitada"
        if "empreitada" in normalized
        else ""
    )
    return {
        "contractDesignation": title,
        "description": procedure.raw_text,
        "contractingEntity": ENTITY_NAME,
        "contractingProcedureType": infer_procedure_type(title),
        "contractType": contract_type,
        "modelType": SOURCE_LABEL,
        "type": "Publicação oficial da entidade adjudicante",
    }


def _ollama_ambiguous(procedure: SourceProcedure) -> bool | None:
    if not OLLAMA_AMBIGUOS:
        return None
    prompt = (
        "Responde apenas ACEITAR ou REJEITAR. O procedimento deve ser aceite "
        "apenas quando inclui serviços de arquitetura, arquitetura paisagista, "
        "urbanismo, planeamento, projeto, especialidades, espaço público ou "
        "levantamentos com componente arquitetónica. Empreitadas puras, "
        "fornecimentos e manutenção devem ser rejeitados.\n\n"
        f"Título: {procedure.title}\nContexto: {procedure.raw_text[:3000]}"
    )
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=20,
        )
        response.raise_for_status()
        answer = normalize(response.json().get("response"))
    except Exception:
        return None
    if answer.startswith("aceitar"):
        return True
    if answer.startswith("rejeitar"):
        return False
    return None


def evaluate_relevance(procedure: SourceProcedure) -> tuple[bool, str]:
    text = normalize(f"{procedure.title} {procedure.raw_text}")

    negative = next(
        (pattern for pattern in NEGATIVE_PATTERNS if re.search(pattern, text)),
        None,
    )
    if negative:
        procedure.relevance_method = "deterministic_negative"
        return False, "Rejeitado por categoria explicitamente irrelevante."

    has_project_component = any(
        re.search(pattern, text) for pattern in PROJECT_COMPONENT_PATTERNS
    )
    if "empreitada" in text and not has_project_component:
        procedure.relevance_method = "deterministic_pure_works"
        return False, "Rejeitado por ser uma empreitada sem elaboração de projeto."

    if any(re.search(pattern, text) for pattern in STRONG_ACCEPT_PATTERNS):
        procedure.relevance_method = "deterministic_positive"
        return True, "Aceite por regra arquitetónica explícita da Lisboa SRU."

    payload = as_base_filter_payload(procedure)
    if parece_relevante(payload):
        procedure.relevance_method = "base_filter"
        return True, "Aceite pelas regras de pertinência do coletor BASE.gov."

    ollama = _ollama_ambiguous(procedure)
    if ollama is not None:
        procedure.relevance_method = "ollama_support"
        return (
            ollama,
            "Decisão auxiliar de Ollama para um título ambíguo; o adaptador continua funcional sem Ollama.",
        )

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
        "CREATE INDEX IF NOT EXISTS idx_concurso_fontes_concurso ON concurso_fontes(concurso_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_concurso_fontes_fonte_estado ON concurso_fontes(fonte, estado_fonte)"
    )


def normalized_entity(value: object) -> str:
    text = normalize(value)
    aliases = {
        "lisboa sru": "lisboa ocidental sru",
        "lisboa ocidental sru em sa": "lisboa ocidental sru",
        "lisboa ocidental sru em s a": "lisboa ocidental sru",
        "lisboa ocidental sru sociedade de reabilitacao urbana em sa": "lisboa ocidental sru",
        "lisboa ocidental sru sociedade de reabilitacao urbana em s a": "lisboa ocidental sru",
    }
    return aliases.get(text, text)


def title_signature(value: object) -> str:
    boilerplate = {
        "concurso", "publico", "internacional", "para", "a", "o", "de",
        "da", "do", "das", "dos", "e", "em", "por", "aquisicao",
        "servicos", "elaboracao", "empreitada",
    }
    return " ".join(
        token for token in normalize(value).split()
        if token not in boilerplate and len(token) > 1
    )


def title_similarity(left: object, right: object) -> float:
    a = title_signature(left)
    b = title_signature(right)
    if not a or not b:
        return 0.0
    sequence = SequenceMatcher(None, a, b).ratio()
    set_a = set(a.split())
    set_b = set(b.split())
    intersection = set_a & set_b
    jaccard = len(intersection) / max(1, len(set_a | set_b))
    containment = len(intersection) / max(1, min(len(set_a), len(set_b)))
    return max(sequence, (jaccard * 0.55) + (containment * 0.45))


def find_existing_source(
    connection: sqlite3.Connection,
    reference: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT cf.*, c.link, c.titulo, c.entidade
        FROM concurso_fontes AS cf
        JOIN concursos AS c ON c.id = cf.concurso_id
        WHERE cf.fonte = ? AND cf.referencia = ?
        """,
        (SOURCE_NAME, reference),
    ).fetchone()


def find_base_match(
    connection: sqlite3.Connection,
    procedure: SourceProcedure,
) -> sqlite3.Row | None:
    if procedure.documents_url:
        exact = connection.execute(
            """
            SELECT c.*
            FROM concursos AS c
            LEFT JOIN concurso_fontes AS cf ON cf.concurso_id = c.id
            WHERE c.link_pecas = ? OR cf.documentos_url = ?
            LIMIT 2
            """,
            (procedure.documents_url, procedure.documents_url),
        ).fetchall()
        if len(exact) == 1:
            return exact[0]

    candidates = connection.execute(
        """
        SELECT DISTINCT c.*
        FROM concursos AS c
        LEFT JOIN concurso_fontes AS cf ON cf.concurso_id = c.id
        WHERE LOWER(COALESCE(c.link, '')) LIKE '%base.gov.pt%'
           OR cf.fonte = 'base_gov'
        """
    ).fetchall()

    source_entity = normalized_entity(ENTITY_NAME)
    matches: list[tuple[float, sqlite3.Row]] = []
    for row in candidates:
        entity = normalized_entity(row["entidade"])
        if entity and source_entity and entity != source_entity:
            continue
        score = title_similarity(procedure.title, row["titulo"])
        if score >= 0.90:
            matches.append((score, row))

    matches.sort(key=lambda item: item[0], reverse=True)
    if not matches:
        return None
    if len(matches) > 1 and matches[0][0] - matches[1][0] < 0.05:
        return None
    return matches[0][1]


def associate_source(
    connection: sqlite3.Connection,
    concurso_id: int,
    procedure: SourceProcedure,
    *,
    principal: bool,
) -> None:
    metadata = {
        "raw_text": procedure.raw_text,
        "relevance_reason": procedure.relevance_reason,
        "relevance_method": procedure.relevance_method,
        "publication_date_is_official": False,
    }
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
            SOURCE_NAME,
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


def update_known_source_state(procedure: SourceProcedure) -> bool:
    connection = abrir_conexao()
    try:
        ensure_source_table(connection)
        existing = find_existing_source(connection, procedure.reference)
        if existing is None:
            return False
        principal = "base.gov.pt" not in str(existing["link"] or "").casefold()
        associate_source(
            connection,
            int(existing["concurso_id"]),
            procedure,
            principal=principal,
        )
        connection.commit()
        return True
    finally:
        connection.close()


def insert_or_associate(procedure: SourceProcedure) -> str:
    criar_base_dados()
    connection = abrir_conexao()
    try:
        ensure_source_table(connection)
        existing_source = find_existing_source(connection, procedure.reference)
        if existing_source is not None:
            principal = "base.gov.pt" not in str(existing_source["link"] or "").casefold()
            associate_source(
                connection,
                int(existing_source["concurso_id"]),
                procedure,
                principal=principal,
            )
            connection.commit()
            return "already_known"

        base_match = find_base_match(connection, procedure)
        if base_match is not None:
            associate_source(
                connection,
                int(base_match["id"]),
                procedure,
                principal=False,
            )
            connection.commit()
            return "associated_to_base"
    finally:
        connection.close()

    new_id = guardar_concurso(
        titulo=procedure.title,
        entidade=ENTITY_NAME,
        link=procedure.page_url,
        data=None,
        data_limite=None,
        preco_base=None,
        cpv=None,
        tipo_procedimento=infer_procedure_type(procedure.title),
        link_pecas=procedure.documents_url or None,
        municipio="Lisboa",
        localizacao_contexto=(
            "Publicado pela Lisboa SRU; first_seen_at é data de deteção e não publicação oficial."
        ),
    )
    if not new_id:
        connection = abrir_conexao()
        try:
            row = connection.execute(
                "SELECT id FROM concursos WHERE link = ?",
                (procedure.page_url,),
            ).fetchone()
            if row is None:
                raise RuntimeError(f"Não foi possível guardar {procedure.reference}.")
            new_id = int(row["id"])
        finally:
            connection.close()

    connection = abrir_conexao()
    try:
        ensure_source_table(connection)
        associate_source(connection, int(new_id), procedure, principal=True)
        connection.commit()
    finally:
        connection.close()
    return "inserted"


def update_checkpoint_entries(
    procedures: list[SourceProcedure],
    checkpoint: dict[str, Any],
    now: datetime,
) -> None:
    entries = checkpoint.setdefault("procedures", {})
    timestamp = now.isoformat()
    seen = {procedure.reference for procedure in procedures}

    for procedure in procedures:
        previous = entries.get(procedure.reference, {})
        first_seen = compact(previous.get("first_seen_at")) or timestamp
        procedure.first_seen_at = first_seen
        procedure.last_seen_at = timestamp
        entries[procedure.reference] = {
            "title": procedure.title,
            "status": procedure.status,
            "page_url": procedure.page_url,
            "documents_url": procedure.documents_url,
            "first_seen_at": first_seen,
            "last_seen_at": timestamp,
            "relevant": procedure.relevant,
            "relevance_reason": procedure.relevance_reason,
            "relevance_method": procedure.relevance_method,
        }

    for reference, previous in entries.items():
        if reference not in seen:
            previous["present_on_latest_page"] = False
        else:
            previous["present_on_latest_page"] = True


def within_window(procedure: SourceProcedure, today: date) -> bool:
    try:
        first_seen = datetime.fromisoformat(procedure.first_seen_at).date()
    except (TypeError, ValueError):
        return True
    return first_seen >= today - timedelta(days=DIAS_A_PESQUISAR)


def collect(
    *,
    html: str | None = None,
    dry_run: bool = False,
    checkpoint_path: Path = CHECKPOINT_PATH,
) -> tuple[list[SourceProcedure], CollectionReport]:
    page = html if html is not None else fetch_page()
    procedures = parse_page(page)
    report = CollectionReport(discovered=len(procedures))
    checkpoint = load_checkpoint(checkpoint_path)
    current = now_portugal()

    for procedure in procedures:
        procedure.relevant, procedure.relevance_reason = evaluate_relevance(procedure)
    update_checkpoint_entries(procedures, checkpoint, current)

    selected: list[SourceProcedure] = []
    for procedure in procedures:
        if not dry_run and update_known_source_state(procedure):
            report.source_state_updated += 1

        if procedure.status != ACTIVE_SECTION:
            continue
        report.active += 1
        if not procedure.relevant:
            report.rejected += 1
            continue

        existing_known = False
        if not dry_run:
            connection = abrir_conexao()
            try:
                ensure_source_table(connection)
                existing_known = find_existing_source(connection, procedure.reference) is not None
            finally:
                connection.close()

        if not existing_known and not within_window(procedure, current.date()):
            report.outside_window += 1
            continue

        report.relevant += 1
        selected.append(procedure)

        if dry_run:
            continue
        result = insert_or_associate(procedure)
        if result == "inserted":
            report.inserted += 1
        elif result == "associated_to_base":
            report.associated_to_base += 1
        else:
            report.already_known += 1

    if not dry_run:
        save_checkpoint(checkpoint, checkpoint_path)
    return selected, report


def print_report(
    procedures: list[SourceProcedure],
    report: CollectionReport,
    *,
    dry_run: bool,
) -> None:
    print("LISBOA SRU — RECOLHA CONTROLADA")
    print(f"- página: {SOURCE_URL}")
    print(f"- janela para novos registos: últimos {DIAS_A_PESQUISAR} dias por first_seen_at")
    print("- registos já conhecidos: acompanhados enquanto existirem na fonte")
    print("- secção importada: Procedimentos em concurso")
    print("- filtro principal: determinístico; Ollama é opcional e não obrigatório")
    print("- prioridade em duplicados: BASE.gov")
    print(f"- modo: {'simulação' if dry_run else 'gravação'}")
    print(f"- procedimentos descobertos: {report.discovered}")
    print(f"- procedimentos em concurso: {report.active}")
    print(f"- relevantes: {report.relevant}")
    print(f"- rejeitados pelo filtro: {report.rejected}")
    print(f"- fora da janela: {report.outside_window}")
    if not dry_run:
        print(f"- novos guardados: {report.inserted}")
        print(f"- associados a registos BASE.gov: {report.associated_to_base}")
        print(f"- já conhecidos: {report.already_known}")
        print(f"- estados de fonte atualizados: {report.source_state_updated}")
    print("- concursos selecionados:")
    for item in procedures:
        print(f"  · {item.reference} — {item.title}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recolhe concursos relevantes publicados pela Lisboa SRU."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Consulta e filtra sem alterar a base de dados ou o checkpoint.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Mostra também o resultado normalizado em JSON.",
    )
    args = parser.parse_args()
    selected, report = collect(dry_run=args.dry_run)
    print_report(selected, report, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(
            {
                "procedures": [asdict(item) for item in selected],
                "report": asdict(report),
            },
            ensure_ascii=False,
            indent=2,
        ))


if __name__ == "__main__":
    main()
