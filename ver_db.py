import sqlite3

conn = sqlite3.connect("concursos.db")
cursor = conn.cursor()

resultado = cursor.execute(
    "SELECT id, titulo, link FROM concursos ORDER BY id DESC LIMIT 20"
).fetchall()

for linha in resultado:
    print("\nID:", linha[0])
    print("TITULO:", linha[1])
    print("LINK:", linha[2])

conn.close()