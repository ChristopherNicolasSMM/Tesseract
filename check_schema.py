import sqlite3

conn = sqlite3.connect("instance/tesseract_dev.db")
cur = conn.cursor()
cur.execute(
    "SELECT sql FROM sqlite_master WHERE name IN "
    "('tesseract_estoque_categoria', 'tesseract_estoque_material_unidade')"
)
rows = cur.fetchall()
if not rows:
    print("Nenhuma das duas tabelas foi encontrada em instance/tesseract_dev.db")
else:
    for row in rows:
        print(row[0])
        print()