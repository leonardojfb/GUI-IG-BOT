import sqlite3
from pathlib import Path

import pytest

from calendar_manifest import _write_payload_version
from shared_planner_apply import preview_shared_manifest_apply


def _manifest(path, entries=None, version=2):
    _write_payload_version(path, list(entries or []), version)


def _preview(source_id="T1:clip.mp4", username="alice"):
    return {
        "plan_version": 1,
        "status": "ready",
        "seed": 7,
        "scope": {"lane": "reel", "placement": "feed", "method": "telegram"},
        "assignments": [{
            "source_id": source_id,
            "source_path": str(Path(__file__).resolve()),
            "display_filename": "clip.mp4",
            "tanda": "T1",
            "media_class": "video",
            "username": username,
            "account_id": 3,
            "day": 1,
            "slot": 1,
            "lane": "reel",
            "placement": "feed",
            "method": "telegram",
        }],
    }


def test_preview_shared_manifest_apply_builds_guarded_v2_preview(tmp_path):
    path = tmp_path / "calendar_manifest.json"
    _manifest(path)

    result = preview_shared_manifest_apply(path, _preview())

    assert result["operation"] == "replace_entries_v2"
    assert result["summary"]["added"] == 1
    assert result["added_entries"][0]["manifest_entry_version"] == 2
    assert result["added_entries"][0]["publication_target"] == "instagram_reel"


def test_apply_preview_refuses_partial_or_v1(tmp_path):
    path = tmp_path / "calendar_manifest.json"
    _manifest(path)
    blocked = _preview()
    blocked["status"] = "blocked"

    with pytest.raises(ValueError, match="no aplicable"):
        preview_shared_manifest_apply(path, blocked)

    _manifest(path, version=1)
    with pytest.raises(ValueError, match="version 2"):
        preview_shared_manifest_apply(path, _preview())


def test_reservations_are_atomic_and_expire_without_import_side_effects(tmp_path):
    from planner_reservations import (
        ensure_reservation_schema,
        inspect_reservations,
        release_reservation,
        reserve_shared_preview,
    )

    conn = sqlite3.connect(":memory:")
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='planner_reservations'").fetchone() is None
    ensure_reservation_schema(conn)
    preview = _preview()
    preview["assignments"].append(dict(preview["assignments"][0], source_id="T1:clip-2.mp4"))

    first = reserve_shared_preview(conn, preview, owner="gui-a", now=100, ttl_seconds=10)
    assert first["status"] == "reserved"
    assert len(inspect_reservations(conn, now=105)) == 2

    conflict = reserve_shared_preview(conn, preview, owner="gui-b", now=105, ttl_seconds=10)
    assert conflict["status"] == "conflict"
    assert conflict["conflicts"][0]["source_id"] == "T1:clip.mp4"
    assert len(inspect_reservations(conn, now=105)) == 2

    expired = reserve_shared_preview(conn, preview, owner="gui-b", now=111, ttl_seconds=10)
    assert expired["status"] == "reserved"
    assert release_reservation(conn, expired["reservation_id"], owner="gui-b") is True
    assert inspect_reservations(conn, now=111) == []


def test_reservation_schema_migrates_legacy_rows_to_copy_one():
    from planner_reservations import ensure_reservation_schema, inspect_reservations, reserve_shared_preview

    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE planner_reservations (
        reservation_id TEXT NOT NULL, owner TEXT NOT NULL, source_id TEXT NOT NULL,
        username TEXT NOT NULL, lane TEXT NOT NULL, expires_at INTEGER NOT NULL,
        created_at INTEGER NOT NULL, PRIMARY KEY(reservation_id, source_id, username, lane),
        UNIQUE(source_id, username, lane)
    )""")
    conn.execute("INSERT INTO planner_reservations VALUES (?, ?, ?, ?, ?, ?, ?)", ("old", "legacy", "source", "alice", "lane", 999, 1))

    ensure_reservation_schema(conn)
    rows = inspect_reservations(conn, now=100)
    assert rows[0]["copy_number"] == 1
    preview = {"status": "ready", "scope": {"lane": "lane"}, "assignments": [{"source_id": "source", "username": "alice", "lane": "lane", "copy_number": 2}]}
    result = reserve_shared_preview(conn, preview, owner="new", now=100)
    assert result["status"] == "reserved"
