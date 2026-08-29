import json
import sqlite3

from database import DatabaseManager


def test_upsert_vault_asset_dedupes_by_hash_and_updates_metadata(tmp_path):
    from vault import hash_asset

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-bytes")
    db = DatabaseManager(str(tmp_path / "organizador.db"))

    first = db.upsert_vault_asset(str(source), tags=["main"])
    second = db.upsert_vault_asset(str(source), display_name="Renamed", tags=["forge"])

    assert second["id"] == first["id"]
    assert second["asset_hash"] == hash_asset(str(source))
    assert second["display_name"] == "Renamed"
    assert json.loads(second["tags_json"]) == ["forge"]
    assert len(db.list_vault_assets()) == 1
    db.close()


def test_transform_log_links_to_vault_asset_and_variant_signature(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"in")
    output.write_bytes(b"out")
    asset = db.upsert_vault_asset(str(source))

    log_id = db.save_video_transform_log(
        "forge",
        str(source),
        str(output),
        {"speed": 1.0},
        vault_asset_id=asset["id"],
        variant_signature="sig-123",
    )

    rows = db.list_video_transform_logs(limit=10)
    assert rows[0]["id"] == log_id
    assert rows[0]["vault_asset_id"] == asset["id"]
    assert rows[0]["variant_signature"] == "sig-123"
    assert db.used_variant_signatures(asset["id"], "forge") == {"sig-123"}
    assert db.list_vault_asset_history(asset["id"])[0]["id"] == log_id
    db.close()


def test_existing_database_migrates_vault_columns_before_index_creation(tmp_path):
    db_path = tmp_path / "organizador.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE video_transform_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process_kind TEXT NOT NULL,
            source_path TEXT NOT NULL,
            output_path TEXT NOT NULL UNIQUE,
            output_filename TEXT NOT NULL,
            tanda_name TEXT,
            source_identity TEXT,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.close()

    db = DatabaseManager(str(db_path))

    columns = {
        row["name"]
        for row in db.conn.execute("PRAGMA table_info(video_transform_logs)").fetchall()
    }
    assert {"vault_asset_id", "variant_signature"}.issubset(columns)
    assert db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='vault_assets'"
    ).fetchone()
    assert db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_video_transform_logs_vault_variant'"
    ).fetchone()
    db.close()
