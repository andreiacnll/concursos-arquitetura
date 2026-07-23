#!/bin/bash
set -e

echo "=== Backup ==="
cp concursos.db concursos.db-backup-antes-data-entrega.db

echo "=== Adicionar coluna data_entrega_propostas ==="

sqlite3 concursos.db <<'SQL'
ALTER TABLE concursos
ADD COLUMN data_entrega_propostas TEXT;
SQL

echo "=== Criar função de extração PDF ==="

python3 - <<'PY'
from pathlib import Path

path = Path("app/coletor.py")

texto = path.read_text(encoding="utf-8")

if "def extrair_data_entrega_propostas" not in texto:

    bloco = '''

def extrair_data_entrega_propostas(texto_pdf: str):
    """
    Extrai a data limite de apresentação de propostas
    a partir do texto do PDF DR.
    """
    import re

    padrao = (
        r"Prazo para apresentação das propostas:"
        r"\\s*(\\d{2}-\\d{2}-\\d{4})"
        r"(?:\\s+(\\d{2}:\\d{2}))?"
    )

    resultado = re.search(
        padrao,
        texto_pdf,
        re.IGNORECASE
    )

    if not resultado:
        return None

    data = resultado.group(1)
    hora = resultado.group(2)

    if hora:
        return f"{data} {hora}"

    return data

'''

    texto += bloco

    path.write_text(texto, encoding="utf-8")

print("OK")
PY


echo "=== Atualizar API para devolver campo ==="

python3 - <<'PY'
from pathlib import Path

path = Path("app/api.py")
texto = path.read_text(encoding="utf-8")

if '"data_entrega_propostas"' not in texto:
    texto = texto.replace(
        '"data_limite": item.get("data_limite"),',
        '"data_limite": item.get("data_limite"),\n'
        '        "data_entrega_propostas": item.get("data_entrega_propostas"),'
    )

path.write_text(texto, encoding="utf-8")

print("OK")
PY


echo "=== Atualizar tipo frontend ==="

python3 - <<'PY'
from pathlib import Path

path = Path(
"frontend/src/components/competition-types.ts"
)

texto = path.read_text(encoding="utf-8")

if "data_entrega_propostas" not in texto:
    texto = texto.replace(
        "data_fim_calculada?: string;",
        "data_fim_calculada?: string;\n"
        "  data_entrega_propostas?: string;"
    )

path.write_text(texto, encoding="utf-8")

print("OK")
PY


echo "=== Concluído ==="
echo "Falta apenas ligar a extração PDF ao enriquecimento dos concursos."
