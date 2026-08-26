def gerar_perfil_concurso(
    criterios: dict,
    equipa: list
):

    analise = {
        "nivel": "",
        "resumo": "",
        "pontos_decisivos": [],
        "perfil_recomendado": ""
    }


    qualidade = criterios.get(
        "qualidade_percentagem"
    )

    preco = criterios.get(
        "preco_percentagem"
    )


    # Avaliação da exigência

    pontos = 0


    if qualidade and qualidade >= 60:
        pontos += 2

    if len(equipa) >= 5:
        pontos += 1


    experiencias = []

    for elemento in equipa:
        experiencias.extend(
            elemento.get(
                "experiencia",
                []
            )
        )


    if "Mercado Municipal Coberto" in experiencias:
        pontos += 2


    if pontos >= 4:
        analise["nivel"] = "Elevada"
    elif pontos >= 2:
        analise["nivel"] = "Média"
    else:
        analise["nivel"] = "Baixa"



    # Texto automático

    if qualidade:
        analise["resumo"] = (
            f"A avaliação privilegia a componente técnica "
            f"da proposta ({qualidade}%), face ao preço "
            f"({preco}%)."
        )


    analise["pontos_decisivos"] = [
        "Experiência específica da equipa técnica",
        "Projetos similares",
        "Capacidade multidisciplinar"
    ]


    if "Mercado Municipal Coberto" in experiencias:
        analise["pontos_decisivos"].append(
            "Experiência prévia em Mercado Municipal Coberto"
        )


    analise["perfil_recomendado"] = (
        "Ateliers com experiência em equipamentos "
        "públicos complexos e equipas multidisciplinares."
    )


    return analise
