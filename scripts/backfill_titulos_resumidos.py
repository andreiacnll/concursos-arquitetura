from __future__ import annotations

import argparse
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import DB_PATH
from app.titulo_resumido import gerar_titulo_resumido


TitleGenerator = Callable[..., str]


def _has_column(connection: sqlite3.Connection, column: str) -> bool:
    return any(row[1] == column for row in connection.execute("PRAGMA table_info(concursos)"))


def executar_backfill(
    connection: sqlite3.Connection,
    *,
    commit: bool = False,
    limit: int | None = None,
    after_id: int | None = None,
    concurso_id: int | None = None,
    generator: TitleGenerator = gerar_titulo_resumido,
) -> list[dict[str, Any]]:
    """Planeia ou grava apenas titulos resumidos vazios, por ordem de ID."""
    has_summary = _has_column(connection, "titulo_resumido")
    if commit and not has_summary:
        raise RuntimeError("A coluna titulo_resumido ainda nao existe; execute a migracao primeiro.")

    summary_select = "titulo_resumido" if has_summary else "NULL AS titulo_resumido"
    conditions = ["1 = 1"]
    params: list[Any] = []
    if has_summary:
        conditions.append("(titulo_resumido IS NULL OR TRIM(titulo_resumido) = '')")
    if concurso_id is not None:
        conditions.append("id = ?")
        params.append(concurso_id)
    if after_id is not None:
        conditions.append("id > ?")
        params.append(after_id)

    query = f"""
        SELECT id, titulo, entidade, municipio, freguesia, morada,
               localizacao_contexto, {summary_select}
        FROM concursos
        WHERE {' AND '.join(conditions)}
        ORDER BY id ASC
    """
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    rows = connection.execute(query, params).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        location = " ".join(
            str(value).strip()
            for value in (row[5], row[4], row[3], row[6])
            if str(value or "").strip()
        )
        summary = generator(
            row[1],
            entidade=row[2],
            localizacao=location,
        )
        result = {
            "id": int(row[0]),
            "titulo": row[1],
            "titulo_resumido": summary,
            "gravado": False,
        }
        if commit and summary:
            cursor = connection.execute(
                """
                UPDATE concursos
                SET titulo_resumido = ?
                WHERE id = ?
                  AND (titulo_resumido IS NULL OR TRIM(titulo_resumido) = '')
                """,
                (summary, row[0]),
            )
            result["gravado"] = cursor.rowcount == 1
        results.append(result)

    if commit:
        connection.commit()
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill retomavel de titulo_resumido; dry-run por defeito.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Mostra resultados sem escrever.")
    parser.add_argument("--commit", action="store_true", help="Grava os titulos planeados.")
    parser.add_argument("--limit", type=int, help="Numero maximo de concursos a processar.")
    parser.add_argument("--after-id", type=int, help="Processa apenas IDs superiores a este valor.")
    parser.add_argument("--id", dest="concurso_id", type=int, help="Processa apenas um concurso.")
    parser.add_argument("--db-path", type=Path, default=DB_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit deve ser superior a zero")
    if args.commit and args.dry_run:
        parser.error("Use apenas --commit ou --dry-run")
    return args


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    args = parse_args()
    connection = sqlite3.connect(args.db_path)
    try:
        results = executar_backfill(
            connection,
            commit=args.commit,
            limit=args.limit,
            after_id=args.after_id,
            concurso_id=args.concurso_id,
        )
    finally:
        connection.close()

    mode = "COMMIT" if args.commit else "DRY-RUN"
    print(f"{mode}: {len(results)} concurso(s)")
    for result in results:
        action = "gravado" if result["gravado"] else "planeado"
        print(f"[{result['id']}] {result['titulo_resumido']} ({action})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
