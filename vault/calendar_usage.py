from __future__ import annotations

from pathlib import Path
from typing import Any

from vault.lineage import VaultLineage


def record_calendar_manifest_usages(db, entries: list[dict[str, Any]]) -> dict[str, Any]:
    lineage = VaultLineage(db)
    rows = []
    recorded = 0
    skipped = 0
    for entry in entries:
        asset_id = _asset_id_for_entry(db, entry)
        if asset_id is None:
            skipped += 1
            rows.append({"entry_id": entry.get("id"), "status": "missing_asset"})
            continue
        external_ref = str(entry.get("id") or "").strip()
        if not external_ref:
            skipped += 1
            rows.append({"entry_id": entry.get("id"), "asset_id": asset_id, "status": "missing_entry_id"})
            continue
        before = len(lineage.usages_for_asset(asset_id))
        usage_id = lineage.record_usage_once(
            asset_id,
            "calendar",
            external_ref,
            {
                "username": entry.get("username"),
                "account_id": entry.get("account_id"),
                "delivery_kind": entry.get("delivery_kind"),
                "publication_target": entry.get("publication_target"),
                "day": entry.get("day"),
                "slot": entry.get("slot"),
                "tanda": entry.get("tanda"),
                "telegram_filename": entry.get("telegram_filename"),
                "transform_log_id": entry.get("transform_log_id"),
            },
        )
        after = len(lineage.usages_for_asset(asset_id))
        inserted = after > before
        recorded += int(inserted)
        rows.append(
            {
                "entry_id": external_ref,
                "asset_id": asset_id,
                "usage_id": usage_id,
                "status": "recorded" if inserted else "existing",
            }
        )
    return {"recorded": recorded, "skipped": skipped, "rows": rows}


def _asset_id_for_entry(db, entry: dict[str, Any]) -> int | None:
    transform_log_id = entry.get("transform_log_id")
    if transform_log_id is not None:
        found = _asset_id_from_transform_log(db, int(transform_log_id))
        if found is not None:
            return found
    source_path = entry.get("source_path")
    if not source_path:
        return None
    return _asset_id_from_location(db, source_path)


def _asset_id_from_transform_log(db, transform_log_id: int) -> int | None:
    cur = db.conn.cursor()
    cur.execute(
        """
        SELECT output_vault_asset_id, source_vault_asset_id
        FROM video_transform_logs
        WHERE id = ?
        """,
        (int(transform_log_id),),
    )
    row = cur.fetchone()
    if not row:
        return None
    return row["output_vault_asset_id"] or row["source_vault_asset_id"]


def _asset_id_from_location(db, source_path: str) -> int | None:
    candidates = [str(source_path)]
    try:
        resolved = str(Path(source_path).resolve())
        if resolved not in candidates:
            candidates.append(resolved)
    except OSError:
        pass
    cur = db.conn.cursor()
    cur.execute(
        f"""
        SELECT asset_id
        FROM vault_locations
        WHERE path IN ({','.join('?' for _ in candidates)})
        ORDER BY managed DESC, id
        LIMIT 1
        """,
        candidates,
    )
    row = cur.fetchone()
    return int(row["asset_id"]) if row else None
