import requests


def testar_anuncio():

    url = "https://diariodarepublica.pt/dr/screenservices/dr/Legislacao_Conteudos/Conteudo_Detalhe/DataActionGetAllConteudoDetalheData"

    resposta = requests.post(
        url,
        json={}
    )

    print("Estado:", resposta.status_code)
    print(resposta.text[:500])


testar_anuncio()
