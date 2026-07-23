import sqlite3
from datetime import date, datetime


DB_NAME = "concursos.db"


COLUNAS_ADICIONAIS = {
    "data_limite": "TEXT",
    "preco_base": "TEXT",
    "cpv": "TEXT",
    "tipo_procedimento": "TEXT",
        "link_anuncio_dr": "TEXT",
}


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


def criar_base_dados():
    """
    Cria a base de dados e a tabela de concursos.

    Se a tabela já existir, acrescenta automaticamente
    as colunas novas sem apagar os dados existentes.
    """
    conn = sqlite3.connect(DB_NAME)
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

    _adicionar_colunas_em_falta(cursor)

    conn.commit()
    conn.close()


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
    preco_base=None,
    cpv=None,
    tipo_procedimento=None,
    link_anuncio_dr=None,
    data_entrega_propostas=None,
):
    """
    Guarda um concurso na base de dados.

    Devolve:
        True  -> concurso novo guardado
        False -> concurso já existia
    """
    conn = sqlite3.connect(DB_NAME)
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
                preco_base,
                cpv,
                tipo_procedimento,
                link_anuncio_dr,
                data_entrega_propostas
            )
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
            """,
            (
                titulo,
                _texto_ou_none(entidade),
                link,
                _texto_ou_none(data),
                _texto_ou_none(data_limite),
                _texto_ou_none(preco_base),
                _texto_ou_none(cpv),
                _texto_ou_none(tipo_procedimento),
                _texto_ou_none(link_anuncio_dr),
                _texto_ou_none(data_entrega_propostas),
            ),
        )

        conn.commit()
        guardado = True

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
    preco_base=None,
    cpv=None,
    tipo_procedimento=None,
    criterio_tipo=None,
    criterio_resumo=None,
    criterio_detalhe=None,
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

    conn = sqlite3.connect(DB_NAME)
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

    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
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

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            titulo,
            entidade,
            link,
            data,
            data_limite,
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