cat > app/emailer.py <<'PY'
import os
import smtplib
from collections import Counter
from email.message import EmailMessage
from html import escape


def _obter_variavel(nome):
    valor = os.getenv(nome)

    if not valor:
        raise RuntimeError(
            f"A variável de ambiente {nome} não está configurada."
        )

    return valor


def _obter_configuracao_smtp():
    """
    Obtém a configuração comum aos emails diários
    e mensais.
    """
    return {
        "host": _obter_variavel("SMTP_HOST"),
        "port": int(_obter_variavel("SMTP_PORT")),
        "user": _obter_variavel("SMTP_USER"),
        "password": _obter_variavel(
            "SMTP_PASSWORD"
        ).strip(),
        "email_from": _obter_variavel("EMAIL_FROM"),
        "email_to": _obter_variavel("EMAIL_TO"),
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
    Envia uma mensagem através do servidor SMTP
    configurado nas variáveis de ambiente.
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
                    f"{concurso.get('titulo', 'Sem título')}"
                ),
                (
                    "Entidade: "
                    f"{concurso.get('entidade', 'Não indicada')}"
                ),
                (
                    "Data de publicação: "
                    f"{concurso.get('data', 'Não indicada')}"
                ),
                (
                    "Data limite: "
                    f"{concurso.get('data_limite', 'Não indicada')}"
                ),
                (
                    "Link: "
                    f"{concurso.get('link', 'Não indicado')}"
                ),
                "",
            ]
        )

    return "\n".join(linhas)


def _criar_html_email(concursos):
    blocos = []

    for concurso in concursos:
        titulo = escape(
            str(
                concurso.get(
                    "titulo",
                    "Sem título",
                )
            )
        )

        entidade = escape(
            str(
                concurso.get(
                    "entidade",
                    "Não indicada",
                )
            )
        )

        data = escape(
            str(
                concurso.get(
                    "data",
                    "Não indicada",
                )
            )
        )

        data_limite = escape(
            str(
                concurso.get(
                    "data_limite",
                    "Não indicada",
                )
            )
        )

        link = escape(
            str(
                concurso.get(
                    "link",
                    "",
                )
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
                padding: 16px;
                margin-bottom: 16px;
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
        max-width: 800px;
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
        print("Não existem concursos novos para enviar.")
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
    Conta quantos concursos foram publicados
    por cada entidade.
    """
    contador = Counter()

    for concurso in concursos:
        entidade = (
            concurso.get("entidade")
            or "Entidade não indicada"
        ).strip()

        contador[entidade] += 1

    return contador.most_common()


def _criar_texto_resumo_mensal(
    concursos,
    nome_mes,
    ano,
):
    linhas = [
        f"Resumo mensal de concursos de arquitetura "
        f"— {nome_mes} de {ano}",
        "",
        f"Total de concursos encontrados: {len(concursos)}",
        "",
        "Entidades que mais publicaram:",
    ]

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
                    f"{concurso.get('titulo', 'Sem título')}"
                ),
                (
                    "Entidade: "
                    f"{concurso.get('entidade') or 'Não indicada'}"
                ),
                (
                    "Data de publicação: "
                    f"{concurso.get('data') or 'Não indicada'}"
                ),
                (
                    "Link: "
                    f"{concurso.get('link') or 'Não indicado'}"
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
    entidades = _contar_entidades(concursos)

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

    blocos_concursos = []

    for concurso in concursos:
        titulo = escape(
            str(
                concurso.get("titulo")
                or "Sem título"
            )
        )

        entidade = escape(
            str(
                concurso.get("entidade")
                or "Não indicada"
            )
        )

        data = escape(
            str(
                concurso.get("data")
                or "Não indicada"
            )
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
                padding: 16px;
                margin-bottom: 16px;
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
        max-width: 850px;
        margin: 0 auto;
        padding: 24px;
    ">
        <h1>
            Resumo mensal de concursos de arquitetura
        </h1>

        <h2>
            {nome_mes_html} de {ano}
        </h2>

        <p>
            Total de concursos encontrados:
            <strong>{len(concursos)}</strong>
        </p>

        <h2>Entidades que mais publicaram</h2>

        <ol>
            {linhas_entidades}
        </ol>

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
    Envia o relatório mensal.

    Ao contrário do email diário, envia o relatório
    mesmo quando o total do mês é zero.
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
PY