from ai import analisar_concurso


concursos = [
    {
        "titulo": "Elaboração de projeto de arquitetura para reabilitação de escola",
        "entidade": "Município de Coimbra",
        "texto": "Aquisição de serviços de arquitetura e especialidades.",
    },
    {
        "titulo": "Aquisição de serviços de limpeza",
        "entidade": "Município de Coimbra",
        "texto": "Limpeza das instalações municipais.",
    },
    {
        "titulo": "Empreitada de requalificação de espaço público",
        "entidade": "Município de Braga",
        "texto": "Execução de trabalhos de construção.",
    },
    {
        "titulo": "Aquisição de serviços para elaboração de projeto de execução",
        "entidade": "Município de Aveiro",
        "texto": (
            "Elaboração dos projetos de arquitetura e especialidades "
            "para futura empreitada."
        ),
    },
]


for concurso in concursos:
    resultado = analisar_concurso(concurso)

    print("\nTítulo:", concurso["titulo"])
    print("Relevante:", resultado["relevante"])
    print("Correspondências:", resultado["correspondencias"])
    print("Exclusões:", resultado["exclusoes"])