import json
from pathlib import Path


BASE = Path("analise_documentos")


def enriquecer_ficha(id_concurso: str):
    caminho = BASE / id_concurso / "ficha.json"

    if not caminho.exists():
        print(f"Ficheiro não encontrado: {caminho}")
        return

    with open(caminho, "r", encoding="utf-8") as f:
        ficha = json.load(f)


    ficha["entregaveis"] = {
        "total": 5,
        "principais": [
            "Memória descritiva e justificativa",
            "Peças desenhadas",
            "Declaração/certificação da ordem profissional",
            "Termos de responsabilidade dos técnicos",
            "Documentos comprovativos da experiência profissional"
        ]
    }


    especialidades = []

    palavras_especialidades = [
        "Coordenação de Projeto",
        "Arquitetura",
        "Estabilidade",
        "Instalações Elétricas",
        "AVAC",
        "Acústica",
        "SCIE"
    ]

    equipa_texto = json.dumps(
        ficha.get("equipa", []),
        ensure_ascii=False
    )

    for especialidade in palavras_especialidades:
        if especialidade.lower() in equipa_texto.lower():
            especialidades.append(especialidade)



    ficha["especialidades"] = {
        "total": len(especialidades),
        "lista": especialidades
    }


    ficha["requisitos"] = {
        "obrigatorios": [
            "Equipa técnica multidisciplinar",
            "Técnicos legalmente habilitados",
            "Comprovação de experiência profissional"
        ],
        "riscos_participacao": [
            "Experiência específica em mercados municipais",
            "Experiência em projetos de reabilitação",
            "Necessidade de vários técnicos especializados"
        ]
    }


    ficha["localizacao"] = {
        "morada": "Mercado Municipal de Castelo Branco",
        "cidade": "Castelo Branco",
        "latitude": 39.8222,
        "longitude": -7.4909
    }


    ficha["entidade"] = {
        "nome": "Município de Castelo Branco",
        "historico_disponivel": False
    }


    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(
            ficha,
            f,
            ensure_ascii=False,
            indent=2
        )


    print(f"Ficha enriquecida: {caminho}")


if __name__ == "__main__":
    enriquecer_ficha("450837")
