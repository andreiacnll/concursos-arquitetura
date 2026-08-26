from pathlib import Path
from zipfile import ZipFile


ZIP = Path(
    "analise_documentos/450837/pecas.zip"
)


def main():

    with ZipFile(ZIP) as z:

        for nome in z.namelist():

            if nome.lower().endswith(".zip"):
                print(nome)


if __name__ == "__main__":
    main()
