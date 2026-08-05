import re


def analisar_criterios(texto: str) -> dict:

    texto_original = texto
    texto = texto.lower()


    resultado = {
        "preco_percentagem": None,
        "qualidade_percentagem": None,
        "subfatores": [],
        "barreiras": [],
    }


    # Procurar percentagens associadas a preço/qualidade

    padrao_preco = re.search(
        r"preço.{0,80}?(\d{1,3})\s*%",
        texto
    )

    if padrao_preco:
        resultado["preco_percentagem"] = int(
            padrao_preco.group(1)
        )


    padrao_qualidade = re.search(
        r"(qualidade|valia técnica).{0,80}?(\d{1,3})\s*%",
        texto
    )

    if padrao_qualidade:
        resultado["qualidade_percentagem"] = int(
            padrao_qualidade.group(2)
        )


    # Subfatores

    termos = [
        "experiência do autor",
        "experiência da equipa",
        "experiência profissional",
        "metodologia",
        "memória descritiva",
        "solução técnica",
        "coordenação de projeto",
    ]


    for termo in termos:
        if termo in texto:
            resultado["subfatores"].append(
                termo
            )


    # Barreiras

    barreiras = [
        "pontuação 0",
        "nota mínima",
        "preço anormalmente baixo",
        "experiência obrigatória",
        "projetos similares",
    ]


    for barreira in barreiras:
        if barreira in texto:
            resultado["barreiras"].append(
                barreira
            )


    return resultado
