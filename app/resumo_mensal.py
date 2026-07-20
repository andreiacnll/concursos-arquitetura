cat > app/resumo_mensal.py <<'PY'
from datetime import date
from zoneinfo import ZoneInfo

from .database import (
    criar_base_dados,
    listar_concursos_periodo,
)
from .emailer import enviar_email_resumo_mensal


MESES_PORTUGUES = {
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


def obter_periodo_mes_anterior():
    """
    Determina o primeiro e o último limite
    do mês anterior, usando a hora portuguesa.
    """
    agora_portugal = (
        __import__("datetime")
        .datetime.now(
            ZoneInfo("Europe/Lisbon")
        )
    )

    primeiro_dia_mes_atual = date(
        agora_portugal.year,
        agora_portugal.month,
        1,
    )

    if primeiro_dia_mes_atual.month == 1:
        primeiro_dia_mes_anterior = date(
            primeiro_dia_mes_atual.year - 1,
            12,
            1,
        )
    else:
        primeiro_dia_mes_anterior = date(
            primeiro_dia_mes_atual.year,
            primeiro_dia_mes_atual.month - 1,
            1,
        )

    return (
        primeiro_dia_mes_anterior,
        primeiro_dia_mes_atual,
    )


def main():
    print("=" * 60)
    print(" Resumo mensal de concursos de arquitetura")
    print("=" * 60)

    criar_base_dados()

    (
        data_inicio,
        data_fim,
    ) = obter_periodo_mes_anterior()

    nome_mes = MESES_PORTUGUES[
        data_inicio.month
    ]

    print(
        "\nPeríodo do relatório: "
        f"{data_inicio.strftime('%d-%m-%Y')} "
        "a "
        f"{data_fim.strftime('%d-%m-%Y')}"
    )

    concursos = listar_concursos_periodo(
        data_inicio,
        data_fim,
    )

    print(
        "Concursos encontrados: "
        f"{len(concursos)}"
    )

    print("\nA enviar resumo mensal...")

    enviar_email_resumo_mensal(
        concursos=concursos,
        nome_mes=nome_mes,
        ano=data_inicio.year,
    )

    print("\nResumo mensal concluído.")


if __name__ == "__main__":
    main()
PY