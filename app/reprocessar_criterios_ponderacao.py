import sqlite3
from urllib.parse import urlparse, parse_qs

from app.coletor import PortalBaseBrowser

from app.dre import (
    obter_pdf,
    extrair_texto_pdf,
    extrair_criterio,
)


DB = "concursos.db"


def atualizar():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, link
        FROM concursos
        WHERE criterio_resumo LIKE 'Ponderação%'
    """)

    concursos = cursor.fetchall()

    print("Encontrados:", len(concursos))

    corrigidos = 0

    with PortalBaseBrowser() as portal:
        portal.inicializar()

        for id_, link in concursos:

            print("\nA processar:", id_)

            try:
                identificador = parse_qs(
                    urlparse(link).query
                ).get("id", [""])[0]

                detalhe = portal.obter_detalhe(
                    identificador
                )

                pdf_url = detalhe.get("reference")

                if not pdf_url:
                    print("Sem PDF DR")
                    continue

                pdf = obter_pdf(pdf_url)
                texto = extrair_texto_pdf(pdf)

                criterio = extrair_criterio(texto)

                if not criterio["criterio_resumo"]:
                    print("Sem critério encontrado")
                    continue

                cursor.execute("""
                    UPDATE concursos
                    SET
                        criterio_tipo=?,
                        criterio_resumo=?,
                        criterio_detalhe=?
                    WHERE id=?
                """, (
                    criterio["criterio_tipo"],
                    criterio["criterio_resumo"],
                    criterio["criterio_detalhe"],
                    id_,
                ))

                corrigidos += 1

                print(
                    "OK:",
                    criterio["criterio_resumo"]
                )

            except Exception as erro:
                print(
                    "ERRO:",
                    erro
                )

    conn.commit()
    conn.close()

    print("\nCorrigidos:", corrigidos)


if __name__ == "__main__":
    atualizar()
