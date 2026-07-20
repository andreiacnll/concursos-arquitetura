import argparse
import os
import re
import smtplib
import sqlite3
import webbrowser
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo


DB_NAME = "concursos.db"
FICHEIRO_PREVISAO = Path("data/apresentacao_mensal.html")

MESES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def inicio_mes(valor):
    return date(valor.year, valor.month, 1)


def adicionar_mes(valor, quantidade):
    indice = valor.year * 12 + valor.month - 1 + quantidade
    ano, mes_zero = divmod(indice, 12)
    return date(ano, mes_zero + 1, 1)


def converter_data(valor):
    if not valor:
        return None

    texto = str(valor).strip()

    formatos = (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    )

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue

    correspondencia = re.search(
        r"(\d{4})-(\d{2})-(\d{2})",
        texto,
    )

    if correspondencia:
        try:
            return date(
                int(correspondencia.group(1)),
                int(correspondencia.group(2)),
                int(correspondencia.group(3)),
            )
        except ValueError:
            return None

    return None


def converter_preco(valor):
    if valor is None:
        return None

    texto = str(valor).strip()

    if not texto:
        return None

    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"[^\d,.\-]", "", texto)

    if not texto:
        return None

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")

    elif "," in texto:
        partes = texto.split(",")

        if len(partes) == 2:
            texto = partes[0].replace(".", "") + "." + partes[1]
        else:
            texto = texto.replace(",", "")

    elif "." in texto:
        partes = texto.split(".")

        if len(partes) > 2:
            if len(partes[-1]) in {1, 2}:
                texto = "".join(partes[:-1]) + "." + partes[-1]
            else:
                texto = "".join(partes)

        elif len(partes) == 2 and len(partes[1]) == 3:
            texto = "".join(partes)

    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return None

    return numero if numero >= 0 else None


def formatar_euros(valor):
    if valor is None:
        return "Não disponível"

    texto = f"{valor:,.2f}"

    texto = (
        texto.replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )

    return f"{texto} €"


def obter_concursos():
    conexao = sqlite3.connect(DB_NAME)
    conexao.row_factory = sqlite3.Row

    linhas = conexao.execute(
        """
        SELECT
            id,
            titulo,
            entidade,
            link,
            data,
            relevante,
            data_limite,
            preco_base,
            cpv,
            tipo_procedimento
        FROM concursos
        WHERE COALESCE(relevante, 1) = 1
        ORDER BY id DESC
        """
    ).fetchall()

    conexao.close()

    return [dict(linha) for linha in linhas]


def filtrar_periodo(concursos, data_inicio, data_fim):
    resultado = []

    for concurso in concursos:
        data_publicacao = converter_data(concurso.get("data"))

        if not data_publicacao:
            continue

        if data_inicio <= data_publicacao < data_fim:
            concurso = dict(concurso)
            concurso["_data_publicacao"] = data_publicacao
            resultado.append(concurso)

    resultado.sort(
        key=lambda item: item["_data_publicacao"],
        reverse=True,
    )

    return resultado


def calcular_estatisticas(concursos):
    entidades = [
        str(item.get("entidade") or "").strip()
        for item in concursos
        if str(item.get("entidade") or "").strip()
    ]

    precos = [
        preco
        for preco in (
            converter_preco(item.get("preco_base"))
            for item in concursos
        )
        if preco is not None
    ]

    total = sum(precos, Decimal("0")) if precos else None
    media = (
        total / Decimal(len(precos))
        if precos and total is not None
        else None
    )

    return {
        "total_concursos": len(concursos),
        "total_entidades": len(set(entidades)),
        "com_preco": len(precos),
        "valor_total": total,
        "valor_medio": media,
        "com_prazo": sum(
            1
            for item in concursos
            if str(item.get("data_limite") or "").strip()
        ),
        "top_entidades": Counter(entidades).most_common(5),
    }


def variacao_percentual(atual, anterior):
    if anterior == 0:
        return None

    return ((atual - anterior) / anterior) * 100


def formatar_variacao(atual, anterior):
    variacao = variacao_percentual(atual, anterior)

    if variacao is None:
        if atual > 0:
            return "Novo"
        return "0%"

    sinal = "+" if variacao > 0 else ""
    return f"{sinal}{variacao:.1f}%"


def texto_seguro(valor, padrao="Não indicado"):
    texto = str(valor or "").strip()
    return texto or padrao


def criar_cartao_estatistica(titulo, valor, detalhe=""):
    return f"""
    <td style="
        width: 25%;
        padding: 8px;
        vertical-align: top;
    ">
        <div style="
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 18px 12px;
            text-align: center;
            min-height: 86px;
        ">
            <div style="
                color: #64748b;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 8px;
            ">
                {escape(titulo)}
            </div>

            <div style="
                color: #0f172a;
                font-size: 24px;
                font-weight: bold;
                line-height: 1.2;
            ">
                {escape(str(valor))}
            </div>

            <div style="
                color: #64748b;
                font-size: 11px;
                margin-top: 6px;
            ">
                {escape(detalhe)}
            </div>
        </div>
    </td>
    """


def criar_linha_entidades(top_entidades):
    if not top_entidades:
        return """
        <p style="color: #64748b;">
            Não existem entidades para apresentar.
        </p>
        """

    maior = max(total for _, total in top_entidades)

    blocos = []

    for entidade, total in top_entidades:
        largura = max(8, round(total / maior * 100))

        blocos.append(
            f"""
            <div style="margin-bottom: 14px;">
                <div style="
                    display: flex;
                    justify-content: space-between;
                    font-size: 13px;
                    margin-bottom: 5px;
                ">
                    <span>{escape(entidade)}</span>
                    <strong>{total}</strong>
                </div>

                <div style="
                    height: 8px;
                    background: #e2e8f0;
                    border-radius: 999px;
                    overflow: hidden;
                ">
                    <div style="
                        width: {largura}%;
                        height: 8px;
                        background: #0f766e;
                        border-radius: 999px;
                    "></div>
                </div>
            </div>
            """
        )

    return "".join(blocos)


def criar_cartao_concurso(concurso):
    titulo = escape(texto_seguro(concurso.get("titulo"), "Sem título"))
    entidade = escape(texto_seguro(concurso.get("entidade")))
    procedimento = escape(
        texto_seguro(concurso.get("tipo_procedimento"))
    )
    cpv = escape(texto_seguro(concurso.get("cpv")))
    preco = escape(texto_seguro(concurso.get("preco_base")))
    prazo = escape(texto_seguro(concurso.get("data_limite")))
    link = escape(str(concurso.get("link") or "").strip())

    data_publicacao = concurso.get("_data_publicacao")

    data_texto = (
        data_publicacao.strftime("%d/%m/%Y")
        if data_publicacao
        else texto_seguro(concurso.get("data"))
    )

    botao = ""

    if link:
        botao = f"""
        <a
            href="{link}"
            target="_blank"
            rel="noopener noreferrer"
            style="
                display: inline-block;
                background: #0f766e;
                color: #ffffff;
                text-decoration: none;
                padding: 10px 16px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            "
        >
            Consultar anúncio
        </a>
        """

    return f"""
    <div style="
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 5px solid #0f766e;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 16px;
    ">
        <div style="
            color: #64748b;
            font-size: 12px;
            margin-bottom: 8px;
        ">
            Publicado em {escape(data_texto)}
        </div>

        <h3 style="
            color: #0f172a;
            font-size: 18px;
            line-height: 1.4;
            margin: 0 0 14px 0;
        ">
            {titulo}
        </h3>

        <table
            role="presentation"
            width="100%"
            cellspacing="0"
            cellpadding="0"
            style="
                border-collapse: collapse;
                font-size: 13px;
                margin-bottom: 16px;
            "
        >
            <tr>
                <td style="padding: 5px 10px 5px 0; color: #64748b;">
                    Entidade
                </td>
                <td style="padding: 5px 0; color: #0f172a;">
                    <strong>{entidade}</strong>
                </td>
            </tr>

            <tr>
                <td style="padding: 5px 10px 5px 0; color: #64748b;">
                    Procedimento
                </td>
                <td style="padding: 5px 0; color: #0f172a;">
                    {procedimento}
                </td>
            </tr>

            <tr>
                <td style="padding: 5px 10px 5px 0; color: #64748b;">
                    Preço base
                </td>
                <td style="padding: 5px 0; color: #0f172a;">
                    {preco}
                </td>
            </tr>

            <tr>
                <td style="padding: 5px 10px 5px 0; color: #64748b;">
                    Prazo
                </td>
                <td style="padding: 5px 0; color: #0f172a;">
                    {prazo}
                </td>
            </tr>

            <tr>
                <td style="padding: 5px 10px 5px 0; color: #64748b;">
                    CPV
                </td>
                <td style="padding: 5px 0; color: #0f172a;">
                    {cpv}
                </td>
            </tr>
        </table>

        {botao}
    </div>
    """


def criar_secao_concursos(titulo, concursos, limite=None):
    lista = concursos if limite is None else concursos[:limite]

    if not lista:
        conteudo = """
        <div style="
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 20px;
            color: #64748b;
        ">
            Não foram encontrados concursos neste período.
        </div>
        """
    else:
        conteudo = "".join(
            criar_cartao_concurso(concurso)
            for concurso in lista
        )

    nota = ""

    if limite and len(concursos) > limite:
        nota = f"""
        <p style="
            color: #64748b;
            font-size: 12px;
            text-align: center;
        ">
            São apresentados os {limite} concursos mais recentes
            de um total de {len(concursos)}.
        </p>
        """

    return f"""
    <h2 style="
        color: #0f172a;
        font-size: 22px;
        margin: 38px 0 16px 0;
    ">
        {escape(titulo)}
    </h2>

    {conteudo}
    {nota}
    """


def criar_html(
    concursos_atual,
    concursos_anterior,
    inicio_atual,
    inicio_anterior,
):
    estat_atual = calcular_estatisticas(concursos_atual)
    estat_anterior = calcular_estatisticas(concursos_anterior)

    nome_atual = f"{MESES[inicio_atual.month]} de {inicio_atual.year}"
    nome_anterior = (
        f"{MESES[inicio_anterior.month]} de {inicio_anterior.year}"
    )

    variacao = formatar_variacao(
        estat_atual["total_concursos"],
        estat_anterior["total_concursos"],
    )

    agora = datetime.now(ZoneInfo("Europe/Lisbon"))

    periodo_atual = (
        f"1 a {agora.day} de {MESES[inicio_atual.month]} "
        f"de {inicio_atual.year}"
    )

    periodo_anterior = (
        f"{MESES[inicio_anterior.month]} de {inicio_anterior.year}"
    )

    concursos_atual_html = criar_secao_concursos(
        f"Concursos publicados em {nome_atual}",
        concursos_atual,
    )

    concursos_anterior_html = criar_secao_concursos(
        f"Concursos publicados em {nome_anterior}",
        concursos_anterior,
        limite=10,
    )

    return f"""
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
    <title>
        Monitorização de concursos públicos de arquitetura
    </title>
</head>

<body style="
    margin: 0;
    padding: 0;
    background: #f1f5f9;
    font-family: Arial, Helvetica, sans-serif;
    color: #0f172a;
">
    <div style="
        display: none;
        max-height: 0;
        overflow: hidden;
        opacity: 0;
    ">
        Comparação de concursos de arquitetura:
        {escape(nome_atual)} e {escape(nome_anterior)}.
    </div>

    <table
        role="presentation"
        width="100%"
        cellspacing="0"
        cellpadding="0"
        style="background: #f1f5f9;"
    >
        <tr>
            <td align="center" style="padding: 24px 10px;">
                <table
                    role="presentation"
                    width="100%"
                    cellspacing="0"
                    cellpadding="0"
                    style="
                        max-width: 860px;
                        background: #f8fafc;
                        border-radius: 16px;
                        overflow: hidden;
                    "
                >
                    <tr>
                        <td style="
                            background: #0f172a;
                            color: #ffffff;
                            padding: 34px 30px;
                        ">
                            <div style="
                                color: #5eead4;
                                font-size: 12px;
                                font-weight: bold;
                                text-transform: uppercase;
                                letter-spacing: 1.5px;
                                margin-bottom: 10px;
                            ">
                                Sistema de monitorização automática
                            </div>

                            <h1 style="
                                margin: 0 0 12px 0;
                                font-size: 30px;
                                line-height: 1.2;
                            ">
                                Concursos públicos de arquitetura
                            </h1>

                            <p style="
                                margin: 0;
                                color: #cbd5e1;
                                font-size: 15px;
                                line-height: 1.6;
                            ">
                                Comparação entre
                                <strong>{escape(nome_atual)}</strong>
                                e
                                <strong>{escape(nome_anterior)}</strong>
                            </p>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 28px 24px;">
                            <div style="
                                background: #ccfbf1;
                                border: 1px solid #99f6e4;
                                border-radius: 12px;
                                padding: 18px;
                                margin-bottom: 22px;
                            ">
                                <strong>
                                    Resultado principal:
                                </strong>

                                foram identificados
                                <strong>
                                    {estat_atual["total_concursos"]}
                                    concursos
                                </strong>
                                no mês atual, uma variação de
                                <strong>{escape(variacao)}</strong>
                                face ao mês anterior.
                            </div>

                            <h2 style="
                                font-size: 20px;
                                margin: 0 0 14px 0;
                            ">
                                {escape(nome_atual)}
                            </h2>

                            <p style="
                                color: #64748b;
                                font-size: 13px;
                                margin-top: -8px;
                            ">
                                Período considerado:
                                {escape(periodo_atual)}
                            </p>

                            <table
                                role="presentation"
                                width="100%"
                                cellspacing="0"
                                cellpadding="0"
                                style="
                                    border-collapse: collapse;
                                    margin: 0 -8px 28px -8px;
                                "
                            >
                                <tr>
                                    {criar_cartao_estatistica(
                                        "Concursos",
                                        estat_atual["total_concursos"],
                                        f"{variacao} face ao mês anterior",
                                    )}

                                    {criar_cartao_estatistica(
                                        "Entidades",
                                        estat_atual["total_entidades"],
                                        "entidades diferentes",
                                    )}

                                    {criar_cartao_estatistica(
                                        "Valor total",
                                        formatar_euros(
                                            estat_atual["valor_total"]
                                        ),
                                        (
                                            f'{estat_atual["com_preco"]} '
                                            "concursos com preço"
                                        ),
                                    )}

                                    {criar_cartao_estatistica(
                                        "Valor médio",
                                        formatar_euros(
                                            estat_atual["valor_medio"]
                                        ),
                                        "por concurso com preço",
                                    )}
                                </tr>
                            </table>

                            <h2 style="
                                font-size: 20px;
                                margin: 0 0 14px 0;
                            ">
                                Comparação mensal
                            </h2>

                            <table
                                width="100%"
                                cellspacing="0"
                                cellpadding="0"
                                style="
                                    background: #ffffff;
                                    border: 1px solid #e2e8f0;
                                    border-radius: 12px;
                                    border-collapse: separate;
                                    overflow: hidden;
                                    margin-bottom: 28px;
                                "
                            >
                                <tr style="background: #e2e8f0;">
                                    <th
                                        align="left"
                                        style="padding: 12px;"
                                    >
                                        Indicador
                                    </th>
                                    <th
                                        align="right"
                                        style="padding: 12px;"
                                    >
                                        {escape(nome_anterior)}
                                    </th>
                                    <th
                                        align="right"
                                        style="padding: 12px;"
                                    >
                                        {escape(nome_atual)}
                                    </th>
                                </tr>

                                <tr>
                                    <td style="padding: 12px;">
                                        Concursos
                                    </td>
                                    <td
                                        align="right"
                                        style="padding: 12px;"
                                    >
                                        {estat_anterior["total_concursos"]}
                                    </td>
                                    <td
                                        align="right"
                                        style="padding: 12px;"
                                    >
                                        <strong>
                                            {estat_atual["total_concursos"]}
                                        </strong>
                                    </td>
                                </tr>

                                <tr style="background: #f8fafc;">
                                    <td style="padding: 12px;">
                                        Entidades
                                    </td>
                                    <td
                                        align="right"
                                        style="padding: 12px;"
                                    >
                                        {estat_anterior["total_entidades"]}
                                    </td>
                                    <td
                                        align="right"
                                        style="padding: 12px;"
                                    >
                                        <strong>
                                            {estat_atual["total_entidades"]}
                                        </strong>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding: 12px;">
                                        Valor total conhecido
                                    </td>
                                    <td
                                        align="right"
                                        style="padding: 12px;"
                                    >
                                        {formatar_euros(
                                            estat_anterior["valor_total"]
                                        )}
                                    </td>
                                    <td
                                        align="right"
                                        style="padding: 12px;"
                                    >
                                        <strong>
                                            {formatar_euros(
                                                estat_atual["valor_total"]
                                            )}
                                        </strong>
                                    </td>
                                </tr>

                                <tr style="background: #f8fafc;">
                                    <td style="padding: 12px;">
                                        Concursos com prazo
                                    </td>
                                    <td
                                        align="right"
                                        style="padding: 12px;"
                                    >
                                        {estat_anterior["com_prazo"]}
                                    </td>
                                    <td
                                        align="right"
                                        style="padding: 12px;"
                                    >
                                        <strong>
                                            {estat_atual["com_prazo"]}
                                        </strong>
                                    </td>
                                </tr>
                            </table>

                            <h2 style="
                                font-size: 20px;
                                margin: 0 0 16px 0;
                            ">
                                Entidades mais ativas no mês atual
                            </h2>

                            <div style="
                                background: #ffffff;
                                border: 1px solid #e2e8f0;
                                border-radius: 12px;
                                padding: 20px;
                            ">
                                {criar_linha_entidades(
                                    estat_atual["top_entidades"]
                                )}
                            </div>

                            {concursos_atual_html}
                            {concursos_anterior_html}
                        </td>
                    </tr>

                    <tr>
                        <td style="
                            background: #e2e8f0;
                            color: #475569;
                            padding: 20px 30px;
                            text-align: center;
                            font-size: 12px;
                            line-height: 1.6;
                        ">
                            Sistema automático de monitorização de
                            concursos públicos relacionados com
                            arquitetura.

                            <br>

                            Relatório gerado em
                            {agora.strftime("%d/%m/%Y às %H:%M")}.
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def criar_texto_simples(
    concursos_atual,
    concursos_anterior,
    inicio_atual,
    inicio_anterior,
):
    estat_atual = calcular_estatisticas(concursos_atual)
    estat_anterior = calcular_estatisticas(concursos_anterior)

    nome_atual = f"{MESES[inicio_atual.month]} de {inicio_atual.year}"
    nome_anterior = (
        f"{MESES[inicio_anterior.month]} de {inicio_anterior.year}"
    )

    linhas = [
        "CONCURSOS PÚBLICOS DE ARQUITETURA",
        "",
        f"{nome_atual}: {estat_atual['total_concursos']} concursos",
        f"{nome_anterior}: {estat_anterior['total_concursos']} concursos",
        "",
        "CONCURSOS DO MÊS ATUAL",
        "",
    ]

    for concurso in concursos_atual:
        linhas.extend(
            [
                texto_seguro(concurso.get("titulo"), "Sem título"),
                f"Entidade: {texto_seguro(concurso.get('entidade'))}",
                f"Data: {texto_seguro(concurso.get('data'))}",
                f"Preço: {texto_seguro(concurso.get('preco_base'))}",
                f"Prazo: {texto_seguro(concurso.get('data_limite'))}",
                f"Link: {texto_seguro(concurso.get('link'))}",
                "",
            ]
        )

    return "\n".join(linhas)


def obter_variavel(nome):
    valor = os.getenv(nome)

    if not valor:
        raise RuntimeError(
            f"A variável de ambiente {nome} não está configurada."
        )

    return valor


def enviar_email(assunto, texto, html):
    host = obter_variavel("SMTP_HOST")
    porta = int(obter_variavel("SMTP_PORT"))
    utilizador = obter_variavel("SMTP_USER")
    password = obter_variavel("SMTP_PASSWORD").strip()
    remetente = obter_variavel("EMAIL_FROM")
    destinatarios = obter_variavel("EMAIL_TO")

    usar_ssl = os.getenv(
        "SMTP_USE_SSL",
        "true",
    ).lower() in {"1", "true", "sim", "yes"}

    mensagem = EmailMessage()
    mensagem["From"] = remetente
    mensagem["To"] = destinatarios
    mensagem["Subject"] = assunto
    mensagem.set_content(texto)
    mensagem.add_alternative(html, subtype="html")

    if usar_ssl:
        with smtplib.SMTP_SSL(host, porta) as servidor:
            servidor.login(utilizador, password)
            servidor.send_message(mensagem)
    else:
        with smtplib.SMTP(host, porta) as servidor:
            servidor.starttls()
            servidor.login(utilizador, password)
            servidor.send_message(mensagem)

    print(f"Email enviado para {destinatarios}.")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Gera uma apresentação dos concursos do mês atual "
            "e do mês anterior."
        )
    )

    parser.add_argument(
        "--enviar",
        action="store_true",
        help="Envia o relatório por email.",
    )

    parser.add_argument(
        "--abrir",
        action="store_true",
        help="Abre a previsão HTML no browser.",
    )

    argumentos = parser.parse_args()

    agora = datetime.now(ZoneInfo("Europe/Lisbon"))
    hoje = agora.date()

    inicio_atual = inicio_mes(hoje)
    inicio_proximo = adicionar_mes(inicio_atual, 1)
    inicio_anterior = adicionar_mes(inicio_atual, -1)

    todos = obter_concursos()

    concursos_atual = filtrar_periodo(
        todos,
        inicio_atual,
        inicio_proximo,
    )

    concursos_anterior = filtrar_periodo(
        todos,
        inicio_anterior,
        inicio_atual,
    )

    html = criar_html(
        concursos_atual,
        concursos_anterior,
        inicio_atual,
        inicio_anterior,
    )

    texto = criar_texto_simples(
        concursos_atual,
        concursos_anterior,
        inicio_atual,
        inicio_anterior,
    )

    FICHEIRO_PREVISAO.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    FICHEIRO_PREVISAO.write_text(
        html,
        encoding="utf-8",
    )

    nome_atual = f"{MESES[inicio_atual.month]} de {inicio_atual.year}"
    nome_anterior = (
        f"{MESES[inicio_anterior.month]} de {inicio_anterior.year}"
    )

    print("=" * 64)
    print(" APRESENTAÇÃO MENSAL — CONCURSOS DE ARQUITETURA")
    print("=" * 64)
    print()
    print(f"{nome_atual}: {len(concursos_atual)} concursos")
    print(f"{nome_anterior}: {len(concursos_anterior)} concursos")
    print()
    print(f"Pré-visualização criada em: {FICHEIRO_PREVISAO}")

    if argumentos.abrir:
        webbrowser.open(FICHEIRO_PREVISAO.resolve().as_uri())

    if argumentos.enviar:
        assunto = (
            "Concursos públicos de arquitetura — "
            f"{nome_atual} vs. {nome_anterior}"
        )

        enviar_email(
            assunto=assunto,
            texto=texto,
            html=html,
        )


if __name__ == "__main__":
    main()
