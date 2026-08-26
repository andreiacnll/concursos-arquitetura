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


def analisar_criterios_documentos(documentos):
    """Agrega criterios documento a documento sem lowercase global."""
    resultado = {
        "preco_percentagem": None,
        "qualidade_percentagem": None,
        "subfatores": [],
        "barreiras": [],
    }
    vistos = {"subfatores": set(), "barreiras": set()}
    for documento in documentos:
        analisado = analisar_criterios(str(documento or ""))
        for campo in ("preco_percentagem", "qualidade_percentagem"):
            if resultado[campo] is None and analisado[campo] is not None:
                resultado[campo] = analisado[campo]
        for campo in ("subfatores", "barreiras"):
            for valor in analisado[campo]:
                if valor not in vistos[campo]:
                    vistos[campo].add(valor)
                    resultado[campo].append(valor)
    return resultado
