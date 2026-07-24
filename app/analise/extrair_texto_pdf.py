from pathlib import Path
from pypdf import PdfReader
import json


PASTA = Path(
    "analise_documentos/450837"
)




def extrair_pdf(pdf):

    texto = ""

    try:

        reader = PdfReader(pdf)

        for pagina in reader.pages:
            texto += (
                pagina.extract_text()
                or ""
            )

    except Exception as e:

        print(
            "Erro:",
            pdf,
            e
        )

    return texto


def main():

    resultado = {}

    for pdf in PASTA.rglob("*.pdf"):

        print(
            "A ler:",
            pdf.name
        )

        texto_pdf = extrair_pdf(
            pdf
        )

        if texto_pdf.strip():
            resultado[pdf.name] = texto_pdf


    destino = Path(
        "analise_documentos/450837/textos.json"
    )

    destino.write_text(
        json.dumps(
            resultado,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    print()
    print(
        "✅ Textos guardados:",
        destino
    )


if __name__ == "__main__":
    main()
