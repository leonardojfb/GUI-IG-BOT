"""Projection of calendar and Telegram activity into operational content uses."""
from __future__ import annotations

import hashlib
import json
import os


def calendar_entry_key(entry: dict) -> str:
    fields = {
        "account_id": entry.get("account_id"),
        "delivery_kind": entry.get("delivery_kind"),
        "day": int(entry.get("day", 0)),
        "slot": int(entry.get("slot", 0)),
        "tanda": entry.get("tanda", ""),
        "source_path": os.path.abspath(entry.get("source_path", "")),
        "telegram_filename": entry.get("telegram_filename", ""),
    }
    encoded = json.dumps(fields, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _entry_context(db, entry: dict) -> tuple[int | None, list[dict]]:
    transform_log_id = entry.get("transform_log_id")
    if transform_log_id is None:
        return None, []
    context = db.get_transform_output_context(transform_log_id)
    return context["vault_asset_id"], context["roots"]


def _root_ids(roots: list[dict]) -> list[int | None]:
    return [int(root["id"]) for root in roots] or [None]


def reconcile_calendar_entries(db, entries, account_ids, delivery_kind):
    account_ids = {int(account_id) for account_id in account_ids}
    active_pairs = set()
    created = 0
    updated = 0
    for entry in entries:
        if entry.get("delivery_kind") != delivery_kind:
            continue
        account_id = entry.get("account_id")
        if account_id is None or int(account_id) not in account_ids:
            continue
        key = calendar_entry_key(entry)
        vault_asset_id, roots = _entry_context(db, entry)
        for root_id in _root_ids(roots):
            result = db.upsert_content_account_use(
                {
                    "calendar_entry_key": key,
                    "content_root_id": root_id,
                    "vault_asset_id": vault_asset_id,
                    "account_id": account_id,
                    "username": entry.get("username"),
                    "delivery_kind": delivery_kind,
                    "tanda_name": entry.get("tanda"),
                    "transform_log_id": entry.get("transform_log_id"),
                    "day": entry.get("day"),
                    "slot": entry.get("slot"),
                    "state": "scheduled",
                }
            )
            active_pairs.add((key, root_id))
            if result["created"]:
                created += 1
            else:
                updated += 1
    cancelled = db.cancel_scoped_content_uses(account_ids, delivery_kind, active_pairs)
    return {"created": created, "updated": updated, "cancelled": cancelled}


def mark_manifest_delivery(db, entry, state, failure_reason=None):
    if state not in {"sent_telegram", "failed", "published_confirmed"}:
        raise ValueError("El estado de entrega no es valido.")
    key = calendar_entry_key(entry)
    _, roots = _entry_context(db, entry)
    rows = []
    for root_id in _root_ids(roots):
        row = db.update_content_account_use_state(key, root_id, state, failure_reason)
        if row:
            rows.append(row)
    return rows
