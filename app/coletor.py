import json
from datetime import datetime, timedelta
from pathlib import Path


CAMINHO_JSON = Path("data/anuncios2025.json")


def converter_data(valor):
    if not valor:
        return None

    try:
        return datetime.strptime(
            valor.strip(),
            "%d/%m/%Y",
        ).date()
    except ValueError:
        return None


def obter_texto_anuncio(anuncio):
    partes = [
        anuncio.get("descricaoAnuncio", ""),
        anuncio.get("designacaoEntidade", ""),
        " ".join(anuncio.get("tiposContrato") or []),
        " ".join(anuncio.get("CPVs") or []),
    ]

    return " ".join(
        str(parte).strip()
        for parte in partes
        if parte
    )


def procurar_concursos(dias_atras=1000, apenas_abertos=False):
    if not CAMINHO_JSON.exists():
        raise FileNotFoundError(
            f"Ficheiro não encontrado: {CAMINHO_JSON}"
        )

    with CAMINHO_JSON.open(encoding="utf-8") as ficheiro:
        anuncios = json.load(ficheiro)

    hoje = datetime.now().date()
    data_minima = hoje - timedelta(days=dias_atras)

    concursos = []

    for anuncio in anuncios:
        data_publicacao = converter_data(
            anuncio.get("dataPublicacao")
        )

        data_limite = converter_data(
            anuncio.get("DataLimitePropostas")
        )

        if data_publicacao is None:
            continue

        if data_publicacao < data_minima:
            continue

        # No funcionamento real, apenas_abertos será True.
        # Neste teste usamos False para analisar anúncios já encerrados.
        if apenas_abertos:
            if data_limite is None:
                continue

            if data_limite < hoje:
                continue

        titulo = (
            anuncio.get("descricaoAnuncio")
            or "Sem descrição"
        ).strip()

        entidade = (
            anuncio.get("designacaoEntidade")
            or "Entidade não identificada"
        ).strip()

        link = (
            anuncio.get("url")
            or anuncio.get("PecasProcedimento")
            or ""
        )

        concursos.append(
            {
                "titulo": titulo,
                "entidade": entidade,
                "link": link,
                "data": anuncio.get("dataPublicacao", ""),
                "data_limite": anuncio.get(
                    "DataLimitePropostas",
                    "",
                ),
                "texto": obter_texto_anuncio(anuncio),
                "numero_anuncio": anuncio.get(
                    "nAnuncio",
                    "",
                ),
                "preco_base": anuncio.get(
                    "PrecoBase",
                    "",
                ),
                "cpvs": anuncio.get("CPVs", []),
                "tipos_contrato": anuncio.get(
                    "tiposContrato",
                    [],
                ),
            }
        )

    print(
        f"   Anúncios publicados desde "
        f"{data_minima.strftime('%d/%m/%Y')}: "
        f"{len(concursos)}"
    )

    return concursos