import fitz
from pathlib import Path

base = Path("analise_documentos/450837")

pdfs = list(base.rglob("*.pdf"))

print("PDFs encontrados:")
for p in pdfs:
    print("-", p)

if not pdfs:
    raise SystemExit("Nenhum PDF encontrado")

# escolher primeiro PDF com peças desenhadas ou levantamento
preferidos = [
    p for p in pdfs
    if "desenh" in p.name.lower()
    or "levant" in p.name.lower()
    or "planta" in p.name.lower()
]

pdf = preferidos[0] if preferidos else pdfs[0]

print("\nA usar:")
print(pdf)

doc = fitz.open(pdf)

pagina = doc[0]

pix = pagina.get_pixmap(
    dpi=150
)

saida = base / "capa.png"

pix.save(saida)

print("\n✅ Imagem criada:")
print(saida)
