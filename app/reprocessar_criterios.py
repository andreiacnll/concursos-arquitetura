from app.database import abrir_conexao


def limpar_resumo(valor):
    if not valor:
        return valor

    partes = [
        p.strip()
        for p in valor.split("•")
        if p.strip()
    ]

    unicos = []

    for parte in partes:
        if parte not in unicos:
            unicos.append(parte)

    return " • ".join(unicos)


conn = abrir_conexao()
cursor = conn.cursor()

cursor.execute(
    """
    SELECT id, criterio_resumo, criterio_detalhe
    FROM concursos
    WHERE criterio_resumo IS NOT NULL
    """
)

linhas = cursor.fetchall()

alterados = 0

for id_, resumo, detalhe in linhas:

    novo_resumo = limpar_resumo(resumo)

    if novo_resumo != resumo:

        cursor.execute(
            """
            UPDATE concursos
            SET criterio_resumo = ?
            WHERE id = ?
            """,
            (
                novo_resumo,
                id_,
            ),
        )

        alterados += 1


conn.commit()
conn.close()

print(
    f"Critérios corrigidos: {alterados}"
)
