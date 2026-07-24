from pathlib import Path
from zipfile import ZipFile


ZIP_PRINCIPAL = Path(
    "analise_documentos/450837/pecas.zip"
)

DESTINO = Path(
    "analise_documentos/450837/pecas_procedimentais"
)


ALVO = (
    "Processo Concurso/"
    "3_Pe_as_Procedimentais.zip"
)


def main():

    DESTINO.mkdir(
        parents=True,
        exist_ok=True
    )

    print("A procurar ZIP interno...")

    with ZipFile(ZIP_PRINCIPAL) as principal:

        dados = principal.read(ALVO)

        zip_interno = DESTINO / "pecas_procedimentais.zip"

        zip_interno.write_bytes(
            dados
        )

        print(
            "Extraído:",
            zip_interno
        )


    print("A abrir ZIP interno...")

    with ZipFile(zip_interno) as z:

        print()
        print("DOCUMENTOS:")
        print("----------------")

        for nome in z.namelist():
            print(nome)

        z.extractall(
            DESTINO / "extraido"
        )

    print()
    print("✅ Concluído")


if __name__ == "__main__":
    main()
