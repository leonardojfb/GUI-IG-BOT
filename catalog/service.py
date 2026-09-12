from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from calendar_manifest import load_entries, publication_target_for_entry


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

    def set_account_category(
        self,
        account_id: int,
        category: str,
        manifest_file: str | Path | None = None,
        allow_confirmed_calendar_changes: bool = False,
    ) -> bool:
        category_name = self._normalise_label(category, "La categoria no puede estar vacia")
        self._account_by_id(account_id)
        self._assert_calendar_change_allowed(
            [int(account_id)],
            manifest_file,
            allow_confirmed_calendar_changes,
        )
        cur = self.conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            cur.execute(
                "INSERT OR IGNORE INTO account_categories (name) VALUES (?)",
                (category_name,),
            )
            cur.execute(
                "UPDATE virtual_accounts SET account_type = ? WHERE id = ?",
                (category_name, int(account_id)),
            )
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return bool(cur.rowcount)

    def add_account_tag(self, account_id: int, tag: str) -> bool:
        tag_name = self._normalise_label(tag, "La etiqueta no puede estar vacia")
        self._account_by_id(account_id)
        cur = self.conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            cur.execute("INSERT OR IGNORE INTO account_tags (name) VALUES (?)", (tag_name,))
            cur.execute(
                """
                INSERT OR IGNORE INTO virtual_account_tags (account_id, tag_name)
                VALUES (?, ?)
                """,
                (int(account_id), tag_name),
            )
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return bool(cur.rowcount)

    def remove_account_tag(self, account_id: int, tag: str) -> bool:
        tag_name = self._normalise_label(tag, "La etiqueta no puede estar vacia")
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM virtual_account_tags WHERE account_id = ? AND tag_name = ?",
            (int(account_id), tag_name),
        )
        self.conn.commit()
        return bool(cur.rowcount)

    def tags_for_account(self, account_id: int) -> list[str]:
        self._account_by_id(account_id)
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT tag_name
            FROM virtual_account_tags
            WHERE account_id = ?
            ORDER BY tag_name COLLATE NOCASE
            """,
            (int(account_id),),
        )
        return [row["tag_name"] for row in cur.fetchall()]

    def preview_bulk_update(
        self,
        account_ids: list[int],
        patch: dict[str, PatchValue],
        manifest_file: str | Path | None = None,
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
            "calendar_conflicts": self.calendar_conflicts_for_accounts(
                [row["id"] for row in rows],
                manifest_file,
            ),
            "rows": preview_rows,
        }

    def apply_bulk_update(
        self,
        preview: dict[str, Any],
        allow_confirmed_calendar_changes: bool = False,
    ) -> int:
        account_ids = [int(account_id) for account_id in preview.get("account_ids", [])]
        rows = self._accounts_by_ids(account_ids)
        if self._bulk_revision(rows) != preview.get("preview_revision"):
            raise ValueError("La revision del catalogo cambio; genera un nuevo preview")
        if preview.get("calendar_conflicts") and not allow_confirmed_calendar_changes:
            raise ValueError("Hay cambios con calendario confirmado; requiere confirmacion explicita")

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

    def calendar_conflicts_for_accounts(
        self,
        account_ids: list[int],
        manifest_file: str | Path | None,
    ) -> list[dict[str, Any]]:
        if manifest_file is None or not Path(manifest_file).exists():
            return []
        rows = self._accounts_by_ids(account_ids)
        selected_ids = {int(row["id"]) for row in rows}
        selected_names = {str(row["username"]).casefold() for row in rows}
        conflicts = []
        for entry in load_entries(manifest_file, require_source=False):
            status = str(entry.get("manual_status") or "planned").strip().casefold()
            if status in {"cancelled", "canceled", "deleted", "removed"}:
                continue
            entry_account_id = entry.get("account_id")
            entry_username = str(entry.get("username") or "").casefold()
            if entry_account_id not in selected_ids and entry_username not in selected_names:
                continue
            conflicts.append(
                {
                    "id": entry.get("id"),
                    "username": entry.get("username"),
                    "account_id": entry.get("account_id"),
                    "delivery_kind": entry.get("delivery_kind"),
                    "publication_target": publication_target_for_entry(entry),
                    "day": entry.get("day"),
                    "slot": entry.get("slot"),
                    "tanda": entry.get("tanda"),
                    "manual_status": entry.get("manual_status") or "planned",
                }
            )
        return conflicts

    def _assert_calendar_change_allowed(
        self,
        account_ids: list[int],
        manifest_file: str | Path | None,
        allow_confirmed_calendar_changes: bool,
    ) -> None:
        if allow_confirmed_calendar_changes:
            return
        if self.calendar_conflicts_for_accounts(account_ids, manifest_file):
            raise ValueError("Hay cambios con calendario confirmado; requiere confirmacion explicita")

    @staticmethod
    def _normalise_platform(value: Any) -> str:
        platform = str(value or "").strip().lower()
        return platform or "needs_review"

    @staticmethod
    def _normalise_label(value: Any, empty_message: str) -> str:
        label = str(value or "").strip()
        if not label:
            raise ValueError(empty_message)
        return label

    def _account_by_id(self, account_id: int) -> dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM virtual_accounts WHERE id = ?", (int(account_id),))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Cuenta no encontrada: {account_id}")
        return dict(row)

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
