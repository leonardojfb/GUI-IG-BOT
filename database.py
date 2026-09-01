"""
📦 DATABASE.PY - Sistema de Gestión de Base de Datos SQLite (VERSIÓN DEFINITIVA V6)
Limpio, sin código legacy, e integra la lógica Anti-Choque Global.
"""
import sqlite3
import os
import json

from social_publishing import normalize_story_link_base, resolve_story_link

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

CREATE TABLE IF NOT EXISTS metadata_fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_hash   TEXT NOT NULL,
    account_id   INTEGER,
    iphone_model TEXT NOT NULL,
    city         TEXT NOT NULL,
    lat          TEXT NOT NULL,
    lon          TEXT NOT NULL,
    carrier      TEXT NOT NULL,
    ios_version  TEXT NOT NULL,
    used_at      TEXT,
    UNIQUE(iphone_model, city, carrier, ios_version)
);

CREATE TABLE IF NOT EXISTS schedule_config (
    va_name     TEXT NOT NULL,
    category    TEXT NOT NULL,
    day_of_week INTEGER NOT NULL,
    time_slots  TEXT NOT NULL,
    PRIMARY KEY (va_name, category, day_of_week)
);

CREATE TABLE IF NOT EXISTS forge_video_registry (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tanda_name   TEXT NOT NULL,
    source_name  TEXT NOT NULL,
    output_name  TEXT NOT NULL,
    video_hash   TEXT DEFAULT '',
    processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tanda_name, source_name, output_name)
);

CREATE TABLE IF NOT EXISTS trial_tandas (
    tanda_name TEXT PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tanda_name) REFERENCES batch_tandas(tanda_name)
);

CREATE TABLE IF NOT EXISTS trial_source_captions (
    tanda_name TEXT NOT NULL,
    source_key TEXT NOT NULL,
    caption_text TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tanda_name, source_key),
    FOREIGN KEY (tanda_name) REFERENCES trial_tandas(tanda_name)
);

CREATE TABLE IF NOT EXISTS normal_source_captions (
    tanda_name TEXT NOT NULL,
    source_key TEXT NOT NULL,
    caption_text TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tanda_name, source_key),
    FOREIGN KEY (tanda_name) REFERENCES batch_tandas(tanda_name)
);

CREATE TABLE IF NOT EXISTS video_transform_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_kind TEXT NOT NULL,
    source_path TEXT NOT NULL,
    output_path TEXT NOT NULL UNIQUE,
    output_filename TEXT NOT NULL,
    tanda_name TEXT,
    source_identity TEXT,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_video_transform_logs_process_created
ON video_transform_logs(process_kind, created_at);

CREATE TABLE IF NOT EXISTS social_publishing_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

class DatabaseManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.initialize()
        
    def initialize(self):
        """Crea todas las tablas necesarias usando el SCHEMA global."""
        try:
            cursor = self.conn.cursor()
            cursor.executescript(SCHEMA)
            self.conn.commit()
        except Exception as e:
            print(f"Error inicializando base de datos: {e}")
        self._migrate_columns()
        self._migrate_forge_registry_unique()

    def _migrate_forge_registry_unique(self):
        """Amplía el UNIQUE de forge_video_registry a (tanda_name, source_name,
        output_name) en DBs viejas, donde solo cubría (tanda_name, source_name)
        y por eso 'INSERT OR REPLACE' pisaba todas las copias salvo la última."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='forge_video_registry'"
        )
        row = cur.fetchone()
        if not row or not row[0] or "UNIQUE(tanda_name, source_name, output_name)" in row[0]:
            return
        try:
            cur.executescript('''
                ALTER TABLE forge_video_registry RENAME TO forge_video_registry_old;
                CREATE TABLE forge_video_registry (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    tanda_name   TEXT NOT NULL,
                    source_name  TEXT NOT NULL,
                    output_name  TEXT NOT NULL,
                    video_hash   TEXT DEFAULT '',
                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tanda_name, source_name, output_name)
                );
                INSERT OR IGNORE INTO forge_video_registry
                    (tanda_name, source_name, output_name, video_hash, processed_at)
                    SELECT tanda_name, source_name, output_name, video_hash, processed_at
                    FROM forge_video_registry_old;
                DROP TABLE forge_video_registry_old;
            ''')
            self.conn.commit()
        except Exception as e:
            print(f"⚠️ No se pudo migrar forge_video_registry: {e}")

    def _migrate_columns(self):
        """Agrega columnas nuevas si aún no existen (migraciones no destructivas)."""
        migrations = [
            "ALTER TABLE virtual_accounts ADD COLUMN ig_status TEXT DEFAULT 'unknown'",
            "ALTER TABLE virtual_accounts ADD COLUMN ig_label  TEXT DEFAULT 'nuevo'",
            "ALTER TABLE virtual_accounts ADD COLUMN followers INTEGER DEFAULT 0",
            "ALTER TABLE virtual_accounts ADD COLUMN notes TEXT DEFAULT ''",
            "ALTER TABLE virtual_accounts ADD COLUMN limitations TEXT DEFAULT '[]'",
            "ALTER TABLE virtual_accounts ADD COLUMN trials_active INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE virtual_accounts ADD COLUMN two_factor TEXT DEFAULT ''",
            "ALTER TABLE virtual_accounts ADD COLUMN account_day TEXT DEFAULT ''",
            "ALTER TABLE virtual_accounts ADD COLUMN social_network TEXT DEFAULT ''",
            "ALTER TABLE virtual_accounts ADD COLUMN vpn_proxy TEXT DEFAULT ''",
            "ALTER TABLE virtual_accounts ADD COLUMN account_link TEXT DEFAULT ''",
            "ALTER TABLE virtual_accounts ADD COLUMN story_link_override_enabled INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE virtual_accounts ADD COLUMN story_link_override TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE virtual_assistants ADD COLUMN timezone TEXT DEFAULT 'America/Argentina/Buenos_Aires'",
        ]
        cur = self.conn.cursor()
        for sql in migrations:
            try:
                cur.execute(sql)
                self.conn.commit()
            except Exception:
                pass  # Columna ya existe

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

    def get_va_timezone(self, va_name: str) -> str:
        """Devuelve el timezone IANA de una VA. Si la VA no existe o no tiene tz, devuelve ART."""
        cur = self.conn.cursor()
        cur.execute("SELECT timezone FROM virtual_assistants WHERE name = ?", (va_name,))
        row = cur.fetchone()
        if row and row["timezone"]:
            return row["timezone"]
        return "America/Argentina/Buenos_Aires"

    def set_va_timezone(self, va_name: str, timezone: str):
        """Actualiza el timezone IANA de una VA."""
        cur = self.conn.cursor()
        cur.execute("UPDATE virtual_assistants SET timezone = ? WHERE name = ?", (timezone, va_name))
        self.conn.commit()

    # ==================== SCHEDULE CONFIG ====================
    def get_schedule_config(self, va_name: str, category: str, day_of_week: int):
        """Devuelve la fila de schedule_config para el set, o None si no existe."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM schedule_config WHERE va_name = ? AND category = ? AND day_of_week = ?",
            (va_name, category, day_of_week),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def set_schedule_config(self, va_name: str, category: str, day_of_week: int, time_slots: list):
        """Inserta o reemplaza el schedule de un set para un día."""
        import json
        cur = self.conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO schedule_config
               (va_name, category, day_of_week, time_slots)
               VALUES (?, ?, ?, ?)""",
            (va_name, category, day_of_week, json.dumps(time_slots)),
        )
        self.conn.commit()

    def delete_schedule_config(self, va_name: str, category: str, day_of_week: int):
        """Elimina la config de un set para un día — el set volverá al fallback DEFAULT_SCHEDULE."""
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM schedule_config WHERE va_name = ? AND category = ? AND day_of_week = ?",
            (va_name, category, day_of_week),
        )
        self.conn.commit()

    # ==================== CUENTAS ====================
    def get_all_accounts(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM virtual_accounts ORDER BY account_type, username")
        return [dict(row) for row in cur.fetchall()]

    def get_story_link_base_url(self):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT setting_value FROM social_publishing_settings "
            "WHERE setting_key = ?",
            ("story_link_base_url",),
        )
        row = cur.fetchone()
        return row["setting_value"] if row else ""

    def set_story_link_base_url(self, value):
        normalized = normalize_story_link_base(value)
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO social_publishing_settings (setting_key, setting_value) "
            "VALUES (?, ?) "
            "ON CONFLICT(setting_key) DO UPDATE SET "
            "setting_value=excluded.setting_value, updated_at=CURRENT_TIMESTAMP",
            ("story_link_base_url", normalized),
        )
        self.conn.commit()
        return normalized

    def set_story_link_override(self, username, enabled, value=""):
        override_enabled = bool(enabled)
        override_url = ""
        if override_enabled:
            override_url = resolve_story_link(
                "",
                username,
                override_enabled=True,
                override_url=value,
            )
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE virtual_accounts "
            "SET story_link_override_enabled = ?, story_link_override = ? "
            "WHERE username = ?",
            (int(override_enabled), override_url, username),
        )
        self.conn.commit()
        return bool(cur.rowcount)

    def resolve_story_link_for_account(self, username):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT username, story_link_override_enabled, story_link_override "
            "FROM virtual_accounts WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return ""
        return resolve_story_link(
            self.get_story_link_base_url(),
            row["username"],
            bool(row["story_link_override_enabled"]),
            row["story_link_override"],
        )

    def set_account_trials_active(self, username: str, active: bool) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE virtual_accounts SET trials_active = ? WHERE username = ?",
            (int(bool(active)), username),
        )
        self.conn.commit()
        return bool(cur.rowcount)

    def get_trials_active_accounts(self):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM virtual_accounts WHERE trials_active = 1 "
            "ORDER BY account_type, username"
        )
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

    def apply_airtable_account_plan(self, plan):
        """Aplica un plan Airtable completo sin tocar los datos locales no compartidos."""
        from airtable_sync import MANAGED_FIELDS

        categories = [str(name or "").strip() for name in plan.categories_to_add]
        if any(not name for name in categories):
            raise ValueError("El plan contiene una categoría vacía.")

        rows = [*plan.create, *plan.update]
        for row in rows:
            if set(row) != set(MANAGED_FIELDS):
                raise ValueError("El plan de Airtable contiene campos inválidos.")
            if not str(row["username"] or "").strip() or not str(row["account_type"] or "").strip():
                raise ValueError("El plan de Airtable contiene una cuenta inválida.")

        usernames_to_delete = [str(username or "").strip() for username in plan.delete_usernames]
        if any(not username for username in usernames_to_delete):
            raise ValueError("El plan contiene un username vacío para eliminar.")

        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            for category in categories:
                cur.execute("INSERT OR IGNORE INTO account_categories (name) VALUES (?)", (category,))

            columns = ", ".join(MANAGED_FIELDS)
            placeholders = ", ".join("?" for _ in MANAGED_FIELDS)
            for row in plan.create:
                cur.execute(
                    f"INSERT INTO virtual_accounts ({columns}) VALUES ({placeholders})",
                    [row[name] for name in MANAGED_FIELDS],
                )

            update_fields = [name for name in MANAGED_FIELDS if name != "username"]
            assignments = ", ".join(f"{name} = ?" for name in update_fields)
            for row in plan.update:
                cur.execute(
                    f"UPDATE virtual_accounts SET {assignments} WHERE lower(username) = lower(?)",
                    [row[name] for name in update_fields] + [row["username"]],
                )

            for username in usernames_to_delete:
                cur.execute("DELETE FROM virtual_accounts WHERE lower(username) = lower(?)", (username,))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        return {
            "created": len(plan.create),
            "updated": len(plan.update),
            "deleted": len(usernames_to_delete),
        }

    def get_accounts_by_type(self, account_type: str) -> list[str]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT username FROM virtual_accounts WHERE account_type = ? ORDER BY username",
            (account_type,),
        )
        return [row["username"] for row in cur.fetchall()]

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

    def set_tanda_captions(self, name, captions_path):
        """Asigna o quita el archivo de captions de una tanda desde Logistica."""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE batch_tandas SET captions_file_path = ? WHERE tanda_name = ?",
            (captions_path or None, name),
        )
        self.conn.commit()
        return cur.rowcount

    def set_tanda_trial(self, name: str, is_trial: bool) -> bool:
        cur = self.conn.cursor()
        if is_trial:
            cur.execute(
                "INSERT OR IGNORE INTO trial_tandas (tanda_name) VALUES (?)",
                (name,),
            )
        else:
            cur.execute("DELETE FROM trial_tandas WHERE tanda_name = ?", (name,))
        self.conn.commit()
        return bool(cur.rowcount)

    def get_trial_tandas(self) -> list[str]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT tanda_name FROM trial_tandas ORDER BY created_at DESC, tanda_name"
        )
        return [row["tanda_name"] for row in cur.fetchall()]

    def is_trial_tanda(self, name: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM trial_tandas WHERE tanda_name = ?", (name,))
        return cur.fetchone() is not None

    def set_trial_source_caption(self, tanda_name: str, source_key: str, caption_text: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO trial_source_captions (tanda_name, source_key, caption_text)
            VALUES (?, ?, ?)
            ON CONFLICT(tanda_name, source_key) DO UPDATE SET
                caption_text=excluded.caption_text,
                updated_at=CURRENT_TIMESTAMP
            """,
            (tanda_name, source_key, caption_text),
        )
        self.conn.commit()

    def get_trial_source_captions(self, tanda_name: str) -> dict[str, str]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT source_key, caption_text FROM trial_source_captions "
            "WHERE tanda_name = ? ORDER BY source_key",
            (tanda_name,),
        )
        return {row["source_key"]: row["caption_text"] for row in cur.fetchall()}

    def set_normal_source_caption(self, tanda_name: str, source_key: str, caption_text: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO normal_source_captions (tanda_name, source_key, caption_text)
            VALUES (?, ?, ?)
            ON CONFLICT(tanda_name, source_key) DO UPDATE SET
                caption_text=excluded.caption_text, updated_at=CURRENT_TIMESTAMP
            """,
            (tanda_name, source_key, caption_text),
        )
        self.conn.commit()

    def get_normal_source_captions(self, tanda_name: str) -> dict[str, str]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT source_key, caption_text FROM normal_source_captions "
            "WHERE tanda_name = ? ORDER BY source_key", (tanda_name,)
        )
        return {row["source_key"]: row["caption_text"] for row in cur.fetchall()}

    def get_tandas(self, active_only=False):
        """Alias de get_all_tandas para compatibilidad."""
        return self.get_all_tandas()

    def get_tanda_by_name(self, name):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM batch_tandas WHERE tanda_name = ?", (name,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_and_sync_tandas(self, videos_finales_root: str) -> list[str]:
        """Sincroniza el desplegable de logística con la realidad del disco.

        1. Escanea ``videos_finales/``: cada subcarpeta con al menos un video se
           registra como tanda si aún no existe (upsert NO destructivo — nunca
           pisa filas ya presentes).
        2. Devuelve los nombres a mostrar: todas las tandas de la DB, pero
           ocultando las tandas tipo Forge (``p1==p2==nombre``) cuya carpeta ya
           no existe en disco (evita "fantasmas" tras renombrar/borrar carpetas).
           Las tandas legacy P1+P2 (``p1 != p2``) siempre se muestran.

        El orden respeta ``get_all_tandas`` (created_at DESC), así las carpetas
        recién detectadas quedan arriba.
        """
        video_exts = (".mp4", ".mov", ".avi")
        folder_names = set()
        if os.path.isdir(videos_finales_root):
            for name in os.listdir(videos_finales_root):
                fpath = os.path.join(videos_finales_root, name)
                if not os.path.isdir(fpath):
                    continue
                try:
                    has_video = any(
                        f.lower().endswith(video_exts) for f in os.listdir(fpath)
                    )
                except OSError:
                    has_video = False
                if not has_video:
                    continue
                folder_names.add(name)
                if not self.get_tanda_by_name(name):
                    self.add_tanda(name, name, name, "")

        visible = []
        for t in self.get_all_tandas():
            name = t.get("tanda_name")
            if not name:
                continue
            is_forge = (t.get("p1_folder") == name and t.get("p2_folder") == name)
            if is_forge and name not in folder_names:
                continue  # tanda Forge huérfana: carpeta borrada o renombrada
            visible.append(name)
        return visible

    def get_video_types(self):
        """Devuelve los tipos de video derivados de las categorías existentes."""
        cats = self.get_categories()
        return [{"type_name": c, "is_active": 1} for c in cats]

    def get_mix_rules(self, active_only=False):
        """Devuelve lista vacía — las reglas legacy no se usan en V6."""
        return []

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

    # ==================== METADATA FINGERPRINTS ====================
    def get_all_used_metadata_combos(self):
        """Devuelve un set de tuplas (model, city, carrier, ios) ya usadas históricamente."""
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT iphone_model, city, carrier, ios_version FROM metadata_fingerprints")
            return {(r[0], r[1], r[2], r[3]) for r in cur.fetchall()}
        except Exception:
            return set()

    def save_forge_video(self, tanda_name: str, source_name: str, output_name: str, video_hash: str = "") -> None:
        """Registra cada video procesado por Forge para tracking y anti-choque."""
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO forge_video_registry
            (tanda_name, source_name, output_name, video_hash, processed_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        ''', (tanda_name, source_name, output_name, video_hash))
        self.conn.commit()

    def save_video_transform_log(
        self,
        process_kind,
        source_path,
        output_path,
        details,
        tanda_name=None,
        source_identity=None,
    ):
        source_path = os.path.abspath(source_path)
        output_path = os.path.abspath(output_path)
        details_json = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
        output_filename = os.path.basename(output_path)
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO video_transform_logs (
                process_kind, source_path, output_path, output_filename,
                tanda_name, source_identity, details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(output_path) DO UPDATE SET
                process_kind=excluded.process_kind,
                source_path=excluded.source_path,
                output_filename=excluded.output_filename,
                tanda_name=excluded.tanda_name,
                source_identity=excluded.source_identity,
                details_json=excluded.details_json,
                created_at=datetime('now')
            """,
            (
                process_kind,
                source_path,
                output_path,
                output_filename,
                tanda_name,
                source_identity,
                details_json,
            ),
        )
        self.conn.commit()
        row = cur.execute("SELECT id FROM video_transform_logs WHERE output_path=?", (output_path,)).fetchone()
        return int(row[0])

    def get_video_transform_log_id(self, output_path):
        output_path = os.path.abspath(output_path)
        row = self.conn.execute(
            "SELECT id FROM video_transform_logs WHERE output_path=?",
            (output_path,),
        ).fetchone()
        return int(row[0]) if row else None

    def list_video_transform_logs(self, limit=500):
        rows = self.conn.execute(
            """
            SELECT id, process_kind, source_path, output_path, output_filename,
                   tanda_name, source_identity, details_json, created_at
            FROM video_transform_logs
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_metadata_fingerprints(self, fingerprints: list):
        """Inserta batch de fingerprints (ignora duplicados por el UNIQUE constraint)."""
        cur = self.conn.cursor()
        for fp in fingerprints:
            try:
                cur.execute('''
                    INSERT OR IGNORE INTO metadata_fingerprints
                    (video_hash, account_id, iphone_model, city, lat, lon, carrier, ios_version, used_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (
                    fp.get('video_hash', ''), fp.get('account_id'),
                    fp['iphone_model'], fp['city'], fp['lat'], fp['lon'],
                    fp['carrier'], fp['ios_version']
                ))
            except Exception as e:
                print(f"⚠️ Error guardando fingerprint: {e}")
        self.conn.commit()
