from pathlib import Path
import json
import sys


def obter_id():

    if len(sys.argv) < 2:
        raise SystemExit(
            "Uso: python3 gerar_destaques.py ID_CONCURSO"
        )

    return sys.argv[1]


ID_CONCURSO = obter_id()


BASE = Path(
    "analise_documentos"
) / ID_CONCURSO

ANALISE = BASE / "analise.json"
FICHA = BASE / "ficha.json"


def main():

    analise = json.loads(
        ANALISE.read_text(
            encoding="utf-8"
        )
    )

    ficha = json.loads(
        FICHA.read_text(
            encoding="utf-8"
        )
    )


    resumo = analise.get(
        "resumo",
        {}
    )


    destaques = []


    regras = [

        (
            "levantamento",
            "📐 Levantamento arquitetónico disponível"
        ),

        (
            "pecas_desenhadas",
            "📄 Peças desenhadas existentes"
        ),

        (
            "mapa_quantidades",
            "📊 Mapa de quantidades disponível"
        ),

        (
            "cartografia",
            "🗺 Elementos cartográficos disponíveis"
        ),

        (
            "programa_preliminar",
            "🏛 Programa preliminar completo"
        ),

        (
            "condicoes_tecnicas",
            "⚙️ Condições técnicas disponíveis"
        ),

        (
            "caderno_encargos",
            "📚 Caderno de encargos disponível"
        ),

    ]


    for chave, texto in regras:

        if resumo.get(chave):

            destaques.append(
                texto
            )


    ficha["destaques"] = destaques


    FICHA.write_text(
        json.dumps(
            ficha,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    print("✅ Destaques adicionados")
    print()

    for item in destaques:
        print("-", item)


if __name__ == "__main__":
    main()
