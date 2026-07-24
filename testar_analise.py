from pathlib import Path
import fitz

from app.analise.criterios import analisar_criterios
from app.analise.equipa import analisar_equipa
from app.analise.normalizador_equipa import normalizar_subfatores
from app.analise.gerador import gerar_perfil_concurso


base = Path(
    "analise_documentos/450837"
)


texto_criterios = ""
texto_equipa = ""


for pdf in base.rglob("*.pdf"):

    nome = pdf.name.lower()

    doc = fitz.open(pdf)

    texto = ""

    for pagina in doc:
        texto += pagina.get_text()

    doc.close()


    if (
        "criter" in nome
        or "valia" in nome
        or "qualifica" in nome
    ):
        texto_criterios += texto


    if (
        "valia" in nome
        or "qualifica" in nome
    ):
        texto_equipa += texto



print("\n===== CRITÉRIOS =====")
print(
    analisar_criterios(texto_criterios)
)


print("\n===== EQUIPA =====")

equipa = analisar_equipa(texto_equipa)

resultado_equipa = normalizar_subfatores(
    equipa["subfatores_equipa"]
)

print(resultado_equipa)


print("\n===== PERFIL DO CONCURSO =====")

perfil = gerar_perfil_concurso(
    analisar_criterios(texto_criterios),
    normalizar_subfatores(
        equipa["subfatores_equipa"]
    )
)

print(perfil)
