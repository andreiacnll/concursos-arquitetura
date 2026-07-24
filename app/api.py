from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "concursos.db"
CHECKPOINT_PATH = BASE_DIR / "concursos_recolhidos.json"


app = FastAPI(
    title="ArquiConcursos API",
    description=(
        "API para consulta de concursos públicos "
        "relacionados com arquitetura."
    ),
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def obter_conexao() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise RuntimeError(
            f"Base de dados não encontrada: {DB_PATH}"
        )

    conexao = sqlite3.connect(DB_PATH)
    conexao.row_factory = sqlite3.Row

    return conexao


def linha_para_dicionario(
    linha: sqlite3.Row,
) -> dict[str, Any]:
    return dict(linha)


@app.get("/")
def inicio() -> dict[str, str]:
    return {
        "nome": "ArquiConcursos API",
        "estado": "online",
        "documentacao": "/docs",
    }



@app.get("/concursos/{concurso_id}/timeline")
def obter_timeline_concurso(
    concurso_id: int,
) -> list[dict[str, Any]]:

    with closing(obter_conexao()) as conexao:

        eventos = conexao.execute(
            """
            SELECT
                tipo,
                titulo,
                data,
                origem
            FROM timeline_eventos
            WHERE concurso_id = ?
            ORDER BY data
            """,
            (concurso_id,),
        ).fetchall()


    return [
        dict(evento)
        for evento in eventos
    ]



@app.get("/health")
def healthcheck() -> dict[str, str]:
    try:
        with closing(obter_conexao()) as conexao:
            conexao.execute("SELECT 1").fetchone()

    except Exception as erro:
        raise HTTPException(
            status_code=503,
            detail=f"Base de dados indisponível: {erro}",
        ) from erro

    return {
        "status": "ok",
        "database": "ok",
    }



DATA_PUBLICACAO_SQL = """
CASE
    WHEN data IS NOT NULL
         AND LENGTH(TRIM(data)) = 10
    THEN
        SUBSTR(TRIM(data), 7, 4)
        || '-'
        || SUBSTR(TRIM(data), 4, 2)
        || '-'
        || SUBSTR(TRIM(data), 1, 2)
    ELSE NULL
END
"""


DATA_FIM_SQL = f"""
CASE
    WHEN data_limite IS NOT NULL
         AND TRIM(data_limite) != ''
         AND CAST(data_limite AS INTEGER) > 0
    THEN DATE(
        {DATA_PUBLICACAO_SQL},
        '+'
        || CAST(data_limite AS INTEGER)
        || ' days'
    )
    ELSE NULL
END
"""


ESTADO_SQL = f"""
CASE
    WHEN {DATA_FIM_SQL} IS NULL
        THEN 'sem_prazo'
    WHEN {DATA_FIM_SQL} >= DATE('now')
        THEN 'aberto'
    ELSE 'encerrado'
END
"""


def converter_data(valor: Any) -> date | None:
    """Converte os formatos de data usados nos registos."""
    if not valor:
        return None

    texto = str(valor).strip()

    formatos = (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    )

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue

    return None


def calcular_data_fim(
    data_publicacao: date | None,
    valor_prazo: Any,
) -> date | None:
    """Calcula a data final a partir da publicação e do prazo."""
    if not data_publicacao or not valor_prazo:
        return None

    texto = str(valor_prazo).strip()

    # O valor pode já ser uma data completa.
    data_absoluta = converter_data(texto)

    if data_absoluta:
        return data_absoluta

    # Exemplos: "18 dias.", "34 dias" ou "31 dias úteis".
    correspondencia = re.search(r"\d+", texto)

    if not correspondencia:
        return None

    numero_dias = int(correspondencia.group())

    if numero_dias <= 0:
        return None

    return data_publicacao + timedelta(days=numero_dias)


def calcular_estado(data_fim: date | None) -> str:
    if data_fim is None:
        return "sem_prazo"

    if data_fim >= date.today():
        return "aberto"

    return "encerrado"


def carregar_concursos_checkpoint() -> list[dict[str, Any]]:
    """Lê os concursos completos acumulados pelo coletor."""

    if not CHECKPOINT_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "O ficheiro de concursos não foi encontrado: "
                f"{CHECKPOINT_PATH}"
            ),
        )

    try:
        dados = json.loads(
            CHECKPOINT_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=f"Erro a ler checkpoint: {erro}",
        ) from erro

    return dados


# =====================================================
# ANÁLISE AUTOMÁTICA DE CONCURSOS
# =====================================================

ANALISE_DIR = BASE_DIR / "analise_documentos"


@app.get("/analise/{id_concurso}")
def obter_analise(
    id_concurso: str,
) -> dict[str, Any]:

    pasta = ANALISE_DIR / id_concurso

    ficha = pasta / "ficha.json"
    analise_ai = pasta / "analise_ai.json"


    if not ficha.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Ficha não encontrada "
                f"para o concurso {id_concurso}"
            ),
        )


    try:

        dados = json.loads(
            ficha.read_text(
                encoding="utf-8"
            )
        )


        if analise_ai.exists():

            dados_ai = json.loads(
                analise_ai.read_text(
                    encoding="utf-8"
                )
            )

            dados.update(
                dados_ai
            )


    except Exception as erro:

        raise HTTPException(
            status_code=500,
            detail=f"Erro a ler análise: {erro}",
        ) from erro


    return {
        "id_concurso": id_concurso,
        "analise": dados,
    }

