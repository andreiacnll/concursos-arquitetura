from pathlib import Path
import json


PASTA = Path(
    "analise_documentos/451655/extraido"
)


def classificar(nome: str):

    nome = nome.lower()

    tipos = []

    if "programa" in nome:
        tipos.append("programa_procedimento")

    if (
        "caderno" in nome
        or "_ce" in nome
    ):
        tipos.append("caderno_encargos")

    if (
        "planta" in nome
        or "desenho" in nome
        or "dwg" in nome
        or "dwf" in nome
    ):
        tipos.append("pecas_desenhadas")

    if (
        "levantamento" in nome
        or "topograf" in nome
    ):
        tipos.append("levantamento")

    if (
        nome.endswith(".zip")
    ):
        tipos.append("arquivo_comprimido")

    if (
        nome.endswith(".xlsx")
        or nome.endswith(".xls")
    ):
        tipos.append("mapa_quantidades")

    return tipos


def main():

    resultado = []

    for ficheiro in PASTA.rglob("*"):

        if ficheiro.is_file():

            tipos = classificar(
                ficheiro.name
            )

            resultado.append(
                {
                    "ficheiro": str(
                        ficheiro.relative_to(PASTA)
                    ),
                    "tipos": tipos,
                }
            )

    print(
        json.dumps(
            resultado,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
