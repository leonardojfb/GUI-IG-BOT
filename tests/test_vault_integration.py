import sqlite3

import database
from vault.integration import register_transform_output, register_transform_output_if_possible
from vault.storage import VaultStorage


def test_register_transform_output_imports_output_managed_and_links_log(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "input.mp4"
        output = tmp_path / "output.mp4"
        source.write_bytes(b"source")
        output.write_bytes(b"output")
        log_id = db.save_video_transform_log("forge", source, output, {"step": "render"})
        storage = VaultStorage(db, tmp_path / "vault")

        result = register_transform_output(db, storage, log_id)

        [log] = db.list_video_transform_logs()
        assert log["output_vault_asset_id"] == result["asset_id"]
        assert result["managed"] is True
        assert result["path"].startswith(str(tmp_path / "vault"))
        output.unlink()
        assert storage.verify_location(result["location_id"])["status"] == "ok"
    finally:
        db.close()


def test_register_transform_output_is_idempotent_for_same_log(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "input.mp4"
        output = tmp_path / "output.mp4"
        source.write_bytes(b"source")
        output.write_bytes(b"output")
        log_id = db.save_video_transform_log("editor", source, output, {})
        storage = VaultStorage(db, tmp_path / "vault")

        first = register_transform_output(db, storage, log_id)
        second = register_transform_output(db, storage, log_id)

        assert first["asset_id"] == second["asset_id"]
        assert len(storage.locations_for_asset(first["asset_id"])) == 1
    finally:
        db.close()


def test_register_transform_output_if_possible_reports_error_without_raising(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "input.mp4"
        output = tmp_path / "missing-output.mp4"
        source.write_bytes(b"source")
        log_id = db.save_video_transform_log("editor", source, output, {})
        storage = VaultStorage(db, tmp_path / "vault")

        result = register_transform_output_if_possible(db, storage, log_id)

        assert result["status"] == "error"
        assert "missing-output.mp4" in result["error"]
        [log] = db.list_video_transform_logs()
        assert log["output_vault_asset_id"] is None
    finally:
        db.close()


def test_existing_database_migrates_transform_log_vault_columns(tmp_path):
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

    db = database.DatabaseManager(str(db_path))
    try:
        columns = {
            row["name"]
            for row in db.conn.execute("PRAGMA table_info(video_transform_logs)").fetchall()
        }

        assert {"source_vault_asset_id", "output_vault_asset_id"}.issubset(columns)
    finally:
        db.close()


def test_gui_transform_logging_registers_output_to_vault():
    source = open("gui_premium_v7.py", encoding="utf-8").read()
    vault_helper = source[source.index("def _register_transform_output_if_possible_to_vault("):source.index("def _format_transform_summary")]

    assert source.count("_register_transform_output_if_possible_to_vault(") >= 4
    assert "VaultStorage" in vault_helper


def test_tandas_transform_logging_registers_output_to_vault():
    source = open("videos.py", encoding="utf-8").read()
    helper = source[source.index("def _register_transform_output_if_possible_to_vault("):source.index("def _ffmpeg_tool_command")]
    body = source[source.index("def process_tandas("):source.index("def process_mix_rules")]

    assert "_register_transform_output_if_possible_to_vault(db, log_id)" in body
    assert "VaultStorage" in helper
