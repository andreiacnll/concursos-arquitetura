from pathlib import Path
from zipfile import ZipFile


ZIP = Path(
    "analise_documentos/450837/pecas.zip"
)


def main():

    with ZipFile(ZIP) as z:

        ficheiros = z.namelist()

        print("TOTAL:", len(ficheiros))
        print()

        for f in ficheiros:
            print(f)


if __name__ == "__main__":
    main()
