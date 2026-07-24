from pathlib import Path
import json
import re
import sys
import json


from equipa import analisar_equipa
from normalizador_equipa import normalizar_subfatores
from gerador import gerar_perfil_concurso


if len(sys.argv) < 2:
    raise SystemExit(
        "Uso: python3 gerar_ficha.py ID_CONCURSO"
    )


ID_CONCURSO = sys.argv[1]


BASE = Path("analise_documentos") / ID_CONCURSO

TEXTOS = BASE / "textos.json"
SAIDA = BASE / "ficha.json"


def procurar(texto, padroes):
    for p in padroes:
        resultado = re.search(
            p,
            texto,
            re.IGNORECASE
        )
        if resultado:
            valor = (
                resultado.group(1)
                if resultado.lastindex
                else resultado.group(0)
            )

            return " ".join(
                valor.split()
            )
    return None


def main():

    dados = json.loads(
        TEXTOS.read_text(
            encoding="utf-8"
        )
    )

    texto_total = "\n".join(
        dados.values()
    )


    equipa_dados = analisar_equipa(
        texto_total
    )


    equipa_normalizada = equipa_dados["subfatores_equipa"]


    perfil = gerar_perfil_concurso(
        {
            "preco_percentagem": 40,
            "qualidade_percentagem": 60
        },
        equipa_normalizada
    )


    ficha = {

        "identificacao": {

            "titulo": procurar(
                texto_total,
                [
                    r"RESTRUTURAÇÃO, REVITALIZAÇÃO E MODERNIZAÇÃO\s+DO MERCADO MUNICIPAL DE CASTELO BRANCO"
                ]
            ),

            "local": "Castelo Branco",

            "tipo": [
                "Reabilitação",
                "Revitalização",
                "Modernização"
            ]

        },


        "programa": {

            "usos": [
                "Mercado Municipal",
                "Comércio",
                "Restauração",
                "Residências temporárias"
            ],

            "areas": {
                "total": "6990 m²",
                "piso_-1": "2210 m²",
                "piso_0": "2650 m²",
                "piso_1": "2130 m²"
            }

        },


        "investimento": {

            "valor_obra": "8.600.000 €",

            "prazo_projeto": "180 dias"

        },


        "analise": {

            "complexidade": "Muito alta",

            "nivel": 5,

            "motivos": [
                "Edifício existente",
                "Alteração funcional profunda",
                "Integração de várias especialidades",
                "Intervenção interior e exterior"
            ]

        },


        "documentos": {

            "programa_preliminar": True,

            "levantamento": True,

            "pecas_desenhadas": True,

            "mapa_quantidades": True,

            "cartografia": True

        },


        "equipa": equipa_normalizada,


        "estrategia": perfil,


        "decisao": {

            "score": 86,

            "classificacao": "Muito interessante",


            "elegibilidade": {

                "estado": "Requer experiência",

                "motivos": [
                    "Experiência específica da equipa técnica",
                    "Experiência em projetos similares"
                ]

            },


            "oportunidades": [

                "Critério privilegia qualidade técnica",

                "Valor de investimento elevado",

                "Equipamento público com elevada visibilidade"

            ],


            "riscos": [

                "Equipa multidisciplinar extensa",

                "Necessidade de comprovação curricular",

                "Experiência específica valorizada"

            ]

        },


        "temas": [

            "Reabilitação urbana",

            "Sustentabilidade",

            "Eficiência energética",

            "Espaço público",

            "Equipamento municipal"

        ]

    }


    SAIDA.write_text(
        json.dumps(
            ficha,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    print("✅ Ficha criada:")
    print(SAIDA)


if __name__ == "__main__":
    main()
