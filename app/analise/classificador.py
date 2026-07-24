REGRAS_DOCUMENTOS = {

    "programa_procedimento": [
        "programa_procedimento",
        "programa do concurso",
        "programa_procedimento_",
    ],

    "caderno_encargos": [
        "caderno",
        "caderno_",
        "_ce",
    ],

    "programa_preliminar": [
        "programa_preliminar",
        "programa preliminar",
    ],

    "levantamento": [
        "levant",
        "topog",
    ],

    "pecas_desenhadas": [
        "peca",
        "peça",
        "desenh",
    ],

    "cartografia": [
        "cartograf",
    ],

    "mapa_quantidades": [
        "mapa",
        "quantidades",
    ],

    "elementos_prediais": [
        "prediais",
    ],

    "condicoes_tecnicas": [
        "condicoes",
        "condições",
        "tecnicas",
    ],

}


def classificar_documento(nome):

    nome = nome.lower()

    resultado = []

    for tipo, palavras in REGRAS_DOCUMENTOS.items():

        for palavra in palavras:

            if palavra in nome:
                resultado.append(tipo)
                break

    return resultado
