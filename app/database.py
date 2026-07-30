import json
import re
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "concursos.db"

ESTADOS_ANALISE = (
    "aguarda",
    "extracao",
    "processamento",
    "geracao",
    "concluida",
    "erro",
)

COLUNAS_ANALISE = {
    "estado": "TEXT NOT NULL DEFAULT 'concluida'",
    "progresso": "INTEGER NOT NULL DEFAULT 100",
    "score": "INTEGER",
    "ficheiro_ficha": "TEXT",
    # O SQLite não aceita CURRENT_TIMESTAMP ao acrescentar uma coluna.
    "updated_at": "TEXT",
}


COLUNAS_ADICIONAIS = {
    "data_limite": "TEXT",
    "data_esclarecimentos": "TEXT",
    "preco_base": "TEXT",
    "cpv": "TEXT",
    "tipo_procedimento": "TEXT",
    "criterio_tipo": "TEXT",
    "criterio_resumo": "TEXT",
    "criterio_detalhe": "TEXT",
    "entregaveis": "TEXT",
    "link_anuncio_dr": "TEXT",
    "data_entrega_propostas": "TEXT",
}


def abrir_conexao() -> sqlite3.Connection:
    """Abre a base principal com as garantias usadas pela API."""
    conexao = sqlite3.connect(DB_PATH, timeout=5)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA busy_timeout = 5000")
    return conexao


def _adicionar_colunas_em_falta(cursor):
    """
    Acrescenta novas colunas à tabela sem apagar
    os concursos que já existem.
    """
    cursor.execute(
        """
        PRAGMA table_info(concursos)
        """
    )

    colunas_existentes = {
        linha[1]
        for linha in cursor.fetchall()
    }

    for nome_coluna, tipo_coluna in (
        COLUNAS_ADICIONAIS.items()
    ):
        if nome_coluna in colunas_existentes:
            continue

        cursor.execute(
            f"""
            ALTER TABLE concursos
            ADD COLUMN {nome_coluna} {tipo_coluna}
            """
        )


def _adicionar_colunas_analise_em_falta(cursor):
    """Migra o registo legado de análises sem perder fichas existentes."""
    cursor.execute("PRAGMA table_info(analises)")
    colunas_existentes = {linha[1] for linha in cursor.fetchall()}

    for nome_coluna, definicao in COLUNAS_ANALISE.items():
        if nome_coluna not in colunas_existentes:
            cursor.execute(
                f"ALTER TABLE analises ADD COLUMN {nome_coluna} {definicao}"
            )


def _id_portal_base(link: str | None):
    if not link:
        return None

    correspondencia = re.search(r"[?&]id=(\d+)", link)
    return correspondencia.group(1) if correspondencia else None


def _extrair_score(ficha: dict):
    candidatos = (
        ficha.get("analise_ai", {}).get("score"),
        ficha.get("decisao", {}).get("score"),
        ficha.get("score"),
    )

    for candidato in candidatos:
        if isinstance(candidato, dict):
            candidato = candidato.get("valor")
        try:
            return max(0, min(100, int(float(candidato))))
        except (TypeError, ValueError):
            continue
    return None


def _sincronizar_fichas_existentes(cursor):
    """Regista as fichas reais do repositório no histórico durável."""
    raiz_fichas = BASE_DIR / "analise_documentos"
    if not raiz_fichas.is_dir():
        return

    concursos = cursor.execute(
        "SELECT id, titulo, link FROM concursos"
    ).fetchall()
    concursos_por_portal = {
        portal_id: concurso
        for concurso in concursos
        if (portal_id := _id_portal_base(concurso["link"]))
    }

    for caminho_ficha in raiz_fichas.glob("*/ficha.json"):
        concurso = concursos_por_portal.get(caminho_ficha.parent.name)
        if concurso is None:
            continue

        try:
            ficha = json.loads(caminho_ficha.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue

        caminho_relativo = caminho_ficha.relative_to(BASE_DIR).as_posix()
        score = _extrair_score(ficha)
        resumo = (
            ficha.get("analise_ai", {}).get("recomendacao")
            or ficha.get("decisao", {}).get("classificacao")
            or concurso["titulo"]
        )

        cursor.execute(
            """
            INSERT INTO analises (
                concurso_id,
                nivel,
                resumo,
                dados_json,
                estado,
                progresso,
                score,
                ficheiro_ficha
            )
            VALUES (?, 'AI', ?, ?, 'concluida', 100, ?, ?)
            ON CONFLICT(concurso_id) DO UPDATE SET
                nivel = excluded.nivel,
                resumo = excluded.resumo,
                dados_json = excluded.dados_json,
                estado = 'concluida',
                progresso = 100,
                score = excluded.score,
                ficheiro_ficha = excluded.ficheiro_ficha,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                concurso["id"],
                resumo,
                json.dumps(ficha, ensure_ascii=False),
                score,
                caminho_relativo,
            ),
        )


def criar_base_dados():
    """
    Cria a base de dados e a tabela de concursos.

    Se a tabela já existir, acrescenta automaticamente
    as colunas novas sem apagar os dados existentes.
    """
    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS concursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            entidade TEXT,
            link TEXT NOT NULL UNIQUE,
            data TEXT,
            relevante INTEGER DEFAULT 1,
            data_limite TEXT,
            preco_base TEXT,
            cpv TEXT,
            tipo_procedimento TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS timeline_eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concurso_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            data TEXT,
            estado TEXT,
            origem TEXT,

            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concurso_id INTEGER UNIQUE,
            nivel TEXT,
            resumo TEXT,
            dados_json TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            estado TEXT NOT NULL DEFAULT 'concluida',
            progresso INTEGER NOT NULL DEFAULT 100,
            score INTEGER,
            ficheiro_ficha TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS favoritos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            concurso_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, concurso_id),
            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
            ON DELETE CASCADE
        )
        """
    )

    estados_sql = ", ".join(
        f"'{estado}'"
        for estado in ESTADOS_ANALISE
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS analise_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            concurso_id INTEGER NOT NULL,
            estado TEXT NOT NULL DEFAULT 'aguarda'
                CHECK (estado IN ({estados_sql})),
            progresso INTEGER NOT NULL DEFAULT 0
                CHECK (progresso BETWEEN 0 AND 100),
            erro TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, concurso_id),
            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
            ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_favoritos_user_id
        ON favoritos(user_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analise_jobs_user_id
        ON analise_jobs(user_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analise_jobs_estado
        ON analise_jobs(estado, created_at)
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS analise_jobs_updated_at
        AFTER UPDATE ON analise_jobs
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE analise_jobs
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END
        """
    )


    _adicionar_colunas_em_falta(cursor)
    _adicionar_colunas_analise_em_falta(cursor)
    cursor.execute(
        """
        UPDATE analises
        SET updated_at = COALESCE(updated_at, criado_em, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL
        """
    )

    cursor.execute(
        """
        UPDATE analise_jobs
        SET estado = 'aguarda', progresso = 0
        WHERE estado IN ('extracao', 'processamento', 'geracao')
          AND id NOT IN (
              SELECT id
              FROM analise_jobs
              WHERE estado IN ('extracao', 'processamento', 'geracao')
              ORDER BY updated_at ASC, id ASC
              LIMIT 1
          )
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_analise_jobs_um_ativo
        ON analise_jobs((1))
        WHERE estado IN ('extracao', 'processamento', 'geracao')
        """
    )

    _sincronizar_fichas_existentes(cursor)

    conn.commit()
    conn.close()


def concurso_por_id(concurso_id: int):
    """Obtém um concurso pelo identificador canónico da BD."""
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT *
            FROM concursos
            WHERE id = ?
            """,
            (concurso_id,),
        ).fetchone()

    return dict(linha) if linha else None


def listar_favoritos_utilizador(user_id: str):
    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT
                f.id,
                f.user_id,
                f.concurso_id,
                f.created_at,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.preco_base,
                c.data_limite,
                c.tipo_procedimento
            FROM favoritos AS f
            JOIN concursos AS c
              ON c.id = f.concurso_id
            WHERE f.user_id = ?
            ORDER BY f.created_at DESC, f.id DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(linha) for linha in linhas]


def criar_ou_obter_favorito(
    user_id: str,
    concurso_id: int,
):
    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            INSERT OR IGNORE INTO favoritos (
                user_id,
                concurso_id
            )
            VALUES (?, ?)
            """,
            (user_id, concurso_id),
        )
        criado = cursor.rowcount == 1

        linha = conexao.execute(
            """
            SELECT
                f.id,
                f.user_id,
                f.concurso_id,
                f.created_at,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.preco_base,
                c.data_limite,
                c.tipo_procedimento
            FROM favoritos AS f
            JOIN concursos AS c
              ON c.id = f.concurso_id
            WHERE f.user_id = ?
              AND f.concurso_id = ?
            """,
            (user_id, concurso_id),
        ).fetchone()

        conexao.commit()

    return dict(linha), criado


def remover_favorito(
    user_id: str,
    concurso_id: int,
) -> bool:
    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            DELETE FROM favoritos
            WHERE user_id = ?
              AND concurso_id = ?
            """,
            (user_id, concurso_id),
        )
        conexao.commit()
        return cursor.rowcount > 0


def listar_analises_utilizador(user_id: str):
    with closing(abrir_conexao()) as conexao:
        fichas = conexao.execute(
            """
            SELECT
                a.id,
                'analise' AS tipo,
                NULL AS user_id,
                a.concurso_id,
                a.estado,
                a.progresso,
                NULL AS erro,
                a.score,
                a.criado_em AS created_at,
                a.updated_at,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.tipo_procedimento
            FROM analises AS a
            JOIN concursos AS c
              ON c.id = a.concurso_id
            WHERE a.estado = 'concluida'
            """
        ).fetchall()

        jobs = conexao.execute(
            """
            SELECT
                j.id,
                'job' AS tipo,
                j.user_id,
                j.concurso_id,
                j.estado,
                j.progresso,
                j.erro,
                NULL AS score,
                j.created_at,
                j.updated_at,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.tipo_procedimento
            FROM analise_jobs AS j
            JOIN concursos AS c
              ON c.id = j.concurso_id
            WHERE j.user_id = ?
            ORDER BY j.updated_at DESC, j.id DESC
            """,
            (user_id,),
        ).fetchall()

    concursos_concluidos = {linha["concurso_id"] for linha in fichas}
    resultados = [dict(linha) for linha in fichas]
    resultados.extend(
        dict(linha)
        for linha in jobs
        if linha["concurso_id"] not in concursos_concluidos
    )
    resultados.sort(
        key=lambda linha: (linha.get("updated_at") or "", linha["id"]),
        reverse=True,
    )
    return resultados


def analise_concluida_por_concurso(concurso_id: int):
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT
                a.id,
                'analise' AS tipo,
                NULL AS user_id,
                a.concurso_id,
                a.estado,
                a.progresso,
                NULL AS erro,
                a.score,
                a.criado_em AS created_at,
                a.updated_at,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.tipo_procedimento
            FROM analises AS a
            JOIN concursos AS c ON c.id = a.concurso_id
            WHERE a.concurso_id = ? AND a.estado = 'concluida'
            """,
            (concurso_id,),
        ).fetchone()
    return dict(linha) if linha else None


def reivindicar_proximo_analise_job():
    """Reserva atomicamente o job mais antigo para um futuro worker."""
    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")

        ativo = conexao.execute(
            """
            SELECT 1
            FROM analise_jobs
            WHERE estado IN ('extracao', 'processamento', 'geracao')
            LIMIT 1
            """
        ).fetchone()
        if ativo:
            conexao.rollback()
            return None

        job = conexao.execute(
            """
            SELECT id
            FROM analise_jobs
            WHERE estado = 'aguarda'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """
        ).fetchone()
        if job is None:
            conexao.rollback()
            return None

        conexao.execute(
            """
            UPDATE analise_jobs
            SET estado = 'extracao', progresso = 5, erro = NULL
            WHERE id = ? AND estado = 'aguarda'
            """,
            (job["id"],),
        )
        linha = conexao.execute(
            "SELECT * FROM analise_jobs WHERE id = ?",
            (job["id"],),
        ).fetchone()
        conexao.commit()
        return dict(linha) if linha else None


def atualizar_analise_job(
    job_id: int,
    estado: str,
    progresso: int,
    erro: str | None = None,
):
    """Atualiza um job; é a fronteira de integração do futuro worker."""
    if estado not in ESTADOS_ANALISE:
        raise ValueError(f"Estado de análise inválido: {estado}")
    if not 0 <= progresso <= 100:
        raise ValueError("O progresso tem de estar entre 0 e 100.")
    if estado == "concluida":
        progresso = 100

    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            UPDATE analise_jobs
            SET estado = ?, progresso = ?, erro = ?
            WHERE id = ?
            """,
            (estado, progresso, erro, job_id),
        )
        conexao.commit()
        return cursor.rowcount == 1


def criar_ou_obter_analise_job(
    user_id: str,
    concurso_id: int,
):
    """Cria um job idempotente sem iniciar o processamento."""
    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            INSERT OR IGNORE INTO analise_jobs (
                user_id,
                concurso_id,
                estado,
                progresso
            )
            VALUES (?, ?, 'aguarda', 0)
            """,
            (user_id, concurso_id),
        )
        criado = cursor.rowcount == 1

        linha = conexao.execute(
            """
            SELECT
                j.id,
                j.user_id,
                j.concurso_id,
                j.estado,
                j.progresso,
                j.erro,
                j.created_at,
                j.updated_at,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.tipo_procedimento
            FROM analise_jobs AS j
            JOIN concursos AS c
              ON c.id = j.concurso_id
            WHERE j.user_id = ?
              AND j.concurso_id = ?
            """,
            (user_id, concurso_id),
        ).fetchone()

        conexao.commit()

    return dict(linha), criado


def _texto_ou_none(valor):
    """
    Converte valores vazios em None.
    """
    if valor is None:
        return None

    texto = str(valor).strip()

    if not texto:
        return None

    return texto


def guardar_concurso(
    titulo,
    entidade,
    link,
    data,
    data_limite=None,
    data_esclarecimentos=None,
    preco_base=None,
    cpv=None,
    tipo_procedimento=None,
    link_anuncio_dr=None,
    data_entrega_propostas=None,
):
    """
    Guarda um concurso na base de dados.

    Devolve:
        ID do concurso -> concurso novo guardado
        False -> concurso já existia
    """
    conn = abrir_conexao()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO concursos (
                titulo,
                entidade,
                link,
                data,
                relevante,
                data_limite,
                data_esclarecimentos,
                preco_base,
                cpv,
                tipo_procedimento,
                link_anuncio_dr,
                data_entrega_propostas
            )
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                titulo,
                _texto_ou_none(entidade),
                link,
                _texto_ou_none(data),
                _texto_ou_none(data_limite),
                _texto_ou_none(data_esclarecimentos),
                _texto_ou_none(preco_base),
                _texto_ou_none(cpv),
                _texto_ou_none(tipo_procedimento),
                _texto_ou_none(link_anuncio_dr),
                _texto_ou_none(data_entrega_propostas),
            ),
        )

        conn.commit()
        guardado = cursor.lastrowid

    except sqlite3.IntegrityError:
        guardado = False

    finally:
        conn.close()

    return guardado


def atualizar_dados_concurso(
    link,
    titulo=None,
    entidade=None,
    data=None,
    data_limite=None,
    data_esclarecimentos=None,
    preco_base=None,
    cpv=None,
    tipo_procedimento=None,
    criterio_tipo=None,
    criterio_resumo=None,
    criterio_detalhe=None,
    link_anuncio_dr=None,
    data_entrega_propostas=None,
):
    """
    Atualiza os dados complementares de um concurso existente.

    Valores vazios não substituem informação que já esteja
    guardada na base de dados.
    """
    if not link:
        return False

    titulo = _texto_ou_none(titulo)
    entidade = _texto_ou_none(entidade)
    data = _texto_ou_none(data)
    data_limite = _texto_ou_none(data_limite)
    data_esclarecimentos = _texto_ou_none(
        data_esclarecimentos
    )
    preco_base = _texto_ou_none(preco_base)
    cpv = _texto_ou_none(cpv)
    tipo_procedimento = _texto_ou_none(
        tipo_procedimento
    )
    criterio_tipo = _texto_ou_none(
        criterio_tipo
    )
    criterio_resumo = _texto_ou_none(
        criterio_resumo
    )
    criterio_detalhe = _texto_ou_none(
        criterio_detalhe
    )

    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE concursos
        SET
            titulo = COALESCE(?, titulo),
            entidade = COALESCE(?, entidade),
            data = COALESCE(?, data),
            data_limite = COALESCE(
                ?,
                data_limite
            ),
            data_esclarecimentos = COALESCE(
                ?,
                data_esclarecimentos
            ),
            preco_base = COALESCE(
                ?,
                preco_base
            ),
            cpv = COALESCE(?, cpv),
            tipo_procedimento = COALESCE(
                ?,
                tipo_procedimento
            ),
            criterio_tipo = COALESCE(
                ?,
                criterio_tipo
            ),
            criterio_resumo = COALESCE(
                ?,
                criterio_resumo
            ),
            criterio_detalhe = COALESCE(
                ?,
                criterio_detalhe
            )
        WHERE link = ?
        """,
        (
            titulo,
            entidade,
            data,
            data_limite,
            data_esclarecimentos,
            preco_base,
            cpv,
            tipo_procedimento,
            criterio_tipo,
            criterio_resumo,
            criterio_detalhe,
            link,
        ),
    )

    atualizado = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return atualizado


def concurso_existe(link):
    """
    Verifica se existe um concurso com o mesmo link.
    """
    if not link:
        return False

    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM concursos
        WHERE link = ?
        LIMIT 1
        """,
        (link,),
    )

    existe = cursor.fetchone() is not None

    conn.close()

    return existe


def contar_concursos():
    """
    Devolve o número total de concursos guardados.
    """
    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM concursos
        """
    )

    total = cursor.fetchone()[0]

    conn.close()

    return total


def _converter_data_guardada(valor):
    """
    Converte uma data guardada na base de dados.

    Aceita os formatos mais comuns usados pelo projeto.
    """
    if not valor:
        return None

    texto = str(valor).strip()

    formatos = (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    )

    for formato in formatos:
        try:
            return datetime.strptime(
                texto,
                formato,
            ).date()

        except ValueError:
            continue

    try:
        return datetime.fromisoformat(
            texto.replace("Z", "+00:00")
        ).date()

    except ValueError:
        return None


def listar_concursos_periodo(
    data_inicio,
    data_fim,
):
    """
    Devolve os concursos publicados entre duas datas,
    incluindo a data inicial e excluindo a data final.

    Os argumentos devem ser objetos datetime.date.
    """
    if not isinstance(data_inicio, date):
        raise TypeError(
            "data_inicio deve ser uma data."
        )

    if not isinstance(data_fim, date):
        raise TypeError(
            "data_fim deve ser uma data."
        )

    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            titulo,
            entidade,
            link,
            data,
            data_limite,
            data_esclarecimentos,
            preco_base,
            cpv,
            tipo_procedimento
        FROM concursos
        WHERE relevante = 1
        """
    )

    linhas = cursor.fetchall()
    conn.close()

    concursos = []

    for linha in linhas:
        (
            titulo,
            entidade,
            link,
            data_texto,
            data_limite,
            data_esclarecimentos,
            preco_base,
            cpv,
            tipo_procedimento,
        ) = linha

        data_publicacao = _converter_data_guardada(
            data_texto
        )

        if data_publicacao is None:
            continue

        if not (
            data_inicio
            <= data_publicacao
            < data_fim
        ):
            continue

        concursos.append(
            {
                "titulo": titulo,
                "entidade": entidade,
                "link": link,
                "data": data_texto,
                "data_limite": data_limite,
                "preco_base": preco_base,
                "cpv": cpv,
                "tipo_procedimento": (
                    tipo_procedimento
                ),
                "_data_ordenacao": data_publicacao,
            }
        )

    concursos.sort(
        key=lambda concurso: (
            concurso["_data_ordenacao"],
            concurso.get("titulo") or "",
        )
    )

    for concurso in concursos:
        concurso.pop(
            "_data_ordenacao",
            None,
        )

    return concursos

def guardar_analise(
    concurso_id,
    nivel,
    resumo,
    dados_json,
):
    """
    Guarda ou atualiza a análise automática
    de um concurso.
    """

    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO analises
        (
            concurso_id,
            nivel,
            resumo,
            dados_json
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(concurso_id)
        DO UPDATE SET
            nivel = excluded.nivel,
            resumo = excluded.resumo,
            dados_json = excluded.dados_json,
            estado = 'concluida',
            progresso = 100,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            concurso_id,
            nivel,
            resumo,
            dados_json,
        )
    )

    conn.commit()
    conn.close()


def obter_analise(concurso_id):
    """
    Obtém a análise guardada.
    """

    conn = abrir_conexao()
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM analises
        WHERE concurso_id = ?
        """,
        (
            concurso_id,
        )
    )

    resultado = cursor.fetchone()

    conn.close()

    if resultado:
        return dict(resultado)

    return None


def guardar_evento_timeline(
    concurso_id,
    tipo,
    titulo,
    data=None,
    estado=None,
    origem=None,
):
    """
    Guarda um evento na timeline de um concurso.
    """

    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO timeline_eventos
        (
            concurso_id,
            tipo,
            titulo,
            data,
            estado,
            origem
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            concurso_id,
            tipo,
            titulo,
            data,
            estado,
            origem,
        ),
    )

    conn.commit()
    conn.close()



def obter_timeline(concurso_id):
    """
    Devolve os eventos de timeline de um concurso.
    """

    conn = abrir_conexao()
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM timeline_eventos
        WHERE concurso_id = ?
        ORDER BY data
        """,
        (
            concurso_id,
        ),
    )

    eventos = [
        dict(linha)
        for linha in cursor.fetchall()
    ]

    conn.close()

    return eventos


def gerar_timeline(concurso):
    """
    Gera automaticamente os eventos timeline
    a partir dos dados do concurso.
    """

    concurso_id = concurso.get("id")

    if not concurso_id:
        return


    conn = abrir_conexao()
    cursor = conn.cursor()


    # evitar duplicados
    cursor.execute(
        """
        DELETE FROM timeline_eventos
        WHERE concurso_id = ?
        """,
        (concurso_id,)
    )


    eventos = []


    if concurso.get("data"):

        eventos.append(
            (
                concurso_id,
                "publicacao",
                "Publicado",
                concurso.get("data"),
                "DR",
            )
        )


    if concurso.get("data_entrega_propostas"):

        eventos.append(
            (
                concurso_id,
                "entrega",
                "Entrega de propostas",
                concurso.get("data_entrega_propostas"),
                "DR",
            )
        )


    for evento in eventos:

        cursor.execute(
            """
            INSERT INTO timeline_eventos
            (
                concurso_id,
                tipo,
                titulo,
                data,
                origem
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            evento
        )


    conn.commit()
    conn.close()

