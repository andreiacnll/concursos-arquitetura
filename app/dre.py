from __future__ import annotations

import argparse
import re
import threading
import time
import unicodedata
from io import BytesIO
from urllib.parse import urlparse

import requests
from pypdf import PdfReader


TIMEOUT = 30
INTERVALO_MINIMO = 10.0

DOMINIOS_PERMITIDOS = {
    "files.diariodarepublica.pt",
    "diariodarepublica.pt",
    "www.diariodarepublica.pt",
}

_ultimo_pedido = 0.0
_bloqueio_pedidos = threading.Lock()


def _texto_limpo(valor: object) -> str:
    """
    Converte um valor em texto e normaliza espaços.
    """
    if valor is None:
        return ""

    return re.sub(
        r"[ \t]+",
        " ",
        str(valor).replace("\r\n", "\n").replace("\r", "\n"),
    ).strip()


def _sem_acentos(texto: str) -> str:
    """
    Produz uma versão sem acentos para pesquisas tolerantes.
    """
    normalizado = unicodedata.normalize("NFKD", texto)

    return "".join(
        caractere
        for caractere in normalizado
        if not unicodedata.combining(caractere)
    )


def _validar_url_pdf(url: str) -> None:
    """
    Aceita apenas HTTPS e domínios oficiais do DR.
    """
    partes = urlparse(url)

    if partes.scheme.lower() != "https":
        raise ValueError(
            "O PDF do Diário da República tem de usar HTTPS."
        )

    dominio = (partes.hostname or "").lower()

    if dominio not in DOMINIOS_PERMITIDOS:
        raise ValueError(
            f"Domínio não permitido para o PDF do DR: {dominio}"
        )


def _aguardar_intervalo() -> None:
    """
    Garante o intervalo mínimo entre pedidos ao DR.

    O primeiro pedido não precisa de esperar.
    """
    global _ultimo_pedido

    with _bloqueio_pedidos:
        agora = time.monotonic()
        decorrido = agora - _ultimo_pedido
        espera = INTERVALO_MINIMO - decorrido

        if _ultimo_pedido and espera > 0:
            time.sleep(espera)

        _ultimo_pedido = time.monotonic()


def obter_pdf(url: str) -> bytes:
    """
    Descarrega um PDF oficial do Diário da República.

    Respeita um intervalo mínimo entre pedidos.
    """
    _validar_url_pdf(url)
    _aguardar_intervalo()

    resposta = requests.get(
        url,
        timeout=TIMEOUT,
        headers={
            "User-Agent": (
                "ArqConcursos/1.0 "
                "(consulta moderada de anúncios públicos)"
            )
        },
    )

    resposta.raise_for_status()

    conteudo = resposta.content
    tipo = resposta.headers.get("Content-Type", "").lower()

    parece_pdf = (
        conteudo.startswith(b"%PDF")
        or "application/pdf" in tipo
    )

    if not parece_pdf:
        raise ValueError(
            "A resposta do Diário da República não parece ser um PDF."
        )

    return conteudo


def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    """
    Extrai texto pesquisável de todas as páginas do PDF.
    """
    if not pdf_bytes:
        raise ValueError("O PDF está vazio.")

    leitor = PdfReader(BytesIO(pdf_bytes))
    paginas = []

    for numero, pagina in enumerate(leitor.pages, start=1):
        try:
            texto = pagina.extract_text() or ""
        except Exception as erro:
            print(
                f"Aviso: não foi possível ler a página "
                f"{numero}: {erro}"
            )
            texto = ""

        paginas.append(texto)

    texto_completo = "\n".join(paginas).strip()

    if not texto_completo:
        raise ValueError(
            "Não foi possível extrair texto pesquisável do PDF."
        )

    return texto_completo


def _extrair_secao_criterio(texto: str) -> str:
    """
    Isola a secção do critério de adjudicação.

    Tenta terminar no cabeçalho numerado seguinte.
    """
    linhas = texto.replace("\r", "\n").splitlines()
    inicio = None

    padrao_inicio = re.compile(
        r"criterios?\s+de\s+adjudicacao",
        re.IGNORECASE,
    )

    for indice, linha in enumerate(linhas):
        linha_pesquisa = _sem_acentos(linha)

        if padrao_inicio.search(linha_pesquisa):
            inicio = indice
            break

    if inicio is None:
        return ""

    selecionadas = [linhas[inicio]]
    numero_secao = None

    correspondencia_numero = re.search(
        r"^\s*(\d+)\s*[-–—.]",
        linhas[inicio],
    )

    if correspondencia_numero:
        numero_secao = int(correspondencia_numero.group(1))

    for linha in linhas[inicio + 1:]:
        texto_linha = linha.strip()

        cabecalho = re.match(
            r"^\s*(\d+)\s*[-–—.]\s+\S",
            texto_linha,
        )

        if cabecalho:
            numero_encontrado = int(cabecalho.group(1))

            if (
                numero_secao is None
                or numero_encontrado > numero_secao
            ):
                break

        selecionadas.append(linha)

        # Evita capturar acidentalmente o resto de PDFs
        # cujo cabeçalho seguinte não seja reconhecido.
        if len(selecionadas) >= 100:
            break

    return "\n".join(selecionadas).strip()


def _percentagem(texto: str) -> str | None:
    """
    Extrai uma percentagem explícita de um texto.
    """
    correspondencia = re.search(
        r"(\d+(?:[.,]\d+)?)\s*%",
        texto,
    )

    if not correspondencia:
        return None

    valor = correspondencia.group(1).replace(",", ".")

    if valor.endswith(".0"):
        valor = valor[:-2]

    return f"{valor}%"


def _limpar_nome_fator(nome: str) -> str:
    """
    Limpa etiquetas e pontuação em nomes de fatores.
    """
    nome = re.sub(
        r"^\s*(?:nome|designacao|fator|factor)\s*:\s*",
        "",
        nome,
        flags=re.IGNORECASE,
    )

    nome = re.sub(
        r"\s+",
        " ",
        nome,
    ).strip(" :-–—.;")

    return nome


def _extrair_fatores(secao: str) -> list[tuple[str, str]]:
    """
    Procura fatores e respetivas percentagens.

    Reconhece exemplos como:
        Preço 40%
        Nome: Qualidade
        Ponderação: 60%
    """
    linhas = [
        _texto_limpo(linha)
        for linha in secao.splitlines()
        if _texto_limpo(linha)
    ]

    fatores: list[tuple[str, str]] = []
    nome_pendente = ""

    ignorar = re.compile(
        r"^(?:"
        r"\d+\s*[-–—.]?\s*criterios?\s+de\s+adjudicacao"
        r"|multifator"
        r"|monofator"
        r"|sim"
        r"|nao"
        r")\s*:?\s*(?:sim|nao)?\s*$",
        re.IGNORECASE,
    )

    for linha in linhas:
        linha_sem_acentos = _sem_acentos(linha)

        if ignorar.match(linha_sem_acentos):
            continue

        percentagem = _percentagem(linha)

        if percentagem:
            nome_na_linha = re.sub(
                r"\d+(?:[.,]\d+)?\s*%",
                "",
                linha,
            )

            nome_na_linha = re.sub(
                r"^\s*(?:ponderacao|peso|percentagem)\s*:\s*",
                "",
                nome_na_linha,
                flags=re.IGNORECASE,
            )

            nome = _limpar_nome_fator(nome_na_linha)

            if not nome:
                nome = nome_pendente

            if nome:
                par = (nome, percentagem)

                if par not in fatores:
                    fatores.append(par)

                nome_pendente = ""

            continue

        correspondencia_nome = re.match(
            r"^\s*(?:nome|designacao|fator|factor)\s*:\s*(.+)$",
            linha,
            flags=re.IGNORECASE,
        )

        if correspondencia_nome:
            nome_pendente = _limpar_nome_fator(
                correspondencia_nome.group(1)
            )
            continue

        if re.match(
            r"^\s*(?:ponderacao|peso|percentagem)\s*:",
            linha,
            flags=re.IGNORECASE,
        ):
            continue

        # Em alguns anúncios o nome aparece sozinho na linha.
        if len(linha) <= 100:
            nome_pendente = _limpar_nome_fator(linha)

    return fatores


def extrair_criterio(texto: str) -> dict:
    """
    Extrai critérios de adjudicação do DR.
    Associa cada Nome à sua Ponderação.
    """

    import re

    resultado = {
        "criterio_tipo": None,
        "criterio_resumo": None,
        "criterio_detalhe": None,
    }

    texto_limpo = texto.replace("\r", "\n")

    encontrados = []

    # Formato habitual do Diário da República:
    #
    # Nome: Qualidade
    # Ponderação: 30%
    #
    # Nome: Preço
    # Ponderação: 70%

    padrao_nome = re.compile(
        r"Nome:\s*(.*?)\s+Ponderação:\s*(\d{1,3})%",
        re.IGNORECASE | re.DOTALL,
    )

    for nome, percentagem in padrao_nome.findall(texto_limpo):

        nome = " ".join(nome.split()).strip()

        if not nome:
            continue

        valor = f"{nome} {percentagem}%"

        if valor not in encontrados:
            encontrados.append(valor)


    # fallback para anúncios antigos
    if not encontrados:

        padrao = re.compile(
            r"([A-Za-zÀ-ÿ\s\-\/]+?)\s*[:\-]\s*(\d{1,3})\s*%",
            re.IGNORECASE,
        )

        for nome, percentagem in padrao.findall(texto_limpo):

            nome = " ".join(nome.split()).strip()

            if (
                "ponderação" in nome.lower()
                or "ponderacao" in nome.lower()
                or len(nome) > 80
            ):
                continue

            valor = f"{nome} {percentagem}%"

            if valor not in encontrados:
                encontrados.append(valor)


    if not encontrados:
        # Alguns anuncios monofator indicam apenas "Nome: Preco", sem
        # ponderacao. O valor e extraido apenas dentro da secao oficial.
        secao_criterio = _extrair_secao_criterio(texto_limpo)
        secao_sem_acentos = _sem_acentos(secao_criterio).lower()
        e_monofator = bool(
            re.search(r"multifator\s*:\s*(?:nao|n[^\s]*o)\b", secao_sem_acentos)
        )
        nome_monofator = re.search(
            r"monofator\s*:\s*(?:\s*\n\s*)*(?:nome\s*:\s*)?([^\n\r]+)",
            secao_criterio,
            re.IGNORECASE,
        )

        if e_monofator and nome_monofator:
            nome = _limpar_nome_fator(nome_monofator.group(1))
            if nome:
                encontrados.append(nome)

    if not encontrados:
        return resultado


    resultado["criterio_tipo"] = (
        "Monofator"
        if len(encontrados) == 1
        else "Multifator"
    )

    resultado["criterio_resumo"] = " • ".join(encontrados)
    resultado["criterio_detalhe"] = "\n".join(encontrados)

    from app.criterios_adjudicacao import normalizar_criterio_adjudicacao

    return normalizar_criterio_adjudicacao(**resultado)

def extrair_entregaveis(texto: str) -> str | None:
    """
    A extração de entregáveis será implementada depois
    de validarmos o critério de adjudicação.
    """
    return None


def enriquecer_concurso(
    concurso: dict,
    pdf_url: str,
) -> dict:
    """
    Enriquece uma cópia do concurso com dados do PDF do DR.
    """
    enriquecido = dict(concurso)

    pdf = obter_pdf(pdf_url)
    texto = extrair_texto_pdf(pdf)

    enriquecido.update(
        extrair_criterio(texto)
    )

    enriquecido["entregaveis"] = (
        extrair_entregaveis(texto)
    )

    enriquecido["data_entrega_propostas"] = (
        extrair_data_entrega_propostas(texto)
    )

    enriquecido["data_esclarecimentos"] = (
        extrair_data_esclarecimentos(texto)
    )

    # Permite distinguir uma extração concluída (mesmo quando o
    # documento não contém todos os campos) de uma tentativa que falhou.
    enriquecido["enriquecimento_dr_concluido"] = True

    return enriquecido


def testar_pdf(url: str) -> None:
    """
    Testa a extração num único PDF.
    """
    print("A descarregar um PDF oficial do DR...")
    pdf = obter_pdf(url)

    print(f"PDF recebido: {len(pdf):,} bytes")

    texto = extrair_texto_pdf(pdf)
    secao = _extrair_secao_criterio(texto)
    resultado = extrair_criterio(texto)

    print("\n===== SECÇÃO ENCONTRADA =====")
    print(secao or "Não encontrada")

    print("\n===== RESULTADO =====")
    for chave, valor in resultado.items():
        print(f"{chave}: {valor or 'não identificado'}")



def extrair_data_entrega_propostas(texto: str) -> str | None:
    """
    Extrai a data/hora limite de apresentação
    de propostas a partir do texto do PDF DR.
    """

    import re

    padroes = [
        r"Prazo para apresentação das propostas\s*[:\-]?\s*(\d{2}-\d{2}-\d{4})(?:\s+(\d{2}:\d{2}))?",
        r"Data limite para apresentação das propostas\s*[:\-]?\s*(\d{2}-\d{2}-\d{4})(?:\s+(\d{2}:\d{2}))?",
    ]

    for padrao in padroes:
        resultado = re.search(
            padrao,
            texto,
            re.IGNORECASE
        )

        if resultado:
            data = resultado.group(1)
            hora = resultado.group(2)

            if hora:
                return f"{data} {hora}"

            return data

    return None





def extrair_data_esclarecimentos(texto: str) -> str | None:
    """
    Extrai a data limite para pedidos de esclarecimento.
    """

    padroes = [
        r"pedidos de esclarecimento.*?(\d{2}-\d{2}-\d{4})",
        r"esclarecimentos.*?(\d{2}-\d{2}-\d{4})",
        r"solicita[cç][aã]o de esclarecimentos.*?(\d{2}-\d{2}-\d{4})",
    ]

    for padrao in padroes:
        resultado = re.search(
            padrao,
            texto,
            re.IGNORECASE | re.DOTALL,
        )

        if resultado:
            return resultado.group(1)

    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Testa a extração do critério de adjudicação "
            "num PDF do Diário da República."
        )
    )

    parser.add_argument(
        "url",
        help="URL oficial do PDF do Diário da República.",
    )

    argumentos = parser.parse_args()
    testar_pdf(argumentos.url)



if __name__ == "__main__":
    main()


def _normalizar_referencia_dr(valor: object) -> str:
    """Normaliza Unicode e espaços sem recorrer a fuzzy matching."""
    texto = unicodedata.normalize("NFKC", _texto_limpo(valor))
    texto = texto.replace("\u00a0", " ").replace("\u202f", " ")
    texto = texto.replace("\u00ba", "o").replace("\u00b0", "o")
    texto = _sem_acentos(texto.casefold())
    texto = re.sub(r"\bn\s*\.\s*o\b", "n", texto)
    texto = re.sub(r"\bn\s*o\b", "n", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _numero_anuncio_dr(valor: object) -> str:
    texto = _normalizar_referencia_dr(valor)
    resultado = re.search(r"\b(\d{1,6})\s*/\s*(\d{4})\b", texto)
    if not resultado:
        return texto
    return f"{resultado.group(1)}/{resultado.group(2)}"


def resolver_versoes_dr(original: dict, candidatos: list[dict]) -> dict:
    """Resolve cadeias DR suportadas apenas por referência oficial explícita."""
    def valor(item, *chaves):
        return next(
            (item.get(chave) for chave in chaves if item.get(chave) is not None),
            "",
        )

    def numero(item):
        return _numero_anuncio_dr(
            valor(item, "numero", "numero_anuncio", "anuncio")
        )

    def id_dr(item):
        return _normalizar_referencia_dr(
            valor(item, "id_dr", "dr_id", "id")
        )

    def texto(item):
        return _normalizar_referencia_dr(
            valor(item, "texto", "descricao", "referencia")
        )

    cadeia = [original]
    atual = original

    while True:
        numero_atual = numero(atual)
        id_atual = id_dr(atual)
        correspondencias = []

        for candidato in candidatos:
            if candidato in cadeia:
                continue

            texto_candidato = texto(candidato)
            referencia = re.search(
                r"\balteracao\s+do\s+anuncio\s+de\s+procedimento\b",
                texto_candidato,
            )
            numeros_referidos = {
                f"{grupo[0]}/{grupo[1]}"
                for grupo in re.findall(
                    r"\b(\d{1,6})\s*/\s*(\d{4})\b",
                    texto_candidato[referencia.end():] if referencia else "",
                )
            }
            por_numero = bool(
                referencia and numero_atual in numeros_referidos
            )
            por_id = bool(id_atual and id_atual in texto_candidato)

            if por_numero or por_id:
                correspondencias.append(candidato)

        if len(correspondencias) != 1:
            break

        atual = correspondencias[0]
        cadeia.append(atual)

    resolvido = len(cadeia) > 1
    return {
        "current": atual,
        "chain": cadeia,
        "resolved": resolvido,
        "reason": "explicit_reference" if resolvido else "unresolved",
    }
