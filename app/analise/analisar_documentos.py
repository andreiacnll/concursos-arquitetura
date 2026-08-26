from pathlib import Path
import json

from classificador import classificar_documento


PASTA_RAIZ = Path(
    "analise_documentos/450837"
)


def main():

    documentos = []

    resumo = {

        "total_documentos": 0,

        "programa_procedimento": False,
        "caderno_encargos": False,
        "programa_preliminar": False,
        "levantamento": False,
        "pecas_desenhadas": False,
        "cartografia": False,
        "mapa_quantidades": False,
        "elementos_prediais": False,
        "condicoes_tecnicas": False,

    }


    vistos = set()


    for ficheiro in PASTA_RAIZ.rglob("*"):

            if ficheiro.is_file():

                if ficheiro.suffix.lower() in [
                    ".zip",
                    ".json"
                ]:
                    continue

                nome = str(
                    ficheiro.relative_to(PASTA_RAIZ)
                )

                if nome in vistos:
                    continue

                vistos.add(nome)


                tipos = classificar_documento(
                    ficheiro.name
                )


                resumo["total_documentos"] += 1


                for tipo in tipos:
                    resumo[tipo] = True


                documentos.append(
                    {
                        "nome": nome,
                        "tipos": tipos
                    }
                )


    elementos_score = {

        "levantamento": 20,
        "pecas_desenhadas": 20,
        "programa_preliminar": 20,
        "mapa_quantidades": 15,
        "cartografia": 15,
        "condicoes_tecnicas": 10,

    }


    score = sum(
        valor
        for chave, valor in elementos_score.items()
        if resumo[chave]
    )


    if score >= 80:
        nivel = "muito_alta"
    elif score >= 50:
        nivel = "alta"
    elif score >= 25:
        nivel = "media"
    else:
        nivel = "baixa"


    resultado = {

        "concurso_id": "450837",

        "preparacao": {
            "score": score,
            "nivel": nivel,
        },

        "resumo": resumo,

        "documentos": documentos,

    }


    destino = Path(
        "analise_documentos/450837/analise.json"
    )


    destino.write_text(
        json.dumps(
            resultado,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    print(
        json.dumps(
            resultado,
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
