"""
📦 DATABASE.PY - Sistema de Gestión de Base de Datos SQLite
VERSIÓN COMPLETA SAAS: Incluye Migraciones Legacy, Backups, VAs y Gestión Bulk.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# ==================== CONFIGURACIÓN ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "organizador.db")

# Rutas de archivos legacy (para migración y backup)
ACCOUNTS_PROMO_FILE = os.path.join(BASE_DIR, "accounts_promo.txt")
ACCOUNTS_SUICIDE_FILE = os.path.join(BASE_DIR, "accounts_suicide.txt")
STATE_FILE = os.path.join(BASE_DIR, "telegram_state_v11.json")
FINGERPRINT_FILE = os.path.join(BASE_DIR, "fingerprint_history.json")

# ==================== ESQUEMA DE BASE DE DATOS ====================
SCHEMA = """
-- Categorías de la barra lateral (Pestañas)
CREATE TABLE IF NOT EXISTS account_categories (
    name TEXT PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Agentes Virtuales (VAs)
CREATE TABLE IF NOT EXISTS virtual_assistants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    tg_group_id TEXT
);

-- Tabla de Cuentas Virtuales
CREATE TABLE IF NOT EXISTS virtual_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    account_type TEXT NOT NULL, 
    assigned_va TEXT DEFAULT 'Sin Asignar',
    allowed_video_types TEXT DEFAULT 'ALL',
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'paused', 'disabled')),
    videos_posted INTEGER DEFAULT 0,
    last_post_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    tg_topic_id TEXT
);

-- Tabla de Tipos de Video
CREATE TABLE IF NOT EXISTS video_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_name TEXT UNIQUE NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Reglas de Mezcla
CREATE TABLE IF NOT EXISTS mix_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_category TEXT NOT NULL,
    pre_category TEXT DEFAULT 'RAW',
    post_category TEXT DEFAULT 'PROMO',
    unified_category TEXT,
    p1_source TEXT NOT NULL,        
    p2_source TEXT NOT NULL,        
    combination_order TEXT DEFAULT 'random' CHECK(combination_order IN ('random', 'sequential')),
    max_videos INTEGER DEFAULT 50,  
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Tandas (Batches)
CREATE TABLE IF NOT EXISTS batch_tandas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tanda_name TEXT UNIQUE NOT NULL,
    p1_folder TEXT NOT NULL,
    p2_folder TEXT NOT NULL,
    captions_file_path TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'paused', 'completed')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Historial de Fingerprints
CREATE TABLE IF NOT EXISTS fingerprint_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    video_type_id INTEGER NOT NULL,
    video_path TEXT NOT NULL,
    assigned_caption TEXT,
    upload_date TEXT NOT NULL,
    day_number INTEGER,
    status TEXT DEFAULT 'posted' CHECK(status IN ('posted', 'failed', 'pending')),
    FOREIGN KEY (account_id) REFERENCES virtual_accounts(id),
    FOREIGN KEY (video_type_id) REFERENCES video_types(id)
);

-- Tabla de Configuración del Sistema
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Logs de Actividad
CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES virtual_accounts(id)
);

-- Índices para optimización
CREATE INDEX IF NOT EXISTS idx_fingerprint_account ON fingerprint_history(account_id);
CREATE INDEX IF NOT EXISTS idx_fingerprint_date ON fingerprint_history(upload_date);
CREATE INDEX IF NOT EXISTS idx_fingerprint_video_type ON fingerprint_history(video_type_id);
CREATE INDEX IF NOT EXISTS idx_va_status ON virtual_accounts(status);
"""

# ==================== CLASE PRINCIPAL ====================
class DatabaseManager:
    """Gestor de base de datos SQLite para el organizador"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = None
        self._connect()
        self.initialize()
        
    def _connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        
    def initialize(self):
        cursor = self.conn.cursor()
        cursor.executescript(SCHEMA)
        
        # Migraciones en Caliente (Hotfixes para esquemas viejos)
        try:
            cursor.execute("ALTER TABLE virtual_accounts ADD COLUMN assigned_va TEXT DEFAULT 'Sin Asignar'")
        except sqlite3.OperationalError: 
            pass
        
        try:
            cursor.execute("ALTER TABLE virtual_accounts ADD COLUMN allowed_video_types TEXT DEFAULT 'ALL'")
        except sqlite3.OperationalError: 
            pass
        
        # Nuevas columnas para integración con Telegram
        try:
            cursor.execute("ALTER TABLE virtual_assistants ADD COLUMN tg_group_id TEXT")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE virtual_accounts ADD COLUMN tg_topic_id TEXT")
        except sqlite3.OperationalError:
            pass
        
        # Nuevas columnas para categorías unificadas en mix_rules
        try:
            cursor.execute("ALTER TABLE mix_rules ADD COLUMN pre_category TEXT DEFAULT 'RAW'")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE mix_rules ADD COLUMN post_category TEXT DEFAULT 'PROMO'")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE mix_rules ADD COLUMN unified_category TEXT")
        except sqlite3.OperationalError:
            pass
        
        # Migración para columna assigned_caption en fingerprint_history
        try:
            cursor.execute("ALTER TABLE fingerprint_history ADD COLUMN assigned_caption TEXT")
        except sqlite3.OperationalError:
            pass
        
        # Rescatar categorías existentes
        cursor.execute("INSERT OR IGNORE INTO account_categories (name) SELECT DISTINCT account_type FROM virtual_accounts")
        
        self.conn.commit()
        
    def close(self):
        if self.conn:
            self.conn.close()

    # ==================== OPERACIONES CATEGORÍAS (PESTAÑAS) ====================
    def get_categories(self) -> List[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM account_categories ORDER BY name")
        return [row['name'] for row in cur.fetchall()]

    def add_category(self, name: str):
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO account_categories (name) VALUES (?)", (name,))
        self.conn.commit()

    # ==================== OPERACIONES VIRTUAL ASSISTANTS ====================
    def get_vas(self) -> List[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM virtual_assistants ORDER BY name")
        return [row['name'] for row in cur.fetchall()]

    def add_va(self, name: str):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO virtual_assistants (name) VALUES (?)", (name,))
        self.conn.commit()

    def delete_va(self, name: str):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM virtual_assistants WHERE name = ?", (name,))
        cur.execute("UPDATE virtual_accounts SET assigned_va = 'Sin Asignar' WHERE assigned_va = ?", (name,))
        self.conn.commit()
    
    def update_va_telegram_group(self, va_name: str, tg_group_id: str):
        """Actualizar el ID del grupo de Telegram asociado al VA"""
        cur = self.conn.cursor()
        cur.execute("UPDATE virtual_assistants SET tg_group_id = ? WHERE name = ?", (tg_group_id, va_name))
        self.conn.commit()
            
    # ==================== OPERACIONES VIRTUAL ACCOUNTS ====================
    def add_virtual_account(self, username: str, account_type: str, assigned_va: str = 'Sin Asignar', allowed_types: str = 'ALL') -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_accounts (username, account_type, assigned_va, allowed_video_types)
            VALUES (?, ?, ?, ?)
        """, (username, account_type, assigned_va, allowed_types))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_accounts_by_category(self, category: str) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM virtual_accounts WHERE account_type = ? ORDER BY username", (category,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_accounts(self) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM virtual_accounts ORDER BY account_type, username")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_account_by_username(self, username: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM virtual_accounts WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_account_by_id(self, account_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM virtual_accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_account(self, username: str, **kwargs) -> bool:
        cursor = self.conn.cursor()
        updates = []
        params = []
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            params.append(value)
        if not updates:
            return False
        params.append(username)
        cursor.execute(f"UPDATE virtual_accounts SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE username = ?", params)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_account(self, username: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM virtual_accounts WHERE username = ?", (username,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def increment_video_count(self, username: str):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE virtual_accounts SET videos_posted = videos_posted + 1, last_post_date = CURRENT_TIMESTAMP WHERE username = ?", (username,))
        self.conn.commit()
    
    def bulk_update_accounts(self, account_ids: List[int], **kwargs) -> int:
        cursor = self.conn.cursor()
        updates = []
        params = []
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            params.append(value)
        if not updates:
            return 0
        placeholders = ','.join('?' * len(account_ids))
        params.extend(account_ids)
        cursor.execute(f"UPDATE virtual_accounts SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", params)
        self.conn.commit()
        return cursor.rowcount
    
    def get_accounts_by_va(self, va_name: str) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM virtual_accounts WHERE assigned_va = ? ORDER BY username", (va_name,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== OPERACIONES VIDEO TYPES ====================
    def add_video_type(self, type_name: str, category: str, description: str = '') -> int:
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO video_types (type_name, category, description) VALUES (?, ?, ?)", (type_name, category, description))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_video_types(self, category: Optional[str] = None) -> List[Dict]:
        cursor = self.conn.cursor()
        if category:
            cursor.execute("SELECT * FROM video_types WHERE category = ? ORDER BY type_name", (category,))
        else:
            cursor.execute("SELECT * FROM video_types ORDER BY category, type_name")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_active_video_types(self) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM video_types WHERE is_active = 1")
        return [dict(row) for row in cursor.fetchall()]

    # ==================== OPERACIONES MIX RULES ====================
    def add_mix_rule(self, pre: str, post: str, p1_source: str, p2_source: str, combination_order: str = 'random', max_videos: int = 50) -> int:
        """
        Añade una regla de mezcla con categorías pre y post unificadas.
        
        Args:
            pre: Categoría PRE (ej. 'RAW')
            post: Categoría POST (ej. 'PROMO')
            p1_source: Fuente del primer componente
            p2_source: Fuente del segundo componente
            combination_order: Orden de combinación ('random' o 'sequential')
            max_videos: Número máximo de videos
            
        Returns:
            ID de la regla creada
        """
        cursor = self.conn.cursor()
        unified = f"{pre}_{post}"
        
        # Mantener target_category para compatibilidad con código existente
        target_category = unified
        
        cursor.execute("""
            INSERT INTO mix_rules (target_category, pre_category, post_category, unified_category, p1_source, p2_source, combination_order, max_videos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (target_category, pre, post, unified, p1_source, p2_source, combination_order, max_videos))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_mix_rules(self, target_category: Optional[str] = None, active_only: bool = False) -> List[Dict]:
        cursor = self.conn.cursor()
        query = "SELECT * FROM mix_rules"
        params = []
        conditions = []
        if target_category:
            conditions.append("target_category = ?")
            params.append(target_category)
        if active_only:
            conditions.append("is_active = 1")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY target_category, id"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_active_mix_rules(self, target_category: str) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM mix_rules WHERE target_category = ? AND is_active = 1 ORDER BY id", (target_category,))
        return [dict(row) for row in cursor.fetchall()]

    def update_mix_rule(self, rule_id: int, is_active: Optional[bool] = None, max_videos: Optional[int] = None, combination_order: Optional[str] = None) -> bool:
        cursor = self.conn.cursor()
        updates = []
        params = []
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        if max_videos is not None:
            updates.append("max_videos = ?")
            params.append(max_videos)
        if combination_order is not None:
            updates.append("combination_order = ?")
            params.append(combination_order)
        if not updates: 
            return False
        params.append(rule_id)
        cursor.execute(f"UPDATE mix_rules SET {', '.join(updates)} WHERE id = ?", params)
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_mix_rule(self, rule_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM mix_rules WHERE id = ?", (rule_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ==================== OPERACIONES BATCH TANDAS ====================
    def add_tanda(self, tanda_name: str, p1_folder: str, p2_folder: str, captions_file_path: str = None) -> int:
        """Crear una nueva tanda (batch)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO batch_tandas (tanda_name, p1_folder, p2_folder, captions_file_path)
            VALUES (?, ?, ?, ?)
        """, (tanda_name, p1_folder, p2_folder, captions_file_path))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_tandas(self, active_only: bool = False) -> List[Dict]:
        """Obtener todas las tandas"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM batch_tandas"
        if active_only:
            query += " WHERE status = 'active'"
        query += " ORDER BY tanda_name"
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_tanda_by_name(self, tanda_name: str) -> Optional[Dict]:
        """Obtener tanda por nombre"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM batch_tandas WHERE tanda_name = ?", (tanda_name,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_tanda(self, tanda_name: str, **kwargs) -> bool:
        """Actualizar tanda"""
        cursor = self.conn.cursor()
        updates = []
        params = []
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            params.append(value)
        if not updates:
            return False
        params.append(tanda_name)
        cursor.execute(f"UPDATE batch_tandas SET {', '.join(updates)} WHERE tanda_name = ?", params)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_tanda(self, tanda_name: str) -> bool:
        """Eliminar tanda"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM batch_tandas WHERE tanda_name = ?", (tanda_name,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ==================== OPERACIONES FINGERPRINT HISTORY ====================
    def add_fingerprint(self, account_id: int, video_type_id: int, video_path: str, day_number: Optional[int] = None, assigned_caption: str = None) -> int:
        """Añadir fingerprint con caption asignado opcional"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO fingerprint_history (account_id, video_type_id, video_path, assigned_caption, upload_date, day_number)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (account_id, video_type_id, video_path, assigned_caption, day_number))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_fingerprints_by_account(self, account_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT fh.*, vt.type_name, vt.category
            FROM fingerprint_history fh
            JOIN video_types vt ON fh.video_type_id = vt.id
            WHERE fh.account_id = ? ORDER BY fh.upload_date DESC
        """, (account_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_account_video_combinations(self, account_id: int) -> List[Dict]:
        """Obtener todas las combinaciones P1+P2 que una cuenta ya ha publicado"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT p1_source, p2_source 
            FROM fingerprint_history 
            WHERE account_id = ?
        """, (account_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_fingerprints_by_day(self, day_number: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT fh.*, va.username
            FROM fingerprint_history fh
            JOIN virtual_accounts va ON fh.account_id = va.id
            WHERE fh.day_number = ? ORDER BY fh.upload_date
        """, (day_number,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== CONFIG & LOGS ====================
    def set_config(self, key: str, value: str):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (key, value))
        self.conn.commit()
    
    def get_config(self, key: str) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else None
    
    # ==================== ESTADÍSTICAS ====================
    def get_account_stats(self) -> Dict:
        cursor = self.conn.cursor()
        stats = {}
        cursor.execute("SELECT COUNT(*) as total FROM virtual_accounts")
        stats['total_accounts'] = cursor.fetchone()['total']
        
        cursor.execute("SELECT account_type, COUNT(*) as count FROM virtual_accounts GROUP BY account_type")
        stats['by_type'] = {row['account_type']: row['count'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT status, COUNT(*) as count FROM virtual_accounts GROUP BY status")
        stats['by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT SUM(videos_posted) as total FROM virtual_accounts")
        stats['total_videos'] = cursor.fetchone()['total'] or 0
        return stats
    
    # ==================== MIGRACIÓN LEGACY & BACKUPS ====================
    def migrate_from_legacy_files(self) -> Dict:
        """Migrar datos desde archivos legacy a la base de datos"""
        migration_stats = {'accounts_promo': 0, 'accounts_suicide': 0, 'state_migrated': 0, 'fingerprints_migrated': 0, 'errors': []}
        
        if os.path.exists(ACCOUNTS_PROMO_FILE):
            try:
                with open(ACCOUNTS_PROMO_FILE, 'r', encoding='utf-8') as f:
                    accounts = [line.strip() for line in f if line.strip()]
                for username in accounts:
                    try:
                        self.add_virtual_account(username, 'PROMO')
                        migration_stats['accounts_promo'] += 1
                    except sqlite3.IntegrityError: 
                        migration_stats['errors'].append(f"Cuenta duplicada: {username}")
            except Exception as e: 
                migration_stats['errors'].append(f"Error migrando accounts_promo: {e}")
            
        if os.path.exists(ACCOUNTS_SUICIDE_FILE):
            try:
                with open(ACCOUNTS_SUICIDE_FILE, 'r', encoding='utf-8') as f:
                    accounts = [line.strip() for line in f if line.strip()]
                for username in accounts:
                    try:
                        self.add_virtual_account(username, 'SUICIDE')
                        migration_stats['accounts_suicide'] += 1
                    except sqlite3.IntegrityError: 
                        migration_stats['errors'].append(f"Cuenta duplicada: {username}")
            except Exception as e: 
                migration_stats['errors'].append(f"Error migrando accounts_suicide: {e}")
            
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                for username, video_count in state_data.items():
                    account = self.get_account_by_username(username)
                    if account:
                        cursor = self.conn.cursor()
                        cursor.execute("UPDATE virtual_accounts SET videos_posted = ? WHERE username = ?", (video_count, username))
                        migration_stats['state_migrated'] += 1
                self.conn.commit()
            except Exception as e: 
                migration_stats['errors'].append(f"Error migrando estado: {e}")
            
        if os.path.exists(FINGERPRINT_FILE):
            try:
                with open(FINGERPRINT_FILE, 'r', encoding='utf-8') as f:
                    fp_data = json.load(f)
                self.add_video_type('PROMO', 'PROMO', 'Videos de promoción')
                self.add_video_type('SUICIDE', 'SUICIDE', 'Videos de contenido suicide')
                promo_type = self.get_video_types('PROMO')[0]
                suicide_type = self.get_video_types('SUICIDE')[0]
                
                for username, videos in fp_data.items():
                    account = self.get_account_by_username(username)
                    if account:
                        for video_path in videos:
                            category = 'PROMO' if 'promo' in video_path.lower() else 'SUICIDE'
                            video_type_id = promo_type['id'] if category == 'PROMO' else suicide_type['id']
                            day_number = None
                            if 'Dia_' in video_path:
                                try: 
                                    day_number = int(video_path.split('Dia_')[1].split('\\')[0])
                                except: 
                                    pass
                            self.add_fingerprint(account['id'], video_type_id, video_path, day_number)
                            migration_stats['fingerprints_migrated'] += 1
            except Exception as e: 
                migration_stats['errors'].append(f"Error migrando fingerprints: {e}")
        return migration_stats
    
    def archive_legacy_files(self) -> bool:
        import shutil
        archive_dir = os.path.join(BASE_DIR, "archive_legacy")
        os.makedirs(archive_dir, exist_ok=True)
        files_to_archive = [ACCOUNTS_PROMO_FILE, ACCOUNTS_SUICIDE_FILE, STATE_FILE, FINGERPRINT_FILE]
        archived = []
        for file_path in files_to_archive:
            if os.path.exists(file_path):
                filename = os.path.basename(file_path)
                dest = os.path.join(archive_dir, filename)
                shutil.move(file_path, dest)
                archived.append(filename)
        return len(archived) > 0
    
    def export_to_json(self, output_path: str) -> bool:
        cursor = self.conn.cursor()
        export_data = {'export_date': datetime.now().isoformat(), 'virtual_accounts': [], 'video_types': [], 'fingerprint_history': [], 'system_config': []}
        cursor.execute("SELECT * FROM virtual_accounts")
        export_data['virtual_accounts'] = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM video_types")
        export_data['video_types'] = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM fingerprint_history")
        export_data['fingerprint_history'] = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM system_config")
        export_data['system_config'] = [dict(row) for row in cursor.fetchall()]
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e: 
            return False

def init_database() -> DatabaseManager:
    db = DatabaseManager()
    db.initialize()
    return db

def migrate_and_archive() -> Dict:
    db = DatabaseManager()
    db.initialize()
    stats = db.migrate_from_legacy_files()
    if stats['accounts_promo'] > 0 or stats['accounts_suicide'] > 0:
        db.archive_legacy_files()
    db.close()
    return stats

# ==================== PUNTO DE ENTRADA ====================
if __name__ == "__main__":
    db = init_database()
    print("✅ Base de datos inicializada y lista para producción.")
    db.close()
