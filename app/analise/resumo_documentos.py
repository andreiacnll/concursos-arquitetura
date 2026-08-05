from pathlib import Path
from classificar_documentos import classificar
import json


PASTA = Path(
    "analise_documentos/451655/extraido"
)


def main():

    resumo = {
        "total_ficheiros": 0,
        "programa_procedimento": False,
        "caderno_encargos": False,
        "pecas_desenhadas": False,
        "levantamento": False,
        "mapa_quantidades": False,
        "arquivos": False,
    }

    for ficheiro in PASTA.rglob("*"):

        if ficheiro.is_file():

            resumo["total_ficheiros"] += 1

            tipos = classificar(
                ficheiro.name
            )

            if "programa_procedimento" in tipos:
                resumo["programa_procedimento"] = True

            if "caderno_encargos" in tipos:
                resumo["caderno_encargos"] = True

            if "pecas_desenhadas" in tipos:
                resumo["pecas_desenhadas"] = True

            if "levantamento" in tipos:
                resumo["levantamento"] = True

            if "mapa_quantidades" in tipos:
                resumo["mapa_quantidades"] = True

            if "arquivo_comprimido" in tipos:
                resumo["arquivos"] = True


    pontos = sum(
        [
            resumo["programa_procedimento"],
            resumo["caderno_encargos"],
            resumo["pecas_desenhadas"],
            resumo["levantamento"],
            resumo["mapa_quantidades"],
        ]
    )

    if pontos >= 4:
        resumo["complexidade"] = "alta"
    elif pontos >= 2:
        resumo["complexidade"] = "média"
    else:
        resumo["complexidade"] = "baixa"


    print(
        json.dumps(
            resumo,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
