from pathlib import Path
import requests


URL = "https://www.acingov.pt/acingovprod/2/zonaPublica/zona_publica_c/donwloadProcedurePiece/MTExOTQ1OQ"

PASTA = Path(
    "analise_documentos/450837"
)


def main():

    PASTA.mkdir(
        parents=True,
        exist_ok=True
    )

    print("A descarregar peças...")

    resposta = requests.get(
        URL,
        timeout=60,
        allow_redirects=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120 Safari/537.36"
            ),
            "Referer": "https://www.acingov.pt/",
            "Accept": "*/*",
        },
    )

    print("Status:", resposta.status_code)
    print(
        "Content-Type:",
        resposta.headers.get("content-type")
    )

    ficheiro = PASTA / "pecas.zip"

    ficheiro.write_bytes(
        resposta.content
    )

    print(
        "Guardado:",
        ficheiro
    )

    print(
        "Tamanho:",
        len(resposta.content),
        "bytes"
    )


if __name__ == "__main__":
    main()
