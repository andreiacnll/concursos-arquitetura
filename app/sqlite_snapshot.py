from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing, suppress
from pathlib import Path
from threading import Lock



SNAPSHOT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app_state_snapshots (
    snapshot_key TEXT PRIMARY KEY,
    payload_gzip BYTEA NOT NULL,
    sha256 TEXT NOT NULL,
    sqlite_size BIGINT NOT NULL,
    gzip_size BIGINT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

SNAPSHOT_UPSERT_SQL = """
INSERT INTO app_state_snapshots (
    snapshot_key,
    payload_gzip,
    sha256,
    sqlite_size,
    gzip_size,
    metadata,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
ON CONFLICT (snapshot_key)
DO UPDATE SET
    payload_gzip = EXCLUDED.payload_gzip,
    sha256 = EXCLUDED.sha256,
    sqlite_size = EXCLUDED.sqlite_size,
    gzip_size = EXCLUDED.gzip_size,
    metadata = EXCLUDED.metadata,
    updated_at = CURRENT_TIMESTAMP
"""

SNAPSHOT_SECURITY_SQL = (
    (
        "ALTER TABLE public.app_state_snapshots "
        "ENABLE ROW LEVEL SECURITY"
    ),
    (
        "REVOKE ALL ON TABLE public.app_state_snapshots "
        "FROM PUBLIC, anon, authenticated"
    ),
)


def _garantir_tabela_snapshot(conn) -> None:
    conn.execute(SNAPSHOT_TABLE_SQL)

    roles = {
        linha[0]
        for linha in conn.execute(
            "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
            (["anon", "authenticated"],),
        ).fetchall()
    }
    comandos = [SNAPSHOT_SECURITY_SQL[0]]
    if {"anon", "authenticated"}.issubset(roles):
        comandos.append(SNAPSHOT_SECURITY_SQL[1])

    for comando in comandos:
        conn.execute(comando)


TABLES_TO_COUNT = (
    "concursos",
    "concurso_fontes",
    "analises",
    "analise_versoes",
    "analise_jobs",
    "companies",
    "company_members",
    "company_profiles",
    "company_knowledge_memory",
    "company_interview_sessions",
    "company_interview_questions",
    "company_interview_answers",
    "company_source_raw_texts",
    "member_profiles",
    "favoritos",
    "alertas",
    "alerta_subscricoes",
    "timeline_eventos",
)

_TRUE_VALUES = {"1", "true", "sim", "yes", "on"}
_state_lock = Lock()
_upload_lock = Lock()
_generation = 0
_synced_generation = 0



def _psycopg_modulos():
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise RuntimeError(
            "CNLL_SQLITE_SNAPSHOT_ENABLED está ativo, "
            "mas psycopg[binary] não está instalado."
        ) from exc

    return psycopg, Jsonb

def _log(message: str) -> None:
    print(f"[sqlite-snapshot] {message}", flush=True)


def snapshot_ativo() -> bool:
    return (
        os.getenv("CNLL_SQLITE_SNAPSHOT_ENABLED", "0")
        .strip()
        .lower()
        in _TRUE_VALUES
    )


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        raise RuntimeError(
            "CNLL_SQLITE_SNAPSHOT_ENABLED está ativo, "
            "mas DATABASE_URL não está configurada."
        )

    return database_url


def _snapshot_key() -> str:
    return (
        os.getenv("CNLL_SQLITE_SNAPSHOT_KEY", "cnll-main").strip()
        or "cnll-main"
    )


def _intervalo_segundos() -> int:
    valor = os.getenv("CNLL_SQLITE_SNAPSHOT_INTERVAL_SECONDS", "15")

    try:
        intervalo = int(valor)
    except ValueError:
        intervalo = 15

    return max(5, intervalo)


def marcar_snapshot_pendente() -> None:
    global _generation

    if not snapshot_ativo():
        return

    with _state_lock:
        _generation += 1


def _estado_geracoes() -> tuple[int, int]:
    with _state_lock:
        return _generation, _synced_generation


def _marcar_geracao_sincronizada(geracao: int) -> None:
    global _synced_generation

    with _state_lock:
        _synced_generation = max(_synced_generation, geracao)


def snapshot_pendente() -> bool:
    geracao, sincronizada = _estado_geracoes()
    return geracao > sincronizada


class SnapshotConnection(sqlite3.Connection):
    """Ligação SQLite que assinala commits para sincronização posterior."""

    def commit(self):
        resultado = super().commit()
        marcar_snapshot_pendente()
        return resultado

    def __exit__(self, exc_type, exc_value, traceback):
        resultado = super().__exit__(exc_type, exc_value, traceback)

        if exc_type is None:
            marcar_snapshot_pendente()

        return resultado


def _verificar_integridade(caminho: Path) -> None:
    with closing(sqlite3.connect(caminho)) as conn:
        resultado = conn.execute("PRAGMA integrity_check").fetchone()

    if not resultado or resultado[0] != "ok":
        raise RuntimeError(
            f"Falha no integrity_check de {caminho.name}: {resultado!r}"
        )


def _obter_contagens(
    caminho: Path,
    tabelas_alvo: tuple[str, ...] | None = None,
) -> dict[str, int]:
    contagens: dict[str, int] = {}
    tabelas_para_contar = tabelas_alvo or TABLES_TO_COUNT

    with closing(sqlite3.connect(caminho)) as conn:
        tabelas = {
            linha[0]
            for linha in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

        for tabela in tabelas_para_contar:
            if tabela not in tabelas:
                contagens[tabela] = -1
                continue

            contagens[tabela] = int(
                conn.execute(
                    f'SELECT COUNT(*) FROM "{tabela}"'
                ).fetchone()[0]
            )

    return contagens


def _criar_copia_consistente(origem: Path, destino: Path) -> None:
    with closing(sqlite3.connect(origem, timeout=30)) as source:
        with closing(sqlite3.connect(destino)) as target:
            source.backup(target)

    _verificar_integridade(destino)


def _hash_ficheiro(caminho: Path) -> str:
    digest = hashlib.sha256()

    with caminho.open("rb") as ficheiro:
        for bloco in iter(lambda: ficheiro.read(1024 * 1024), b""):
            digest.update(bloco)

    return digest.hexdigest()


def _normalizar_contagens(valor) -> dict[str, int]:
    if not isinstance(valor, dict):
        return {}

    return {
        str(chave): int(contagem)
        for chave, contagem in valor.items()
    }


def _tabelas_para_validar_snapshot(
    contagens_esperadas: dict[str, int],
) -> tuple[str, ...]:
    """Conta tabelas atuais e todas as tabelas presentes na metadata.

    Snapshots antigos podem ter metadata com menos tabelas do que a versão
    atual da aplicação conhece. Isso não torna o snapshot inválido: a
    validação forte é comparar todas as contagens declaradas pela metadata.
    """

    return tuple(
        dict.fromkeys(
            [
                *TABLES_TO_COUNT,
                *contagens_esperadas.keys(),
            ]
        )
    )


def _validar_contagens_snapshot(
    contagens_reais: dict[str, int],
    contagens_esperadas: dict[str, int],
) -> None:
    if not contagens_esperadas:
        return

    divergencias = {
        tabela: {
            "metadata": esperada,
            "snapshot": contagens_reais.get(tabela),
        }
        for tabela, esperada in contagens_esperadas.items()
        if contagens_reais.get(tabela) != esperada
    }

    if divergencias:
        detalhe = json.dumps(
            divergencias,
            ensure_ascii=False,
            sort_keys=True,
        )
        raise RuntimeError(
            "As contagens do snapshot remoto não correspondem "
            f"aos metadados guardados: {detalhe}"
        )


def restaurar_snapshot_se_ativo(db_path: Path | str) -> bool:
    """Restaura o snapshot validado antes de a API abrir o SQLite."""

    if not snapshot_ativo():
        return False

    caminho_db = Path(db_path)
    caminho_db.parent.mkdir(parents=True, exist_ok=True)
    chave = _snapshot_key()

    _log(f"A obter snapshot remoto '{chave}'...")

    psycopg, _ = _psycopg_modulos()
    with psycopg.connect(_database_url()) as conn:
        _garantir_tabela_snapshot(conn)
        conn.commit()

        linha = conn.execute(
            """
            SELECT payload_gzip, sha256, sqlite_size, metadata
            FROM app_state_snapshots
            WHERE snapshot_key = %s
            """,
            (chave,),
        ).fetchone()

    if linha is None:
        raise RuntimeError(
            f"Não existe snapshot remoto com a chave '{chave}'. "
            "O arranque foi cancelado para evitar uma base vazia."
        )

    payload_gzip = bytes(linha[0])
    sha256_esperado = str(linha[1])
    tamanho_esperado = int(linha[2])
    metadata = linha[3] or {}
    contagens_esperadas = _normalizar_contagens(
        metadata.get("counts", {})
        if isinstance(metadata, dict)
        else {}
    )

    dados_sqlite = gzip.decompress(payload_gzip)

    if len(dados_sqlite) != tamanho_esperado:
        raise RuntimeError(
            "O tamanho do snapshot descomprimido não corresponde "
            "ao valor guardado."
        )

    sha256_real = hashlib.sha256(dados_sqlite).hexdigest()

    if sha256_real != sha256_esperado:
        raise RuntimeError(
            "O hash do snapshot remoto é inválido. "
            "A base existente não foi substituída."
        )

    caminho_tmp = caminho_db.with_name(
        f".{caminho_db.name}.restore.tmp"
    )
    caminho_backup = caminho_db.with_name(
        f".{caminho_db.name}.before_restore"
    )

    caminho_tmp.unlink(missing_ok=True)
    caminho_backup.unlink(missing_ok=True)

    try:
        with caminho_tmp.open("wb") as ficheiro:
            ficheiro.write(dados_sqlite)
            ficheiro.flush()
            os.fsync(ficheiro.fileno())

        _verificar_integridade(caminho_tmp)
        contagens_reais = _obter_contagens(
            caminho_tmp,
            _tabelas_para_validar_snapshot(contagens_esperadas),
        )
        _validar_contagens_snapshot(
            contagens_reais,
            contagens_esperadas,
        )

        if (
            caminho_db.exists()
            and _hash_ficheiro(caminho_db) == sha256_esperado
        ):
            caminho_tmp.unlink(missing_ok=True)
            _log("A base local já corresponde ao snapshot remoto.")
            return False

        for sufixo in ("-wal", "-shm"):
            Path(f"{caminho_db}{sufixo}").unlink(missing_ok=True)

        if caminho_db.exists():
            os.replace(caminho_db, caminho_backup)

        try:
            os.replace(caminho_tmp, caminho_db)
            _verificar_integridade(caminho_db)
        except Exception:
            caminho_db.unlink(missing_ok=True)

            if caminho_backup.exists():
                os.replace(caminho_backup, caminho_db)

            raise
        else:
            caminho_backup.unlink(missing_ok=True)

    finally:
        caminho_tmp.unlink(missing_ok=True)

    _log(
        "Snapshot restaurado e validado: "
        f"{contagens_reais.get('concursos', '?')} concursos, "
        f"{contagens_reais.get('analises', '?')} análises."
    )
    return True


def sincronizar_snapshot(db_path: Path | str) -> bool:
    """Envia uma cópia SQLite consistente para o Supabase."""

    if not snapshot_ativo():
        return False

    caminho_db = Path(db_path)

    if not caminho_db.is_file():
        raise RuntimeError(f"Base SQLite não encontrada: {caminho_db}")

    with _upload_lock:
        geracao_inicio, geracao_sincronizada = _estado_geracoes()

        if geracao_inicio <= geracao_sincronizada:
            return False

        descritor, nome_tmp = tempfile.mkstemp(
            prefix="cnll_snapshot_",
            suffix=".db",
            dir=caminho_db.parent,
        )
        os.close(descritor)
        caminho_tmp = Path(nome_tmp)

        try:
            caminho_tmp.unlink(missing_ok=True)
            _criar_copia_consistente(caminho_db, caminho_tmp)

            dados_sqlite = caminho_tmp.read_bytes()
            payload_gzip = gzip.compress(
                dados_sqlite,
                compresslevel=9,
                mtime=0,
            )
            sha256 = hashlib.sha256(dados_sqlite).hexdigest()
            contagens = _obter_contagens(caminho_tmp)
            metadata = {
                "format": "sqlite3+gzip",
                "source_filename": caminho_db.name,
                "counts": contagens,
            }

            psycopg, Jsonb = _psycopg_modulos()
            with psycopg.connect(_database_url()) as conn:
                with conn.transaction():
                    _garantir_tabela_snapshot(conn)
                    conn.execute(
                        SNAPSHOT_UPSERT_SQL,
                        (
                            _snapshot_key(),
                            payload_gzip,
                            sha256,
                            len(dados_sqlite),
                            len(payload_gzip),
                            Jsonb(metadata),
                        ),
                    )

                confirmacao = conn.execute(
                    """
                    SELECT sha256, sqlite_size, gzip_size
                    FROM app_state_snapshots
                    WHERE snapshot_key = %s
                    """,
                    (_snapshot_key(),),
                ).fetchone()

            esperado = (
                sha256,
                len(dados_sqlite),
                len(payload_gzip),
            )

            if confirmacao is None or tuple(confirmacao) != esperado:
                raise RuntimeError(
                    "O Supabase não confirmou corretamente "
                    "o snapshot enviado."
                )

            _marcar_geracao_sincronizada(geracao_inicio)
            _log(
                "Snapshot sincronizado: "
                f"{contagens.get('concursos', '?')} concursos, "
                f"{contagens.get('analises', '?')} análises."
            )
            return True

        finally:
            caminho_tmp.unlink(missing_ok=True)


async def executar_sincronizador_snapshot(
    db_path: Path | str,
) -> None:
    """Sincroniza alterações em segundo plano, com repetição em caso de erro."""

    if not snapshot_ativo():
        return

    intervalo = _intervalo_segundos()
    _log(f"Sincronização automática ativa a cada {intervalo}s.")

    while True:
        await asyncio.sleep(intervalo)

        if not snapshot_pendente():
            continue

        try:
            await asyncio.to_thread(sincronizar_snapshot, db_path)
        except asyncio.CancelledError:
            raise
        except Exception as erro:
            _log(
                "Falha ao sincronizar; será tentado novamente: "
                f"{erro}"
            )


async def encerrar_sincronizador_snapshot(
    tarefa: asyncio.Task | None,
    db_path: Path | str,
) -> None:
    """Para a tarefa e tenta guardar alterações pendentes no encerramento."""

    if tarefa is not None and not tarefa.done():
        tarefa.cancel()

        with suppress(asyncio.CancelledError):
            await tarefa

    if not snapshot_ativo() or not snapshot_pendente():
        return

    try:
        await asyncio.to_thread(sincronizar_snapshot, db_path)
    except Exception as erro:
        _log(f"Falha na sincronização final: {erro}")
