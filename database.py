"""
📦 DATABASE.PY - Sistema de Gestión de Base de Datos SQLite
Migración de datos estáticos a SQL para el Organizador de Videos Instagram

Fase 1: Migración de Datos (Semana 1)
- Eliminar dependencias estáticas (accounts_promo.txt, accounts_suicide.txt)
- Mover control de estado a SQL
- Crear esquema de base de datos con tablas para: VAs, Accounts, VideoTypes, FingerprintHistory
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# ==================== CONFIGURACIÓN ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "organizador.db")

# Rutas de archivos legacy (para migración)
ACCOUNTS_PROMO_FILE = os.path.join(BASE_DIR, "accounts_promo.txt")
ACCOUNTS_SUICIDE_FILE = os.path.join(BASE_DIR, "accounts_suicide.txt")
STATE_FILE = os.path.join(BASE_DIR, "telegram_state_v11.json")
FINGERPRINT_FILE = os.path.join(BASE_DIR, "fingerprint_history.json")

# ==================== ESQUEMA DE BASE DE DATOS ====================
SCHEMA = """
-- Tabla de Agentes Virtuales (VAs)
CREATE TABLE IF NOT EXISTS virtual_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    account_type TEXT NOT NULL CHECK(account_type IN ('PROMO', 'SUICIDE')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'paused', 'disabled')),
    videos_posted INTEGER DEFAULT 0,
    last_post_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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

-- Tabla de Historial de Fingerprints
CREATE TABLE IF NOT EXISTS fingerprint_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    video_type_id INTEGER NOT NULL,
    video_path TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_va_type ON virtual_accounts(account_type);
CREATE INDEX IF NOT EXISTS idx_va_status ON virtual_accounts(status);
"""

# ==================== CLASE PRINCIPAL ====================
class DatabaseManager:
    """Gestor de base de datos SQLite para el organizador"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = None
        self._connect()
        
    def _connect(self):
        """Establecer conexión con la base de datos"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # Habilitar claves foráneas
        self.conn.execute("PRAGMA foreign_keys = ON")
        
    def initialize(self):
        """Inicializar la base de datos con el esquema"""
        cursor = self.conn.cursor()
        
        # Ejecutar esquema
        cursor.executescript(SCHEMA)
        self.conn.commit()
        
        print("✅ Base de datos inicializada correctamente")
        print(f"📁 Ubicación: {self.db_path}")
        
    def close(self):
        """Cerrar conexión"""
        if self.conn:
            self.conn.close()
            
    # ==================== OPERACIONES VIRTUAL ACCOUNTS ====================
    
    def add_virtual_account(self, username: str, account_type: str) -> int:
        """Agregar una cuenta virtual a la base de datos"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_accounts (username, account_type)
            VALUES (?, ?)
        """, (username, account_type))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_all_accounts(self, account_type: Optional[str] = None) -> List[Dict]:
        """Obtener todas las cuentas, opcionalmente filtradas por tipo"""
        cursor = self.conn.cursor()
        if account_type:
            cursor.execute("""
                SELECT * FROM virtual_accounts 
                WHERE account_type = ?
                ORDER BY username
            """, (account_type,))
        else:
            cursor.execute("""
                SELECT * FROM virtual_accounts 
                ORDER BY account_type, username
            """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_account_by_username(self, username: str) -> Optional[Dict]:
        """Obtener cuenta por nombre de usuario"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM virtual_accounts WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_account_status(self, username: str, status: str) -> bool:
        """Actualizar estado de una cuenta"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE virtual_accounts 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE username = ?
        """, (status, username))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def increment_videos_posted(self, username: str) -> bool:
        """Incrementar contador de videos publicados"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE virtual_accounts 
            SET videos_posted = videos_posted + 1,
                last_post_date = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE username = ?
        """, (username,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_account(self, username: str) -> bool:
        """Eliminar cuenta virtual"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM virtual_accounts WHERE username = ?", (username,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ==================== OPERACIONES VIDEO TYPES ====================
    
    def add_video_type(self, type_name: str, category: str, description: str = "") -> int:
        """Agregar tipo de video"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO video_types (type_name, category, description)
            VALUES (?, ?, ?)
        """, (type_name, category, description))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_video_type(self, type_name: str, is_active: Optional[bool] = None, 
                          description: Optional[str] = None) -> bool:
        """Actualizar tipo de video"""
        cursor = self.conn.cursor()
        updates = []
        params = []
        
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        
        if not updates:
            return False
            
        params.append(type_name)
        cursor.execute(f"""
            UPDATE video_types 
            SET {', '.join(updates)}
            WHERE type_name = ?
        """, params)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_video_type(self, type_name: str) -> bool:
        """Eliminar tipo de video (solo si no tiene fingerprints asociados)"""
        cursor = self.conn.cursor()
        
        # Verificar si hay fingerprints asociados
        cursor.execute("""
            SELECT COUNT(*) FROM fingerprint_history fh
            JOIN video_types vt ON fh.video_type_id = vt.id
            WHERE vt.type_name = ?
        """, (type_name,))
        
        if cursor.fetchone()[0] > 0:
            # En lugar de eliminar, marcar como inactivo
            return self.update_video_type(type_name, is_active=False)
        
        cursor.execute("DELETE FROM video_types WHERE type_name = ?", (type_name,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_video_types(self, category: Optional[str] = None) -> List[Dict]:
        """Obtener tipos de video"""
        cursor = self.conn.cursor()
        if category:
            cursor.execute("SELECT * FROM video_types WHERE category = ?", (category,))
        else:
            cursor.execute("SELECT * FROM video_types")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_active_video_types(self) -> List[Dict]:
        """Obtener solo tipos de video activos"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM video_types WHERE is_active = 1")
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== OPERACIONES FINGERPRINT HISTORY ====================
    
    def add_fingerprint(self, account_id: int, video_type_id: int, video_path: str, 
                       day_number: Optional[int] = None) -> int:
        """Agregar registro de fingerprint"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO fingerprint_history 
            (account_id, video_type_id, video_path, upload_date, day_number)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (account_id, video_type_id, video_path, day_number))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_fingerprints_by_account(self, account_id: int) -> List[Dict]:
        """Obtener historial de fingerprints de una cuenta"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT fh.*, vt.type_name, vt.category
            FROM fingerprint_history fh
            JOIN video_types vt ON fh.video_type_id = vt.id
            WHERE fh.account_id = ?
            ORDER BY fh.upload_date DESC
        """, (account_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_fingerprints_by_day(self, day_number: int) -> List[Dict]:
        """Obtener fingerprints de un día específico"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT fh.*, va.username
            FROM fingerprint_history fh
            JOIN virtual_accounts va ON fh.account_id = va.id
            WHERE fh.day_number = ?
            ORDER BY fh.upload_date
        """, (day_number,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== OPERACIONES SYSTEM CONFIG ====================
    
    def set_config(self, key: str, value: str):
        """Establecer configuración del sistema"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO system_config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, value))
        self.conn.commit()
    
    def get_config(self, key: str) -> Optional[str]:
        """Obtener configuración del sistema"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else None
    
    # ==================== ESTADÍSTICAS ====================
    
    def get_account_stats(self) -> Dict:
        """Obtener estadísticas generales"""
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Total cuentas
        cursor.execute("SELECT COUNT(*) as total FROM virtual_accounts")
        stats['total_accounts'] = cursor.fetchone()['total']
        
        # Cuentas por tipo
        cursor.execute("""
            SELECT account_type, COUNT(*) as count 
            FROM virtual_accounts 
            GROUP BY account_type
        """)
        stats['by_type'] = {row['account_type']: row['count'] for row in cursor.fetchall()}
        
        # Cuentas por estado
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM virtual_accounts 
            GROUP BY status
        """)
        stats['by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # Videos totales publicados
        cursor.execute("SELECT SUM(videos_posted) as total FROM virtual_accounts")
        stats['total_videos'] = cursor.fetchone()['total'] or 0
        
        return stats
    
    # ==================== MIGRACIÓN DE DATOS LEGACY ====================
    
    def migrate_from_legacy_files(self) -> Dict:
        """
        Migrar datos desde archivos legacy a la base de datos
        Returns: Diccionario con estadísticas de la migración
        """
        migration_stats = {
            'accounts_promo': 0,
            'accounts_suicide': 0,
            'state_migrated': 0,
            'fingerprints_migrated': 0,
            'errors': []
        }
        
        # 1. Migrar cuentas PROMO
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
        
        # 2. Migrar cuentas SUICIDE
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
        
        # 3. Migrar estado de cuentas (telegram_state_v11.json)
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                for username, video_count in state_data.items():
                    account = self.get_account_by_username(username)
                    if account:
                        # Actualizar videos_posted al valor del estado
                        cursor = self.conn.cursor()
                        cursor.execute("""
                            UPDATE virtual_accounts 
                            SET videos_posted = ?
                            WHERE username = ?
                        """, (video_count, username))
                        migration_stats['state_migrated'] += 1
                self.conn.commit()
            except Exception as e:
                migration_stats['errors'].append(f"Error migrando estado: {e}")
        
        # 4. Migrar fingerprint history
        if os.path.exists(FINGERPRINT_FILE):
            try:
                with open(FINGERPRINT_FILE, 'r', encoding='utf-8') as f:
                    fp_data = json.load(f)
                
                # Asegurar que existen los tipos de video
                self.add_video_type('PROMO', 'PROMO', 'Videos de promoción')
                self.add_video_type('SUICIDE', 'SUICIDE', 'Videos de contenido suicide')
                
                promo_type = self.get_video_types('PROMO')[0]
                suicide_type = self.get_video_types('SUICIDE')[0]
                
                for username, videos in fp_data.items():
                    account = self.get_account_by_username(username)
                    if account:
                        # Determinar tipo basado en el path del video
                        for video_path in videos:
                            category = 'PROMO' if 'promo' in video_path.lower() else 'SUICIDE'
                            video_type_id = promo_type['id'] if category == 'PROMO' else suicide_type['id']
                            
                            # Extraer día del path
                            day_number = None
                            if 'Dia_' in video_path:
                                try:
                                    day_part = video_path.split('Dia_')[1].split('\\')[0]
                                    day_number = int(day_part)
                                except:
                                    pass
                            
                            self.add_fingerprint(account['id'], video_type_id, video_path, day_number)
                            migration_stats['fingerprints_migrated'] += 1
            except Exception as e:
                migration_stats['errors'].append(f"Error migrando fingerprints: {e}")
        
        return migration_stats
    
    def archive_legacy_files(self) -> bool:
        """Archivar archivos legacy después de migración exitosa"""
        import shutil
        
        archive_dir = os.path.join(BASE_DIR, "archive_legacy")
        os.makedirs(archive_dir, exist_ok=True)
        
        files_to_archive = [
            ACCOUNTS_PROMO_FILE,
            ACCOUNTS_SUICIDE_FILE,
            STATE_FILE,
            FINGERPRINT_FILE
        ]
        
        archived = []
        for file_path in files_to_archive:
            if os.path.exists(file_path):
                filename = os.path.basename(file_path)
                dest = os.path.join(archive_dir, filename)
                shutil.move(file_path, dest)
                archived.append(filename)
        
        print(f"✅ Archivados {len(archived)} archivos legacy")
        return len(archived) > 0
    
    # ==================== BACKUP Y RESTAURACIÓN ====================
    
    def export_to_json(self, output_path: str) -> bool:
        """Exportar toda la base de datos a JSON"""
        cursor = self.conn.cursor()
        
        export_data = {
            'export_date': datetime.now().isoformat(),
            'virtual_accounts': [],
            'video_types': [],
            'fingerprint_history': [],
            'system_config': []
        }
        
        # Exportar cuentas
        cursor.execute("SELECT * FROM virtual_accounts")
        export_data['virtual_accounts'] = [dict(row) for row in cursor.fetchall()]
        
        # Exportar tipos de video
        cursor.execute("SELECT * FROM video_types")
        export_data['video_types'] = [dict(row) for row in cursor.fetchall()]
        
        # Exportar fingerprints
        cursor.execute("SELECT * FROM fingerprint_history")
        export_data['fingerprint_history'] = [dict(row) for row in cursor.fetchall()]
        
        # Exportar configuración
        cursor.execute("SELECT * FROM system_config")
        export_data['system_config'] = [dict(row) for row in cursor.fetchall()]
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error exportando: {e}")
            return False


# ==================== FUNCIONES DE UTILIDAD ====================

def init_database() -> DatabaseManager:
    """Inicializar base de datos y retornar gestor"""
    db = DatabaseManager()
    db.initialize()
    return db


def migrate_and_archive() -> Dict:
    """Migrar datos legacy y archivar archivos"""
    db = DatabaseManager()
    db.initialize()
    
    # Migrar datos
    stats = db.migrate_from_legacy_files()
    
    # Mostrar resultados
    print("\n" + "="*50)
    print("📊 RESUMEN DE MIGRACIÓN")
    print("="*50)
    print(f"Cuentas PROMO migradas: {stats['accounts_promo']}")
    print(f"Cuentas SUICIDE migradas: {stats['accounts_suicide']}")
    print(f"Estados de cuenta migrados: {stats['state_migrated']}")
    print(f"Fingerprints migrados: {stats['fingerprints_migrated']}")
    
    if stats['errors']:
        print(f"\n⚠️ Errores: {len(stats['errors'])}")
        for error in stats['errors'][:5]:
            print(f"  - {error}")
    
    # Verificar si migración fue exitosa
    if stats['accounts_promo'] > 0 or stats['accounts_suicide'] > 0:
        # Mostrar estadísticas
        db_stats = db.get_account_stats()
        print(f"\n📈 ESTADÍSTICAS FINALES")
        print(f"Total cuentas: {db_stats['total_accounts']}")
        print(f"Videos publicados: {db_stats['total_videos']}")
    
    db.close()
    return stats


# ==================== PUNTO DE ENTRADA ====================
if __name__ == "__main__":
    print("🎬 ORGANIZADOR DE VIDEOS - MIGRACIÓN A SQL")
    print("="*50)
    
    # Inicializar base de datos
    db = init_database()
    
    # Migrar datos
    stats = migrate_and_archive()
    
    print("\n✅ Migración completada")
    print(f"📁 Base de datos: {DB_PATH}")