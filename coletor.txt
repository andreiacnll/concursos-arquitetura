"""
Coletor de anúncios públicos do Portal BASE.

Este módulo:

1. Consulta a listagem pública de anúncios do Portal BASE.
2. Limita os resultados ao intervalo de datas configurado.
3. Faz um pré-filtro textual para reduzir pedidos desnecessários.
4. Consulta o detalhe dos anúncios candidatos.
5. Devolve os dados completos no formato esperado pela aplicação.

Não necessita de token de API.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


URL_PESQUISA = (
    "https://www.base.gov.pt/Base4/pt/pesquisa/"
    "?atedatapublicacao="
    "&ateprecobase="
    "&cpv="
    "&desdedatapublicacao="
    "&desdeprecobase="
    "&emissora="
    "&numeroanuncio="
    "&texto="
    "&tipoacto=0"
    "&tipocontrato=0"
    "&tipomodelo=0"
    "&type=anuncios"
)

URL_RESULTADOS = (
    "https://www.base.gov.pt/Base4/pt/resultados/"
)

URL_DETALHE = (
    "https://www.base.gov.pt/Base4/pt/detalhe/"
)

VERSAO_PORTAL = os.getenv(
    "BASE_VERSAO_PORTAL",
    "126.0",
)

TIMEOUT_SEGUNDOS = int(
    os.getenv(
        "BASE_TIMEOUT_SEGUNDOS",
        "45",
    )
)

TAMANHO_PAGINA = int(
    os.getenv(
        "BASE_PAGE_SIZE",
        "25",
    )
)

DIAS_A_PESQUISAR = int(
    os.getenv(
        "BASE_DIAS_PESQUISA",
        "2",
    )
)

MAXIMO_PAGINAS = int(
    os.getenv(
        "BASE_MAX_PAGINAS",
        "100",
    )
)

INTERVALO_PEDIDOS = float(
    os.getenv(
        "BASE_INTERVALO_PEDIDOS",
        "0.3",
    )
)

INTERVALO_DETALHES = float(
    os.getenv(
        "BASE_INTERVALO_DETALHES",
        "0.25",
    )
)

MAXIMO_DETALHES = int(
    os.getenv(
        "BASE_MAX_DETALHES",
        "300",
    )
)

MOSTRAR_DIAGNOSTICO = (
    os.getenv(
        "BASE_MOSTRAR_DIAGNOSTICO",
        "1",
    ).strip().lower()
    not in {
        "0",
        "false",
        "nao",
        "não",
        "off",
    }
)


PALAVRAS_CHAVE_FORTES = {
    "arquitetura",
    "arquitetonico",
    "arquitetonica",
    "arquitetónicos",
    "arquitetonicos",
    "arquiteto",
    "arquitectura",
    "arquitectonico",
    "arquitectonica",
    "urbanismo",
    "urbanistico",
    "urbanistica",
    "planeamento urbano",
    "plano de urbanizacao",
    "plano de pormenor",
    "projeto de arquitetura",
    "projecto de arquitectura",
    "estudo previo",
    "levantamento arquitetonico",
    "levantamento topografico",
    "projeto de execucao",
    "projecto de execucao",
    "concurso de concecao",
    "concurso de concepção",
    "concurso de ideias",
    "projetista",
    "projetistas",
}


PALAVRAS_CHAVE_PROJETO = {
    "elaboracao de projeto",
    "elaboracao do projeto",
    "elaboracao de projetos",
    "elaboracao dos projetos",
    "prestacao de servicos para elaboracao",
    "prestacao de servicos de elaboracao",
    "projeto para",
    "projeto da",
    "projeto do",
    "projeto de",
    "projetos de",
    "projeto geral",
    "projeto integrado",
    "projetos de especialidades",
    "projeto de especialidades",
    "estudos e projetos",
    "estudo e projeto",
    "estudos e projectos",
    "estudo e projecto",
    "projeto base",
    "projeto de licenciamento",
    "assistencia tecnica ao projeto",
    "revisao de projeto",
    "revisao do projeto",
    "revisao de projetos",
}


PALAVRAS_CHAVE_EDIFICIOS = {
    "requalificacao",
    "reabilitacao",
    "remodelacao",
    "ampliacao",
    "beneficiacao",
    "reconversao",
    "recuperacao",
    "conservacao",
    "adaptacao",
    "modernizacao",
    "construcao",
    "edificio",
    "edificios",
    "equipamento",
    "equipamentos",
    "escola",
    "escolar",
    "jardim de infancia",
    "creche",
    "biblioteca",
    "museu",
    "mercado municipal",
    "pavilhao",
    "pavilhão",
    "centro cultural",
    "centro comunitario",
    "centro de saude",
    "unidade de saude",
    "habitacao",
    "habitacional",
    "residencia",
    "residencial",
    "instalacoes",
    "instalações",
    "quartel",
    "auditorio",
    "teatro",
    "arquivo",
    "complexo desportivo",
    "piscina",
    "cemiterio",
    "espaco publico",
    "espaço público",
    "praca",
    "praça",
    "parque urbano",
    "arranjo urbanistico",
    "arranjo paisagistico",
}


PALAVRAS_CHAVE_SERVICOS_TECNICOS = {
    "fiscalizacao",
    "coordenação de segurança",
    "coordenacao de seguranca",
    "gestao de projeto",
    "gestão de projeto",
    "consultoria de arquitetura",
    "consultoria tecnica",
    "consultoria técnica",
    "equipa projetista",
    "equipa de projeto",
    "estudo de viabilidade",
    "programa preliminar",
    "programa base",
    "levantamento de edificios",
    "levantamento de edifícios",
    "diagnostico do edificado",
    "diagnóstico do edificado",
}


PALAVRAS_EXCLUSAO = {
    "produtos fitofarmacos",
    "fitofarmacos",
    "manutencao de arvores",
    "manutenção de árvores",
    "abate de arvores",
    "poda de arvores",
    "limpeza urbana",
    "recolha de residuos",
    "residuos urbanos",
    "refeicoes escolares",
    "refeições escolares",
    "generos alimenticios",
    "géneros alimentícios",
    "combustiveis",
    "combustíveis",
    "eletricidade",
    "energia eletrica",
    "gas natural",
    "telecomunicacoes",
    "telecomunicações",
    "seguros",
    "vigilancia",
    "vigilância",
    "limpeza de instalacoes",
    "limpeza de instalações",
    "material de escritorio",
    "material de escritório",
    "equipamento informatico",
    "equipamento informático",
    "software",
    "licenciamento de software",
    "viaturas",
    "pneus",
    "medicamentos",
    "dispositivos medicos",
    "dispositivos médicos",
}


PREFIXOS_CPV_ARQUITETURA = (
    "712",
    "714",
)

CPVS_ARQUITETURA_CONHECIDOS = {
    "71200000",
    "71210000",
    "71220000",
    "71221000",
    "71222000",
    "71223000",
    "71230000",
    "71240000",
    "71241000",
    "71242000",
    "71243000",
    "71244000",
    "71245000",
    "71246000",
    "71247000",
    "71248000",
    "71250000",
    "71251000",
    "71252000",
    "71253000",
    "71254000",
    "71255000",
    "71256000",
    "71400000",
    "71410000",
    "71420000",
}


def criar_sessao() -> requests.Session:
    """
    Cria uma sessão HTTP semelhante à utilizada por um navegador.

    Também configura novas tentativas automáticas para erros temporários.
    """

    sessao = requests.Session()

    politica_novas_tentativas = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.8,
        status_forcelist=(
            429,
            500,
            502,
            503,
            504,
        ),
        allowed_methods=(
            "GET",
            "POST",
        ),
        raise_on_status=False,
    )

    adaptador = HTTPAdapter(
        max_retries=politica_novas_tentativas,
    )

    sessao.mount(
        "https://",
        adaptador,
    )

    sessao.mount(
        "http://",
        adaptador,
    )

    sessao.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "application/json, text/javascript, "
                "text/plain, */*; q=0.01"
            ),
            "Accept-Language": (
                "pt-PT,pt;q=0.9,en;q=0.8"
            ),
            "Content-Type": (
                "application/x-www-form-urlencoded; "
                "charset=UTF-8"
            ),
            "Origin": "https://www.base.gov.pt",
            "Referer": URL_PESQUISA,
            "X-Requested-With": "XMLHttpRequest",
        }
    )

    return sessao


def converter_resposta_json(
    resposta: requests.Response,
) -> dict[str, Any]:
    """
    Converte uma resposta do Portal BASE num dicionário.

    O Portal BASE normalmente devolve JSON válido, apesar de identificar
    a resposta como text/plain.
    """

    try:
        dados = resposta.json()

        if isinstance(
            dados,
            dict,
        ):
            return dados

    except ValueError:
        pass

    texto = resposta.text.strip()

    if texto.startswith("(") and texto.endswith(")"):
        texto = texto[1:-1].strip()

    try:
        dados = json.loads(texto)

    except json.JSONDecodeError as erro:
        excerto = texto[:500]

        raise RuntimeError(
            "O Portal BASE devolveu uma resposta inesperada. "
            f"Estado HTTP: {resposta.status_code}. "
            f"Excerto: {excerto}"
        ) from erro

    if not isinstance(
        dados,
        dict,
    ):
        raise RuntimeError(
            "A resposta do Portal BASE não contém um objeto JSON."
        )

    return dados


def converter_data(
    valor: Any,
) -> date | None:
    """
    Converte datas do Portal BASE em objetos date.
    """

    if valor is None:
        return None

    texto = str(valor).strip()

    if not texto:
        return None

    formatos = (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
    )

    for formato in formatos:
        try:
            return datetime.strptime(
                texto,
                formato,
            ).date()

        except ValueError:
            continue

    return None


def formatar_data(
    valor: Any,
) -> str:
    """
    Normaliza uma data para o formato DD-MM-AAAA.

    Quando o valor não é uma data, mantém o texto original. Isto é necessário
    porque o prazo para propostas pode vir como "3 dias".
    """

    data_convertida = converter_data(
        valor
    )

    if data_convertida is None:
        return normalizar_texto(
            valor
        )

    return data_convertida.strftime(
        "%d-%m-%Y"
    )


def normalizar_texto(
    valor: Any,
) -> str:
    """
    Converte um valor em texto limpo.
    """

    if valor is None:
        return ""

    if isinstance(
        valor,
        bool,
    ):
        return "Sim" if valor else "Não"

    return " ".join(
        str(valor).split()
    )


def normalizar_para_pesquisa(
    valor: Any,
) -> str:
    """
    Normaliza texto para comparação de palavras-chave.

    Remove acentos, converte para minúsculas e reduz espaços.
    """

    texto = normalizar_texto(
        valor
    ).lower()

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(
            caractere
        )
    )

    texto = re.sub(
        r"[^a-z0-9]+",
        " ",
        texto,
    )

    return " ".join(
        texto.split()
    )


def normalizar_conjunto_palavras(
    palavras: set[str],
) -> set[str]:
    """
    Normaliza todas as palavras de um conjunto para pesquisa.
    """

    return {
        normalizar_para_pesquisa(
            palavra
        )
        for palavra in palavras
    }


PALAVRAS_CHAVE_FORTES_NORMALIZADAS = normalizar_conjunto_palavras(
    PALAVRAS_CHAVE_FORTES
)

PALAVRAS_CHAVE_PROJETO_NORMALIZADAS = normalizar_conjunto_palavras(
    PALAVRAS_CHAVE_PROJETO
)

PALAVRAS_CHAVE_EDIFICIOS_NORMALIZADAS = normalizar_conjunto_palavras(
    PALAVRAS_CHAVE_EDIFICIOS
)

PALAVRAS_CHAVE_SERVICOS_NORMALIZADAS = normalizar_conjunto_palavras(
    PALAVRAS_CHAVE_SERVICOS_TECNICOS
)

PALAVRAS_EXCLUSAO_NORMALIZADAS = normalizar_conjunto_palavras(
    PALAVRAS_EXCLUSAO
)


def contem_alguma_palavra(
    texto: str,
    palavras: set[str],
) -> bool:
    """
    Indica se o texto contém alguma expressão do conjunto.
    """

    return any(
        palavra
        and palavra in texto
        for palavra in palavras
    )


def criar_link_detalhe(
    identificador: Any,
) -> str:
    """
    Constrói o endereço público do detalhe do anúncio.
    """

    if identificador in (
        None,
        "",
    ):
        return URL_PESQUISA

    parametros = urlencode(
        {
            "type": "anuncios",
            "id": identificador,
        }
    )

    return f"{URL_DETALHE}?{parametros}"


def obter_data_atual_portugal() -> date:
    """
    Obtém a data atual no fuso horário de Portugal.
    """

    agora = datetime.now(
        ZoneInfo("Europe/Lisbon")
    )

    return agora.date()


def obter_data_minima() -> date:
    """
    Calcula a data mais antiga que deve ser pesquisada.

    Com BASE_DIAS_PESQUISA=2, procura hoje e os dois dias anteriores.
    """

    return (
        obter_data_atual_portugal()
        - timedelta(
            days=DIAS_A_PESQUISAR
        )
    )


def inicializar_sessao(sessao):
    resposta = sessao.get(
        URL_PESQUISA,
        timeout=TIMEOUT_SEGUNDOS,
        allow_redirects=True,
    )

    print("STATUS:", resposta.status_code)
    print("URL FINAL:", resposta.url)
    print("SERVER:", resposta.headers.get("Server"))
    print("CONTENT-TYPE:", resposta.headers.get("Content-Type"))
    print("\nINÍCIO DA RESPOSTA:\n")
    print(resposta.text[:500])

    resposta.raise_for_status()

def descarregar_pagina(
    sessao: requests.Session,
    pagina: int,
) -> dict[str, Any]:
    """
    Obtém uma página de anúncios ordenada pela data de publicação.
    """

    resposta = sessao.post(
        URL_RESULTADOS,
        data={
            "type": "search_anuncios",
            "version": VERSAO_PORTAL,
            "query": "",
            "sort": "-drPublicationDate",
            "page": str(pagina),
            "size": str(TAMANHO_PAGINA),
        },
        timeout=TIMEOUT_SEGUNDOS,
    )

    resposta.raise_for_status()

    return converter_resposta_json(
        resposta
    )


def obter_detalhe_anuncio(
    sessao: requests.Session,
    identificador: str,
) -> dict[str, Any]:
    """
    Consulta os dados completos de um anúncio.

    Endpoint descoberto na própria página de detalhe do Portal BASE:

    type=detail_anuncios
    version=126.0
    id=<identificador>
    """

    referer_anterior = sessao.headers.get(
        "Referer",
        URL_PESQUISA,
    )

    sessao.headers["Referer"] = criar_link_detalhe(
        identificador
    )

    try:
        resposta = sessao.post(
            URL_RESULTADOS,
            data={
                "type": "detail_anuncios",
                "version": VERSAO_PORTAL,
                "id": identificador,
            },
            timeout=TIMEOUT_SEGUNDOS,
        )

        resposta.raise_for_status()

        detalhe = converter_resposta_json(
            resposta
        )

    finally:
        sessao.headers["Referer"] = referer_anterior

    return detalhe


def obter_entidades(
    anuncio: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Obtém a lista de entidades do anúncio.
    """

    entidades = anuncio.get(
        "contractingEntities"
    )

    if isinstance(
        entidades,
        list,
    ):
        return [
            entidade
            for entidade in entidades
            if isinstance(
                entidade,
                dict,
            )
        ]

    return []


def obter_nome_entidade(
    anuncio: dict[str, Any],
) -> str:
    """
    Obtém o nome da entidade adjudicante ou emissora.
    """

    entidades = obter_entidades(
        anuncio
    )

    nomes = []

    for entidade in entidades:
        nome = normalizar_texto(
            entidade.get(
                "description"
            )
        )

        if nome and nome not in nomes:
            nomes.append(
                nome
            )

    if nomes:
        return "; ".join(
            nomes
        )

    campos_alternativos = (
        "contractingEntity",
        "entity",
        "entityName",
        "contractingEntityName",
    )

    for campo in campos_alternativos:
        valor = normalizar_texto(
            anuncio.get(
                campo
            )
        )

        if valor:
            return valor

    return ""


def obter_cpvs(
    anuncio: dict[str, Any],
) -> list[str]:
    """
    Converte os CPVs do Portal BASE numa lista de textos.
    """

    valor = anuncio.get(
        "cpvs"
    )

    if valor is None:
        valor = anuncio.get(
            "cpv"
        )

    if isinstance(
        valor,
        list,
    ):
        resultados = []

        for item in valor:
            if isinstance(
                item,
                dict,
            ):
                codigo = normalizar_texto(
                    item.get("code")
                    or item.get("cpv")
                    or item.get("id")
                )

                descricao = normalizar_texto(
                    item.get("description")
                    or item.get("name")
                )

                texto = ", ".join(
                    parte
                    for parte in (
                        codigo,
                        descricao,
                    )
                    if parte
                )

            else:
                texto = normalizar_texto(
                    item
                )

            if texto and texto not in resultados:
                resultados.append(
                    texto
                )

        return resultados

    texto = normalizar_texto(
        valor
    )

    if not texto:
        return []

    partes = re.split(
        r"\s*[;|]\s*",
        texto,
    )

    resultados = []

    for parte in partes:
        parte = normalizar_texto(
            parte
        )

        if parte and parte not in resultados:
            resultados.append(
                parte
            )

    return resultados


def obter_codigos_cpv(
    anuncio: dict[str, Any],
) -> set[str]:
    """
    Extrai códigos CPV numéricos dos dados do anúncio.
    """

    texto = " ".join(
        obter_cpvs(
            anuncio
        )
    )

    correspondencias = re.findall(
        r"\b(\d{8})(?:-\d)?\b",
        texto,
    )

    return set(
        correspondencias
    )


def possui_cpv_arquitetura(
    anuncio: dict[str, Any],
) -> bool:
    """
    Indica se o anúncio possui um CPV ligado a arquitetura ou urbanismo.
    """

    codigos = obter_codigos_cpv(
        anuncio
    )

    for codigo in codigos:
        if codigo in CPVS_ARQUITETURA_CONHECIDOS:
            return True

        if codigo.startswith(
            PREFIXOS_CPV_ARQUITETURA
        ):
            return True

    return False


def criar_texto_prefiltro(
    anuncio: dict[str, Any],
) -> str:
    """
    Cria o texto usado para decidir se vale a pena consultar o detalhe.
    """

    partes = [
        anuncio.get(
            "contractDesignation"
        ),
        anuncio.get(
            "description"
        ),
        anuncio.get(
            "contractingEntity"
        ),
        anuncio.get(
            "contractingProcedureType"
        ),
        anuncio.get(
            "contractType"
        ),
        anuncio.get(
            "modelType"
        ),
        anuncio.get(
            "type"
        ),
    ]

    return normalizar_para_pesquisa(
        " ".join(
            normalizar_texto(
                parte
            )
            for parte in partes
            if parte
        )
    )


def deve_consultar_detalhe(
    anuncio: dict[str, Any],
) -> bool:
    """
    Decide se um anúncio da listagem merece consulta detalhada.

    O pré-filtro é deliberadamente abrangente para evitar excluir concursos
    relevantes antes de termos acesso ao CPV e à descrição completa.
    """

    texto = criar_texto_prefiltro(
        anuncio
    )

    if not texto:
        return False

    if contem_alguma_palavra(
        texto,
        PALAVRAS_CHAVE_FORTES_NORMALIZADAS,
    ):
        return True

    tem_palavra_projeto = contem_alguma_palavra(
        texto,
        PALAVRAS_CHAVE_PROJETO_NORMALIZADAS,
    )

    tem_edificio_ou_espaco = contem_alguma_palavra(
        texto,
        PALAVRAS_CHAVE_EDIFICIOS_NORMALIZADAS,
    )

    tem_servico_tecnico = contem_alguma_palavra(
        texto,
        PALAVRAS_CHAVE_SERVICOS_NORMALIZADAS,
    )

    if tem_palavra_projeto:
        return True

    if (
        tem_edificio_ou_espaco
        and tem_servico_tecnico
    ):
        return True

    texto_tipo = normalizar_para_pesquisa(
        " ".join(
            [
                normalizar_texto(
                    anuncio.get(
                        "modelType"
                    )
                ),
                normalizar_texto(
                    anuncio.get(
                        "type"
                    )
                ),
            ]
        )
    )

    if (
        "concurso de concecao" in texto_tipo
        or "concurso de ideias" in texto_tipo
    ):
        return True

    return False


def parece_relevante_apos_detalhe(
    anuncio: dict[str, Any],
) -> bool:
    """
    Faz uma validação adicional após obter o detalhe completo.

    Esta função não substitui a análise da IA. Serve apenas para remover casos
    evidentemente alheios à arquitetura.
    """

    texto = criar_texto_completo(
        anuncio
    )

    texto_normalizado = normalizar_para_pesquisa(
        texto
    )

    if possui_cpv_arquitetura(
        anuncio
    ):
        return True

    if contem_alguma_palavra(
        texto_normalizado,
        PALAVRAS_CHAVE_FORTES_NORMALIZADAS,
    ):
        return True

    tem_projeto = contem_alguma_palavra(
        texto_normalizado,
        PALAVRAS_CHAVE_PROJETO_NORMALIZADAS,
    )

    tem_edificio = contem_alguma_palavra(
        texto_normalizado,
        PALAVRAS_CHAVE_EDIFICIOS_NORMALIZADAS,
    )

    tem_servico = contem_alguma_palavra(
        texto_normalizado,
        PALAVRAS_CHAVE_SERVICOS_NORMALIZADAS,
    )

    if tem_projeto:
        return True

    if tem_edificio and tem_servico:
        return True

    tem_exclusao = contem_alguma_palavra(
        texto_normalizado,
        PALAVRAS_EXCLUSAO_NORMALIZADAS,
    )

    if tem_exclusao:
        return False

    return False


def criar_texto_completo(
    anuncio: dict[str, Any],
) -> str:
    """
    Cria o texto completo que será enviado para a análise.
    """

    cpvs = obter_cpvs(
        anuncio
    )

    entidade = obter_nome_entidade(
        anuncio
    )

    partes = [
        (
            "Descrição: "
            + normalizar_texto(
                anuncio.get(
                    "contractDesignation"
                )
            )
        ),
        (
            "Entidade: "
            + entidade
        ),
        (
            "Tipo de ato: "
            + normalizar_texto(
                anuncio.get(
                    "type"
                )
            )
        ),
        (
            "Tipo de modelo: "
            + normalizar_texto(
                anuncio.get(
                    "modelType"
                )
            )
        ),
        (
            "Tipo de contrato: "
            + normalizar_texto(
                anuncio.get(
                    "contractType"
                )
            )
        ),
        (
            "Tipo de procedimento: "
            + normalizar_texto(
                anuncio.get(
                    "contractingProcedureType"
                )
            )
        ),
        (
            "CPV: "
            + "; ".join(
                cpvs
            )
        ),
        (
            "Preço base: "
            + normalizar_texto(
                anuncio.get(
                    "basePrice"
                )
            )
        ),
        (
            "Prazo para propostas: "
            + normalizar_texto(
                anuncio.get(
                    "proposalDeadline"
                )
            )
        ),
        (
            "Data de publicação: "
            + normalizar_texto(
                anuncio.get(
                    "drPublicationDate"
                )
            )
        ),
        (
            "Número do anúncio: "
            + normalizar_texto(
                anuncio.get(
                    "announcementNumber"
                )
            )
        ),
    ]

    resultados = []

    for parte in partes:
        parte = parte.strip()

        if parte.endswith(":"):
            continue

        resultados.append(
            parte
        )

    return "\n".join(
        resultados
    )


def combinar_listagem_e_detalhe(
    listagem: dict[str, Any],
    detalhe: dict[str, Any],
) -> dict[str, Any]:
    """
    Combina os dados resumidos com os dados da API de detalhe.
    """

    combinado = dict(
        listagem
    )

    for chave, valor in detalhe.items():
        if valor not in (
            None,
            "",
            [],
            {},
        ):
            combinado[chave] = valor

    return combinado


def normalizar_anuncio(
    anuncio: dict[str, Any],
) -> dict[str, Any]:
    """
    Converte um anúncio completo para o formato esperado pela aplicação.
    """

    identificador = anuncio.get(
        "id"
    )

    titulo = normalizar_texto(
        anuncio.get(
            "contractDesignation"
        )
        or anuncio.get(
            "description"
        )
    )

    entidade = obter_nome_entidade(
        anuncio
    )

    tipo_procedimento = normalizar_texto(
        anuncio.get(
            "contractingProcedureType"
        )
    )

    tipo_contrato = normalizar_texto(
        anuncio.get(
            "contractType"
        )
    )

    tipo_modelo = normalizar_texto(
        anuncio.get(
            "modelType"
        )
    )

    tipo_anuncio = normalizar_texto(
        anuncio.get(
            "type"
        )
    )

    preco_base = normalizar_texto(
        anuncio.get(
            "basePrice"
        )
    )

    data_publicacao = formatar_data(
        anuncio.get(
            "drPublicationDate"
        )
    )

    data_limite = formatar_data(
        anuncio.get(
            "proposalDeadline"
        )
    )

    numero_anuncio = normalizar_texto(
        anuncio.get(
            "announcementNumber"
        )
    )

    if not numero_anuncio:
        numero_anuncio = normalizar_texto(
            identificador
        )

    tipos_contrato = []

    for valor in (
        tipo_contrato,
        tipo_procedimento,
        tipo_modelo,
        tipo_anuncio,
    ):
        if (
            valor
            and valor not in tipos_contrato
        ):
            tipos_contrato.append(
                valor
            )

    link_detalhe = criar_link_detalhe(
        identificador
    )

    link_anuncio_dr = normalizar_texto(
        anuncio.get(
            "reference"
        )
    )

    link_pecas = normalizar_texto(
        anuncio.get(
            "contractingProcedureUrl"
        )
    )

    return {
        "titulo": titulo,
        "entidade": entidade,
        "link": link_detalhe,
        "data": data_publicacao,
        "data_limite": data_limite,
        "texto": criar_texto_completo(
            anuncio
        ),
        "numero_anuncio": numero_anuncio,
        "preco_base": preco_base,
        "cpvs": obter_cpvs(
            anuncio
        ),
        "tipos_contrato": tipos_contrato,
        "link_anuncio_dr": link_anuncio_dr,
        "link_pecas": link_pecas,
        "id_portal_base": normalizar_texto(
            identificador
        ),
        "id_procedimento": normalizar_texto(
            anuncio.get(
                "contractingProcedureId"
            )
        ),
    }


def recolher_listagem_recente(
    sessao: requests.Session,
) -> list[dict[str, Any]]:
    """
    Recolhe os anúncios publicados dentro do intervalo configurado.
    """

    data_minima = obter_data_minima()

    anuncios: list[
        dict[str, Any]
    ] = []

    identificadores_vistos: set[str] = set()

    for pagina in range(
        MAXIMO_PAGINAS
    ):
        dados = descarregar_pagina(
            sessao,
            pagina,
        )

        itens = dados.get(
            "items",
            [],
        )

        if not isinstance(
            itens,
            list,
        ):
            raise RuntimeError(
                "O Portal BASE devolveu um campo 'items' inválido."
            )

        if not itens:
            break

        encontrou_anuncio_antigo = False

        for item in itens:
            if not isinstance(
                item,
                dict,
            ):
                continue

            data_publicacao = converter_data(
                item.get(
                    "drPublicationDate"
                )
            )

            if (
                data_publicacao is not None
                and data_publicacao < data_minima
            ):
                encontrou_anuncio_antigo = True
                continue

            identificador = normalizar_texto(
                item.get(
                    "id"
                )
            )

            if (
                identificador
                and identificador in identificadores_vistos
            ):
                continue

            if identificador:
                identificadores_vistos.add(
                    identificador
                )

            anuncios.append(
                item
            )

        if encontrou_anuncio_antigo:
            break

        if len(
            itens
        ) < TAMANHO_PAGINA:
            break

        if INTERVALO_PEDIDOS > 0:
            time.sleep(
                INTERVALO_PEDIDOS
            )

    return anuncios


def enriquecer_candidatos(
    sessao: requests.Session,
    anuncios: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    int,
    int,
]:
    """
    Consulta o detalhe dos anúncios que passaram no pré-filtro.

    Retorna:
    - anúncios completos e normalizados;
    - número de candidatos;
    - número de erros de detalhe.
    """

    candidatos = [
        anuncio
        for anuncio in anuncios
        if deve_consultar_detalhe(
            anuncio
        )
    ]

    if MAXIMO_DETALHES > 0:
        candidatos = candidatos[
            :MAXIMO_DETALHES
        ]

    resultados: list[
        dict[str, Any]
    ] = []

    erros = 0

    total_candidatos = len(
        candidatos
    )

    for indice, candidato in enumerate(
        candidatos,
        start=1,
    ):
        identificador = normalizar_texto(
            candidato.get(
                "id"
            )
        )

        if not identificador:
            continue

        if MOSTRAR_DIAGNOSTICO:
            titulo = normalizar_texto(
                candidato.get(
                    "contractDesignation"
                )
            )

            print(
                f"Detalhe {indice}/{total_candidatos}: "
                f"{identificador} — {titulo[:90]}"
            )

        try:
            detalhe = obter_detalhe_anuncio(
                sessao,
                identificador,
            )

        except (
            requests.RequestException,
            RuntimeError,
        ) as erro:
            erros += 1

            print(
                "Aviso: não foi possível obter o detalhe "
                f"do anúncio {identificador}: {erro}"
            )

            continue

        anuncio_completo = combinar_listagem_e_detalhe(
            candidato,
            detalhe,
        )

        if parece_relevante_apos_detalhe(
            anuncio_completo
        ):
            resultados.append(
                normalizar_anuncio(
                    anuncio_completo
                )
            )

        if INTERVALO_DETALHES > 0:
            time.sleep(
                INTERVALO_DETALHES
            )

    return (
        resultados,
        total_candidatos,
        erros,
    )


def descarregar_anuncios() -> list[dict[str, Any]]:
    """
    Executa todo o processo de recolha e enriquecimento.
    """

    sessao = criar_sessao()

    try:
        inicializar_sessao(
            sessao
        )

        listagem = recolher_listagem_recente(
            sessao
        )

        if MOSTRAR_DIAGNOSTICO:
            print(
                "Anúncios encontrados no intervalo: "
                f"{len(listagem)}"
            )

        (
            anuncios_relevantes,
            total_candidatos,
            erros,
        ) = enriquecer_candidatos(
            sessao,
            listagem,
        )

        print(
            "Anúncios selecionados pelo pré-filtro: "
            f"{total_candidatos}"
        )

        print(
            "Anúncios enviados para análise: "
            f"{len(anuncios_relevantes)}"
        )

        if erros:
            print(
                "Detalhes que não foi possível obter: "
                f"{erros}"
            )

        return anuncios_relevantes

    finally:
        sessao.close()


def procurar_concursos() -> list[dict[str, Any]]:
    """
    Função utilizada pelo restante projeto.

    Mantém o nome e o formato de resposta esperados pela aplicação.
    """

    anuncios = descarregar_anuncios()

    print(
        "Anúncios recolhidos do Portal BASE para análise: "
        f"{len(anuncios)}"
    )

    print(
        "Intervalo pesquisado: "
        f"{obter_data_minima().strftime('%d-%m-%Y')} "
        "até "
        f"{obter_data_atual_portugal().strftime('%d-%m-%Y')}"
    )

    return anuncios


if __name__ == "__main__":
    resultados = procurar_concursos()

    print(
        "\nPrimeiros anúncios encontrados:\n"
    )

    for concurso in resultados[:5]:
        print(
            json.dumps(
                concurso,
                ensure_ascii=False,
                indent=2,
            )
        )