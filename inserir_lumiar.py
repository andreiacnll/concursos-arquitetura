import sqlite3

conn = sqlite3.connect("concursos.db")
cursor = conn.cursor()

cursor.execute(
    """
    INSERT INTO concursos (
        titulo,
        entidade,
        link,
        data,
        relevante,
        preco_base,
        tipo_procedimento
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    (
        "Concurso de Conceção para Reabilitação da Escola Secundária do Lumiar",
        "Município de Lisboa",
        "https://www.base.gov.pt/Base4/pt/detalhe/?type=anuncios&id=420959",
        "2026",
        1,
        "26000",
        "Concurso de conceção"
    )
)

conn.commit()

print("Lumiar inserido com ID:", cursor.lastrowid)

conn.close()