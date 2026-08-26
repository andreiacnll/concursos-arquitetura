from pathlib import Path
import fitz
import sys


def extrair_texto_pdf(pdf: Path) -> str:
    texto = ""

    try:
        doc = fitz.open(pdf)

        for pagina in doc:
            texto += pagina.get_text()

        doc.close()

    except Exception as erro:
        print(f"Erro a ler {pdf}: {erro}")

    return texto.lower()



def classificar_documento(texto: str) -> str:

    texto = texto.lower()


    # Critérios de avaliação
    if (
        "critério de adjudicação" in texto
        or "critérios de adjudicação" in texto
        or "fatores de avaliação" in texto
        or "subfator" in texto
        or "valia técnica" in texto
    ):
        return "criterios_adjudicacao"


    # Experiência / equipa
    if (
        "autor do projeto" in texto
        or "coordenador de projeto" in texto
        or "experiência profissional" in texto
        or "qualificação dos técnicos" in texto
    ):
        return "valia_equipa"


    # Peças desenhadas
    if (
        "peças desenhadas" in texto
        or "planta" in texto
        or "alçado" in texto
        or "corte" in texto
        or "levantamento arquitetónico" in texto
    ):
        return "pecas_desenhadas"


    # Programa preliminar
    if (
        "programa funcional" in texto
        or "objetivo principal" in texto
        or "objetivos específicos" in texto
        or "âmbito da intervenção" in texto
    ):
        return "programa_preliminar"


    return "outro"



def analisar_concurso(id_concurso: str):

    base = Path(
        f"analise_documentos/{id_concurso}"
    )

    if not base.exists():
        print("Pasta não encontrada:", base)
        return


    pdfs = list(base.rglob("*.pdf"))

    print()
    print("=" * 60)
    print(f"ANÁLISE DOCUMENTOS - CONCURSO {id_concurso}")
    print("=" * 60)
    print()


    encontrados = {}


    for pdf in pdfs:

        texto = extrair_texto_pdf(pdf)

        tipo = classificar_documento(texto)

        encontrados[pdf.name] = tipo

        print("📄", pdf.name)
        print("   →", tipo)
        print()


    print("=" * 60)
    print("RESUMO")
    print("=" * 60)


    for tipo in sorted(set(encontrados.values())):
        quantidade = list(encontrados.values()).count(tipo)

        print(
            f"✓ {tipo}: {quantidade}"
        )



if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(
            "Uso: python3 app/analisador_documentos.py ID"
        )
        sys.exit()


    analisar_concurso(sys.argv[1])
