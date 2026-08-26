import requests
import time
from typing import Optional


def obter_coordenadas(
    morada: str,
    cidade: str | None = None,
) -> dict | None:
    """
    Obtém latitude e longitude através do OpenStreetMap Nominatim.
    """

    if not morada:
        return None


    query = morada

    if cidade and cidade.lower() not in morada.lower():
        query += f", {cidade}"


    query += ", Portugal"


    url = "https://nominatim.openstreetmap.org/search"


    headers = {
        "User-Agent": "concursos-arquitetura/1.0"
    }


    params = {
        "q": query,
        "format": "json",
        "limit": 1,
    }


    try:

        resposta = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10,
        )

        resposta.raise_for_status()

        dados = resposta.json()


        if not dados:
            return None


        resultado = dados[0]


        return {
            "latitude": float(resultado["lat"]),
            "longitude": float(resultado["lon"]),
        }


    except Exception as erro:

        print(
            f"Erro no geocoding: {erro}"
        )

        return None


    finally:

        # respeitar limite do Nominatim
        time.sleep(1)
