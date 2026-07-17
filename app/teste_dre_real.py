import json
import requests


URL_PAGINA = (
    "https://diariodarepublica.pt/dr/detalhe/"
    "anuncio-procedimento/14547-2026-1129514911"
)

URL_ENDPOINT = (
    "https://diariodarepublica.pt/dr/screenservices/dr/"
    "Legislacao_Conteudos/Conteudo_Detalhe/"
    "DataActionGetAllConteudoDetalheData"
)


def main():
    sessao = requests.Session()

    # Primeiro abrimos a página normal para obter cookies públicos da sessão.
    resposta_pagina = sessao.get(URL_PAGINA, timeout=30)
    resposta_pagina.raise_for_status()

    payload = {
        "versionInfo": {
            "moduleVersion": "ovoWWgHG1DswwMxuU9YY6Q",
            "apiVersion": "B3l5BYZxaLmWUxGR3tmKGw",
        },
        "viewName": "Legislacao_Conteudos.Conteudo_Detalhe",
        "screenData": {
            "variables": {
                "ParteIdAux": "0",
                "Pesquisa": "",
                "Comes": "",
                "ShowResumoPT": False,
                "HasJurisprudenciaAssociadaVar": False,
                "FragmentoVersaoIdAux": "0",
                "Key": "14547-2026-1129514911",
                "KeyAux": "",
                "ParteId": "",
                "Tipo": "anuncio-procedimento",
                "_keyInDataFetchStatus": 1,
                "_parteIdInDataFetchStatus": 1,
                "_tipoInDataFetchStatus": 1,
            }
        },
        "clientVariables": {},
    }

    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json",
        "Referer": URL_PAGINA,
        "Origin": "https://diariodarepublica.pt",
        "User-Agent": "Mozilla/5.0",
    }

 resposta = sessao.post(
    URL_ENDPOINT,
    json=payload,
    headers=headers,
    timeout=30,
    allow_redirects=False,
)

print("Estado HTTP:", resposta.status_code)
print("URL final:", resposta.url)
print("Content-Type:", resposta.headers.get("content-type"))
print("Location:", resposta.headers.get("location"))
print("Cookies da sessão:", sessao.cookies.get_dict())
print("Primeiros caracteres:", resposta.text[:500])

    # Guarda a resposta completa para podermos analisá-la.
    with open("resposta_dre.json", "w", encoding="utf-8") as ficheiro:
        json.dump(dados, ficheiro, ensure_ascii=False, indent=2)

    print(json.dumps(dados, ensure_ascii=False, indent=2)[:3000])


if __name__ == "__main__":
    main()