import database
from calendar_manifest import build_entry
from vault.calendar_usage import record_calendar_manifest_usages
from vault.lineage import VaultLineage
from vault.storage import VaultStorage


def test_calendar_usage_records_output_asset_from_transform_log_once(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "source.mp4"
        output = tmp_path / "output.mp4"
        source.write_bytes(b"source")
        output.write_bytes(b"output")
        log_id = db.save_video_transform_log("forge", source, output, {})
        storage = VaultStorage(db, tmp_path / "vault")
        output_asset = storage.import_managed(output)["asset_id"]
        db.conn.execute(
            "UPDATE video_transform_logs SET output_vault_asset_id = ? WHERE id = ?",
            (output_asset, log_id),
        )
        db.conn.commit()
        entry = build_entry(
            "alice",
            1,
            "normal",
            2,
            3,
            "T",
            str(output),
            "output__TANDA_T__ACC_1__D02__S03.mp4",
            transform_log_id=log_id,
            created_at="2026-09-13T00:00:00Z",
        )

        first = record_calendar_manifest_usages(db, [entry])
        second = record_calendar_manifest_usages(db, [entry])

        assert first["recorded"] == 1
        assert second["recorded"] == 0
        assert first["skipped"] == 0
        usages = VaultLineage(db).usages_for_asset(output_asset)
        assert [(row["usage_kind"], row["external_ref"]) for row in usages] == [
            ("calendar", entry["id"])
        ]
    finally:
        db.close()


def test_calendar_usage_falls_back_to_vault_location_path(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "scheduled.mp4"
        source.write_bytes(b"scheduled")
        asset = VaultStorage(db, tmp_path / "vault").register_external(source)
        entry = build_entry(
            "bob",
            2,
            "trial",
            1,
            1,
            "TRIAL",
            str(source),
            "scheduled__TANDA_TRIAL__ACC_2__D01__S01.mp4",
            created_at="2026-09-13T00:00:00Z",
        )

        summary = record_calendar_manifest_usages(db, [entry])

        assert summary["recorded"] == 1
        assert VaultLineage(db).usages_for_asset(asset["asset_id"])[0]["external_ref"] == entry["id"]
    finally:
        db.close()


def test_calendar_usage_skips_entries_without_resolvable_asset(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "untracked.mp4"
        source.write_bytes(b"untracked")
        entry = build_entry("alice", 1, "normal", 1, 1, "T", str(source), "untracked.mp4")

        summary = record_calendar_manifest_usages(db, [entry])

        assert summary["recorded"] == 0
        assert summary["skipped"] == 1
        assert summary["rows"][0]["status"] == "missing_asset"
    finally:
        db.close()
