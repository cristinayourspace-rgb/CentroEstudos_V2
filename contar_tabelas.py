import sqlite3

conn = sqlite3.connect("database/centro.db")
cursor = conn.cursor()

cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
)

tabelas = cursor.fetchall()

print("\nTABELAS ENCONTRADAS:\n")

for tabela in tabelas:

    nome = tabela[0]

    try:

        cursor.execute(
            f"SELECT COUNT(*) FROM {nome}"
        )

        total = cursor.fetchone()[0]

        print(f"{nome}: {total} registos")

    except Exception as erro:

        print(f"{nome}: erro -> {erro}")

conn.close()