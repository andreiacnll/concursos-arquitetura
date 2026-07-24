import re


def normalizar_subfatores(subfatores):

    resultado = []


    for item in subfatores:

        titulo = item["titulo"]
        texto = item["descricao"]

        # normalizar espaços e quebras de linha do PDF
        texto = re.sub(
            r"\s+",
            " ",
            texto
        ).strip()


        funcao = "Equipa técnica"


        if "COORDENAÇÃO" in titulo.upper():
            funcao = "Coordenação de projeto"

        elif "ARQUITETURA" in titulo.upper():
            funcao = "Autor de arquitetura"

        elif "ESTABILIDADE" in titulo.upper():
            funcao = "Estruturas"

        elif "ELÉTRICAS" in titulo.upper():
            funcao = "Instalações elétricas"

        elif "AVAC" in titulo.upper():
            funcao = "AVAC"

        elif "ACÚSTICA" in titulo.upper():
            funcao = "Acústica"

        elif "SCIE" in titulo.upper():
            funcao = "SCIE"


        experiencia = []


        if (
            "Mercado Municipal Coberto" in texto
            or "mercado municipal coberto" in texto.lower()
            or "mercado municipal" in texto.lower()
        ):
            experiencia.append(
                "Mercado Municipal Coberto"
            )


        if "residencial" in texto.lower():
            experiencia.append(
                "Edifício residencial/coletivo"
            )


        if "público/comercial" in texto.lower():
            experiencia.append(
                "Edifício público/comercial"
            )


        caracteristicas = []


        vao = re.findall(
            r"Vão de nave.*?(\d+)\s*m",
            texto,
            flags=re.I
        )

        if vao:
            caracteristicas.append(
                f"Vão mínimo {vao[0]} m"
            )


        pe = re.findall(
            r"Pé-direito livre.*?(\d+)\s*m",
            texto,
            flags=re.I
        )

        if pe:
            caracteristicas.append(
                f"Pé-direito mínimo {pe[0]} m"
            )


        quantidade = re.findall(
            r"(\d+)\s+Projeto",
            texto,
            flags=re.I
        )

        resultado.append(
            {
                "funcao": funcao,
                "experiencia": experiencia,
                "quantidade_projetos": quantidade[:3],
                "caracteristicas": caracteristicas
            }
        )


    return resultado
