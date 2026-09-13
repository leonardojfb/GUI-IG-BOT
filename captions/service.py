from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from .importer import preview_txt
from trial_content import source_key_from_filename


@dataclass(frozen=True)
class CaptionPool:
    pool_id: str
    scope_kind: str
    scope_id: str
    name: str


@dataclass(frozen=True)
class CaptionVersion:
    caption_id: str
    pool_id: str
    position: int
    version: int
    text: str
    text_hash: str
    source_ref: str


@dataclass(frozen=True)
class CaptionSnapshot:
    caption_id: str
    caption_version: int
    text: str
    resolution_mode: str
    resolution_source_id: str
    strategy: str
    source_ref: str
    text_hash: str

    def as_manifest_dict(self) -> dict[str, str | int]:
        return {
            "caption_id": self.caption_id,
            "caption_version": self.caption_version,
            "text": self.text,
            "resolution_mode": self.resolution_mode,
            "resolution_source_id": self.resolution_source_id,
            "strategy": self.strategy,
            "source_ref": self.source_ref,
            "text_hash": self.text_hash,
        }


class MissingCaptionError(ValueError):
    def __init__(self, asset_id: str, fallback_available: bool = False):
        super().__init__(f"No hay caption individual para {asset_id}")
        self.asset_id = asset_id
        self.fallback_available = fallback_available


class CaptionService:
    def __init__(self, db):
        self.db = db
        self._ensure_schema()

    @property
    def conn(self):
        return self.db.conn

    def create_pool(self, scope_kind: str, scope_id: str, name: str) -> CaptionPool:
        scope_kind = self._required(scope_kind, "scope_kind")
        scope_id = self._required(scope_id, "scope_id")
        name = self._required(name, "name")
        pool_id = f"caption-pool-{uuid.uuid4().hex}"
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO caption_pools (pool_id, scope_kind, scope_id, name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(scope_kind, scope_id, name) DO NOTHING
            """,
            (pool_id, scope_kind, scope_id, name),
        )
        if not cur.rowcount:
            cur.execute(
                """
                SELECT pool_id, scope_kind, scope_id, name
                FROM caption_pools
                WHERE scope_kind = ? AND scope_id = ? AND name = ?
                """,
                (scope_kind, scope_id, name),
            )
        else:
            self.conn.commit()
            return CaptionPool(pool_id, scope_kind, scope_id, name)
        row = cur.fetchone()
        if not row:
            raise RuntimeError("No se pudo crear el pool de captions")
        return self._pool_from_row(row)

    def import_txt(
        self,
        pool_id: str,
        captions: list[str],
        source_ref: str = "",
    ) -> list[CaptionVersion]:
        imported = []
        for position, text in enumerate(captions):
            imported.append(
                self._create_or_update_position(pool_id, position, text, source_ref)
            )
        return imported

    def create_version(
        self,
        pool_or_caption_id: str,
        text: str,
        source_ref: str = "",
        position: int | None = None,
    ) -> CaptionVersion:
        text = self._required(text, "text")
        cur = self.conn.cursor()
        cur.execute(
            "SELECT caption_id, pool_id, position FROM caption_items WHERE caption_id = ?",
            (pool_or_caption_id,),
        )
        item = cur.fetchone()
        if item:
            return self._append_version(dict(item), text, source_ref)

        pool = self._get_pool(pool_or_caption_id)
        if position is None:
            position = self._next_position(pool.pool_id)
        caption_id = f"caption-{uuid.uuid4().hex}"
        cur.execute(
            """
            INSERT INTO caption_items (caption_id, pool_id, position)
            VALUES (?, ?, ?)
            """,
            (caption_id, pool.pool_id, int(position)),
        )
        self.conn.commit()
        return self._append_version(
            {"caption_id": caption_id, "pool_id": pool.pool_id, "position": int(position)},
            text,
            source_ref,
        )

    def bind_individual(self, asset_id: str, caption_id: str, strategy: str = "manual") -> None:
        asset_id = self._required(asset_id, "asset_id")
        self._latest_version(caption_id)
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO caption_bindings (asset_id, caption_id, strategy, active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(asset_id, caption_id, strategy)
            DO UPDATE SET active = 1
            """,
            (asset_id, caption_id, self._required(strategy, "strategy")),
        )
        self.conn.commit()

    def resolve_individual(
        self,
        asset_id: str,
        strategy: str,
        allow_general_fallback: bool = False,
        fallback_pool_id: str | None = None,
    ) -> CaptionSnapshot:
        asset_id = self._required(asset_id, "asset_id")
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT caption_id
            FROM caption_bindings
            WHERE asset_id = ? AND active = 1 AND strategy = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (asset_id, self._required(strategy, "strategy")),
        )
        row = cur.fetchone()
        if row:
            return self.snapshot(
                row["caption_id"],
                mode="individual",
                source_id=asset_id,
                strategy=strategy,
            )
        if allow_general_fallback and fallback_pool_id:
            fallback = self.first_pool_snapshot(
                fallback_pool_id,
                mode="general_fallback",
                source_id=fallback_pool_id,
                strategy=strategy,
            )
            if fallback:
                return fallback
        raise MissingCaptionError(asset_id, fallback_available=bool(fallback_pool_id))

    def first_pool_snapshot(
        self,
        pool_id: str,
        mode: str,
        source_id: str,
        strategy: str = "manual",
    ) -> CaptionSnapshot | None:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT caption_id
            FROM caption_items
            WHERE pool_id = ?
            ORDER BY position ASC
            LIMIT 1
            """,
            (pool_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return self.snapshot(row["caption_id"], mode=mode, source_id=source_id, strategy=strategy)

    def pool_snapshot_at(
        self,
        pool_id: str,
        index: int,
        mode: str,
        source_id: str,
        strategy: str = "manual",
    ) -> CaptionSnapshot | None:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT caption_id
            FROM caption_items
            WHERE pool_id = ?
            ORDER BY position ASC
            """,
            (pool_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return None
        row = rows[int(index) % len(rows)]
        return self.snapshot(row["caption_id"], mode=mode, source_id=source_id, strategy=strategy)

    def resolve_legacy_manifest_caption(
        self,
        tanda_name: str,
        filename: str,
        mode: str,
        delivery_kind: str = "normal",
        pool_index: int = 0,
        allow_general_fallback: bool = False,
    ) -> CaptionSnapshot | None:
        self.migrate_legacy_captions()
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode == "general":
            mapping = self._migration_row("general_txt", tanda_name, "")
            if not mapping:
                return None
            return self.pool_snapshot_at(
                mapping["pool_id"],
                pool_index,
                mode="general",
                source_id=mapping["pool_id"],
                strategy="round_robin",
            )

        source_key = source_key_from_filename(filename)
        legacy_kind = "trial_individual" if delivery_kind == "trial" else "normal_individual"
        mapping = self._migration_row(legacy_kind, tanda_name, source_key)
        if mapping and mapping["caption_id"]:
            return self.snapshot(
                mapping["caption_id"],
                mode="individual",
                source_id=source_key,
                strategy="manual",
            )
        if allow_general_fallback:
            general = self._migration_row("general_txt", tanda_name, "")
            if general:
                return self.pool_snapshot_at(
                    general["pool_id"],
                    pool_index,
                    mode="general_fallback",
                    source_id=general["pool_id"],
                    strategy="manual",
                )
        raise MissingCaptionError(source_key, fallback_available=allow_general_fallback)

    def snapshot(
        self,
        caption_id: str,
        version: int | None = None,
        mode: str = "manual",
        source_id: str = "",
        strategy: str = "manual",
    ) -> CaptionSnapshot:
        row = self._version(caption_id, version)
        return CaptionSnapshot(
            caption_id=row["caption_id"],
            caption_version=int(row["version"]),
            text=row["text"],
            resolution_mode=mode,
            resolution_source_id=source_id,
            strategy=strategy,
            source_ref=row["source_ref"],
            text_hash=row["text_hash"],
        )

    def upsert_legacy_source_caption(
        self,
        legacy_kind: str,
        tanda_name: str,
        source_key: str,
        text: str,
    ) -> CaptionVersion | None:
        text = str(text or "").strip()
        if not text:
            return None
        if legacy_kind not in {"normal_individual", "trial_individual"}:
            raise ValueError(f"legacy_kind invalido: {legacy_kind}")
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT pool_id, caption_id
            FROM caption_migration_map
            WHERE legacy_kind = ? AND tanda_name = ? AND source_key = ?
            """,
            (legacy_kind, tanda_name, source_key),
        )
        mapping = cur.fetchone()
        if mapping and mapping["caption_id"]:
            latest = self._latest_version(mapping["caption_id"])
            if latest["text_hash"] == self._hash_text(text):
                return self._version_from_row(latest)
            return self.create_version(
                mapping["caption_id"],
                text,
                source_ref=f"{legacy_kind}:{tanda_name}:{source_key}",
            )

        pool_name = "normal individual" if legacy_kind == "normal_individual" else "trial individual"
        pool = self.create_pool("tanda", tanda_name, pool_name)
        version = self.create_version(
            pool.pool_id,
            text,
            source_ref=f"{legacy_kind}:{tanda_name}:{source_key}",
        )
        self._record_migration(
            legacy_kind,
            tanda_name,
            source_key,
            pool.pool_id,
            version.caption_id,
            version.source_ref,
            "imported",
        )
        return version

    def migrate_legacy_captions(self) -> dict[str, int]:
        report = {
            "general_imported": 0,
            "normal_individual_imported": 0,
            "trial_individual_imported": 0,
            "missing_files": 0,
        }
        cur = self.conn.cursor()
        cur.execute("SELECT tanda_name, captions_file_path FROM batch_tandas ORDER BY tanda_name")
        for row in cur.fetchall():
            tanda_name = row["tanda_name"]
            captions_path = row["captions_file_path"]
            if not captions_path:
                continue
            if self._migration_exists("general_txt", tanda_name, ""):
                continue
            pool = self.create_pool("tanda", tanda_name, "general")
            try:
                preview = preview_txt(captions_path)
            except FileNotFoundError:
                self._record_migration(
                    "general_txt",
                    tanda_name,
                    "",
                    pool.pool_id,
                    None,
                    captions_path,
                    "missing_file",
                )
                report["missing_files"] += 1
                continue
            versions = self.import_txt(pool.pool_id, preview.captions, source_ref=preview.source_path)
            self._record_migration(
                "general_txt",
                tanda_name,
                "",
                pool.pool_id,
                versions[0].caption_id if versions else None,
                preview.source_path,
                "imported",
            )
            report["general_imported"] += len(versions)

        cur.execute(
            """
            SELECT tanda_name, source_key, caption_text
            FROM normal_source_captions
            ORDER BY tanda_name, source_key
            """
        )
        for row in cur.fetchall():
            if self._migration_exists("normal_individual", row["tanda_name"], row["source_key"]):
                continue
            pool = self.create_pool("tanda", row["tanda_name"], "normal individual")
            version = self.create_version(
                pool.pool_id,
                row["caption_text"],
                source_ref=f"normal_source_captions:{row['tanda_name']}:{row['source_key']}",
            )
            self._record_migration(
                "normal_individual",
                row["tanda_name"],
                row["source_key"],
                pool.pool_id,
                version.caption_id,
                version.source_ref,
                "imported",
            )
            report["normal_individual_imported"] += 1

        cur.execute(
            """
            SELECT tanda_name, source_key, caption_text
            FROM trial_source_captions
            ORDER BY tanda_name, source_key
            """
        )
        for row in cur.fetchall():
            if self._migration_exists("trial_individual", row["tanda_name"], row["source_key"]):
                continue
            pool = self.create_pool("tanda", row["tanda_name"], "trial individual")
            version = self.create_version(
                pool.pool_id,
                row["caption_text"],
                source_ref=f"trial_source_captions:{row['tanda_name']}:{row['source_key']}",
            )
            self._record_migration(
                "trial_individual",
                row["tanda_name"],
                row["source_key"],
                pool.pool_id,
                version.caption_id,
                version.source_ref,
                "imported",
            )
            report["trial_individual_imported"] += 1
        return report

    def get_migration_mappings(self, tanda_name: str) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT legacy_kind, tanda_name, source_key, pool_id, caption_id, source_ref, status
            FROM caption_migration_map
            WHERE tanda_name = ?
            ORDER BY legacy_kind, source_key
            """,
            (tanda_name,),
        )
        return [dict(row) for row in cur.fetchall()]

    def _create_or_update_position(
        self,
        pool_id: str,
        position: int,
        text: str,
        source_ref: str,
    ) -> CaptionVersion:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT caption_id, pool_id, position
            FROM caption_items
            WHERE pool_id = ? AND position = ?
            """,
            (pool_id, int(position)),
        )
        row = cur.fetchone()
        if not row:
            return self.create_version(pool_id, text, source_ref, position=position)
        latest = self._latest_version(row["caption_id"])
        if latest["text_hash"] == self._hash_text(text):
            return self._version_from_row(latest)
        return self._append_version(dict(row), text, source_ref)

    def _append_version(
        self,
        item: dict,
        text: str,
        source_ref: str,
    ) -> CaptionVersion:
        cur = self.conn.cursor()
        version = self._next_version(item["caption_id"])
        text_hash = self._hash_text(text)
        cur.execute(
            """
            INSERT INTO caption_versions
                (caption_id, version, text, text_hash, source_ref)
            VALUES (?, ?, ?, ?, ?)
            """,
            (item["caption_id"], version, text, text_hash, source_ref or ""),
        )
        self.conn.commit()
        return CaptionVersion(
            caption_id=item["caption_id"],
            pool_id=item["pool_id"],
            position=int(item["position"]),
            version=version,
            text=text,
            text_hash=text_hash,
            source_ref=source_ref or "",
        )

    def _version(self, caption_id: str, version: int | None):
        cur = self.conn.cursor()
        if version is None:
            return self._latest_version(caption_id)
        cur.execute(
            """
            SELECT ci.pool_id, ci.position, cv.*
            FROM caption_versions cv
            JOIN caption_items ci ON ci.caption_id = cv.caption_id
            WHERE cv.caption_id = ? AND cv.version = ?
            """,
            (caption_id, int(version)),
        )
        row = cur.fetchone()
        if not row:
            raise KeyError(f"{caption_id}@{version}")
        return row

    def _latest_version(self, caption_id: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT ci.pool_id, ci.position, cv.*
            FROM caption_versions cv
            JOIN caption_items ci ON ci.caption_id = cv.caption_id
            WHERE cv.caption_id = ?
            ORDER BY cv.version DESC
            LIMIT 1
            """,
            (caption_id,),
        )
        row = cur.fetchone()
        if not row:
            raise KeyError(caption_id)
        return row

    def _get_pool(self, pool_id: str) -> CaptionPool:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT pool_id, scope_kind, scope_id, name FROM caption_pools WHERE pool_id = ?",
            (pool_id,),
        )
        row = cur.fetchone()
        if not row:
            raise KeyError(pool_id)
        return self._pool_from_row(row)

    def _next_position(self, pool_id: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_position FROM caption_items WHERE pool_id = ?",
            (pool_id,),
        )
        return int(cur.fetchone()["next_position"])

    def _next_version(self, caption_id: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM caption_versions WHERE caption_id = ?",
            (caption_id,),
        )
        return int(cur.fetchone()["next_version"])

    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS caption_pools (
                pool_id TEXT PRIMARY KEY,
                scope_kind TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(scope_kind, scope_id, name)
            );
            CREATE TABLE IF NOT EXISTS caption_items (
                caption_id TEXT PRIMARY KEY,
                pool_id TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pool_id) REFERENCES caption_pools(pool_id),
                UNIQUE(pool_id, position)
            );
            CREATE TABLE IF NOT EXISTS caption_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caption_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                text TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                source_ref TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (caption_id) REFERENCES caption_items(caption_id),
                UNIQUE(caption_id, version)
            );
            CREATE INDEX IF NOT EXISTS idx_caption_versions_caption
            ON caption_versions(caption_id, version);
            CREATE TABLE IF NOT EXISTS caption_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT NOT NULL,
                caption_id TEXT NOT NULL,
                strategy TEXT NOT NULL DEFAULT 'manual',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (caption_id) REFERENCES caption_items(caption_id),
                UNIQUE(asset_id, caption_id, strategy)
            );
            CREATE INDEX IF NOT EXISTS idx_caption_bindings_asset
            ON caption_bindings(asset_id, active);
            CREATE TABLE IF NOT EXISTS caption_migration_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                legacy_kind TEXT NOT NULL,
                tanda_name TEXT NOT NULL,
                source_key TEXT NOT NULL DEFAULT '',
                pool_id TEXT NOT NULL,
                caption_id TEXT,
                source_ref TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(legacy_kind, tanda_name, source_key)
            );
            """
        )
        self.conn.commit()

    def _migration_exists(self, legacy_kind: str, tanda_name: str, source_key: str) -> bool:
        return self._migration_row(legacy_kind, tanda_name, source_key) is not None

    def _migration_row(self, legacy_kind: str, tanda_name: str, source_key: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT legacy_kind, tanda_name, source_key, pool_id, caption_id, source_ref, status
            FROM caption_migration_map
            WHERE legacy_kind = ? AND tanda_name = ? AND source_key = ?
            """,
            (legacy_kind, tanda_name, source_key),
        )
        return cur.fetchone()

    def _record_migration(
        self,
        legacy_kind: str,
        tanda_name: str,
        source_key: str,
        pool_id: str,
        caption_id: str | None,
        source_ref: str,
        status: str,
    ) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO caption_migration_map
                (legacy_kind, tanda_name, source_key, pool_id, caption_id, source_ref, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(legacy_kind, tanda_name, source_key) DO NOTHING
            """,
            (legacy_kind, tanda_name, source_key, pool_id, caption_id, source_ref or "", status),
        )
        self.conn.commit()

    @staticmethod
    def _pool_from_row(row) -> CaptionPool:
        return CaptionPool(
            pool_id=row["pool_id"],
            scope_kind=row["scope_kind"],
            scope_id=row["scope_id"],
            name=row["name"],
        )

    @staticmethod
    def _version_from_row(row) -> CaptionVersion:
        return CaptionVersion(
            caption_id=row["caption_id"],
            pool_id=row["pool_id"],
            position=int(row["position"]),
            version=int(row["version"]),
            text=row["text"],
            text_hash=row["text_hash"],
            source_ref=row["source_ref"],
        )

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(str(text).encode("utf-8")).hexdigest()

    @staticmethod
    def _required(value: str, field: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field} no puede estar vacio")
        return normalized
