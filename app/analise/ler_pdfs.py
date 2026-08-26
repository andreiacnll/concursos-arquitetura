from pathlib import Path
from pypdf import PdfReader


PASTA = Path(
    "analise_documentos/451655/extraido"
)


def ler_pdf(path: Path):

    try:
        reader = PdfReader(path)

        texto = ""

        for pagina in reader.pages:
            texto += pagina.extract_text() or ""

        return texto.strip()

    except Exception as erro:
        print(
            "Erro:",
            path,
            erro
        )
        return ""


def main():

    for pdf in PASTA.rglob("*.pdf"):

        print("\n================")
        print(pdf.name)
        print("================")

        texto = ler_pdf(pdf)

        print(
            texto[:1000]
        )


if __name__ == "__main__":
    main()
