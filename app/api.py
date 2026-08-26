from __future__ import annotations

import json
import asyncio
import os
import re
import sqlite3
from contextlib import asynccontextmanager, closing, suppress
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .database import (
    DB_PATH,
    abrir_conexao,
    criar_base_dados,
    estados_analise_concursos,
    listar_versoes_analise,
    obter_analise_ativa_concurso,
)
from .auth import obter_utilizador_atual
from .analise.worker import executar_worker
from .company_ai.router import router as company_ai_router
from .company_ai.company_storage import obter_empresa_utilizador
from .company_ai.company_context import build_company_context
from .company_ai.competition_context import build_competition_context
from .company_ai.compatibility_analysis import analyze_compatibility
from .routes.analises import router as analises_router
from .routes.alertas import router as alertas_router
from .routes.favoritos import router as favoritos_router


BASE_DIR = Path(__file__).resolve().parent.parent
CHECKPOINT_PATH = BASE_DIR / "concursos_recolhidos.json"


@asynccontextmanager
async def lifespan(_: FastAPI):
    criar_base_dados()
    stop_worker = asyncio.Event()
    worker_task = None

    if os.getenv("CNLL_ANALISE_WORKER", "1").strip().lower() not in {
        "0",
        "false",
        "nao",
        "não",
        "off",
    }:
        worker_task = asyncio.create_task(
            executar_worker(stop_worker)
        )

    try:
        yield
    finally:
        stop_worker.set()
        if worker_task is not None:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task


app = FastAPI(
    title="ArquiConcursos API",
    description=(
        "API para consulta de concursos públicos "
        "relacionados com arquitetura."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(favoritos_router)
app.include_router(analises_router)
app.include_router(alertas_router)
app.include_router(company_ai_router)


def obter_conexao() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise RuntimeError(
            f"Base de dados não encontrada: {DB_PATH}"
        )

    return abrir_conexao()


def linha_para_dicionario(
    linha: sqlite3.Row,
) -> dict[str, Any]:
    return dict(linha)


def extrair_id_portal_base(link: Any) -> str | None:
    if not link:
        return None

    correspondencia = re.search(
        r"[?&]id=(\d+)",
        str(link),
    )
    return correspondencia.group(1) if correspondencia else None


def procurar_concurso_por_identificador(
    conexao: sqlite3.Connection,
    concurso_id: int,
) -> sqlite3.Row | None:
    """Aceita o ID canónico e mantém os IDs BASE como alias."""
    return conexao.execute(
        """
        SELECT *
        FROM concursos
        WHERE id = ?
           OR link LIKE ?
        ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END
        LIMIT 1
        """,
        (
            concurso_id,
            f"%id={concurso_id}%",
            concurso_id,
        ),
    ).fetchone()


def obter_user_id_opcional(request: Request) -> str | None:
    autorizacao = request.headers.get("authorization") or ""
    if not autorizacao.lower().startswith("bearer "):
        return None

    from fastapi.security import HTTPAuthorizationCredentials

    try:
        utilizador = obter_utilizador_atual(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=autorizacao.split(" ", 1)[1],
            )
        )
    except HTTPException:
        return None
    return utilizador.id


def obter_company_id_opcional(user_id: str | None) -> int | None:
    if not user_id:
        return None
    empresa = obter_empresa_utilizador(user_id)
    return int(empresa["id"]) if empresa else None


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

        concurso = procurar_concurso_por_identificador(
            conexao,
            concurso_id,
        )

        if concurso is None:
            raise HTTPException(
                status_code=404,
                detail="Concurso não encontrado.",
            )

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
            (concurso["id"],),
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
            CHECKPOINT_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as erro:
        raise HTTPException(
            status_code=503,
            detail=f"Não foi possível ler os concursos: {erro}",
        ) from erro

    if not isinstance(dados, list):
        raise HTTPException(
            status_code=503,
            detail="O ficheiro de concursos não contém uma lista válida.",
        )

    return [
        item
        for item in dados
        if isinstance(item, dict)
    ]



def carregar_concursos_base_dados() -> list[dict[str, Any]]:
    """
    Lê os concursos diretamente da base de dados.
    Inclui os campos enriquecidos dos procedimentos.
    """
    with closing(obter_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT
                id,
                titulo,
                titulo_resumido,
                entidade,
                link,
                data,
                relevante,
                data_limite,
                preco_base,
                cpv,
                tipo_procedimento,
                criterio_tipo,
                criterio_resumo,
                criterio_detalhe,
                criterio_fatores,
                criterio_estado,
                entregaveis,
                link_anuncio_dr,
                link_pecas,
                data_entrega_propostas,
                data_esclarecimentos,
                municipio,
                freguesia,
                morada,
                codigo_postal,
                latitude,
                longitude,
                localizacao_contexto,
                (
                    SELECT cf.fonte
                    FROM concurso_fontes AS cf
                    WHERE cf.concurso_id = concursos.id
                    ORDER BY cf.principal DESC, cf.id ASC
                    LIMIT 1
                ) AS fonte,
                (
                    SELECT cf.referencia
                    FROM concurso_fontes AS cf
                    WHERE cf.concurso_id = concursos.id
                    ORDER BY cf.principal DESC, cf.id ASC
                    LIMIT 1
                ) AS referencia_fonte,
                (
                    SELECT cf.estado_fonte
                    FROM concurso_fontes AS cf
                    WHERE cf.concurso_id = concursos.id
                    ORDER BY cf.principal DESC, cf.id ASC
                    LIMIT 1
                ) AS estado_fonte,
                (
                    SELECT MIN(cf.first_seen_at)
                    FROM concurso_fontes AS cf
                    WHERE cf.concurso_id = concursos.id
                ) AS first_seen_at,
                (
                    SELECT MAX(cf.last_seen_at)
                    FROM concurso_fontes AS cf
                    WHERE cf.concurso_id = concursos.id
                ) AS last_seen_at
            FROM concursos
            WHERE relevante = 1
            ORDER BY id DESC
            """
        ).fetchall()

    return [dict(linha) for linha in linhas]


def juntar_valores(valor: Any) -> str | None:
    """Transforma listas e outros valores num texto para a API."""
    if isinstance(valor, list):
        valores = [
            str(item).strip()
            for item in valor
            if item is not None and str(item).strip()
        ]
        return ", ".join(valores) or None

    if valor is None:
        return None

    texto = str(valor).strip()
    return texto or None


def normalizar_concurso_json(
    item: dict[str, Any],
    _indice: int,
) -> dict[str, Any]:
    data_publicacao = converter_data(item.get("data"))

    data_fim = calcular_data_fim(
        data_publicacao,
        item.get("data_limite"),
    )

    cpv = juntar_valores(
        item.get("cpvs")
        or item.get("cpv")
    )

    tipo_procedimento = juntar_valores(
        item.get("tipos_contrato")
        or item.get("tipo_procedimento")
    )

    id_portal_base = (
        item.get("id_portal_base")
        or extrair_id_portal_base(item.get("link"))
    )

    identificador = (
        item.get("id")
        or id_portal_base
        or item.get("id_procedimento")
        or item.get("numero_anuncio")
    )

    if identificador is None:
        raise ValueError("Concurso sem identificador estável.")

    return {
        "id": identificador,
        "titulo": item.get("titulo") or "Concurso sem título",
        "titulo_resumido": item.get("titulo_resumido") or None,
        "entidade": item.get("entidade") or "Entidade não indicada",
        "link": (
            item.get("link")
            or item.get("link_anuncio_dr")
            or ""
        ),
        "data": item.get("data"),
        "relevante": 1,
        "data_limite": item.get("data_limite"),
        "preco_base": item.get("preco_base"),
        "cpv": cpv,
        "tipo_procedimento": tipo_procedimento,
        "criterio_tipo": item.get("criterio_tipo"),
        "criterio_resumo": item.get("criterio_resumo"),
        "criterio_detalhe": item.get("criterio_detalhe"),
        "criterio_fatores": item.get("criterio_fatores"),
        "criterio_estado": item.get("criterio_estado"),
        "entregaveis": item.get("entregaveis"),
        "numero_anuncio": item.get("numero_anuncio"),
        "link_anuncio_dr": item.get("link_anuncio_dr"),
        "link_pecas": item.get("link_pecas"),
        "data_entrega_propostas": item.get(
            "data_entrega_propostas"
        ),
        "data_esclarecimentos": item.get(
            "data_esclarecimentos"
        ),
        "municipio": item.get("municipio"),
        "freguesia": item.get("freguesia"),
        "morada": item.get("morada"),
        "codigo_postal": item.get("codigo_postal"),
        "latitude": item.get("latitude"),
        "longitude": item.get("longitude"),
        "localizacao_contexto": item.get("localizacao_contexto"),
        "fonte": item.get("fonte") or ("base_gov" if id_portal_base else None),
        "referencia_fonte": item.get("referencia_fonte"),
        "estado_fonte": item.get("estado_fonte"),
        "first_seen_at": item.get("first_seen_at"),
        "last_seen_at": item.get("last_seen_at"),
        "data_ordenacao_iso": (
            data_publicacao.isoformat()
            if data_publicacao
            else item.get("first_seen_at")
        ),
        "id_portal_base": id_portal_base,
        "id_procedimento": item.get("id_procedimento"),
        "texto": item.get("texto"),
        "data_publicacao_iso": (
            data_publicacao.isoformat()
            if data_publicacao
            else None
        ),
        "data_fim_calculada": (
            data_fim.isoformat()
            if data_fim
            else None
        ),
        "estado": calcular_estado(data_fim),
    }


def executar_listagem(
    *,
    periodo: Literal["atual", "historico"],
    pesquisa: str | None,
    entidade: str | None,
    tipo_procedimento: str | None,
    apenas_relevantes: bool,
    estado: Literal[
        "todos",
        "aberto",
        "encerrado",
        "sem_prazo",
    ],
    limite: int,
    pagina: int,
    user_id: str | None = None,
    company_id: int | None = None,
) -> dict[str, Any]:
    dados = carregar_concursos_base_dados()
    estados_analise = estados_analise_concursos(user_id, company_id)

    concursos = [
        normalizar_concurso_json(item, indice)
        for indice, item in enumerate(dados, start=1)
    ]
    for concurso in concursos:
        estado_da_analise = estados_analise.get(int(concurso["id"]))
        if estado_da_analise:
            concurso.update(estado_da_analise)
        else:
            concurso.update(
                {
                    "temAnalise": False,
                    "estadoAnalise": None,
                    "analiseId": None,
                    "analiseTipo": None,
                    "progressoAnalise": None,
                    "scoreAnalise": None,
                    "updatedAtAnalise": None,
                }
            )

    if periodo == "atual":
        concursos = [
            concurso
            for concurso in concursos
            if concurso["estado"] != "encerrado"
        ]
    else:
        concursos = [
            concurso
            for concurso in concursos
            if concurso["estado"] == "encerrado"
        ]

    if apenas_relevantes:
        concursos = [
            concurso
            for concurso in concursos
            if concurso["relevante"] == 1
        ]

    if estado != "todos":
        concursos = [
            concurso
            for concurso in concursos
            if concurso["estado"] == estado
        ]

    if pesquisa:
        termo = pesquisa.strip().casefold()

        concursos = [
            concurso
            for concurso in concursos
            if (
                termo in str(
                    concurso.get("titulo") or ""
                ).casefold()
                or termo in str(
                    concurso.get("titulo_resumido") or ""
                ).casefold()
                or termo in str(
                    concurso.get("entidade") or ""
                ).casefold()
                or termo in str(
                    concurso.get("cpv") or ""
                ).casefold()
            )
        ]

    if entidade:
        termo_entidade = entidade.strip().casefold()

        concursos = [
            concurso
            for concurso in concursos
            if termo_entidade
            in str(
                concurso.get("entidade") or ""
            ).casefold()
        ]

    if tipo_procedimento:
        termo_tipo = tipo_procedimento.strip().casefold()

        concursos = [
            concurso
            for concurso in concursos
            if termo_tipo
            in str(
                concurso.get("tipo_procedimento") or ""
            ).casefold()
        ]

    concursos.sort(
        key=lambda concurso: (
            concurso.get("data_ordenacao_iso")
            or concurso.get("data_publicacao_iso")
            or "",
            str(concurso.get("id") or ""),
        ),
        reverse=True,
    )

    total = len(concursos)
    inicio_pagina = (pagina - 1) * limite
    fim_pagina = inicio_pagina + limite

    return {
        "pagina": pagina,
        "limite": limite,
        "total": total,
        "periodo": periodo,
        "estado": estado,
        "resultados": concursos[inicio_pagina:fim_pagina],
    }




# =====================================================
# ANÁLISE AUTOMÁTICA DE CONCURSOS
# =====================================================

ANALISE_DIR = BASE_DIR / "analise_documentos"


def resolver_pasta_analise(id_concurso: str) -> Path:
    """Resolve fichas antigas pelo ID BASE a partir do ID canónico."""
    pasta_direta = ANALISE_DIR / id_concurso

    if (pasta_direta / "ficha.json").exists():
        return pasta_direta

    try:
        identificador = int(id_concurso)
    except ValueError:
        return pasta_direta

    with closing(obter_conexao()) as conexao:
        concurso = procurar_concurso_por_identificador(
            conexao,
            identificador,
        )

    if concurso is None:
        return pasta_direta

    id_portal_base = extrair_id_portal_base(concurso["link"])

    if id_portal_base:
        return ANALISE_DIR / id_portal_base

    return pasta_direta


@app.get("/analise/{id_concurso}")
def obter_analise(
    request: Request,
    id_concurso: str,
) -> dict[str, Any]:
    try:
        identificador = int(id_concurso)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Identificador de concurso inv?lido.",
        )

    with closing(obter_conexao()) as conexao:
        concurso = procurar_concurso_por_identificador(
            conexao,
            identificador,
        )

    if concurso is None:
        raise HTTPException(
            status_code=404,
            detail=f"Concurso {id_concurso} n?o encontrado.",
        )

    user_id = obter_user_id_opcional(request)
    analise_ativa = obter_analise_ativa_concurso(
        concurso["id"],
        user_id,
        obter_company_id_opcional(user_id),
    )
    if analise_ativa is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "An?lise ativa n?o encontrada "
                f"para o concurso {id_concurso}"
            ),
        )

    try:
        # CNLL_API_ACTIVE_ANALYSIS_SOURCE_V17_5_5
        #
        # A linha ativa da BD é a fonte de verdade. `dados_json` pode ser
        # enriquecido posteriormente (canonical, CV, recuperação procedural),
        # enquanto `ficheiro_ficha` pode continuar a apontar para um snapshot
        # antigo do job. Ler primeiro o ficheiro fazia a API devolver dados
        # stale mesmo quando a BD já tinha perguntas/fatores/equipa corretos.
        dados = None

        dados_json = analise_ativa.get("dados_json")
        if dados_json:
            try:
                candidato = json.loads(dados_json)
                if isinstance(candidato, dict) and candidato:
                    dados = candidato
            except (TypeError, json.JSONDecodeError):
                dados = None

        # Compatibilidade apenas para análises antigas cujo `dados_json`
        # esteja vazio ou ilegível.
        if dados is None:
            ficheiro_relativo = analise_ativa.get("ficheiro_ficha")
            if ficheiro_relativo:
                ficha = (BASE_DIR / ficheiro_relativo).resolve()
                if (
                    ANALISE_DIR.resolve() in ficha.parents
                    and ficha.name == "ficha.json"
                    and ficha.is_file()
                ):
                    dados = json.loads(
                        ficha.read_text(encoding="utf-8-sig")
                    )

        if dados is None:
            dados = {}

        pasta_legado = resolver_pasta_analise(str(concurso["id"]))
        analise_ai = pasta_legado / "analise_ai.json"
        if analise_ativa.get("user_id") is None and analise_ai.exists():
            dados_ai = json.loads(
                analise_ai.read_text(encoding="utf-8-sig")
            )
            dados.update(dados_ai)

        company_id = obter_company_id_opcional(user_id)
        if company_id is not None and isinstance(dados, dict):
            try:
                company_context = build_company_context(company_id)
                competition_context = build_competition_context(dados)
                matching = analyze_compatibility(
                    company_context,
                    competition_context,
                )
                dados.setdefault(
                    "company_context",
                    company_context.model_dump(mode="json"),
                )
                dados["company_matching"] = matching.model_dump(mode="json")
            except Exception:
                pass

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=f"Erro a ler an?lise ativa: {erro}",
        ) from erro

    versoes_antigas = listar_versoes_analise(
        analise_ativa["id"]
    )
    historico = [
        {
            "id": analise_ativa["id"],
            "tipo": "atual",
            "score": analise_ativa.get("score"),
            "ficheiro_ficha": analise_ativa.get("ficheiro_ficha"),
            "created_at": analise_ativa.get("updated_at"),
        },
        *[
            {
                **versao,
                "tipo": "historico",
            }
            for versao in versoes_antigas
        ],
    ]

    return {
        "id_concurso": id_concurso,
        "concurso_id": concurso["id"],
        "analise_id": analise_ativa["id"],
        "versao_atual": {
            "analise_id": analise_ativa["id"],
            "ficheiro_ficha": analise_ativa.get("ficheiro_ficha"),
            "updated_at": analise_ativa.get("updated_at"),
            "score": analise_ativa.get("score"),
            "origem": (
                "utilizador"
                if analise_ativa.get("user_id")
                else "sistema"
            ),
        },
        "historico_versoes": historico,
        "analise": dados,
    }


@app.get("/concursos")
def listar_concursos(
    request: Request,
    pesquisa: str | None = Query(
        default=None,
        description="Pesquisa no título, entidade ou CPV.",
    ),
    entidade: str | None = Query(
        default=None,
        description="Filtrar por entidade.",
    ),
    tipo_procedimento: str | None = Query(
        default=None,
        description="Filtrar por tipo de procedimento.",
    ),
    apenas_relevantes: bool = Query(
        default=False,
        description="Mostrar apenas concursos relevantes.",
    ),
    estado: Literal[
        "todos",
        "aberto",
        "encerrado",
        "sem_prazo",
    ] = Query(
        default="todos",
        description="Filtrar pelo estado do concurso.",
    ),
    limite: int = Query(
        default=100,
        ge=1,
        le=100,
    ),
    pagina: int = Query(
        default=1,
        ge=1,
    ),
) -> dict[str, Any]:
    user_id = obter_user_id_opcional(request)
    return executar_listagem(
        periodo="atual",
        pesquisa=pesquisa,
        entidade=entidade,
        tipo_procedimento=tipo_procedimento,
        apenas_relevantes=apenas_relevantes,
        estado=estado,
        limite=limite,
        pagina=pagina,
        user_id=user_id,
        company_id=obter_company_id_opcional(user_id),
    )


@app.get("/historico")
def listar_historico(
    request: Request,
    pesquisa: str | None = Query(
        default=None,
        description="Pesquisa no título, entidade ou CPV.",
    ),
    entidade: str | None = Query(
        default=None,
        description="Filtrar por entidade.",
    ),
    tipo_procedimento: str | None = Query(
        default=None,
        description="Filtrar por tipo de procedimento.",
    ),
    apenas_relevantes: bool = Query(
        default=False,
        description="Mostrar apenas concursos relevantes.",
    ),
    estado: Literal[
        "todos",
        "aberto",
        "encerrado",
        "sem_prazo",
    ] = Query(
        default="todos",
        description="Filtrar pelo estado do concurso.",
    ),
    limite: int = Query(
        default=100,
        ge=1,
        le=100,
    ),
    pagina: int = Query(
        default=1,
        ge=1,
    ),
) -> dict[str, Any]:
    user_id = obter_user_id_opcional(request)
    return executar_listagem(
        periodo="historico",
        pesquisa=pesquisa,
        entidade=entidade,
        tipo_procedimento=tipo_procedimento,
        apenas_relevantes=apenas_relevantes,
        estado=estado,
        limite=limite,
        pagina=pagina,
        user_id=user_id,
        company_id=obter_company_id_opcional(user_id),
    )


@app.get("/concursos/{concurso_id}")
def obter_concurso(
    request: Request,
    concurso_id: int,
) -> dict[str, Any]:
    with closing(obter_conexao()) as conexao:
        linha = procurar_concurso_por_identificador(
            conexao,
            concurso_id,
        )

    if linha is None:
        raise HTTPException(
            status_code=404,
            detail="Concurso não encontrado.",
        )

    concurso = linha_para_dicionario(linha)
    concurso["id_portal_base"] = extrair_id_portal_base(
        concurso.get("link")
    )
    user_id = obter_user_id_opcional(request)
    estados = estados_analise_concursos(
        user_id,
        obter_company_id_opcional(user_id),
    )
    estado = estados.get(concurso["id"])
    if estado:
        concurso.update(estado)
    else:
        concurso.update(
            {
                "temAnalise": False,
                "estadoAnalise": None,
                "analiseId": None,
                "analiseTipo": None,
            }
        )
    return concurso


@app.get("/estatisticas")
def obter_estatisticas() -> dict[str, Any]:
    with closing(obter_conexao()) as conexao:
        total = conexao.execute(
            """
            SELECT COUNT(*)
            FROM concursos
            """
        ).fetchone()[0]

        relevantes = conexao.execute(
            """
            SELECT COUNT(*)
            FROM concursos
            """
        ).fetchone()[0]

        com_preco = conexao.execute(
            """
            SELECT COUNT(*)
            FROM concursos
            WHERE
                preco_base IS NOT NULL
                AND TRIM(preco_base) != ''
            """
        ).fetchone()[0]

        com_prazo = conexao.execute(
            """
            SELECT COUNT(*)
            FROM concursos
            WHERE
                data_limite IS NOT NULL
                AND TRIM(data_limite) != ''
            """
        ).fetchone()[0]

        entidades = conexao.execute(
            """
            SELECT
                entidade,
                COUNT(*) AS total
            FROM concursos
            WHERE
                entidade IS NOT NULL
                AND TRIM(entidade) != ''
            GROUP BY entidade
            ORDER BY total DESC
            LIMIT 10
            """
        ).fetchall()

    return {
        "total_concursos": total,
        "concursos_relevantes": relevantes,
        "concursos_com_preco": com_preco,
        "concursos_com_prazo": com_prazo,
        "principais_entidades": [
            {
                "entidade": linha["entidade"],
                "total": linha["total"],
            }
            for linha in entidades
        ],
   
     }
