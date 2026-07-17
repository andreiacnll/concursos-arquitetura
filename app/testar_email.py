from emailer import enviar_email_concursos


def main():
    concurso_teste = {
        "titulo": "Teste do sistema de concursos de arquitetura",
        "entidade": "Teste",
        "data": "17/07/2026",
        "data_limite": "31/07/2026",
        "link": "https://www.base.gov.pt/",
    }

    try:
        enviar_email_concursos([concurso_teste])
        print("Email de teste enviado com sucesso.")

    except Exception as erro:
        print("Não foi possível enviar o email.")
        print(f"Erro: {erro}")


if __name__ == "__main__":
    main()