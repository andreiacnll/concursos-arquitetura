from __future__ import annotations

import re
import unicodedata
from typing import Any


COORDENADAS_PORTUGAL = {
    "lat_min": 32.0,
    "lat_max": 42.5,
    "lon_min": -32.0,
    "lon_max": -6.0,
}


LOCALIZACOES_CONHECIDAS = (
    {
        "chaves": ("escola secundaria do lumiar", "secundaria do lumiar"),
        "municipio": "Lisboa",
        "freguesia": "Lumiar",
        "morada": "Escola Secundária do Lumiar, Rua do Lumiar, 1600-497 Lisboa",
        "codigo_postal": "1600-497",
        "latitude": 38.76981,
        "longitude": -9.16252,
        "contexto_urbano": (
            "Equipamento educativo inserido numa zona urbana consolidada "
            "do Lumiar, em Lisboa, próximo de equipamentos públicos, "
            "rede de transportes e tecido residencial. A estratégia deve "
            "valorizar a reabilitação em funcionamento, a relação com o "
            "espaço público e a integração paisagística."
        ),
        "fonte": "referencia_osm",
    },
    {
        "chaves": (
            "mercado municipal de castelo branco",
            "revitalizacao e modernizacao do mercado municipal de castelo branco",
        ),
        "municipio": "Castelo Branco",
        "freguesia": "Castelo Branco",
        "morada": "Mercado Municipal de Castelo Branco",
        "codigo_postal": None,
        "latitude": 39.82201,
        "longitude": -7.49367,
        "contexto_urbano": (
            "Intervenção num mercado municipal existente no centro urbano "
            "de Castelo Branco, com impacto direto na atividade comercial "
            "local e na qualificação do espaço público envolvente. A leitura "
            "CNLL deve ponderar operação faseada, compatibilização técnica "
            "em edifício público e continuidade funcional."
        ),
        "fonte": "referencia_osm",
    },
    {
        "chaves": (
            "quinta da charnequinha",
            "escola basica quinta da charnequinha",
        ),
        "municipio": "Seixal",
        "freguesia": "Amora",
        "morada": "Escola Básica Quinta da Charnequinha, Amora, Seixal",
        "codigo_postal": None,
        "latitude": 38.60726,
        "longitude": -9.1346,
        "contexto_urbano": (
            "Equipamento educativo localizado na Quinta da Charnequinha, "
            "na freguesia de Amora, Seixal, numa área urbana residencial. "
            "O projeto deve articular a intervenção escolar com acessos, "
            "espaço exterior, continuidade de funcionamento e necessidades "
            "da comunidade educativa."
        ),
        "fonte": "referencia_osm",
    },
    {
        "chaves": (
            "auditorio principal da escola naval",
            "escola naval",
            "base naval do alfeite",
        ),
        "municipio": "Almada",
        "freguesia": "Laranjeiro e Feijó",
        "morada": "Escola Naval, Alfeite, 2810-001 Almada",
        "codigo_postal": "2810-001",
        "latitude": 38.66221,
        "longitude": -9.1472,
        "contexto_urbano": (
            "Intervenção técnica no auditório principal da Escola Naval, "
            "integrada no perímetro militar do Alfeite. A estratégia deve "
            "considerar condicionantes de acesso, coordenação com serviços "
            "da Marinha, compatibilização AVAC/eletricidade e execução em "
            "equipamento institucional sensível."
        ),
        "fonte": "referencia_osm",
    },
)


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    return " ".join(str(valor).strip().split())


def _sem_acentos(valor: str) -> str:
    normalizado = unicodedata.normalize("NFKD", valor)
    return "".join(
        letra
        for letra in normalizado
        if not unicodedata.combining(letra)
    )


def _normalizar(valor: Any) -> str:
    return _sem_acentos(_texto(valor)).casefold()


def _coordenada_valida(latitude: Any, longitude: Any) -> tuple[float, float] | None:
    try:
        lat = float(str(latitude).replace(",", "."))
        lon = float(str(longitude).replace(",", "."))
    except (TypeError, ValueError):
        return None

    if (
        COORDENADAS_PORTUGAL["lat_min"] <= lat <= COORDENADAS_PORTUGAL["lat_max"]
        and COORDENADAS_PORTUGAL["lon_min"] <= lon <= COORDENADAS_PORTUGAL["lon_max"]
    ):
        return lat, lon
    return None


def _extrair_coordenadas(texto_total: str) -> tuple[float, float] | None:
    padrao_decimal = re.compile(
        r"(?<!\d)((?:3[2-9]|4[0-2])(?:[.,]\d{3,8})?)\s*[,;/ ]+\s*(-(?:[6-9]|[12]\d|3[0-2])(?:[.,]\d{3,8})?)(?!\d)"
    )
    for resultado in padrao_decimal.finditer(texto_total):
        coordenadas = _coordenada_valida(
            resultado.group(1),
            resultado.group(2),
        )
        if coordenadas:
            return coordenadas
    return None


def _extrair_campo(texto_total: str, nome: str) -> str | None:
    resultado = re.search(
        rf"{nome}\s*:\s*([^\n\r]+)",
        texto_total,
        flags=re.IGNORECASE,
    )
    if not resultado:
        return None
    valor = _texto(resultado.group(1))
    return valor or None


def _extrair_codigo_postal(texto_total: str) -> str | None:
    resultado = re.search(r"\b\d{4}-\d{3}\b", texto_total)
    return resultado.group(0) if resultado else None


def _localizacao_conhecida(texto_total: str) -> dict[str, Any] | None:
    texto_normalizado = _normalizar(texto_total)
    for localizacao in LOCALIZACOES_CONHECIDAS:
        if any(chave in texto_normalizado for chave in localizacao["chaves"]):
            return {
                chave: valor
                for chave, valor in localizacao.items()
                if chave != "chaves"
            }
    return None


def _morada_do_concurso(
    *,
    titulo: str,
    municipio: str | None,
    freguesia: str | None,
) -> str | None:
    if "escola" in _normalizar(titulo):
        partes = [titulo, freguesia, municipio]
        return ", ".join(_texto(parte) for parte in partes if _texto(parte))
    return None


def _contexto_urbano_generico(
    *,
    municipio: str | None,
    freguesia: str | None,
    morada: str | None,
    titulo: str,
    texto_total: str,
) -> str | None:
    if not any((municipio, freguesia, morada)):
        return None

    texto_normalizado = _normalizar(" ".join((titulo, texto_total[:5000])))
    tipo = "intervenção"
    if "escola" in texto_normalizado:
        tipo = "equipamento educativo"
    elif "mercado" in texto_normalizado:
        tipo = "mercado municipal"
    elif "auditorio" in texto_normalizado or "auditório" in texto_normalizado:
        tipo = "auditório/equipamento público"

    local = morada or freguesia or municipio
    contexto = (
        f"{tipo.capitalize()} localizado em {local}. "
        "A análise CNLL deve considerar a relação com a envolvente, "
        "os acessos, as condicionantes funcionais do local e a "
        "coordenação entre arquitetura e especialidades."
    )

    pistas = []
    if re.search(r"funcionamento|faseamento|estruturas provis[oó]rias", texto_total, re.I):
        pistas.append(
            "Os documentos referem funcionamento/faseamento, aumentando "
            "a importância de uma estratégia de obra compatível com o uso existente."
        )
    if re.search(r"acessibilidades|espa[cç]o exterior|arranjos exteriores", texto_total, re.I):
        pistas.append(
            "Há referências a acessibilidades e espaço exterior, relevantes "
            "para a integração urbana e paisagística."
        )
    if re.search(r"avac|climatiza[cç][aã]o|el[eé]ctric", texto_total, re.I):
        pistas.append(
            "A componente técnica AVAC/elétrica deve ser articulada com "
            "as condições físicas e operacionais do edifício."
        )

    return " ".join([contexto, *pistas])


def resolver_localizacao(
    concurso: dict[str, Any],
    texto_total: str = "",
    *,
    documentos: Any = None,
) -> dict[str, Any]:
    """
    Resolve uma localização sem recorrer a fallbacks genéricos.

    Prioridade:
    1. Coordenadas explícitas em dados/documentos.
    2. Morada/localização oficial extraída dos dados.
    3. Geocoding da morada concreta.
    """
    if documentos is not None:
        return _resolver_localizacao_documentos(concurso, documentos)

    titulo = _texto(concurso.get("titulo"))
    texto_completo = "\n".join(
        parte
        for parte in (
            titulo,
            _texto(concurso.get("entidade")),
            _texto(concurso.get("localizacao")),
            _texto(concurso.get("morada")),
            _texto(concurso.get("municipio")),
            _texto(concurso.get("freguesia")),
            texto_total,
        )
        if parte
    )

    conhecida = _localizacao_conhecida(texto_completo) or {}

    municipio = (
        _texto(concurso.get("municipio"))
        or _extrair_campo(texto_total, "Concelho")
        or conhecida.get("municipio")
        or None
    )
    freguesia = (
        _texto(concurso.get("freguesia"))
        or _extrair_campo(texto_total, "Freguesia")
        or conhecida.get("freguesia")
        or None
    )
    if freguesia and freguesia.casefold().startswith("freguesia de "):
        freguesia = freguesia[13:].strip()

    codigo_postal = (
        _texto(concurso.get("codigo_postal"))
        or conhecida.get("codigo_postal")
        or _extrair_codigo_postal(texto_total)
        or None
    )
    morada = (
        _texto(concurso.get("morada"))
        or conhecida.get("morada")
        or _morada_do_concurso(
            titulo=titulo,
            municipio=municipio,
            freguesia=freguesia,
        )
    )

    coordenadas = (
        _coordenada_valida(concurso.get("latitude"), concurso.get("longitude"))
        or _extrair_coordenadas(texto_total)
        or _coordenada_valida(conhecida.get("latitude"), conhecida.get("longitude"))
    )

    fonte = "dados_documentos" if coordenadas else conhecida.get("fonte")

    if coordenadas is None and morada:
        try:
            from app.geocoding import obter_coordenadas

            resultado = obter_coordenadas(morada, municipio)
            if resultado:
                coordenadas = _coordenada_valida(
                    resultado.get("latitude"),
                    resultado.get("longitude"),
                )
                if coordenadas:
                    fonte = "geocoding_morada"
        except Exception:
            coordenadas = None

    latitude = coordenadas[0] if coordenadas else None
    longitude = coordenadas[1] if coordenadas else None

    contexto = (
        _texto(concurso.get("localizacao_contexto"))
        or conhecida.get("contexto_urbano")
        or _contexto_urbano_generico(
            municipio=municipio,
            freguesia=freguesia,
            morada=morada,
            titulo=titulo,
            texto_total=texto_total,
        )
    )

    return {
        "municipio": municipio,
        "freguesia": freguesia,
        "morada": morada,
        "codigo_postal": codigo_postal,
        "latitude": latitude,
        "longitude": longitude,
        "coordenadas": (
            f"{latitude:.5f}, {longitude:.5f}"
            if latitude is not None and longitude is not None
            else None
        ),
        "contexto_urbano": contexto,
        "fonte": fonte or (
            "dados_concurso" if any((municipio, freguesia, morada)) else None
        ),
    }


def _resolver_localizacao_documentos(
    concurso: dict[str, Any],
    documentos: Any,
) -> dict[str, Any]:
    """Resolve a localizacao sem materializar o texto de todos os documentos."""
    titulo = _texto(concurso.get("titulo"))
    partes_concurso = (
        titulo,
        _texto(concurso.get("entidade")),
        _texto(concurso.get("localizacao")),
        _texto(concurso.get("morada")),
        _texto(concurso.get("municipio")),
        _texto(concurso.get("freguesia")),
    )
    localizacoes_encontradas = set()

    def registar_localizacoes(texto: str) -> None:
        texto_normalizado = _normalizar(texto)
        for indice, localizacao in enumerate(LOCALIZACOES_CONHECIDAS):
            if any(chave in texto_normalizado for chave in localizacao["chaves"]):
                localizacoes_encontradas.add(indice)

    for parte in partes_concurso:
        if parte:
            registar_localizacoes(parte)

    municipio_documento = None
    freguesia_documento = None
    codigo_postal_documento = None
    coordenadas_documento = None
    pistas = []
    tem_funcionamento = False
    tem_acessibilidades = False
    tem_avac = False
    limite_contexto = 4800
    prefixo_contexto = ""

    for documento in documentos:
        texto = str(documento or "")
        if not texto:
            continue
        registar_localizacoes(texto)
        if municipio_documento is None:
            municipio_documento = _extrair_campo(texto, "Concelho")
        if freguesia_documento is None:
            freguesia_documento = _extrair_campo(texto, "Freguesia")
        if codigo_postal_documento is None:
            codigo_postal_documento = _extrair_codigo_postal(texto)
        if coordenadas_documento is None:
            coordenadas_documento = _extrair_coordenadas(texto)
        if not tem_funcionamento and re.search(
            r"funcionamento|faseamento|estruturas provis[oó]rias", texto, re.I
        ):
            tem_funcionamento = True
        if not tem_acessibilidades and re.search(
            r"acessibilidades|espa[cç]o exterior|arranjos exteriores", texto, re.I
        ):
            tem_acessibilidades = True
        if not tem_avac and re.search(
            r"avac|climatiza[cç][aã]o|el[eé]ctric", texto, re.I
        ):
            tem_avac = True
        restante = limite_contexto - len(prefixo_contexto)
        if restante > 0:
            prefixo_contexto += texto[:restante]

    if tem_funcionamento:
        pistas.append("funcionamento")
    if tem_acessibilidades:
        pistas.append("acessibilidades")
    if tem_avac:
        pistas.append("avac")
    texto_contexto = "\n".join((prefixo_contexto, *pistas))

    conhecida = {}
    if localizacoes_encontradas:
        conhecida = {
            chave: valor
            for chave, valor in LOCALIZACOES_CONHECIDAS[min(localizacoes_encontradas)].items()
            if chave != "chaves"
        }

    municipio = (
        _texto(concurso.get("municipio"))
        or municipio_documento
        or conhecida.get("municipio")
        or None
    )
    freguesia = (
        _texto(concurso.get("freguesia"))
        or freguesia_documento
        or conhecida.get("freguesia")
        or None
    )
    if freguesia and freguesia.casefold().startswith("freguesia de "):
        freguesia = freguesia[13:].strip()

    codigo_postal = (
        _texto(concurso.get("codigo_postal"))
        or codigo_postal_documento
        or conhecida.get("codigo_postal")
        or None
    )
    morada = (
        _texto(concurso.get("morada"))
        or conhecida.get("morada")
        or _morada_do_concurso(
            titulo=titulo,
            municipio=municipio,
            freguesia=freguesia,
        )
    )
    coordenadas = (
        _coordenada_valida(concurso.get("latitude"), concurso.get("longitude"))
        or coordenadas_documento
        or _coordenada_valida(conhecida.get("latitude"), conhecida.get("longitude"))
    )
    fonte = "dados_documentos" if coordenadas else conhecida.get("fonte")

    if coordenadas is None and morada:
        try:
            from app.geocoding import obter_coordenadas

            resultado = obter_coordenadas(morada, municipio)
            if resultado:
                coordenadas = _coordenada_valida(
                    resultado.get("latitude"), resultado.get("longitude")
                )
                if coordenadas:
                    fonte = "geocoding_morada"
        except Exception:
            coordenadas = None

    latitude = coordenadas[0] if coordenadas else None
    longitude = coordenadas[1] if coordenadas else None
    contexto = (
        _texto(concurso.get("localizacao_contexto"))
        or conhecida.get("contexto_urbano")
        or _contexto_urbano_generico(
            municipio=municipio,
            freguesia=freguesia,
            morada=morada,
            titulo=titulo,
            texto_total=texto_contexto,
        )
    )
    return {
        "municipio": municipio,
        "freguesia": freguesia,
        "morada": morada,
        "codigo_postal": codigo_postal,
        "latitude": latitude,
        "longitude": longitude,
        "coordenadas": (
            f"{latitude:.5f}, {longitude:.5f}"
            if latitude is not None and longitude is not None
            else None
        ),
        "contexto_urbano": contexto,
        "fonte": fonte or (
            "dados_concurso" if any((municipio, freguesia, morada)) else None
        ),
    }
