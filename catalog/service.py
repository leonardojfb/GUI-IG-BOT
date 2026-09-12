from __future__ import annotations

from typing import Any


class CatalogService:
    def __init__(self, db):
        self.db = db

    @property
    def conn(self):
        return self.db.conn

    def ensure_identity_catalog(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM virtual_accounts ORDER BY id")
        accounts = [dict(row) for row in cur.fetchall()]
        migrated = 0
        for account in accounts:
            identity_id = account.get("identity_id") or f"legacy-account-{account['id']}"
            platform = self._normalise_platform(account.get("social_network"))
            cur.execute(
                """
                INSERT OR IGNORE INTO social_identities
                    (identity_id, legacy_account_id, platform, display_name)
                VALUES (?, ?, ?, ?)
                """,
                (identity_id, account["id"], platform, account["username"]),
            )
            cur.execute(
                """
                UPDATE social_identities
                SET legacy_account_id = ?, platform = ?, display_name = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE identity_id = ?
                """,
                (account["id"], platform, account["username"], identity_id),
            )
            cur.execute(
                "UPDATE virtual_accounts SET identity_id = ? WHERE id = ?",
                (identity_id, account["id"]),
            )
            cur.execute(
                """
                INSERT OR IGNORE INTO identity_aliases
                    (identity_id, alias, alias_type, is_current, source)
                VALUES (?, ?, 'username', 1, 'legacy_migration')
                """,
                (identity_id, account["username"]),
            )
            migrated += 1
        self.conn.commit()
        return migrated

    def get_identity(self, identity_id: str) -> dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM social_identities WHERE identity_id = ?",
            (identity_id,),
        )
        row = cur.fetchone()
        if not row:
            raise KeyError(identity_id)
        return dict(row)

    def get_aliases(self, identity_id: str) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT alias, alias_type, is_current, source
            FROM identity_aliases
            WHERE identity_id = ?
            ORDER BY is_current DESC, created_at DESC, id DESC
            """,
            (identity_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def rename_identity(self, identity_id: str, new_username: str) -> None:
        username = str(new_username or "").strip()
        if not username:
            raise ValueError("El username no puede estar vacio")

        identity = self.get_identity(identity_id)
        legacy_account_id = identity["legacy_account_id"]
        cur = self.conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            cur.execute(
                """
                UPDATE identity_aliases
                SET is_current = 0, archived_at = CURRENT_TIMESTAMP
                WHERE identity_id = ? AND alias_type = 'username' AND is_current = 1
                """,
                (identity_id,),
            )
            cur.execute(
                """
                INSERT INTO identity_aliases
                    (identity_id, alias, alias_type, is_current, source)
                VALUES (?, ?, 'username', 1, 'rename')
                ON CONFLICT(identity_id, alias_type, alias)
                DO UPDATE SET is_current = 1, archived_at = NULL, source = 'rename'
                """,
                (identity_id, username),
            )
            cur.execute(
                """
                UPDATE social_identities
                SET display_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE identity_id = ?
                """,
                (username, identity_id),
            )
            cur.execute(
                "UPDATE virtual_accounts SET username = ? WHERE id = ?",
                (username, legacy_account_id),
            )
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()

    def set_trial_capability(self, identity_id: str, active: bool) -> bool:
        identity = self.get_identity(identity_id)
        platform = self._normalise_platform(identity.get("platform"))
        if platform != "instagram":
            raise ValueError("Trial solo puede activarse para identidades Instagram")
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE virtual_accounts SET trials_active = ? WHERE id = ?",
            (int(bool(active)), identity["legacy_account_id"]),
        )
        self.conn.commit()
        return bool(cur.rowcount)

    @staticmethod
    def _normalise_platform(value: Any) -> str:
        platform = str(value or "").strip().lower()
        return platform or "needs_review"
