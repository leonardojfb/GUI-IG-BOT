from database import DatabaseManager
from vault_usage import backfill_vault_provenance, reconcile_calendar_entries


def test_backfill_never_guesses_when_legacy_source_is_not_resolved(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    output = tmp_path / "out.mp4"
    output.write_bytes(b"out")
    db.save_video_transform_log("tandas", "C:/legacy/P1.mp4", output, {"p1_id": "P1"})

    result = backfill_vault_provenance(db)

    assert result["linked"] == 0
    assert result["review"][0]["reason"] == "source_not_resolved"
    db.close()


def test_backfill_rejects_an_unreadable_legacy_overlay_record(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "source.mp4"
    output = tmp_path / "out.mp4"
    source.write_bytes(b"source")
    output.write_bytes(b"out")
    db.upsert_vault_asset(source)
    db.save_video_transform_log(
        "video_editor", source, output, {"overlays": ["legacy overlay without path"]}
    )

    result = backfill_vault_provenance(db)

    assert result["linked"] == 0
    assert result["review"][0]["reason"] == "source_not_resolved"
    db.close()


def test_reconcile_manifest_is_idempotent_and_cancels_replaced_slot(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    entry = {
        "id": "a",
        "account_id": 7,
        "username": "ana",
        "delivery_kind": "normal",
        "day": 1,
        "slot": 1,
        "tanda": "T1",
        "source_path": "C:/out/a.mp4",
        "telegram_filename": "a__TANDA_T1.mp4",
        "transform_log_id": None,
    }

    first = reconcile_calendar_entries(db, [entry], {7}, "normal")
    second = reconcile_calendar_entries(db, [entry], {7}, "normal")
    replacement = {
        **entry,
        "id": "b",
        "source_path": "C:/out/b.mp4",
        "telegram_filename": "b__TANDA_T1.mp4",
    }
    reconcile_calendar_entries(db, [replacement], {7}, "normal")

    assert first["created"] == 1
    assert second["created"] == 0
    assert [row["state"] for row in db.list_content_account_uses(account_id=7)] == [
        "cancelled",
        "scheduled",
    ]
    db.close()


def test_reconcile_projects_one_calendar_entry_for_each_output_root(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"source")
    output.write_bytes(b"output")
    first_root = db.create_content_root("First")
    second_root = db.create_content_root("Second")
    log_id = db.save_video_transform_log("forge", source, output, {})
    db.register_transform_output(log_id, output, [], [first_root["id"], second_root["id"]])
    entry = {
        "account_id": 7,
        "username": "ana",
        "delivery_kind": "normal",
        "day": 1,
        "slot": 1,
        "tanda": "T1",
        "source_path": str(output),
        "telegram_filename": "output__TANDA_T1.mp4",
        "transform_log_id": log_id,
    }

    first = reconcile_calendar_entries(db, [entry], {7}, "normal")
    second = reconcile_calendar_entries(db, [entry], {7}, "normal")

    assert first["created"] == 2
    assert second["created"] == 0
    assert {row["content_root_id"] for row in db.list_content_account_uses(account_id=7)} == {
        first_root["id"],
        second_root["id"],
    }
    db.close()
