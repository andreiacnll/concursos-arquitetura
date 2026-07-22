from .ai import analisar_concurso
from .coletor import procurar_concursos
from .database import (
    atualizar_dados_concurso,
    concurso_existe,
    contar_concursos,
    criar_base_dados,
    guardar_concurso,
)
from .emailer import enviar_email_concursos


LIMITE_RESULTADOS_NO_ECRA = 30


def _obter_cpv_texto(concurso):
    """
    Converte os CPVs do concurso num único texto.
    """
    cpvs = concurso.get("cpvs")

    if isinstance(cpvs, list):
        return "; ".join(
            str(cpv).strip()
            for cpv in cpvs
            if str(cpv).strip()
        )

    if cpvs:
        return str(cpvs).strip()

    cpv = concurso.get("cpv")

    if cpv:
        return str(cpv).strip()

    return ""


def _obter_tipo_procedimento(concurso):
    """
    Obtém o tipo de procedimento disponível no concurso.

    O coletor fornece uma lista com o tipo de contrato,
    procedimento, modelo e anúncio. Mantemos toda essa
    informação para não perder dados.
    """
    tipo_direto = concurso.get(
        "tipo_procedimento"
    )

    if tipo_direto:
        return str(tipo_direto).strip()

    tipos = concurso.get("tipos_contrato")

    if isinstance(tipos, list):
        valores = []

        for tipo in tipos:
            texto = str(tipo).strip()

            if texto and texto not in valores:
                valores.append(texto)

        return "; ".join(valores)

    if tipos:
        return str(tipos).strip()

    return ""


def mostrar_concurso(numero, concurso):
    """
    Mostra um concurso no terminal.
    """
    print("\n" + "-" * 52)
    print(f"{numero}. {concurso['titulo']}")

    print(
        "   Entidade: "
        f"{concurso.get('entidade') or 'não indicada'}"
    )

    print(
        "   Publicação: "
        f"{concurso.get('data') or 'não indicada'}"
    )

    print(
        "   Prazo: "
        f"{concurso.get('data_limite') or 'não indicado'}"
    )

    print(
        "   Preço base: "
        f"{concurso.get('preco_base') or 'não indicado'}"
    )

    print(
        "   Procedimento: "
        f"{_obter_tipo_procedimento(concurso) or 'não indicado'}"
    )

    print(
        "   CPV: "
        f"{_obter_cpv_texto(concurso) or 'não indicado'}"
    )

    print(f"   Link: {concurso['link']}")


def atualizar_concursos_existentes(concursos):
    """
    Atualiza preço, prazo, CPV e procedimento dos
    concursos que já estavam guardados.
    """
    quantidade_atualizada = 0

    for concurso in concursos:
        atualizado = atualizar_dados_concurso(
            link=concurso["link"],
            titulo=concurso.get("titulo"),
            entidade=concurso.get("entidade"),
            data=concurso.get("data"),
            data_limite=concurso.get(
                "data_limite"
            ),
            preco_base=concurso.get(
                "preco_base"
            ),
            cpv=_obter_cpv_texto(concurso),
            tipo_procedimento=(
                _obter_tipo_procedimento(
                    concurso
                )
            ),
        )

        if atualizado:
            quantidade_atualizada += 1

    return quantidade_atualizada


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
            data_limite=concurso.get(
                "data_limite"
            ),
            preco_base=concurso.get(
                "preco_base"
            ),
            cpv=_obter_cpv_texto(concurso),
            tipo_procedimento=(
                _obter_tipo_procedimento(
                    concurso
                )
            ),
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

    print(
        "\nA recolher anúncios recentes "
        "do Portal BASE..."
    )

    try:
        concursos = procurar_concursos()

    except Exception as erro:
        print(
            "\nERRO: não foi possível consultar "
            "o Portal BASE."
        )
        print(f"Detalhe: {erro}")
        return

    concursos_relevantes = []
    concursos_novos = []
    concursos_ja_existentes = []
    concursos_excluidos = 0

    print("\nA analisar os anúncios recolhidos...")

    for concurso in concursos:
        try:
            resultado = analisar_concurso(
                concurso
            )

        except Exception as erro:
            concursos_excluidos += 1

            print(
                "\nAviso: não foi possível analisar "
                "o anúncio:"
            )

            print(
                concurso.get(
                    "titulo",
                    "Título não indicado",
                )
            )

            print(f"Detalhe: {erro}")

            continue

        if not resultado["relevante"]:
            concursos_excluidos += 1
            continue

        concurso["analise"] = resultado
        concursos_relevantes.append(concurso)

        if concurso_existe(concurso["link"]):
            concursos_ja_existentes.append(
                concurso
            )
        else:
            concursos_novos.append(
                concurso
            )

    quantidade_atualizada = (
        atualizar_concursos_existentes(
            concursos_ja_existentes
        )
    )

    print("\n" + "=" * 52)
    print("RESUMO DA ANÁLISE")
    print("=" * 52)

    print(
        f"Anúncios analisados: {len(concursos)}"
    )

    print(
        "Concursos relevantes: "
        f"{len(concursos_relevantes)}"
    )

    print(
        f"Anúncios excluídos: {concursos_excluidos}"
    )

    print(
        "Concursos novos encontrados: "
        f"{len(concursos_novos)}"
    )

    print(
        "Concursos que já existiam: "
        f"{len(concursos_ja_existentes)}"
    )

    print(
        "Concursos existentes atualizados: "
        f"{quantidade_atualizada}"
    )

    if not concursos_novos:
        print(
            "\nNão foram encontrados concursos novos."
        )
        print("Nenhum email foi enviado.")
        return

    quantidade_a_mostrar = min(
        LIMITE_RESULTADOS_NO_ECRA,
        len(concursos_novos),
    )

    print(
        "\nA mostrar os primeiros "
        f"{quantidade_a_mostrar} concursos novos:"
    )

    for numero, concurso in enumerate(
        concursos_novos[
            :LIMITE_RESULTADOS_NO_ECRA
        ],
        start=1,
    ):
        mostrar_concurso(
            numero,
            concurso,
        )

    restantes = (
        len(concursos_novos)
        - LIMITE_RESULTADOS_NO_ECRA
    )

    if restantes > 0:
        print(
            f"\nExistem ainda {restantes} concursos "
            "novos que não foram mostrados "
            "no terminal."
        )

    quantidade_guardada = (
        guardar_concursos_enviados(
            concursos_novos
        )
    )

    total_final_base_dados = contar_concursos()

    print(
        f"\nConcursos guardados: {quantidade_guardada}"
    )

    print(
        "Total na base de dados: "
        f"{total_inicial_base_dados} -> "
        f"{total_final_base_dados}"
    )

    quantidade_guardada = (
        guardar_concursos_enviados(
            concursos_novos
        )
    )

    total_final_base_dados = contar_concursos()

    print(
        f"\nConcursos guardados: {quantidade_guardada}"
    )

    print(
        "Total na base de dados: "
        f"{total_inicial_base_dados} -> "
        f"{total_final_base_dados}"
    )

    print("\nA enviar email...")

    try:
        email_enviado = enviar_email_concursos(
            concursos_novos
        )

        if email_enviado:
            print("\nEmail enviado com sucesso.")
        else:
            print("\nO email não foi enviado.")

    except Exception as erro:
        print(
            "\nAviso: não foi possível enviar o email."
        )
        print(f"Detalhe: {erro}")

    print(
        "\nOs concursos já ficaram guardados na base de dados."
    )


if __name__ == "__main__":
    main()