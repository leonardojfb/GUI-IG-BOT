from database import DatabaseManager
import os

db = DatabaseManager()
tandas = db.get_all_tandas()
print(f"--- DIAGNÓSTICO DE BASE DE DATOS ---")
print(f"Ruta DB: {os.path.abspath(db.db_path)}")
print(f"Tandas registradas: {len(tandas)}")
for t in tandas:
    print(f" - {t['tanda_name']}")
db.close()