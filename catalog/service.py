from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PatchValue:
    action: str
    value: Any = None


UNSET = PatchValue("unset")
CLEAR = PatchValue("clear")


def SET(value: Any) -> PatchValue:
    return PatchValue("set", value)


class CatalogService:
    BULK_FIELDS = frozenset({"account_type", "assigned_va", "trials_active"})

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

    def preview_bulk_update(
        self,
        account_ids: list[int],
        patch: dict[str, PatchValue],
    ) -> dict[str, Any]:
        normalized_patch = self._normalise_bulk_patch(patch)
        rows = self._accounts_by_ids(account_ids)
        preview_rows = []
        for row in rows:
            before = self._bulk_snapshot(row)
            after = dict(before)
            for field, patch_value in normalized_patch.items():
                if patch_value.action == "unset":
                    continue
                if patch_value.action == "clear":
                    after[field] = self._bulk_clear_value(field)
                else:
                    after[field] = patch_value.value
            preview_rows.append(
                {
                    "id": row["id"],
                    "identity_id": row.get("identity_id"),
                    "username": row["username"],
                    "before": before,
                    "after": after,
                }
            )
        return {
            "account_ids": [row["id"] for row in rows],
            "patch": {
                field: {"action": patch_value.action, "value": patch_value.value}
                for field, patch_value in normalized_patch.items()
            },
            "preview_revision": self._bulk_revision(rows),
            "rows": preview_rows,
        }

    def apply_bulk_update(self, preview: dict[str, Any]) -> int:
        account_ids = [int(account_id) for account_id in preview.get("account_ids", [])]
        rows = self._accounts_by_ids(account_ids)
        if self._bulk_revision(rows) != preview.get("preview_revision"):
            raise ValueError("La revision del catalogo cambio; genera un nuevo preview")

        assignments = []
        params: list[Any] = []
        patch = preview.get("patch", {})
        for field, payload in patch.items():
            if field not in self.BULK_FIELDS:
                raise ValueError(f"Campo bulk no permitido: {field}")
            action = payload.get("action")
            if action == "unset":
                continue
            if action == "clear":
                value = self._bulk_clear_value(field)
            elif action == "set":
                value = payload.get("value")
            else:
                raise ValueError(f"Accion bulk invalida: {action}")
            assignments.append(f"{field} = ?")
            params.append(value)

        if not assignments:
            return 0

        placeholders = ",".join("?" for _ in account_ids)
        cur = self.conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            cur.execute(
                f"UPDATE virtual_accounts SET {', '.join(assignments)} WHERE id IN ({placeholders})",
                params + account_ids,
            )
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return int(cur.rowcount)

    @staticmethod
    def _normalise_platform(value: Any) -> str:
        platform = str(value or "").strip().lower()
        return platform or "needs_review"

    def _normalise_bulk_patch(self, patch: dict[str, PatchValue]) -> dict[str, PatchValue]:
        normalized = {}
        for field, patch_value in patch.items():
            if field not in self.BULK_FIELDS:
                raise ValueError(f"Campo bulk no permitido: {field}")
            if not isinstance(patch_value, PatchValue):
                raise ValueError(f"Patch invalido para {field}")
            normalized[field] = patch_value
        return normalized

    def _accounts_by_ids(self, account_ids: list[int]) -> list[dict[str, Any]]:
        if not account_ids:
            return []
        unique_ids = list(dict.fromkeys(int(account_id) for account_id in account_ids))
        placeholders = ",".join("?" for _ in unique_ids)
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT * FROM virtual_accounts WHERE id IN ({placeholders}) ORDER BY id",
            unique_ids,
        )
        rows = [dict(row) for row in cur.fetchall()]
        if len(rows) != len(unique_ids):
            found = {row["id"] for row in rows}
            missing = [account_id for account_id in unique_ids if account_id not in found]
            raise ValueError(f"Cuentas no encontradas: {missing}")
        return rows

    @staticmethod
    def _bulk_snapshot(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "account_type": row["account_type"],
            "assigned_va": row["assigned_va"],
            "trials_active": int(row["trials_active"]),
        }

    @staticmethod
    def _bulk_clear_value(field: str) -> Any:
        if field == "assigned_va":
            return "Sin Asignar"
        if field == "trials_active":
            return 0
        if field == "account_type":
            raise ValueError("La categoria no se puede limpiar sin reemplazo")
        raise ValueError(f"Campo bulk no permitido: {field}")

    def _bulk_revision(self, rows: list[dict[str, Any]]) -> str:
        payload = [
            {
                "id": row["id"],
                "identity_id": row.get("identity_id"),
                "username": row["username"],
                **self._bulk_snapshot(row),
            }
            for row in rows
        ]
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
