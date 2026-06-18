import sqlite3

conn = sqlite3.connect("database/centro.db")
cursor = conn.cursor()

cursor.execute("""
SELECT id, logo
FROM configuracao_centro
""")

for linha in cursor.fetchall():
    print(linha)

conn.close()