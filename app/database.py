cat > app/database.py <<'PY'
import sqlite3
from datetime import date, datetime


DB_NAME = "concursos.db"


def criar_base_dados():
    """
    Cria a base de dados e a tabela de concursos,
    caso ainda não existam.
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
            relevante INTEGER DEFAULT 1
        )
        """
    )

    conn.commit()
    conn.close()


def guardar_concurso(titulo, entidade, link, data):
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
                relevante
            )
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                titulo,
                entidade,
                link,
                data,
            ),
        )

        conn.commit()
        guardado = True

    except sqlite3.IntegrityError:
        guardado = False

    finally:
        conn.close()

    return guardado


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
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    )

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(
            texto.replace("Z", "+00:00")
        ).date()
    except ValueError:
        return None


def listar_concursos_periodo(data_inicio, data_fim):
    """
    Devolve os concursos publicados entre duas datas,
    incluindo a data inicial e excluindo a data final.

    Os argumentos devem ser objetos datetime.date.
    """
    if not isinstance(data_inicio, date):
        raise TypeError("data_inicio deve ser uma data.")

    if not isinstance(data_fim, date):
        raise TypeError("data_fim deve ser uma data.")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            titulo,
            entidade,
            link,
            data
        FROM concursos
        WHERE relevante = 1
        """
    )

    linhas = cursor.fetchall()
    conn.close()

    concursos = []

    for titulo, entidade, link, data_texto in linhas:
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
        concurso.pop("_data_ordenacao", None)

    return concursos
PY