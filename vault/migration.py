from __future__ import annotations

from pathlib import Path
from typing import Any


def plan_external_migration(db) -> dict[str, Any]:
    cur = db.conn.cursor()
    cur.execute(
        """
        SELECT l.id AS location_id, l.asset_id, l.path, a.sha256, a.size_bytes, a.display_name
        FROM vault_locations l
        JOIN vault_assets a ON a.id = l.asset_id
        WHERE l.managed = 0
        ORDER BY l.id
        """
    )
    locations = []
    missing = []
    copy_bytes = 0
    for row in cur.fetchall():
        item = dict(row)
        path = Path(item["path"])
        if path.is_file():
            item["status"] = "ready"
            item["copy_bytes"] = path.stat().st_size
            copy_bytes += int(item["copy_bytes"])
            locations.append(item)
        else:
            item["status"] = "missing"
            item["copy_bytes"] = 0
            missing.append(item)
    return {
        "total_locations": len(locations),
        "copy_bytes": copy_bytes,
        "locations": locations,
        "missing": missing,
    }


def migrate_external_locations(db, storage, location_ids: list[int]) -> dict[str, Any]:
    selected = {int(location_id) for location_id in location_ids}
    if not selected:
        return {"migrated": 0, "skipped_missing": 0, "failed": 0, "locations": []}
    plan = plan_external_migration(db)
    rows = [row for row in plan["locations"] if int(row["location_id"]) in selected]
    missing = [row for row in plan["missing"] if int(row["location_id"]) in selected]
    results = []
    failed = 0
    for row in rows:
        try:
            managed = storage.import_managed(row["path"])
        except Exception as exc:
            failed += 1
            results.append(
                {
                    "location_id": row["location_id"],
                    "status": "failed",
                    "error": str(exc),
                }
            )
            continue
        results.append(
            {
                "location_id": row["location_id"],
                "asset_id": managed["asset_id"],
                "managed_location_id": managed["location_id"],
                "status": "managed",
            }
        )
    return {
        "migrated": len([row for row in results if row["status"] == "managed"]),
        "skipped_missing": len(missing),
        "failed": failed,
        "locations": results,
    }
