from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.base.gov.pt"
ID_ANUNCIO = 451494

PASTA_SAIDA = Path("diagnostico-detalhe")
CAMINHO_HTML = PASTA_SAIDA / "detalhe.html"
CAMINHO_TEXTO = PASTA_SAIDA / "detalhe.txt"
CAMINHO_JSON = PASTA_SAIDA / "dados-encontrados.json"


def criar_sessao() -> requests.Session:
    sessao = requests.Session()

    sessao.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,image/avif,"
                "image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.7",
            "Referer": f"{BASE_URL}/Base4/pt/pesquisa/",
        }
    )

    return sessao


def limpar_texto(valor: Any) -> str:
    if valor is None:
        return ""

    texto = str(valor)
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def obter_texto_elemento(elemento) -> str:
    if elemento is None:
        return ""

    return limpar_texto(
        elemento.get_text(
            " ",
            strip=True,
        )
    )


def extrair_tabelas(sopa: BeautifulSoup) -> list[dict[str, Any]]:
    tabelas_encontradas = []

    for numero_tabela, tabela in enumerate(
        sopa.find_all("table"),
        start=1,
    ):
        linhas = []

        for linha in tabela.find_all("tr"):
            celulas = [
                obter_texto_elemento(celula)
                for celula in linha.find_all(
                    ["th", "td"],
                    recursive=False,
                )
            ]

            celulas = [
                celula
                for celula in celulas
                if celula
            ]

            if celulas:
                linhas.append(celulas)

        if linhas:
            tabelas_encontradas.append(
                {
                    "numero": numero_tabela,
                    "linhas": linhas,
                }
            )

    return tabelas_encontradas


def extrair_listas_descricao(
    sopa: BeautifulSoup,
) -> list[dict[str, str]]:
    resultados = []

    for lista in sopa.find_all("dl"):
        termos = lista.find_all("dt")
        descricoes = lista.find_all("dd")

        for termo, descricao in zip(
            termos,
            descricoes,
        ):
            chave = obter_texto_elemento(termo)
            valor = obter_texto_elemento(descricao)

            if chave or valor:
                resultados.append(
                    {
                        "chave": chave,
                        "valor": valor,
                    }
                )

    return resultados


def extrair_pares_visuais(
    sopa: BeautifulSoup,
) -> list[dict[str, str]]:
    resultados = []
    vistos = set()

    seletores_rotulos = [
        "label",
        "strong",
        "b",
        ".label",
        ".field-label",
        ".form-label",
        ".title",
        ".caption",
    ]

    for seletor in seletores_rotulos:
        for rotulo in sopa.select(seletor):
            chave = obter_texto_elemento(rotulo)

            if not chave:
                continue

            candidatos = [
                rotulo.find_next_sibling(),
                rotulo.parent.find_next_sibling()
                if rotulo.parent
                else None,
                rotulo.find_next(),
            ]

            for candidato in candidatos:
                valor = obter_texto_elemento(candidato)

                if not valor:
                    continue

                if valor == chave:
                    continue

                if len(valor) > 1500:
                    continue

                identificador = (
                    chave.lower(),
                    valor.lower(),
                )

                if identificador in vistos:
                    continue

                vistos.add(identificador)

                resultados.append(
                    {
                        "chave": chave,
                        "valor": valor,
                    }
                )

                break

    return resultados


def extrair_scripts_json(
    sopa: BeautifulSoup,
) -> list[dict[str, Any]]:
    resultados = []

    for numero, script in enumerate(
        sopa.find_all("script"),
        start=1,
    ):
        conteudo = script.string or script.get_text()

        if not conteudo:
            continue

        conteudo = conteudo.strip()

        if not conteudo:
            continue

        tipo = limpar_texto(script.get("type"))

        if tipo in {
            "application/json",
            "application/ld+json",
        }:
            try:
                dados = json.loads(conteudo)

            except json.JSONDecodeError:
                dados = conteudo

            resultados.append(
                {
                    "numero": numero,
                    "tipo": tipo,
                    "dados": dados,
                }
            )

    return resultados


def extrair_possiveis_json_inline(
    html: str,
) -> list[str]:
    padroes = [
        r'"cpv[^"]*"\s*:',
        r'"description"\s*:',
        r'"contractDesignation"\s*:',
        r'"contractingEntity"\s*:',
        r'"basePrice"\s*:',
        r'"proposalDeadline"\s*:',
        r'"id"\s*:\s*\d+',
    ]

    resultados = []

    for padrao in padroes:
        for correspondencia in re.finditer(
            padrao,
            html,
            flags=re.IGNORECASE,
        ):
            inicio = max(
                0,
                correspondencia.start() - 250,
            )

            fim = min(
                len(html),
                correspondencia.end() + 750,
            )

            trecho = limpar_texto(
                html[inicio:fim]
            )

            if trecho not in resultados:
                resultados.append(trecho)

    return resultados


def guardar_texto_visivel(
    sopa: BeautifulSoup,
) -> str:
    for elemento in sopa(
        [
            "script",
            "style",
            "noscript",
            "svg",
        ]
    ):
        elemento.decompose()

    linhas = []

    for linha in sopa.get_text("\n").splitlines():
        linha_limpa = limpar_texto(linha)

        if linha_limpa:
            linhas.append(linha_limpa)

    return "\n".join(linhas)


def main() -> None:
    PASTA_SAIDA.mkdir(
        parents=True,
        exist_ok=True,
    )

    url = (
        f"{BASE_URL}/Base4/pt/detalhe/"
        f"?type=anuncios&id={ID_ANUNCIO}"
    )

    print("=" * 72)
    print("Diagnóstico da página de detalhe do Portal BASE")
    print("=" * 72)
    print(f"URL: {url}")

    sessao = criar_sessao()

    resposta = sessao.get(
        url,
        timeout=45,
    )

    print(f"Estado HTTP: {resposta.status_code}")
    print(f"Tipo: {resposta.headers.get('Content-Type')}")
    print(f"Tamanho: {len(resposta.content)} bytes")
    print(f"URL final: {resposta.url}")

    resposta.raise_for_status()

    resposta.encoding = resposta.apparent_encoding or "utf-8"

    html = resposta.text

    CAMINHO_HTML.write_text(
        html,
        encoding="utf-8",
    )

    sopa = BeautifulSoup(
        html,
        "html.parser",
    )

    titulo_pagina = (
        obter_texto_elemento(sopa.title)
        or "sem título"
    )

    tabelas = extrair_tabelas(sopa)
    listas_descricao = extrair_listas_descricao(sopa)
    pares_visuais = extrair_pares_visuais(sopa)
    scripts_json = extrair_scripts_json(sopa)
    possiveis_json_inline = extrair_possiveis_json_inline(
        html
    )

    texto_visivel = guardar_texto_visivel(
        BeautifulSoup(
            html,
            "html.parser",
        )
    )

    CAMINHO_TEXTO.write_text(
        texto_visivel,
        encoding="utf-8",
    )

    dados = {
        "id_anuncio": ID_ANUNCIO,
        "url": url,
        "url_final": resposta.url,
        "estado_http": resposta.status_code,
        "titulo_pagina": titulo_pagina,
        "tabelas": tabelas,
        "listas_descricao": listas_descricao,
        "pares_visuais": pares_visuais,
        "scripts_json": scripts_json,
        "possiveis_json_inline": possiveis_json_inline,
    }

    CAMINHO_JSON.write_text(
        json.dumps(
            dados,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(f"Título da página: {titulo_pagina}")
    print(f"Tabelas encontradas: {len(tabelas)}")
    print(
        "Pares em listas de descrição: "
        f"{len(listas_descricao)}"
    )
    print(
        "Pares visuais encontrados: "
        f"{len(pares_visuais)}"
    )
    print(
        "Scripts JSON encontrados: "
        f"{len(scripts_json)}"
    )
    print(
        "Trechos JSON inline encontrados: "
        f"{len(possiveis_json_inline)}"
    )

    print()
    print("Primeiros pares encontrados:")

    pares_para_mostrar = (
        listas_descricao
        + pares_visuais
    )

    for item in pares_para_mostrar[:40]:
        print("-" * 72)
        print(f"CHAVE: {item['chave']}")
        print(f"VALOR: {item['valor']}")

    print()
    print("Ficheiros criados:")
    print(f"- {CAMINHO_HTML}")
    print(f"- {CAMINHO_TEXTO}")
    print(f"- {CAMINHO_JSON}")


if __name__ == "__main__":
    main()