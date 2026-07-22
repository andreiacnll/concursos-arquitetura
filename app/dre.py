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


def extrair_criterio(texto: str) -> dict[str, str | None]:
    """
    Extrai o critério de adjudicação do texto do anúncio.

    Não inventa percentagens em critérios multifator.
    Para monofator, o único fator corresponde a 100%.
    """
    resultado: dict[str, str | None] = {
        "criterio_tipo": None,
        "criterio_resumo": None,
        "criterio_detalhe": None,
    }

    secao = _extrair_secao_criterio(texto)

    if not secao:
        return resultado

    pesquisa = _sem_acentos(secao).casefold()

    multifator_nao = bool(
        re.search(
            r"multifator\s*:\s*nao\b",
            pesquisa,
        )
    )

    multifator_sim = bool(
        re.search(
            r"multifator\s*:\s*sim\b",
            pesquisa,
        )
    )

    tem_monofator = "monofator" in pesquisa
    fatores = _extrair_fatores(secao)

    if multifator_nao or tem_monofator:
        resultado["criterio_tipo"] = "Monofator"

        nome = ""

        correspondencia = re.search(
            r"(?:nome|designacao)\s*:\s*([^\n]+)",
            secao,
            flags=re.IGNORECASE,
        )

        if correspondencia:
            nome = _limpar_nome_fator(
                correspondencia.group(1)
            )

        if not nome and fatores:
            nome = fatores[0][0]

        if not nome and re.search(
            r"\bpreco\b",
            pesquisa,
        ):
            nome = "Preço"

        if nome:
            resumo = f"{nome} 100%"

            resultado["criterio_resumo"] = resumo
            resultado["criterio_detalhe"] = resumo

        return resultado

    if multifator_sim or len(fatores) >= 2:
        resultado["criterio_tipo"] = "Multifator"

        if fatores:
            linhas = [
                f"{nome} {percentagem}"
                for nome, percentagem in fatores
            ]

            resultado["criterio_resumo"] = " • ".join(linhas)
            resultado["criterio_detalhe"] = "\n".join(linhas)

        return resultado

    # A secção existe, mas o formato não foi suficientemente
    # claro para classificar com segurança.
    resultado["criterio_detalhe"] = secao

    return resultado


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
