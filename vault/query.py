from __future__ import annotations

from typing import Any


class VaultQuery:
    def __init__(self, db):
        self.db = db

    @property
    def conn(self):
        return self.db.conn

    def create_family(self, name: str, notes: str = "") -> dict[str, Any]:
        return self._create_named("content_families", name, notes)

    def create_collection(self, name: str, notes: str = "") -> dict[str, Any]:
        return self._create_named("vault_collections", name, notes)

    def add_asset_to_family(self, family_id: int, asset_id: int, role: str = "asset") -> bool:
        self._require_row("content_families", family_id, "familia")
        self._require_row("vault_assets", asset_id, "asset")
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO content_family_assets (family_id, asset_id, role)
            VALUES (?, ?, ?)
            """,
            (int(family_id), int(asset_id), self._label(role, "El rol no puede estar vacio")),
        )
        self.conn.commit()
        return bool(cur.rowcount)

    def add_asset_to_collection(self, collection_id: int, asset_id: int) -> bool:
        self._require_row("vault_collections", collection_id, "coleccion")
        self._require_row("vault_assets", asset_id, "asset")
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO vault_collection_assets (collection_id, asset_id)
            VALUES (?, ?)
            """,
            (int(collection_id), int(asset_id)),
        )
        self.conn.commit()
        return bool(cur.rowcount)

    def assets_for_family(self, family_id: int) -> list[dict[str, Any]]:
        self._require_row("content_families", family_id, "familia")
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT a.*, m.role
            FROM content_family_assets m
            JOIN vault_assets a ON a.id = m.asset_id
            WHERE m.family_id = ?
            ORDER BY a.id
            """,
            (int(family_id),),
        )
        return [dict(row) for row in cur.fetchall()]

    def assets_for_collection(self, collection_id: int) -> list[dict[str, Any]]:
        self._require_row("vault_collections", collection_id, "coleccion")
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT a.*
            FROM vault_collection_assets m
            JOIN vault_assets a ON a.id = m.asset_id
            WHERE m.collection_id = ?
            ORDER BY a.id
            """,
            (int(collection_id),),
        )
        return [dict(row) for row in cur.fetchall()]

    def search_assets(
        self,
        *,
        media_type: str | None = None,
        status: str | None = None,
        family_id: int | None = None,
        collection_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        where = []
        params: list[Any] = []
        joins = [
            """
            LEFT JOIN vault_locations l ON l.id = (
                SELECT l2.id FROM vault_locations l2
                WHERE l2.asset_id = a.id
                ORDER BY l2.managed DESC, l2.id
                LIMIT 1
            )
            """
        ]
        if family_id is not None:
            joins.append("JOIN content_family_assets fa ON fa.asset_id = a.id AND fa.family_id = ?")
            params.append(int(family_id))
        if collection_id is not None:
            joins.append("JOIN vault_collection_assets ca ON ca.asset_id = a.id AND ca.collection_id = ?")
            params.append(int(collection_id))
        if media_type:
            where.append("a.media_type = ?")
            params.append(str(media_type))
        if status:
            where.append("COALESCE(l.status, 'missing') = ?")
            params.append(str(status))

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        join_sql = "\n".join(joins)
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT COUNT(DISTINCT a.id) AS total FROM vault_assets a {join_sql} {where_sql}",
            params,
        )
        total = int(cur.fetchone()["total"])
        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))
        cur.execute(
            f"""
            SELECT DISTINCT a.*, COALESCE(l.status, 'missing') AS status, l.path
            FROM vault_assets a
            {join_sql}
            {where_sql}
            ORDER BY a.id
            LIMIT ? OFFSET ?
            """,
            params + [safe_limit, safe_offset],
        )
        return {
            "items": [dict(row) for row in cur.fetchall()],
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
        }

    def inspect_asset(self, asset_id: int, *, storage, thumbnail_cache) -> dict[str, Any]:
        asset = self._asset(asset_id)
        locations = []
        for location in storage.locations_for_asset(asset_id):
            locations.append(storage.verify_location(location["id"]))
        from vault.thumbnails import VaultThumbnailer
        from vault.lineage import VaultLineage
        from vault.signatures import VaultSignatures

        lineage = VaultLineage(self.db)
        signatures = VaultSignatures(self.db)
        thumbnail = VaultThumbnailer(storage, thumbnail_cache).ensure_thumbnail(asset_id)
        return {
            "asset": asset,
            "locations": locations,
            "families": self.families_for_asset(asset_id),
            "collections": self.collections_for_asset(asset_id),
            "transform_logs": self.transform_logs_for_asset(asset_id),
            "parents": lineage.parents_for_asset(asset_id),
            "children": lineage.children_for_asset(asset_id),
            "usages": lineage.usages_for_asset(asset_id),
            "signatures": signatures.signatures_for_asset(asset_id),
            "thumbnail": thumbnail,
        }

    def families_for_asset(self, asset_id: int) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT f.*, m.role
            FROM content_family_assets m
            JOIN content_families f ON f.id = m.family_id
            WHERE m.asset_id = ?
            ORDER BY f.name COLLATE NOCASE, m.role
            """,
            (int(asset_id),),
        )
        return [dict(row) for row in cur.fetchall()]

    def collections_for_asset(self, asset_id: int) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT c.*
            FROM vault_collection_assets m
            JOIN vault_collections c ON c.id = m.collection_id
            WHERE m.asset_id = ?
            ORDER BY c.name COLLATE NOCASE
            """,
            (int(asset_id),),
        )
        return [dict(row) for row in cur.fetchall()]

    def transform_logs_for_asset(self, asset_id: int) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, process_kind, source_path, output_path, output_filename,
                   tanda_name, source_identity, source_vault_asset_id,
                   output_vault_asset_id, details_json, created_at
            FROM video_transform_logs
            WHERE source_vault_asset_id = ?
               OR output_vault_asset_id = ?
               OR source_path IN (SELECT path FROM vault_locations WHERE asset_id = ?)
               OR output_path IN (SELECT path FROM vault_locations WHERE asset_id = ?)
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (int(asset_id), int(asset_id), int(asset_id), int(asset_id)),
        )
        return [dict(row) for row in cur.fetchall()]

    def _create_named(self, table: str, name: str, notes: str) -> dict[str, Any]:
        label = self._label(name, "El nombre no puede estar vacio")
        cur = self.conn.cursor()
        cur.execute(
            f"""
            INSERT INTO {table} (name, notes)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET notes = excluded.notes
            """,
            (label, str(notes or "")),
        )
        self.conn.commit()
        cur.execute(f"SELECT * FROM {table} WHERE name = ?", (label,))
        return dict(cur.fetchone())

    def _asset(self, asset_id: int) -> dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM vault_assets WHERE id = ?", (int(asset_id),))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"No existe asset: {asset_id}")
        return dict(row)

    def _require_row(self, table: str, row_id: int, label: str) -> None:
        cur = self.conn.cursor()
        cur.execute(f"SELECT id FROM {table} WHERE id = ?", (int(row_id),))
        if not cur.fetchone():
            raise ValueError(f"No existe {label}: {row_id}")

    @staticmethod
    def _label(value: Any, message: str) -> str:
        label = str(value or "").strip()
        if not label:
            raise ValueError(message)
        return label
