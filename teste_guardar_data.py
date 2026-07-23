from app.dre import enriquecer_concurso
from app.database import guardar_concurso

concurso = {
    "titulo": "TESTE DATA ENTREGA",
    "entidade": "Teste",
    "link": "teste-123",
    "data": "23-07-2026",
    "link_anuncio_dr": "https://files.diariodarepublica.pt/cp_hora/2026/07/138/419967796.pdf"
}

concurso = enriquecer_concurso(
    concurso,
    concurso["link_anuncio_dr"]
)

print("Campo extraído:")
print(concurso.get("data_entrega_propostas"))

guardar_concurso(
    titulo=concurso["titulo"],
    entidade=concurso["entidade"],
    link=concurso["link"],
    data=concurso["data"],
    link_anuncio_dr=concurso["link_anuncio_dr"],
    data_entrega_propostas=concurso.get("data_entrega_propostas"),
)

print("Guardado")
