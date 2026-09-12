import database

from vault.backfill import backfill_transform_log_references
from vault.migration import migrate_external_locations, plan_external_migration
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


def test_external_migration_plan_estimates_bytes_without_copying(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "external.mp4"
        source.write_bytes(b"external")
        storage = VaultStorage(db, tmp_path / "vault")
        location = storage.register_external(source)

        plan = plan_external_migration(db)

        assert plan["total_locations"] == 1
        assert plan["copy_bytes"] == source.stat().st_size
        assert plan["locations"][0]["location_id"] == location["location_id"]
        assert plan["locations"][0]["path"] == str(source)
        assert not list((tmp_path / "vault").rglob("*.mp4"))
    finally:
        db.close()


def test_external_migration_requires_explicit_location_ids_and_preserves_external_history(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "external.mp4"
        source.write_bytes(b"external")
        storage = VaultStorage(db, tmp_path / "vault")
        location = storage.register_external(source)

        empty = migrate_external_locations(db, storage, location_ids=[])
        migrated = migrate_external_locations(db, storage, location_ids=[location["location_id"]])

        assert empty["migrated"] == 0
        assert migrated["migrated"] == 1
        locations = storage.locations_for_asset(location["asset_id"])
        assert {bool(row["managed"]) for row in locations} == {False, True}
        assert source.exists()
    finally:
        db.close()
