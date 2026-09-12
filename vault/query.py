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
