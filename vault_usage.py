"""Projection of calendar and Telegram activity into operational content uses."""
from __future__ import annotations

import hashlib
import json
import os

from vault import hash_asset


def _provenance_review(log, reason):
    return {
        "transform_log_id": int(log["id"]),
        "path": log["output_path"],
        "reason": reason,
    }


def _legacy_parent_paths(log, details):
    process_kind = log["process_kind"]
    if process_kind == "tandas":
        return [(details.get("p1_path"), "p1"), (details.get("p2_path"), "p2")]
    if process_kind == "video_editor":
        parents = [(details.get("input_path") or log["source_path"], "source")]
        overlays = details.get("overlays", [])
        if not isinstance(overlays, list):
            return []
        if any(not isinstance(overlay, dict) for overlay in overlays):
            return []
        parents.extend((overlay.get("photo_path"), "overlay") for overlay in overlays)
        return parents
    return [(log["source_path"], "source")]


def backfill_vault_provenance(db):
    """Link only legacy transform records whose output and parents are exact facts."""
    logs = db.conn.execute(
        """
        SELECT id, process_kind, source_path, output_path, details_json
        FROM video_transform_logs
        WHERE output_vault_asset_id IS NULL
        ORDER BY id ASC
        """
    ).fetchall()
    linked = 0
    skipped = 0
    review = []

    for row in logs:
        log = dict(row)
        output_path = log["output_path"]
        try:
            if not os.path.isfile(output_path):
                raise OSError("output_missing")
            hash_asset(output_path)
        except OSError:
            skipped += 1
            review.append(_provenance_review(log, "output_not_readable"))
            continue

        try:
            details = json.loads(log["details_json"] or "{}")
        except json.JSONDecodeError:
            skipped += 1
            review.append(_provenance_review(log, "details_not_readable"))
            continue
        if not isinstance(details, dict):
            skipped += 1
            review.append(_provenance_review(log, "details_not_readable"))
            continue

        expected_parents = _legacy_parent_paths(log, details)
        parent_paths = [path for path, _kind in expected_parents]
        if (
            not expected_parents
            or any(not isinstance(path, str) or not path.strip() for path in parent_paths)
            or len({os.path.abspath(path) for path in parent_paths}) != len(parent_paths)
        ):
            skipped += 1
            review.append(_provenance_review(log, "source_not_resolved"))
            continue

        parent_links = []
        for path, relation_kind in expected_parents:
            asset = db.find_vault_asset_by_path(path)
            if asset is None:
                parent_links = []
                break
            parent_links.append((asset["id"], relation_kind))
        if not parent_links:
            skipped += 1
            review.append(_provenance_review(log, "source_not_resolved"))
            continue

        db.register_transform_output(log["id"], output_path, parent_links)
        linked += 1

    return {"linked": linked, "review": review, "skipped": skipped}


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
