import json

with open(
    "data/anuncios2025.json",
    encoding="utf-8"
) as f:
    dados = json.load(f)

print(type(dados))
print("Número de registos:", len(dados))

print("\nPrimeiro anúncio:\n")
print(json.dumps(dados[0], indent=4, ensure_ascii=False))