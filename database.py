"""
📦 DATABASE.PY - Sistema de Gestión de Base de Datos SQLite (VERSIÓN DEFINITIVA V6)
Limpio, sin código legacy, e integra la lógica Anti-Choque Global.
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "organizador.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS account_categories (
    name TEXT PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS virtual_assistants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    tg_group_id TEXT
);

CREATE TABLE IF NOT EXISTS virtual_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    account_type TEXT NOT NULL, 
    assigned_va TEXT DEFAULT 'Sin Asignar',
    videos_posted INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS batch_tandas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tanda_name TEXT UNIQUE NOT NULL,
    p1_folder TEXT NOT NULL,
    p2_folder TEXT NOT NULL,
    captions_file_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fingerprint_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    video_path TEXT NOT NULL,
    p1_source TEXT,
    p2_source TEXT,
    assigned_caption TEXT,
    upload_date TEXT DEFAULT CURRENT_TIMESTAMP,
    day_number INTEGER,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (account_id) REFERENCES virtual_accounts(id)
);
"""

class DatabaseManager:
    def get_accounts_by_type(self, type_name):
        """Busca cuentas usando los nombres reales de tu BD V6."""
        cur = self.conn.cursor()
        # Usamos account_type que es el nombre real en tu tabla virtual_accounts
        cur.execute("SELECT * FROM virtual_accounts WHERE UPPER(TRIM(account_type)) = UPPER(TRIM(?))", (type_name,))
        return [dict(row) for row in cur.fetchall()]
    def update_accounts_category_bulk(self, new_category):
        """Actualiza la categoría de todas las cuentas existentes de forma masiva."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE accounts SET category = ?", (new_category,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error en actualización masiva: {e}")
            return False
    def update_specific_accounts_category(self, account_ids, new_category):
        """Actualiza la categoría de una lista de IDs de cuentas específicos."""
        try:
            cursor = self.conn.cursor()
            # Generamos los placeholders (?,?,?) según la cantidad de IDs
            placeholders = ','.join(['?'] * len(account_ids))
            query = f"UPDATE accounts SET category = ? WHERE id IN ({placeholders})"
            
            # Combinamos la categoría con los IDs para la ejecución
            params = [new_category] + list(account_ids)
            cursor.execute(query, params)
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error en actualización por selección: {e}")
            return False
    def __init__(self):
        self.db_path = DB_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.initialize()
        
    def initialize(self):
        """Crea todas las tablas necesarias si no existen."""
        cursor = self.conn.cursor()
        
        # 1. Tabla de Categorías
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                color TEXT
            )
        """)

        # 2. Tabla de Cuentas (ESTA ES LA QUE FALTA)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                category TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category) REFERENCES categories(name)
            )
        """)

        # 3. Tabla de Tandas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tandas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tanda_name TEXT UNIQUE,
                p1_folder TEXT,
                p2_folder TEXT,
                captions_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Tabla de Historial (Fingerprint)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fingerprint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                video_name TEXT,
                category TEXT,
                p1_source TEXT,
                p2_source TEXT,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)

        self.conn.commit()
        print("✅ Base de datos sincronizada y tablas verificadas.")
        
    def close(self):
        if self.conn: self.conn.close()

    # ==================== CATEGORÍAS ====================
    def get_categories(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM account_categories ORDER BY name")
        return [row['name'] for row in cur.fetchall()]

    def add_category(self, name):
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO account_categories (name) VALUES (?)", (name,))
        self.conn.commit()
        
    def delete_category(self, name):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM account_categories WHERE name = ?", (name,))
        self.conn.commit()

    # ==================== VAs ====================
    def get_vas(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM virtual_assistants ORDER BY name")
        return [row['name'] for row in cur.fetchall()]

    def add_va(self, name):
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO virtual_assistants (name) VALUES (?)", (name,))
        self.conn.commit()
        
    def delete_va(self, name):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM virtual_assistants WHERE name = ?", (name,))
        # Si borramos al VA, dejamos sus cuentas "Sin Asignar"
        cur.execute("UPDATE virtual_accounts SET assigned_va = 'Sin Asignar' WHERE assigned_va = ?", (name,))
        self.conn.commit()

    def update_va_telegram_group(self, va_name, tg_group_id):
        cur = self.conn.cursor()
        cur.execute("UPDATE virtual_assistants SET tg_group_id = ? WHERE name = ?", (tg_group_id, va_name))
        self.conn.commit()

    # ==================== CUENTAS ====================
    def get_all_accounts(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM virtual_accounts ORDER BY account_type, username")
        return [dict(row) for row in cur.fetchall()]

    def add_virtual_account(self, username, account_type):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO virtual_accounts (username, account_type) VALUES (?, ?)", (username, account_type))
        self.conn.commit()

    def update_account(self, username, **kwargs):
        cur = self.conn.cursor()
        updates = [f"{k} = ?" for k in kwargs.keys()]
        params = list(kwargs.values()) + [username]
        cur.execute(f"UPDATE virtual_accounts SET {', '.join(updates)} WHERE username = ?", params)
        self.conn.commit()
        
    def bulk_update_accounts(self, account_ids, **kwargs):
        cur = self.conn.cursor()
        updates = [f"{k} = ?" for k in kwargs.keys()]
        placeholders = ','.join('?' * len(account_ids))
        params = list(kwargs.values()) + account_ids
        cur.execute(f"UPDATE virtual_accounts SET {', '.join(updates)} WHERE id IN ({placeholders})", params)
        self.conn.commit()

    def delete_account(self, username):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM virtual_accounts WHERE username = ?", (username,))
        self.conn.commit()

    # ==================== TANDAS ====================
    def get_all_tandas(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM batch_tandas ORDER BY created_at DESC")
        return [dict(row) for row in cur.fetchall()]
    def get_accounts_by_category(self, category_name):
        """Devuelve la lista de cuentas que pertenecen a una categoría específica."""
        cursor = self.conn.cursor()
        # Buscamos en la tabla accounts filtrando por la columna category
        cursor.execute("SELECT * FROM accounts WHERE category = ?", (category_name,))
        rows = cursor.fetchall()
        
        # Convertimos a lista de diccionarios para que sea fácil de leer
        accounts = []
        for row in rows:
            accounts.append({
                'id': row['id'],
                'username': row['username'],
                'category': row['category'],
                'status': row['status']
            })
        return accounts
    def add_tanda(self, name, p1, p2, captions):
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO batch_tandas (tanda_name, p1_folder, p2_folder, captions_file_path)
            VALUES (?, ?, ?, ?)
        ''', (name, p1, p2, captions))
        self.conn.commit()

    # ==================== HISTORIAL (ANTI-CHOQUE) ====================
    def get_account_history(self, account_id):
        cur = self.conn.cursor()
        cur.execute("SELECT p1_source, p2_source FROM fingerprint_history WHERE account_id = ?", (account_id,))
        return [dict(row) for row in cur.fetchall()]
        
    def add_video_to_history(self, account_id, video_path, p1, p2, caption, day):
        cur = self.conn.cursor()
        cur.execute('''
            INSERT INTO fingerprint_history (account_id, video_path, p1_source, p2_source, assigned_caption, day_number)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (account_id, video_path, p1, p2, caption, day))
        cur.execute("UPDATE virtual_accounts SET videos_posted = videos_posted + 1 WHERE id = ?", (account_id,))
        self.conn.commit()