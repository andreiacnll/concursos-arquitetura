from ai import analisar_concurso
from coletor import procurar_concursos
from database import (
    concurso_existe,
    contar_concursos,
    criar_base_dados,
    guardar_concurso,
)
from emailer import enviar_email_concursos


LIMITE_RESULTADOS_NO_ECRA = 30


def mostrar_concurso(numero, concurso):
    """
    Mostra um concurso no terminal.
    """
    print("\n" + "-" * 52)
    print(f"{numero}. {concurso['titulo']}")
    print(
        f"   Entidade: "
        f"{concurso.get('entidade') or 'não indicada'}"
    )
    print(
        f"   Publicação: "
        f"{concurso.get('data') or 'não indicada'}"
    )
    print(
        f"   Prazo: "
        f"{concurso.get('data_limite') or 'não indicado'}"
    )
    print(f"   Link: {concurso['link']}")


def guardar_concursos_enviados(concursos):
    """
    Guarda na base de dados os concursos cujo email
    foi enviado com sucesso.

    Devolve a quantidade efetivamente guardada.
    """
    quantidade_guardada = 0

    for concurso in concursos:
        guardado = guardar_concurso(
            titulo=concurso["titulo"],
            entidade=concurso.get("entidade"),
            link=concurso["link"],
            data=concurso.get("data"),
        )

        if guardado:
            quantidade_guardada += 1

    return quantidade_guardada


def main():
    print("=" * 52)
    print(" Concursos para Projetos de Arquitetura")
    print("=" * 52)

    criar_base_dados()

    total_inicial_base_dados = contar_concursos()

    print("\nA analisar os anúncios de 2025...")

    concursos = procurar_concursos(
        dias_atras=1000,
        apenas_abertos=False,
    )

    concursos_relevantes = []
    concursos_novos = []
    concursos_ja_existentes = []
    concursos_excluidos = 0

    for concurso in concursos:
        resultado = analisar_concurso(concurso)

        if not resultado["relevante"]:
            concursos_excluidos += 1
            continue

        concurso["analise"] = resultado
        concursos_relevantes.append(concurso)

        if concurso_existe(concurso["link"]):
            concursos_ja_existentes.append(concurso)
        else:
            concursos_novos.append(concurso)

    print("\n" + "=" * 52)
    print("RESUMO DA ANÁLISE")
    print("=" * 52)
    print(f"Anúncios analisados: {len(concursos)}")
    print(
        f"Concursos relevantes: "
        f"{len(concursos_relevantes)}"
    )
    print(f"Anúncios excluídos: {concursos_excluidos}")
    print(
        f"Concursos novos encontrados: "
        f"{len(concursos_novos)}"
    )
    print(
        f"Concursos que já existiam: "
        f"{len(concursos_ja_existentes)}"
    )

    if not concursos_novos:
        print("\nNão foram encontrados concursos novos.")
        print("Nenhum email foi enviado.")
        return

    quantidade_a_mostrar = min(
        LIMITE_RESULTADOS_NO_ECRA,
        len(concursos_novos),
    )

    print(
        f"\nA mostrar os primeiros "
        f"{quantidade_a_mostrar} concursos novos:"
    )

    for numero, concurso in enumerate(
        concursos_novos[:LIMITE_RESULTADOS_NO_ECRA],
        start=1,
    ):
        mostrar_concurso(numero, concurso)

    restantes = (
        len(concursos_novos)
        - LIMITE_RESULTADOS_NO_ECRA
    )

    if restantes > 0:
        print(
            f"\nExistem ainda {restantes} concursos novos "
            "que não foram mostrados no terminal."
        )

    print("\nA enviar email...")

    try:
        email_enviado = enviar_email_concursos(
            concursos_novos
        )

        if not email_enviado:
            raise RuntimeError(
                "A função de email não confirmou o envio."
            )

    except Exception as erro:
        print("\nERRO: não foi possível enviar o email.")
        print(f"Detalhe: {erro}")
        print(
            "\nOs concursos não foram guardados. "
            "O programa poderá tentar novamente "
            "na próxima execução."
        )
        return

    quantidade_guardada = guardar_concursos_enviados(
        concursos_novos
    )

    total_final_base_dados = contar_concursos()

    print("\nEmail enviado com sucesso.")
    print(
        f"Concursos guardados depois do envio: "
        f"{quantidade_guardada}"
    )
    print(
        f"Total na base de dados: "
        f"{total_inicial_base_dados} -> "
        f"{total_final_base_dados}"
    )


if __name__ == "__main__":
    main()