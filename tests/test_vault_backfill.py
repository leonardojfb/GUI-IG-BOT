import database

from vault.backfill import backfill_transform_log_references
from vault.storage import VaultStorage


def test_backfill_transform_logs_registers_existing_paths_as_external(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "input.mp4"
        output = tmp_path / "output.mp4"
        missing = tmp_path / "missing.mp4"
        source.write_bytes(b"source")
        output.write_bytes(b"output")
        db.save_video_transform_log("forge", source, output, {"ok": True})
        db.save_video_transform_log("forge", missing, tmp_path / "missing-out.mp4", {})
        storage = VaultStorage(db, tmp_path / "vault")

        report = backfill_transform_log_references(db, storage)

        assert report["registered"] == 2
        assert report["skipped_missing"] == 2
        assert report["copied_bytes"] == 0
        rows = storage.list_assets()
        assert {row["display_name"] for row in rows} == {"input.mp4", "output.mp4"}
        for asset in rows:
            assert storage.locations_for_asset(asset["id"])[0]["managed"] == 0
    finally:
        db.close()


def test_backfill_is_idempotent_and_reports_existing_locations(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "input.mp4"
        output = tmp_path / "output.mp4"
        source.write_bytes(b"same")
        output.write_bytes(b"same")
        db.save_video_transform_log("forge", source, output, {})
        storage = VaultStorage(db, tmp_path / "vault")

        first = backfill_transform_log_references(db, storage)
        second = backfill_transform_log_references(db, storage)

        assert first["registered"] == 2
        assert second["registered"] == 0
        assert second["already_registered"] == 2
        assert len(storage.list_assets()) == 1
        assert len(storage.locations_for_asset(storage.list_assets()[0]["id"])) == 2
    finally:
        db.close()
