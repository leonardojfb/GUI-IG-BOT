import json

from database import DatabaseManager


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
    rows = db.list_video_transform_logs(limit=10)
    assert rows[0]["id"] == log_id
    assert rows[0]["process_kind"] == "forge"
    assert rows[0]["tanda_name"] == "TANDA_A"
    assert json.loads(rows[0]["details_json"])["speed"] == 1.003
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
