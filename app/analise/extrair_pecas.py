from pathlib import Path
from zipfile import ZipFile


ORIGEM = Path(
    "analise_documentos/451655/pecas_download"
)

DESTINO = Path(
    "analise_documentos/451655/extraido"
)


def extrair_zip_recursivo(
    ficheiro_zip: Path,
    destino: Path,
):
    """
    Extrai ZIP e procura ZIPs internos.
    """

    print(f"\n📦 A extrair: {ficheiro_zip.name}")

    with ZipFile(ficheiro_zip) as zip_file:

        nomes = zip_file.namelist()

        for nome in nomes:
            print("-", nome)

        zip_file.extractall(destino)


    # procurar novos ZIPs
    for ficheiro in destino.rglob("*"):

        if (
            ficheiro.is_file()
            and ficheiro.suffix.lower() == ".zip"
        ):
            nova_pasta = ficheiro.parent / ficheiro.stem

            nova_pasta.mkdir(
                exist_ok=True
            )

            extrair_zip_recursivo(
                ficheiro,
                nova_pasta,
            )


def listar_documentos(
    pasta: Path,
):
    print("\n📄 DOCUMENTOS FINAIS")
    print("-------------------")

    for ficheiro in pasta.rglob("*"):

        if ficheiro.is_file():

            print(
                ficheiro.relative_to(pasta)
            )


def main():

    DESTINO.mkdir(
        parents=True,
        exist_ok=True,
    )

    extrair_zip_recursivo(
        ORIGEM,
        DESTINO,
    )

    listar_documentos(
        DESTINO
    )

    print("\n✅ Extração completa")


if __name__ == "__main__":
    main()
