import json
import sqlite3

import pytest

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
    assert {"vault_asset_id", "variant_signature", "output_vault_asset_id"}.issubset(columns)
    assert db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='vault_assets'"
    ).fetchone()
    assert db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='vault_asset_links'"
    ).fetchone()
    assert db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_video_transform_logs_vault_variant'"
    ).fetchone()
    db.close()


def test_register_transform_output_links_two_parents_and_a_root(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    p1, p2, out = [tmp_path / name for name in ("p1.mp4", "p2.mp4", "mix.mp4")]
    p1.write_bytes(b"p1")
    p2.write_bytes(b"p2")
    out.write_bytes(b"mix")
    a1, a2 = db.upsert_vault_asset(p1), db.upsert_vault_asset(p2)
    root = db.create_content_root("Mix family")
    log_id = db.save_video_transform_log(
        "tandas", p1, out, {"p1_path": str(p1), "p2_path": str(p2)}
    )

    output = db.register_transform_output(
        log_id, out, [(a1["id"], "p1"), (a2["id"], "p2")], [root["id"]]
    )

    assert {link["relation_kind"] for link in db.list_vault_asset_links(output["id"])} == {"p1", "p2"}
    assert db.list_root_assets(root["id"])[0]["role"] == "tanda_output"
    assert db.list_video_transform_logs()[0]["output_vault_asset_id"] == output["id"]
    assert db.list_vault_asset_history(output["id"])[0]["id"] == log_id
    db.close()


def test_register_transform_output_rejects_unknown_root_without_partial_records(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    parent = tmp_path / "parent.mp4"
    output_path = tmp_path / "output.mp4"
    parent.write_bytes(b"parent")
    output_path.write_bytes(b"output")
    parent_asset = db.upsert_vault_asset(parent)
    log_id = db.save_video_transform_log("forge", parent, output_path, {})

    with pytest.raises(ValueError, match="familia"):
        db.register_transform_output(
            log_id,
            output_path,
            [(parent_asset["id"], "source")],
            [99999],
        )

    log = db.list_video_transform_logs()[0]
    assert log["output_vault_asset_id"] is None
    assert db.list_vault_asset_links(parent_asset["id"]) == []
    assert db.list_vault_assets(search="output.mp4") == []
    db.close()


def test_register_transform_output_rejects_unknown_log_and_self_parent(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    asset = db.upsert_vault_asset(source)

    with pytest.raises(ValueError, match="No existe"):
        db.register_transform_output(99999, source, [], [])

    log_id = db.save_video_transform_log("forge", source, tmp_path / "same.mp4", {})
    same_output = tmp_path / "same.mp4"
    same_output.write_bytes(b"source")
    with pytest.raises(ValueError, match="padre"):
        db.register_transform_output(log_id, same_output, [(asset["id"], "source")])

    assert db.list_video_transform_logs()[0]["output_vault_asset_id"] is None
    db.close()


def test_manual_vault_asset_links_are_idempotent_but_keep_distinct_logs(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    parent_path = tmp_path / "parent.mp4"
    child_path = tmp_path / "child.mp4"
    parent_path.write_bytes(b"parent")
    child_path.write_bytes(b"child")
    parent = db.upsert_vault_asset(parent_path)
    child = db.upsert_vault_asset(child_path)

    db.link_vault_assets(parent["id"], child["id"], "derived")
    db.link_vault_assets(parent["id"], child["id"], "derived")
    db.link_vault_assets(parent["id"], child["id"], "derived", transform_log_id=101)
    db.link_vault_assets(parent["id"], child["id"], "derived", transform_log_id=102)

    links = db.list_vault_asset_links(child["id"])
    assert len(links) == 3
    assert sum(link["transform_log_id"] is None for link in links) == 1
    assert {link["transform_log_id"] for link in links if link["transform_log_id"] is not None} == {101, 102}
    db.close()


def test_existing_database_dedupes_nullable_vault_asset_links_before_unique_index(tmp_path):
    db_path = tmp_path / "organizador.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE vault_asset_links (
            parent_asset_id INTEGER NOT NULL,
            child_asset_id INTEGER NOT NULL,
            relation_kind TEXT NOT NULL,
            transform_log_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (parent_asset_id, child_asset_id, relation_kind, transform_log_id)
        );
        INSERT INTO vault_asset_links (parent_asset_id, child_asset_id, relation_kind, transform_log_id)
        VALUES (1, 2, 'derived', NULL), (1, 2, 'derived', NULL);
        """
    )
    conn.close()

    db = DatabaseManager(str(db_path))

    assert db.conn.execute(
        "SELECT COUNT(*) FROM vault_asset_links WHERE transform_log_id IS NULL"
    ).fetchone()[0] == 1
    assert db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_vault_asset_links_identity'"
    ).fetchone()
    db.close()
