from database import DatabaseManager
db = DatabaseManager()
cursor = db.conn.cursor()
cursor.execute("SELECT id, username, category FROM accounts")
rows = cursor.fetchall()
print("--- CUENTAS ENCONTRADAS ---")
for r in rows:
    print(f"ID: {r['id']} | Usuario: '{r['username']}' | Categoría: '{r['category']}'")
db.close()