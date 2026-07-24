import re


def extrair_subfatores(texto):

    resultado = []

    padrao = r"(SUBFATOR\s+2\.\d+.*?)(?=SUBFATOR\s+2\.\d+|$)"

    blocos = re.findall(
        padrao,
        texto,
        flags=re.I | re.S
    )

    for bloco in blocos:

        linhas = [
            l.strip()
            for l in bloco.splitlines()
            if l.strip()
        ]

        if not linhas:
            continue


        titulo = linhas[0]


        # remover lixo inicial
        conteudo = " ".join(linhas[1:])


        resultado.append(
            {
                "titulo": titulo,
                "descricao": conteudo[:2000]
            }
        )


    return resultado



def analisar_equipa(texto: str):

    texto_lower = texto.lower()


    resultado = {
        "especialidades": [],
        "experiencia_exigida": [],
        "subfatores_equipa": [],
        "alertas": []
    }


    especialidades = [
        "arquitetura",
        "estruturas",
        "instalações elétricas",
        "avac",
        "acústica",
        "scie"
    ]


    for item in especialidades:
        if item in texto_lower:
            resultado["especialidades"].append(item)



    resultado["subfatores_equipa"] = extrair_subfatores(texto)



    if len(resultado["subfatores_equipa"]) > 0:
        resultado["alertas"].append(
            "A experiência específica da equipa é valorizada na avaliação."
        )


    return resultado
