import sqlite3
import os

# Ruta a tu base de datos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "organizador.db")

def reparar_base_de_datos():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("Iniciando cirugía en la base de datos...")
        
        # 1. Renombramos la tabla vieja para que no estorbe
        cursor.execute("ALTER TABLE virtual_accounts RENAME TO virtual_accounts_old;")
        
        # 2. Creamos la tabla nueva SIN la restricción tóxica
        cursor.execute("""
        CREATE TABLE virtual_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            account_type TEXT NOT NULL, 
            assigned_va TEXT DEFAULT 'Sin Asignar',
            videos_posted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 3. Trasvasamos toda tu información (cuentas, VAs, etc.) a la tabla nueva
        # Usamos un try/except interno por si tu tabla vieja no tenía la columna 'updated_at'
        try:
            cursor.execute("""
            INSERT INTO virtual_accounts (id, username, account_type, assigned_va, videos_posted, created_at, updated_at)
            SELECT id, username, account_type, assigned_va, videos_posted, created_at, updated_at 
            FROM virtual_accounts_old;
            """)
        except sqlite3.OperationalError:
            # Si la tabla vieja no tenía updated_at, lo omitimos en la copia
            cursor.execute("""
            INSERT INTO virtual_accounts (id, username, account_type, assigned_va, videos_posted, created_at)
            SELECT id, username, account_type, assigned_va, videos_posted, created_at 
            FROM virtual_accounts_old;
            """)
            
        # 4. Eliminamos la tabla vieja
        cursor.execute("DROP TABLE virtual_accounts_old;")
        
        # Guardamos los cambios
        conn.commit()
        print("✅ ¡Éxito! La restricción ('PROMO', 'SUICIDE') ha sido eliminada para siempre.")
        
    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")
        conn.rollback() # Si algo sale mal, deshace los cambios para no romper nada
    finally:
        conn.close()

if __name__ == "__main__":
    reparar_base_de_datos()