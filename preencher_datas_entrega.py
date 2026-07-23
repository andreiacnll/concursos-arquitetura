import json
import sqlite3

from app.dre import (
    obter_pdf,
    extrair_texto_pdf,
    extrair_data_entrega_propostas,
)

DB = "concursos.db"
JSON = "concursos_recolhidos.json"

conn = sqlite3.connect(DB)
cursor = conn.cursor()

with open(JSON, encoding="utf-8") as f:
    concursos = json.load(f)

contador = 0

for concurso in concursos:
    pdf_url = concurso.get("link_anuncio_dr")
    link = concurso.get("link")

    if not pdf_url or not link:
        continue

    try:
        pdf = obter_pdf(pdf_url)
        texto = extrair_texto_pdf(pdf)
        data = extrair_data_entrega_propostas(texto)

        if data:
            cursor.execute(
                """
                UPDATE concursos
                SET data_entrega_propostas = ?,
                    link_anuncio_dr = ?
                WHERE link = ?
                """,
                (
                    data,
                    pdf_url,
                    link,
                ),
            )

            if cursor.rowcount:
                contador += 1
                print(
                    "OK:",
                    data,
                    concurso.get("titulo", "")[:70],
                )

    except Exception as erro:
        print(
            "ERRO:",
            concurso.get("titulo", "")[:70],
            erro,
        )

conn.commit()
conn.close()

print()
print("Atualizados:", contador)
