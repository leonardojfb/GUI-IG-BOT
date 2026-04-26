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
    def __init__(self):
        self.db_path = DB_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.initialize()
        
    def initialize(self):
        """Crea todas las tablas necesarias usando el SCHEMA global."""
        try:
            cursor = self.conn.cursor()
            cursor.executescript(SCHEMA) # <--- Esto crea TODAS las tablas del SCHEMA de un solo golpe
            self.conn.commit()
            print("✅ Base de datos V6 sincronizada con el SCHEMA correcto.")
        except Exception as e:
            print(f"❌ Error inicializando base de datos: {e}")

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

    def add_tanda(self, name, p1, p2, captions):
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO batch_tandas (tanda_name, p1_folder, p2_folder, captions_file_path)
            VALUES (?, ?, ?, ?)
        ''', (name, p1, p2, captions))
        self.conn.commit()

    def get_tanda_by_name(self, name):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM batch_tandas WHERE tanda_name = ?", (name,))
        row = cur.fetchone()
        return dict(row) if row else None

    # ==================== HISTORIAL ====================
    def add_video_to_history(self, account_id, video_path, p1, p2, caption, day):
        """Registra el envío en el historial con la columna video_path."""
        try:
            cur = self.conn.cursor()
            cur.execute('''
                INSERT INTO fingerprint_history 
                (account_id, video_path, p1_source, p2_source, assigned_caption, day_number)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (account_id, video_path, p1, p2, caption, day))
            
            # Actualizamos el contador de la cuenta
            cur.execute("UPDATE virtual_accounts SET videos_posted = videos_posted + 1 WHERE id = ?", (account_id,))
            self.conn.commit()
        except sqlite3.OperationalError as e:
            print(f"❌ Error de columna: {e}. Es necesario resetear la base de datos.")