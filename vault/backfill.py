from __future__ import annotations

from pathlib import Path
from typing import Any


def backfill_transform_log_references(db, storage) -> dict[str, Any]:
    """Register historical transform paths as external Vault locations only."""
    report = {
        "registered": 0,
        "already_registered": 0,
        "skipped_missing": 0,
        "copied_bytes": 0,
        "missing": [],
    }
    for path in _iter_transform_paths(db):
        candidate = Path(path)
        if not candidate.is_file():
            report["skipped_missing"] += 1
            report["missing"].append(str(candidate))
            continue
        before = _location_count(db)
        storage.register_external(candidate)
        after = _location_count(db)
        if after > before:
            report["registered"] += 1
        else:
            report["already_registered"] += 1
    return report


def _iter_transform_paths(db):
    cur = db.conn.cursor()
    cur.execute(
        """
        SELECT source_path, output_path
        FROM video_transform_logs
        ORDER BY id
        """
    )
    for row in cur.fetchall():
        for field in ("source_path", "output_path"):
            value = str(row[field] or "").strip()
            if value:
                yield value


def _location_count(db) -> int:
    cur = db.conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM vault_locations")
    return int(cur.fetchone()["total"])
