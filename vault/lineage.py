from __future__ import annotations

import json
from typing import Any


class VaultLineage:
    def __init__(self, db):
        self.db = db
        self._ensure_schema()

    @property
    def conn(self):
        return self.db.conn

    def record_derivation(
        self,
        child_asset_id: int,
        parent_asset_ids: list[int],
        relation_kind: str,
        details: dict[str, Any] | None = None,
    ) -> int:
        child = int(child_asset_id)
        relation = self._required(relation_kind, "relation_kind")
        parents = list(dict.fromkeys(int(parent_id) for parent_id in parent_asset_ids))
        self._require_asset(child)
        if not parents:
            return 0
        inserted = 0
        cur = self.conn.cursor()
        for parent in parents:
            self._require_asset(parent)
            if parent == child:
                raise ValueError("Un asset no puede ser padre de si mismo")
            if self._has_path(child, parent):
                raise ValueError("La relacion crearia un ciclo de linaje")
            cur.execute(
                """
                INSERT OR IGNORE INTO vault_asset_lineage
                    (child_asset_id, parent_asset_id, relation_kind, details_json)
                VALUES (?, ?, ?, ?)
                """,
                (child, parent, relation, self._json(details)),
            )
            inserted += int(cur.rowcount)
        self.conn.commit()
        return inserted

    def parents_for_asset(self, asset_id: int) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT l.child_asset_id, l.parent_asset_id, l.relation_kind,
                   l.details_json, l.created_at, a.sha256, a.media_type,
                   a.display_name
            FROM vault_asset_lineage l
            JOIN vault_assets a ON a.id = l.parent_asset_id
            WHERE l.child_asset_id = ?
            ORDER BY l.created_at, l.parent_asset_id
            """,
            (int(asset_id),),
        )
        return [dict(row) for row in cur.fetchall()]

    def children_for_asset(self, asset_id: int) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT l.child_asset_id, l.parent_asset_id, l.relation_kind,
                   l.details_json, l.created_at, a.sha256, a.media_type,
                   a.display_name
            FROM vault_asset_lineage l
            JOIN vault_assets a ON a.id = l.child_asset_id
            WHERE l.parent_asset_id = ?
            ORDER BY l.created_at, l.child_asset_id
            """,
            (int(asset_id),),
        )
        return [dict(row) for row in cur.fetchall()]

    def record_usage(
        self,
        asset_id: int,
        usage_kind: str,
        external_ref: str,
        details: dict[str, Any] | None = None,
    ) -> int:
        asset = int(asset_id)
        self._require_asset(asset)
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO vault_asset_usages
                (asset_id, usage_kind, external_ref, details_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                asset,
                self._required(usage_kind, "usage_kind"),
                self._required(external_ref, "external_ref"),
                self._json(details),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def record_usage_once(
        self,
        asset_id: int,
        usage_kind: str,
        external_ref: str,
        details: dict[str, Any] | None = None,
    ) -> int:
        asset = int(asset_id)
        kind = self._required(usage_kind, "usage_kind")
        ref = self._required(external_ref, "external_ref")
        self._require_asset(asset)
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM vault_asset_usages
            WHERE asset_id = ? AND usage_kind = ? AND external_ref = ?
            ORDER BY id
            LIMIT 1
            """,
            (asset, kind, ref),
        )
        existing = cur.fetchone()
        if existing:
            return int(existing["id"])
        return self.record_usage(asset, kind, ref, details)

    def usages_for_asset(self, asset_id: int) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, asset_id, usage_kind, external_ref, details_json, created_at
            FROM vault_asset_usages
            WHERE asset_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (int(asset_id),),
        )
        return [dict(row) for row in cur.fetchall()]

    def _has_path(self, start_asset_id: int, target_asset_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            """
            WITH RECURSIVE descendants(asset_id) AS (
                SELECT child_asset_id
                FROM vault_asset_lineage
                WHERE parent_asset_id = ?
                UNION
                SELECT l.child_asset_id
                FROM vault_asset_lineage l
                JOIN descendants d ON d.asset_id = l.parent_asset_id
            )
            SELECT 1 FROM descendants WHERE asset_id = ? LIMIT 1
            """,
            (int(start_asset_id), int(target_asset_id)),
        )
        return cur.fetchone() is not None

    def _require_asset(self, asset_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM vault_assets WHERE id = ?", (int(asset_id),))
        if not cur.fetchone():
            raise ValueError(f"No existe asset: {asset_id}")

    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS vault_asset_lineage (
                child_asset_id INTEGER NOT NULL,
                parent_asset_id INTEGER NOT NULL,
                relation_kind TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (child_asset_id, parent_asset_id, relation_kind),
                FOREIGN KEY (child_asset_id) REFERENCES vault_assets(id),
                FOREIGN KEY (parent_asset_id) REFERENCES vault_assets(id)
            );
            CREATE INDEX IF NOT EXISTS idx_vault_asset_lineage_parent
            ON vault_asset_lineage(parent_asset_id);
            CREATE TABLE IF NOT EXISTS vault_asset_usages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                usage_kind TEXT NOT NULL,
                external_ref TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES vault_assets(id)
            );
            CREATE INDEX IF NOT EXISTS idx_vault_asset_usages_asset
            ON vault_asset_usages(asset_id, created_at);
            """
        )
        self.conn.commit()

    @staticmethod
    def _json(payload: dict[str, Any] | None) -> str:
        return json.dumps(payload or {}, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def _required(value: str, field: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field} no puede estar vacio")
        return normalized
