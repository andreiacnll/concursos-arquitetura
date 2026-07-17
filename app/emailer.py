import os
import smtplib
from email.message import EmailMessage
from html import escape


def _obter_variavel(nome):
    valor = os.getenv(nome)

    if not valor:
        raise RuntimeError(
            f"A variável de ambiente {nome} não está configurada."
        )

    return valor


def _criar_texto_email(concursos):
    linhas = [
        f"Foram encontrados {len(concursos)} novos concursos de arquitetura.",
        "",
    ]

    for indice, concurso in enumerate(concursos, start=1):
        linhas.extend(
            [
                f"{indice}. {concurso.get('titulo', 'Sem título')}",
                f"Entidade: {concurso.get('entidade', 'Não indicada')}",
                f"Data de publicação: {concurso.get('data', 'Não indicada')}",
                f"Data limite: {concurso.get('data_limite', 'Não indicada')}",
                f"Link: {concurso.get('link', 'Não indicado')}",
                "",
            ]
        )

    return "\n".join(linhas)


def _criar_html_email(concursos):
    blocos = []

    for concurso in concursos:
        titulo = escape(str(concurso.get("titulo", "Sem título")))
        entidade = escape(str(concurso.get("entidade", "Não indicada")))
        data = escape(str(concurso.get("data", "Não indicada")))
        data_limite = escape(
            str(concurso.get("data_limite", "Não indicada"))
        )
        link = escape(str(concurso.get("link", "")))

        if link:
            link_html = (
                f'<a href="{link}" target="_blank" '
                f'rel="noopener noreferrer">Abrir concurso</a>'
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
                <h2 style="margin-top: 0;">{titulo}</h2>
                <p><strong>Entidade:</strong> {entidade}</p>
                <p><strong>Data de publicação:</strong> {data}</p>
                <p><strong>Data limite:</strong> {data_limite}</p>
                <p>{link_html}</p>
            </div>
            """
        )

    return f"""
    <!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">
        <title>Novos concursos de arquitetura</title>
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
    if not concursos:
        print("Não existem concursos novos para enviar.")
        return False

    smtp_host = _obter_variavel("SMTP_HOST")
    smtp_port = int(_obter_variavel("SMTP_PORT"))
    smtp_user = _obter_variavel("SMTP_USER")
    smtp_password = _obter_variavel("SMTP_PASSWORD")
    email_from = _obter_variavel("EMAIL_FROM")
    email_to = _obter_variavel("EMAIL_TO")

    usar_ssl = os.getenv("SMTP_USE_SSL", "true").lower() in {
        "1",
        "true",
        "sim",
        "yes",
    }

    mensagem = EmailMessage()
    mensagem["From"] = email_from
    mensagem["To"] = email_to
    mensagem["Subject"] = (
        f"Novos concursos de arquitetura ({len(concursos)})"
    )

    mensagem.set_content(_criar_texto_email(concursos))
    mensagem.add_alternative(
        _criar_html_email(concursos),
        subtype="html",
    )

    if usar_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as servidor:
            servidor.login(smtp_user, smtp_password)
            servidor.send_message(mensagem)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as servidor:
            servidor.starttls()
            servidor.login(smtp_user, smtp_password)
            servidor.send_message(mensagem)

    print(
        f"Email enviado para {email_to} "
        f"com {len(concursos)} concurso(s)."
    )

    return True