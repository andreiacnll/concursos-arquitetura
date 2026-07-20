import os
import re
import smtplib
from collections import Counter
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from html import escape


def _obter_variavel(nome):
    valor = os.getenv(nome)

    if not valor:
        raise RuntimeError(
            f"A variável de ambiente {nome} "
            "não está configurada."
        )

    return valor


def _obter_configuracao_smtp():
    """
    Obtém a configuração comum aos emails diários
    e mensais.
    """
    return {
        "host": _obter_variavel("SMTP_HOST"),
        "port": int(
            _obter_variavel("SMTP_PORT")
        ),
        "user": _obter_variavel("SMTP_USER"),
        "password": _obter_variavel(
            "SMTP_PASSWORD"
        ).strip(),
        "email_from": _obter_variavel(
            "EMAIL_FROM"
        ),
        "email_to": _obter_variavel(
            "EMAIL_TO"
        ),
        "usar_ssl": os.getenv(
            "SMTP_USE_SSL",
            "true",
        ).lower()
        in {
            "1",
            "true",
            "sim",
            "yes",
        },
    }


def _enviar_mensagem(mensagem):
    """
    Envia uma mensagem através do servidor SMTP.
    """
    configuracao = _obter_configuracao_smtp()

    if configuracao["usar_ssl"]:
        with smtplib.SMTP_SSL(
            configuracao["host"],
            configuracao["port"],
        ) as servidor:
            servidor.login(
                configuracao["user"],
                configuracao["password"],
            )
            servidor.send_message(mensagem)

    else:
        with smtplib.SMTP(
            configuracao["host"],
            configuracao["port"],
        ) as servidor:
            servidor.starttls()
            servidor.login(
                configuracao["user"],
                configuracao["password"],
            )
            servidor.send_message(mensagem)

    return configuracao["email_to"]


def _valor_texto(valor, padrao="Não indicado"):
    """
    Devolve um texto limpo ou o valor padrão.
    """
    if valor is None:
        return padrao

    if isinstance(valor, list):
        valores = [
            str(item).strip()
            for item in valor
            if str(item).strip()
        ]

        return "; ".join(valores) or padrao

    texto = str(valor).strip()

    return texto or padrao


def _obter_cpv(concurso):
    return _valor_texto(
        concurso.get("cpv")
        or concurso.get("cpvs")
    )


def _obter_procedimento(concurso):
    return _valor_texto(
        concurso.get("tipo_procedimento")
        or concurso.get("tipos_contrato")
    )


def _converter_preco_decimal(valor):
    """
    Converte preços apresentados em formatos portugueses
    ou internacionais para Decimal.

    Exemplos aceites:
        1.250.000,00 €
        1250000.00
        1 250 000 €
    """
    if valor is None:
        return None

    texto = str(valor).strip()

    if not texto:
        return None

    texto = texto.replace("\xa0", " ")
    texto = re.sub(
        r"[^\d,.\-]",
        "",
        texto,
    )

    if not texto:
        return None

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "")
            texto = texto.replace(",", ".")
        else:
            texto = texto.replace(",", "")

    elif "," in texto:
        partes = texto.split(",")

        if len(partes) == 2:
            texto = (
                partes[0].replace(".", "")
                + "."
                + partes[1]
            )
        else:
            texto = texto.replace(",", "")

    elif "." in texto:
        partes = texto.split(".")

        if len(partes) > 2:
            if len(partes[-1]) in {1, 2}:
                texto = (
                    "".join(partes[:-1])
                    + "."
                    + partes[-1]
                )
            else:
                texto = "".join(partes)

        elif (
            len(partes) == 2
            and len(partes[1]) == 3
        ):
            texto = "".join(partes)

    try:
        numero = Decimal(texto)

    except InvalidOperation:
        return None

    if numero < 0:
        return None

    return numero


def _formatar_euros(valor):
    """
    Formata um Decimal no padrão português.
    """
    texto = f"{valor:,.2f}"

    texto = (
        texto.replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )

    return f"{texto} €"


def _calcular_estatisticas_precos(concursos):
    """
    Calcula valor total, média e número de preços válidos.
    """
    valores = []

    for concurso in concursos:
        valor = _converter_preco_decimal(
            concurso.get("preco_base")
        )

        if valor is not None:
            valores.append(valor)

    if not valores:
        return {
            "quantidade": 0,
            "total": None,
            "media": None,
        }

    total = sum(
        valores,
        Decimal("0"),
    )

    media = total / Decimal(
        len(valores)
    )

    return {
        "quantidade": len(valores),
        "total": total,
        "media": media,
    }


def _criar_texto_email(concursos):
    linhas = [
        f"Foram encontrados {len(concursos)} "
        "novos concursos de arquitetura.",
        "",
    ]

    for indice, concurso in enumerate(
        concursos,
        start=1,
    ):
        linhas.extend(
            [
                (
                    f"{indice}. "
                    f"{_valor_texto(concurso.get('titulo'), 'Sem título')}"
                ),
                (
                    "Entidade: "
                    f"{_valor_texto(concurso.get('entidade'))}"
                ),
                (
                    "Data de publicação: "
                    f"{_valor_texto(concurso.get('data'))}"
                ),
                (
                    "Data limite: "
                    f"{_valor_texto(concurso.get('data_limite'))}"
                ),
                (
                    "Preço base: "
                    f"{_valor_texto(concurso.get('preco_base'))}"
                ),
                (
                    "Procedimento: "
                    f"{_obter_procedimento(concurso)}"
                ),
                (
                    "CPV: "
                    f"{_obter_cpv(concurso)}"
                ),
                (
                    "Link: "
                    f"{_valor_texto(concurso.get('link'))}"
                ),
                "",
            ]
        )

    return "\n".join(linhas)


def _criar_html_email(concursos):
    blocos = []

    for concurso in concursos:
        titulo = escape(
            _valor_texto(
                concurso.get("titulo"),
                "Sem título",
            )
        )

        entidade = escape(
            _valor_texto(
                concurso.get("entidade")
            )
        )

        data = escape(
            _valor_texto(
                concurso.get("data")
            )
        )

        data_limite = escape(
            _valor_texto(
                concurso.get("data_limite")
            )
        )

        preco_base = escape(
            _valor_texto(
                concurso.get("preco_base")
            )
        )

        procedimento = escape(
            _obter_procedimento(concurso)
        )

        cpv = escape(
            _obter_cpv(concurso)
        )

        link = escape(
            str(
                concurso.get("link")
                or ""
            )
        )

        if link:
            link_html = (
                f'<a href="{link}" target="_blank" '
                'rel="noopener noreferrer">'
                "Abrir concurso"
                "</a>"
            )
        else:
            link_html = "Link não indicado"

        blocos.append(
            f"""
            <div style="
                border: 1px solid #dddddd;
                border-radius: 8px;
                padding: 18px;
                margin-bottom: 18px;
            ">
                <h2 style="margin-top: 0;">
                    {titulo}
                </h2>

                <p>
                    <strong>Entidade:</strong>
                    {entidade}
                </p>

                <p>
                    <strong>Data de publicação:</strong>
                    {data}
                </p>

                <p>
                    <strong>Data limite:</strong>
                    {data_limite}
                </p>

                <p>
                    <strong>Preço base:</strong>
                    {preco_base}
                </p>

                <p>
                    <strong>Procedimento:</strong>
                    {procedimento}
                </p>

                <p>
                    <strong>CPV:</strong>
                    {cpv}
                </p>

                <p>{link_html}</p>
            </div>
            """
        )

    return f"""
    <!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">
        <title>
            Novos concursos de arquitetura
        </title>
    </head>

    <body style="
        font-family: Arial, sans-serif;
        color: #222222;
        max-width: 850px;
        margin: 0 auto;
        padding: 24px;
    ">
        <h1>Novos concursos de arquitetura</h1>

        <p>
            Foram encontrados
            <strong>{len(concursos)}</strong>
            novos concursos.
        </p>

        {''.join(blocos)}
    </body>
    </html>
    """


def enviar_email_concursos(concursos):
    """
    Envia o alerta diário com os concursos novos.
    """
    if not concursos:
        print(
            "Não existem concursos novos para enviar."
        )
        return False

    configuracao = _obter_configuracao_smtp()

    mensagem = EmailMessage()
    mensagem["From"] = configuracao["email_from"]
    mensagem["To"] = configuracao["email_to"]
    mensagem["Subject"] = (
        "Novos concursos de arquitetura "
        f"({len(concursos)})"
    )

    mensagem.set_content(
        _criar_texto_email(concursos)
    )

    mensagem.add_alternative(
        _criar_html_email(concursos),
        subtype="html",
    )

    email_to = _enviar_mensagem(mensagem)

    print(
        f"Email enviado para {email_to} "
        f"com {len(concursos)} concurso(s)."
    )

    return True


def _contar_entidades(concursos):
    """
    Conta os concursos publicados por entidade.
    """
    contador = Counter()

    for concurso in concursos:
        entidade = _valor_texto(
            concurso.get("entidade"),
            "Entidade não indicada",
        )

        contador[entidade] += 1

    return contador.most_common()


def _contar_procedimentos(concursos):
    """
    Conta os concursos por tipo de procedimento.
    """
    contador = Counter()

    for concurso in concursos:
        procedimento = _obter_procedimento(
            concurso
        )

        contador[procedimento] += 1

    return contador.most_common()


def _criar_texto_resumo_mensal(
    concursos,
    nome_mes,
    ano,
):
    estatisticas = _calcular_estatisticas_precos(
        concursos
    )

    linhas = [
        (
            "Resumo mensal de concursos "
            f"de arquitetura — {nome_mes} de {ano}"
        ),
        "",
        (
            "Total de concursos encontrados: "
            f"{len(concursos)}"
        ),
    ]

    if estatisticas["total"] is not None:
        linhas.extend(
            [
                (
                    "Valor total com preço conhecido: "
                    f"{_formatar_euros(estatisticas['total'])}"
                ),
                (
                    "Preço base médio: "
                    f"{_formatar_euros(estatisticas['media'])}"
                ),
                (
                    "Concursos com preço conhecido: "
                    f"{estatisticas['quantidade']}"
                ),
            ]
        )
    else:
        linhas.append(
            "Não existem preços base disponíveis."
        )

    linhas.extend(
        [
            "",
            "Entidades que mais publicaram:",
        ]
    )

    entidades = _contar_entidades(concursos)

    if entidades:
        for entidade, total in entidades[:10]:
            linhas.append(
                f"- {entidade}: {total}"
            )
    else:
        linhas.append(
            "- Não foram encontrados concursos."
        )

    linhas.extend(
        [
            "",
            "Tipos de procedimento:",
        ]
    )

    procedimentos = _contar_procedimentos(
        concursos
    )

    if procedimentos:
        for procedimento, total in (
            procedimentos[:10]
        ):
            linhas.append(
                f"- {procedimento}: {total}"
            )
    else:
        linhas.append(
            "- Não existem dados de procedimento."
        )

    linhas.extend(
        [
            "",
            "Concursos:",
            "",
        ]
    )

    if not concursos:
        linhas.append(
            "Não foram encontrados concursos "
            "durante este mês."
        )

    for indice, concurso in enumerate(
        concursos,
        start=1,
    ):
        linhas.extend(
            [
                (
                    f"{indice}. "
                    f"{_valor_texto(concurso.get('titulo'), 'Sem título')}"
                ),
                (
                    "Entidade: "
                    f"{_valor_texto(concurso.get('entidade'))}"
                ),
                (
                    "Data de publicação: "
                    f"{_valor_texto(concurso.get('data'))}"
                ),
                (
                    "Data limite: "
                    f"{_valor_texto(concurso.get('data_limite'))}"
                ),
                (
                    "Preço base: "
                    f"{_valor_texto(concurso.get('preco_base'))}"
                ),
                (
                    "Procedimento: "
                    f"{_obter_procedimento(concurso)}"
                ),
                (
                    "CPV: "
                    f"{_obter_cpv(concurso)}"
                ),
                (
                    "Link: "
                    f"{_valor_texto(concurso.get('link'))}"
                ),
                "",
            ]
        )

    return "\n".join(linhas)


def _criar_html_resumo_mensal(
    concursos,
    nome_mes,
    ano,
):
    entidades = _contar_entidades(
        concursos
    )

    procedimentos = _contar_procedimentos(
        concursos
    )

    estatisticas = _calcular_estatisticas_precos(
        concursos
    )

    if entidades:
        linhas_entidades = "".join(
            (
                "<li>"
                f"{escape(entidade)}: "
                f"<strong>{total}</strong>"
                "</li>"
            )
            for entidade, total in entidades[:10]
        )
    else:
        linhas_entidades = (
            "<li>Não foram encontrados concursos.</li>"
        )

    if procedimentos:
        linhas_procedimentos = "".join(
            (
                "<li>"
                f"{escape(procedimento)}: "
                f"<strong>{total}</strong>"
                "</li>"
            )
            for procedimento, total
            in procedimentos[:10]
        )
    else:
        linhas_procedimentos = (
            "<li>Não existem dados de procedimento.</li>"
        )

    if estatisticas["total"] is not None:
        resumo_precos = f"""
        <p>
            <strong>Valor total com preço conhecido:</strong>
            {_formatar_euros(estatisticas["total"])}
        </p>

        <p>
            <strong>Preço base médio:</strong>
            {_formatar_euros(estatisticas["media"])}
        </p>

        <p>
            <strong>Concursos com preço conhecido:</strong>
            {estatisticas["quantidade"]}
        </p>
        """
    else:
        resumo_precos = """
        <p>
            Não existem preços base disponíveis
            para este período.
        </p>
        """

    blocos_concursos = []

    for concurso in concursos:
        titulo = escape(
            _valor_texto(
                concurso.get("titulo"),
                "Sem título",
            )
        )

        entidade = escape(
            _valor_texto(
                concurso.get("entidade")
            )
        )

        data = escape(
            _valor_texto(
                concurso.get("data")
            )
        )

        data_limite = escape(
            _valor_texto(
                concurso.get("data_limite")
            )
        )

        preco_base = escape(
            _valor_texto(
                concurso.get("preco_base")
            )
        )

        procedimento = escape(
            _obter_procedimento(concurso)
        )

        cpv = escape(
            _obter_cpv(concurso)
        )

        link = escape(
            str(
                concurso.get("link")
                or ""
            )
        )

        if link:
            link_html = (
                f'<a href="{link}" target="_blank" '
                'rel="noopener noreferrer">'
                "Abrir concurso"
                "</a>"
            )
        else:
            link_html = "Link não indicado"

        blocos_concursos.append(
            f"""
            <div style="
                border: 1px solid #dddddd;
                border-radius: 8px;
                padding: 18px;
                margin-bottom: 18px;
            ">
                <h2 style="margin-top: 0;">
                    {titulo}
                </h2>

                <p>
                    <strong>Entidade:</strong>
                    {entidade}
                </p>

                <p>
                    <strong>Data de publicação:</strong>
                    {data}
                </p>

                <p>
                    <strong>Data limite:</strong>
                    {data_limite}
                </p>

                <p>
                    <strong>Preço base:</strong>
                    {preco_base}
                </p>

                <p>
                    <strong>Procedimento:</strong>
                    {procedimento}
                </p>

                <p>
                    <strong>CPV:</strong>
                    {cpv}
                </p>

                <p>{link_html}</p>
            </div>
            """
        )

    if not blocos_concursos:
        blocos_concursos.append(
            """
            <p>
                Não foram encontrados concursos
                durante este mês.
            </p>
            """
        )

    nome_mes_html = escape(nome_mes)

    return f"""
    <!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">

        <title>
            Resumo mensal de concursos de arquitetura
        </title>
    </head>

    <body style="
        font-family: Arial, sans-serif;
        color: #222222;
        max-width: 900px;
        margin: 0 auto;
        padding: 24px;
    ">
        <h1>
            Resumo mensal de concursos de arquitetura
        </h1>

        <h2>
            {nome_mes_html} de {ano}
        </h2>

        <div style="
            border: 1px solid #dddddd;
            border-radius: 8px;
            padding: 18px;
            margin-bottom: 24px;
        ">
            <p>
                <strong>Total de concursos:</strong>
                {len(concursos)}
            </p>

            {resumo_precos}
        </div>

        <h2>Entidades que mais publicaram</h2>

        <ol>
            {linhas_entidades}
        </ol>

        <h2>Tipos de procedimento</h2>

        <ul>
            {linhas_procedimentos}
        </ul>

        <h2>Concursos</h2>

        {''.join(blocos_concursos)}
    </body>
    </html>
    """


def enviar_email_resumo_mensal(
    concursos,
    nome_mes,
    ano,
):
    """
    Envia o relatório mensal, mesmo quando
    o total do mês é zero.
    """
    configuracao = _obter_configuracao_smtp()

    mensagem = EmailMessage()
    mensagem["From"] = configuracao["email_from"]
    mensagem["To"] = configuracao["email_to"]
    mensagem["Subject"] = (
        "Resumo mensal de concursos de arquitetura "
        f"— {nome_mes} de {ano} "
        f"({len(concursos)})"
    )

    mensagem.set_content(
        _criar_texto_resumo_mensal(
            concursos,
            nome_mes,
            ano,
        )
    )

    mensagem.add_alternative(
        _criar_html_resumo_mensal(
            concursos,
            nome_mes,
            ano,
        ),
        subtype="html",
    )

    email_to = _enviar_mensagem(mensagem)

    print(
        f"Resumo mensal enviado para {email_to}."
    )

    print(
        "Concursos incluídos no resumo: "
        f"{len(concursos)}"
    )

    return True