from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.base.gov.pt"
ID_ANUNCIO = 451494

URL_DETALHE = (
    f"{BASE_URL}/Base4/pt/detalhe/"
    f"?type=anuncios&id={ID_ANUNCIO}"
)

PASTA_SAIDA = Path("diagnostico-api-detalhe")
CAMINHO_RELATORIO = PASTA_SAIDA / "relatorio.txt"

PADROES_INTERESSANTES = [
    r"moduleservices",
    r"/rest/",
    r"/api/",
    r"/resultados/",
    r"search_anuncios",
    r"detalhe",
    r"anuncios",
    r"contractDesignation",
    r"contractingEntity",
    r"proposalDeadline",
    r"basePrice",
    r"\bcpv\b",
    r"description",
    r"announcement",
    r"Get[A-Za-z0-9_]*Announcement",
    r"Get[A-Za-z0-9_]*Anuncio",
    r"Get[A-Za-z0-9_]*Detail",
    r"fetch\s*\(",
    r"\.ajax\s*\(",
    r"XMLHttpRequest",
    r"axios",
]


def criar_sessao() -> requests.Session:
    sessao = requests.Session()

    sessao.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.7",
            "Referer": f"{BASE_URL}/Base4/pt/pesquisa/",
        }
    )

    return sessao


def limpar_nome_ficheiro(url: str, numero: int) -> str:
    nome = url.split("?")[0].rstrip("/").split("/")[-1]

    if not nome:
        nome = f"script-{numero}.js"

    nome = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        nome,
    )

    if not nome.endswith(".js"):
        nome += ".js"

    return f"{numero:03d}-{nome}"


def obter_contexto(
    texto: str,
    inicio: int,
    fim: int,
    margem: int = 500,
) -> str:
    inicio_contexto = max(
        0,
        inicio - margem,
    )

    fim_contexto = min(
        len(texto),
        fim + margem,
    )

    trecho = texto[
        inicio_contexto:fim_contexto
    ]

    trecho = trecho.replace("\r", " ")
    trecho = re.sub(r"\s+", " ", trecho)

    return trecho.strip()


def procurar_padroes(
    texto: str,
    origem: str,
) -> list[str]:
    resultados = []
    vistos = set()

    for padrao in PADROES_INTERESSANTES:
        for correspondencia in re.finditer(
            padrao,
            texto,
            flags=re.IGNORECASE,
        ):
            contexto = obter_contexto(
                texto,
                correspondencia.start(),
                correspondencia.end(),
            )

            identificador = contexto.lower()

            if identificador in vistos:
                continue

            vistos.add(identificador)

            resultados.append(
                "\n".join(
                    [
                        "-" * 90,
                        f"ORIGEM: {origem}",
                        f"PADRÃO: {padrao}",
                        f"POSIÇÃO: {correspondencia.start()}",
                        "",
                        contexto,
                    ]
                )
            )

    return resultados


def extrair_urls_do_javascript(
    texto: str,
) -> set[str]:
    urls = set()

    padroes_urls = [
        r"""["']([^"' ]*moduleservices[^"']*)["']""",
        r"""["']([^"' ]*/rest/[^"']*)["']""",
        r"""["']([^"' ]*/api/[^"']*)["']""",
        r"""["']([^"' ]*/resultados/[^"']*)["']""",
        r"""["']([^"' ]*detalhe[^"']*)["']""",
    ]

    for padrao in padroes_urls:
        for resultado in re.findall(
            padrao,
            texto,
            flags=re.IGNORECASE,
        ):
            if len(resultado) > 500:
                continue

            urls.add(resultado)

    return urls


def main() -> None:
    PASTA_SAIDA.mkdir(
        parents=True,
        exist_ok=True,
    )

    sessao = criar_sessao()

    linhas_relatorio = [
        "=" * 90,
        "DESCOBERTA DA API DO DETALHE DO PORTAL BASE",
        "=" * 90,
        f"URL analisada: {URL_DETALHE}",
        "",
    ]

    print("A obter a página de detalhe...")

    resposta = sessao.get(
        URL_DETALHE,
        timeout=45,
    )

    resposta.raise_for_status()

    html = resposta.text

    caminho_html = (
        PASTA_SAIDA / "pagina-detalhe.html"
    )

    caminho_html.write_text(
        html,
        encoding="utf-8",
    )

    sopa = BeautifulSoup(
        html,
        "html.parser",
    )

    urls_scripts = []

    for script in sopa.find_all(
        "script",
        src=True,
    ):
        src = script.get("src")

        if not src:
            continue

        url_completa = urljoin(
            resposta.url,
            src,
        )

        if url_completa not in urls_scripts:
            urls_scripts.append(url_completa)

    linhas_relatorio.extend(
        [
            f"Estado HTTP: {resposta.status_code}",
            f"Tamanho HTML: {len(html)} caracteres",
            f"Scripts encontrados: {len(urls_scripts)}",
            "",
            "SCRIPTS:",
        ]
    )

    for url_script in urls_scripts:
        linhas_relatorio.append(
            f"- {url_script}"
        )

    linhas_relatorio.extend(
        [
            "",
            "=" * 90,
            "CORRESPONDÊNCIAS NO HTML",
            "=" * 90,
        ]
    )

    correspondencias_html = procurar_padroes(
        html,
        "HTML da página de detalhe",
    )

    if correspondencias_html:
        linhas_relatorio.extend(
            correspondencias_html
        )
    else:
        linhas_relatorio.append(
            "Nenhuma correspondência relevante no HTML."
        )

    urls_encontradas = set()
    total_scripts_descarregados = 0
    total_erros = 0

    for numero, url_script in enumerate(
        urls_scripts,
        start=1,
    ):
        print(
            f"[{numero}/{len(urls_scripts)}] "
            f"A analisar {url_script}"
        )

        try:
            resposta_script = sessao.get(
                url_script,
                timeout=45,
            )

            resposta_script.raise_for_status()

        except requests.RequestException as erro:
            total_erros += 1

            linhas_relatorio.extend(
                [
                    "",
                    "-" * 90,
                    f"ERRO AO OBTER: {url_script}",
                    f"Detalhe: {erro}",
                ]
            )

            continue

        conteudo = resposta_script.text

        nome_ficheiro = limpar_nome_ficheiro(
            url_script,
            numero,
        )

        caminho_script = (
            PASTA_SAIDA / nome_ficheiro
        )

        caminho_script.write_text(
            conteudo,
            encoding="utf-8",
        )

        total_scripts_descarregados += 1

        correspondencias = procurar_padroes(
            conteudo,
            url_script,
        )

        if correspondencias:
            linhas_relatorio.extend(
                [
                    "",
                    "=" * 90,
                    f"CORRESPONDÊNCIAS EM {url_script}",
                    "=" * 90,
                ]
            )

            linhas_relatorio.extend(
                correspondencias
            )

        urls_encontradas.update(
            extrair_urls_do_javascript(
                conteudo
            )
        )

    linhas_relatorio.extend(
        [
            "",
            "=" * 90,
            "POSSÍVEIS ENDPOINTS ENCONTRADOS",
            "=" * 90,
        ]
    )

    if urls_encontradas:
        for url in sorted(
            urls_encontradas
        ):
            linhas_relatorio.append(
                f"- {url}"
            )
    else:
        linhas_relatorio.append(
            "Nenhum endpoint explícito encontrado."
        )

    linhas_relatorio.extend(
        [
            "",
            "=" * 90,
            "RESUMO",
            "=" * 90,
            (
                "Scripts descarregados: "
                f"{total_scripts_descarregados}"
            ),
            f"Erros: {total_erros}",
            (
                "Possíveis endpoints: "
                f"{len(urls_encontradas)}"
            ),
        ]
    )

    CAMINHO_RELATORIO.write_text(
        "\n".join(linhas_relatorio),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("Diagnóstico concluído")
    print("=" * 72)
    print(
        "Scripts descarregados: "
        f"{total_scripts_descarregados}"
    )
    print(f"Erros: {total_erros}")
    print(
        "Possíveis endpoints: "
        f"{len(urls_encontradas)}"
    )
    print(f"Relatório: {CAMINHO_RELATORIO}")


if __name__ == "__main__":
    main()
    