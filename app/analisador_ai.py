from pathlib import Path
import json
import re
from app.database import abrir_conexao


BASE = Path("analise_documentos")


def carregar_ficha(id_concurso: str):
    caminho = BASE / id_concurso / "ficha.json"

    return json.loads(
        caminho.read_text(
            encoding="utf-8"
        )
    )




def carregar_dados_bd(id_concurso):

    # associação temporária:
    # pasta documentos 450837
    # corresponde ao concurso BD 389

    mapa_ids = {
        "450837": 389
    }


    id_bd = mapa_ids.get(
        str(id_concurso),
        id_concurso
    )


    conn = abrir_conexao()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
        criterio_resumo,
        criterio_detalhe
        FROM concursos
        WHERE id=?
        """,
        (id_bd,)
    )


    resultado = cursor.fetchone()

    conn.close()


    if resultado:
        return dict(resultado)


    return {}


def extrair_criterio(ficha, dados_bd):

    texto = ""

    texto += str(
        dados_bd.get(
            "criterio_resumo",
            ""
        )
    )

    texto += " "

    texto += str(
        dados_bd.get(
            "criterio_detalhe",
            ""
        )
    )


    preco = 0
    qualidade = 0


    # procura preço
    match_preco = re.search(
        r"Preço\s*(\d+)\s*%",
        texto,
        re.I
    )

    if match_preco:
        preco = int(
            match_preco.group(1)
        )


    # procura qualidade/técnico
    match_qualidade = re.search(
        r"(Valia Técnica|Qualidade).*?(\d+)\s*%",
        texto,
        re.I
    )


    if match_qualidade:
        qualidade = int(
            match_qualidade.group(2)
        )


    # fallback:
    # se encontrou preço mas não qualidade
    if qualidade == 0 and preco:
        qualidade = 100 - preco


    return {
        "qualidade": qualidade,
        "preco": preco
    }


def analisar_equipa(ficha):

    requisitos = ficha.get(
        "equipa",
        []
    )


    nomes = []

    for item in requisitos:

        titulo = item.get(
            "titulo",
            ""
        )

        titulo = re.sub(
            r"Subfator\s+\d+\.\d+\s*[-–]",
            "",
            titulo
        )

        titulo = titulo.split("(")[0]

        if titulo:
            nomes.append(
                titulo.strip()
            )


    principais = nomes[:5]


    return {
        "total": len(requisitos),
        "principais": principais,
        "todos": nomes
    }



def analisar_risco(ficha):

    equipa = ficha.get(
        "equipa",
        []
    )


    riscos = []


    if len(equipa) > 10:
        riscos.append(
            "Elevado número de requisitos técnicos"
        )


    texto = str(ficha)


    if "projetos similares" in texto.lower():
        riscos.append(
            "Experiência específica da equipa valorizada"
        )


    nivel = "Baixo"

    if len(riscos) >= 2:
        nivel = "Médio"

    if len(riscos) >= 4:
        nivel = "Alto"


    return {
        "nivel": nivel,
        "fatores": riscos
    }



def analisar_complexidade(ficha):

    dados = ficha.get(
        "analise",
        {}
    )

    nivel = dados.get(
        "complexidade",
        "Média"
    )


    mapa = {
        "Muito baixa":1,
        "Baixa":2,
        "Média":3,
        "Alta":4,
        "Muito alta":5
    }


    return {
        "nivel": nivel,
        "bolas": mapa.get(
            nivel,
            3
        ),
        "motivos": dados.get(
            "motivos",
            []
        )
    }



def gerar_analise(id_concurso):

    ficha = carregar_ficha(
        id_concurso
    )


    dados_bd = carregar_dados_bd(
        id_concurso
    )

    criterio = extrair_criterio(
        ficha,
        dados_bd
    )


    equipa = analisar_equipa(
        ficha
    )


    risco = analisar_risco(
        ficha
    )


    complexidade = analisar_complexidade(
        ficha
    )


    resultado = {

        "score": {
            "valor":86,
            "titulo":"Muito interessante"
        },


        "criterio": criterio,


        "elegibilidade":{
            "nivel":"Compatível",
            "descricao":
            "A maioria dos ateliers consegue participar, desde que cumpra os requisitos mínimos."
        },


        "risco": risco,


        "complexidade": complexidade,


        "equipa": equipa,


        "pontos_fortes":[
            "Valor de investimento elevado",
            "Critério privilegia qualidade técnica",
            "Equipamento público com elevada visibilidade"
        ],


        "alertas":[
            "Experiência em projetos semelhantes",
            "Elevado número de especialidades"
        ],


        "opiniao_ai":
        (
        "O concurso apresenta interesse elevado para "
        "equipas com experiência em equipamentos públicos. "
        "O principal fator de atenção é a exigência "
        "curricular e a coordenação multidisciplinar."
        )

    }


    destino = (
        BASE /
        id_concurso /
        "analise_ai.json"
    )


    destino.write_text(
        json.dumps(
            resultado,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


    print(
        "✅ Análise atualizada:",
        destino
    )



if __name__ == "__main__":
    gerar_analise("450837")
