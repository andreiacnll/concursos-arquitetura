import sqlite3


DB_NAME = "concursos.db"


def criar_base_dados():
    """
    Cria a base de dados e a tabela de concursos,
    caso ainda não existam.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS concursos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        entidade TEXT,
        link TEXT NOT NULL UNIQUE,
        data TEXT,
        relevante INTEGER DEFAULT 1
    )
    """)

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

    cursor.execute("""
        SELECT COUNT(*)
        FROM concursos
    """)

    total = cursor.fetchone()[0]

    conn.close()

    return total