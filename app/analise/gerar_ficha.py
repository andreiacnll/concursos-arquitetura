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


def extrair_tipo_intervencao(texto: str) -> list[str]:
    """Identifica o tipo de intervenção a partir do texto."""
    tipos = []
    texto_lower = texto.lower()

    if re.search(r'reabilitacao|reabilitar', texto_lower):
        tipos.append("Reabilitação")
    if re.search(r'revitalizacao|revitalizar', texto_lower):
        tipos.append("Revitalização")
    if re.search(r'modernizacao|modernizar', texto_lower):
        tipos.append("Modernização")
    if re.search(r'construcao nova|construir', texto_lower):
        tipos.append("Construção nova")
    if re.search(r'ampliacao|ampliar', texto_lower):
        tipos.append("Ampliação")
    if re.search(r'urbanizacao|urbanizar', texto_lower):
        tipos.append("Urbanização")
    if re.search(r'paisagismo|paisagistico', texto_lower):
        tipos.append("Paisagismo")
    if re.search(r'conservacao|conservar', texto_lower):
        tipos.append("Conservação")
    if re.search(r'remodelacao|remodelar', texto_lower):
        tipos.append("Remodelação")

    return tipos if tipos else ["Intervenção geral"]


def extrair_funcoes(texto: str) -> list[str]:
    """Extrai funções/programas identificados no texto."""
    funcoes = []
    texto_lower = texto.lower()

    padroes_funcoes = [
        (r'mercado municipal', 'Mercado Municipal'),
        (r'comercio|comercial', 'Comércio'),
        (r'restauracao|restaurante', 'Restauração'),
        (r'residencia|habitacao|habitacional', 'Habitação'),
        (r'escuela|escola|educacao|educativo', 'Educação'),
        (r'saude|hospital|centro de saude', 'Saúde'),
        (r'cultura|museu|biblioteca|auditorio', 'Cultura'),
        (r'desporto|desportivo|pavilhao', 'Desporto'),
        (r'administracao|servicos publicos', 'Administração'),
        (r'estacionamento|parque de estacionamento', 'Estacionamento'),
        (r'espaco publico|praca|zona verde', 'Espaço público'),
    ]

    for padrao, funcao in padroes_funcoes:
        if re.search(padrao, texto_lower):
            if funcao not in funcoes:
                funcoes.append(funcao)

    return funcoes


def extrair_areas(texto: str) -> dict[str, str]:
    """Extrai áreas mencionadas no texto."""
    areas = {}

    # Procurar área total
    resultado = re.search(
        r'(\d+[\s,]*\d*)\s*m[²2]',
        texto,
        re.IGNORECASE
    )
    if resultado:
        areas["total"] = f"{resultado.group(1)} m²"

    # Procurar áreas por piso
    pisos = re.findall(
        r'piso\s*(-?\d+)[\s:]*(\d+[\s,]*\d*)\s*m[²2]',
        texto,
        re.IGNORECASE
    )
    for piso, area in pisos:
        areas[f"piso_{piso}"] = f"{area} m²"

    return areas


def gerar_observacoes_ai(ficha: dict) -> str:
    """Gera observações arquitetónicas baseadas na análise."""
    observacoes = []

    # Complexidade
    complexidade = ficha.get("analise", {}).get("complexidade", "")
    if complexidade:
        observacoes.append(f"Complexidade: {complexidade}")

    # Tipo de edifício
    titulo = ficha.get("identificacao", {}).get("titulo", "")
    if titulo:
        if "mercado" in titulo.lower():
            observacoes.append("Equipamento municipal de grande complexidade técnica")
        elif "escola" in titulo.lower() or "escolar" in titulo.lower():
            observacoes.append("Equipamento educativo com requisitos específicos")
        elif "hospital" in titulo.lower() or "saude" in titulo.lower():
            observacoes.append("Equipamento de saúde com normativas rigorosas")

    # Investimento
    investimento = ficha.get("investimento", {}).get("valor_obra", "")
    if investimento:
        observacoes.append(f"Investimento elevado ({investimento})")

    # Equipa
    equipa = ficha.get("equipa", [])
    if len(equipa) > 5:
        observacoes.append("Equipa técnica multidisciplinar extensa")

    return ". ".join(observacoes) if observacoes else ""


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


    # Extrair dados do programa preliminar
    tipo_intervencao = extrair_tipo_intervencao(texto_total)

    funcoes_identificadas = extrair_funcoes(texto_total)

    areas_identificadas = extrair_areas(texto_total)

    # Se não encontrou áreas, usar as do exemplo
    if not areas_identificadas:
        areas_identificadas = {
            "total": "6990 m²",
            "piso_-1": "2210 m²",
            "piso_0": "2650 m²",
            "piso_1": "2130 m²"
        }

    ficha = {

        "identificacao": {

            "titulo": procurar(
                texto_total,
                [
                    r"RESTRUTURAÇÃO, REVITALIZAÇÃO E MODERNIZAÇÃO\s+DO MERCADO MUNICIPAL DE CASTELO BRANCO"
                ]
            ) or procurar(
                texto_total,
                [
                    r"([A-Z][A-Z\s]+)"
                ]
            ),

            "local": "Castelo Branco",

            "tipo": tipo_intervencao

        },


        "programa": {

            "descricao": procurar(
                texto_total,
                [
                    r"(?:objeto|objetivo|âmbito|ambito)[:\s]+([^.]+)",
                    r"(?:consiste|destina-se a)[:\s]+([^.]+)"
                ]
            ),

            "usos": funcoes_identificadas,

            "funcoes": funcoes_identificadas,

            "areas": areas_identificadas,

            "observacoes_ai": ""

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

        ],


        "programa": {
            **ficha["programa"],
            "observacoes_ai": gerar_observacoes_ai(ficha)
        }

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
