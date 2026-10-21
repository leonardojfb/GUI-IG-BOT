import json

from database import DatabaseManager, normalize_video_transform_source_identity


def test_forge_copy_identity_collapses_to_common_source_hash():
    source_hash = "a" * 64
    assert normalize_video_transform_source_identity("forge", source_hash + "_17") == source_hash
    assert normalize_video_transform_source_identity("forge_trial", source_hash + "_2") == source_hash
    assert normalize_video_transform_source_identity("tandas", source_hash + "_2") == source_hash + "_2"


def test_save_video_transform_log_round_trips_json(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"in")
    output.write_bytes(b"out")

    log_id = db.save_video_transform_log(
        "forge",
        str(source),
        str(output),
        {"rotate_deg": 0.8, "crop_px": 2, "speed": 1.003},
        tanda_name="TANDA_A",
        source_identity="hash123",
    )

    assert db.get_video_transform_log_id(str(output)) == log_id
    assert db.get_video_transform_source_identity(str(output)) == "hash123"
    assert db.get_video_transform_source_identity_by_id(log_id) == "hash123"
    rows = db.list_video_transform_logs(limit=10)
    assert rows[0]["id"] == log_id
    assert rows[0]["process_kind"] == "forge"
    assert rows[0]["tanda_name"] == "TANDA_A"
    assert json.loads(rows[0]["details_json"])["speed"] == 1.003
    db.close()


def test_forge_log_lookup_accepts_windows_folder_case_change(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    folder = tmp_path / "TALKING"
    folder.mkdir()
    source = tmp_path / "source.mov"
    output = folder / "clip__c01.mov"
    source.write_bytes(b"source")
    output.write_bytes(b"copy")
    origin = "a" * 64
    log_id = db.save_video_transform_log(
        "forge", str(source), str(output), {},
        tanda_name="TALKING", source_identity=origin,
    )
    calendar_path = str(output).replace("TALKING", "Talking")

    assert db.get_video_transform_log_id(calendar_path) == log_id
    assert db.get_video_transform_source_identity(calendar_path) == origin
    db.close()


def test_save_video_transform_log_updates_same_output_path(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"in")
    output.write_bytes(b"out")

    first_id = db.save_video_transform_log("forge", str(source), str(output), {"rotate_deg": 0.1})
    second_id = db.save_video_transform_log("forge", str(source), str(output), {"rotate_deg": 0.2})

    assert second_id == first_id
    rows = db.list_video_transform_logs(limit=10)
    assert json.loads(rows[0]["details_json"])["rotate_deg"] == 0.2
    db.close()


def test_normalize_forge_transform_source_identities_persists_base_hash(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source_hash = "b" * 64
    log_id = db.save_video_transform_log(
        "forge", str(tmp_path / "source.mp4"), str(tmp_path / "copy.mov"), {},
        source_identity=source_hash + "_9",
    )

    assert db.normalize_forge_transform_source_identities(apply=False) == 1
    raw = db.conn.execute(
        "SELECT source_identity FROM video_transform_logs WHERE id=?", (log_id,)
    ).fetchone()[0]
    assert raw == source_hash + "_9"

    assert db.normalize_forge_transform_source_identities() == 1
    stored = db.conn.execute(
        "SELECT source_identity FROM video_transform_logs WHERE id=?", (log_id,)
    ).fetchone()[0]
    assert stored == source_hash
    assert db.get_video_transform_source_identity_by_id(log_id) == source_hash
    db.close()


def test_missing_forge_copy_inherits_only_unambiguous_sibling_origin(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    folder = tmp_path / "WAN CLON MAIN"
    folder.mkdir()
    source = tmp_path / "source.mov"
    first = folder / "clip__c01.mov"
    missing = folder / "clip__c02.mov"
    db.save_video_transform_log(
        "forge", str(source), str(first), {},
        tanda_name="WAN CLON MAIN", source_identity="a" * 64 + "_1",
    )
    assert db.get_video_transform_source_identity(str(missing)) == "a" * 64

    conflicting = folder / "clip__c03.mov"
    db.save_video_transform_log(
        "forge", str(source), str(conflicting), {},
        tanda_name="WAN CLON MAIN", source_identity="b" * 64 + "_3",
    )
    assert db.get_video_transform_source_identity(str(missing)) is None
    db.close()


def test_missing_forge_copy_finds_sibling_when_folder_case_changed(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    folder = tmp_path / "TALKING"
    folder.mkdir()
    source = tmp_path / "source.mov"
    first = folder / "clip__c01.mov"
    db.save_video_transform_log(
        "forge", str(source), str(first), {},
        tanda_name="TALKING", source_identity="b" * 64,
    )

    missing = str(folder / "clip__c02.mov").replace("TALKING", "Talking")
    assert db.get_video_transform_source_identity(missing) == "b" * 64
    db.close()
