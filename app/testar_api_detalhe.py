from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://www.base.gov.pt"
RESULTADOS_URL = f"{BASE_URL}/Base4/pt/resultados/"

ID_ANUNCIO = 451494
VERSAO_PORTAL = "126.0"

PASTA_SAIDA = Path("diagnostico-api-detalhe")
FICHEIRO_RESPOSTA = PASTA_SAIDA / "resposta-detail-anuncios.txt"
FICHEIRO_JSON = PASTA_SAIDA / "resposta-detail-anuncios.json"


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
                "application/json, text/javascript, "
                "text/plain, */*; q=0.01"
            ),
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.7",
            "Content-Type": (
                "application/x-www-form-urlencoded; charset=UTF-8"
            ),
            "Origin": BASE_URL,
            "Referer": (
                f"{BASE_URL}/Base4/pt/detalhe/"
                f"?type=anuncios&id={ID_ANUNCIO}"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }
    )

    return sessao


def converter_resposta(texto: str) -> Any:
    texto = texto.strip()

    if not texto:
        raise ValueError("O Portal BASE devolveu uma resposta vazia.")

    try:
        return json.loads(texto)

    except json.JSONDecodeError:
        pass

    # Algumas respostas do Portal BASE podem usar valores JavaScript.
    substituicoes = {
        "null": "None",
        "true": "True",
        "false": "False",
    }

    texto_python = texto

    for original, substituto in substituicoes.items():
        texto_python = texto_python.replace(
            f": {original}",
            f": {substituto}",
        )
        texto_python = texto_python.replace(
            f":{original}",
            f":{substituto}",
        )

    try:
        return ast.literal_eval(texto_python)

    except (ValueError, SyntaxError) as erro:
        raise ValueError(
            "Não foi possível interpretar a resposta do Portal BASE."
        ) from erro


def mostrar_valor(nome: str, valor: Any) -> None:
    print("-" * 78)
    print(nome)

    if isinstance(valor, (dict, list)):
        print(
            json.dumps(
                valor,
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(valor if valor not in (None, "") else "(vazio)")


def main() -> None:
    PASTA_SAIDA.mkdir(
        parents=True,
        exist_ok=True,
    )

    sessao = criar_sessao()

    dados_pedido = {
        "type": "detail_anuncios",
        "version": VERSAO_PORTAL,
        "id": str(ID_ANUNCIO),
    }

    print("=" * 78)
    print("TESTE DA API DE DETALHE DO PORTAL BASE")
    print("=" * 78)
    print(f"Endpoint: {RESULTADOS_URL}")
    print(f"ID do anúncio: {ID_ANUNCIO}")
    print()

    resposta = sessao.post(
        RESULTADOS_URL,
        data=dados_pedido,
        timeout=45,
    )

    print(f"Estado HTTP: {resposta.status_code}")
    print(f"Content-Type: {resposta.headers.get('Content-Type')}")
    print(f"Tamanho: {len(resposta.content)} bytes")
    print()

    resposta.raise_for_status()

    resposta.encoding = resposta.apparent_encoding or "utf-8"
    texto_resposta = resposta.text

    FICHEIRO_RESPOSTA.write_text(
        texto_resposta,
        encoding="utf-8",
    )

    detalhe = converter_resposta(texto_resposta)

    FICHEIRO_JSON.write_text(
        json.dumps(
            detalhe,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if not isinstance(detalhe, dict):
        print("A resposta não é um objeto/dicionário.")
        mostrar_valor("Resposta completa", detalhe)
        return

    campos_principais = [
        ("ID", detalhe.get("id")),
        (
            "Número do anúncio",
            detalhe.get("announcementNumber"),
        ),
        (
            "Descrição",
            detalhe.get("contractDesignation"),
        ),
        (
            "Entidades emissoras",
            detalhe.get("contractingEntities"),
        ),
        (
            "Tipo de ato",
            detalhe.get("type"),
        ),
        (
            "Tipo de modelo",
            detalhe.get("modelType"),
        ),
        (
            "Tipos de contrato",
            detalhe.get("contractType"),
        ),
        (
            "Preço base",
            detalhe.get("basePrice"),
        ),
        (
            "CPVs",
            detalhe.get("cpvs"),
        ),
        (
            "Prazo para propostas",
            detalhe.get("proposalDeadline"),
        ),
        (
            "Data de publicação",
            detalhe.get("drPublicationDate"),
        ),
        (
            "Ligação para o anúncio DR",
            detalhe.get("reference"),
        ),
        (
            "Peças do procedimento",
            detalhe.get("contractingProcedureUrl"),
        ),
        (
            "ID do procedimento",
            detalhe.get("contractingProcedureId"),
        ),
    ]

    for nome, valor in campos_principais:
        mostrar_valor(nome, valor)

    mostrar_valor(
        "Resposta completa",
        detalhe,
    )

    print()
    print("=" * 78)
    print("FICHEIROS CRIADOS")
    print("=" * 78)
    print(FICHEIRO_RESPOSTA)
    print(FICHEIRO_JSON)


if __name__ == "__main__":
    main()