import json

from database import DatabaseManager
from video_editor import describe_overlay_log


def test_describe_overlay_log_keeps_effective_overlay_values():
    overlays = [
        {
            "photo_path": "C:/imgs/a.png",
            "start_frame": 12,
            "end_frame": 36,
            "position": "custom",
            "x": 120,
            "y": 40,
            "size": 0.25,
            "opacity": 0.8,
        }
    ]

    assert describe_overlay_log(overlays) == [
        {
            "photo_path": "C:/imgs/a.png",
            "start_frame": 12,
            "end_frame": 36,
            "start_time": None,
            "end_time": None,
            "position": "custom",
            "x": 120,
            "y": 40,
            "size": 0.25,
            "opacity": 0.8,
        }
    ]


def test_video_editor_completion_can_persist_overlay_details(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    src = tmp_path / "src.mp4"
    out = tmp_path / "out.mp4"
    src.write_bytes(b"src")
    out.write_bytes(b"out")

    log_id = db.save_video_transform_log(
        "video_editor",
        str(src),
        str(out),
        {"overlays": describe_overlay_log([{"photo_path": "x.png", "start_frame": 1, "end_frame": 2}])},
    )

    row = db.list_video_transform_logs()[0]
    assert row["id"] == log_id
    assert json.loads(row["details_json"])["overlays"][0]["photo_path"] == "x.png"
    db.close()


def test_ensure_vault_asset_reuses_an_asset_found_by_path(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")

    created = db.ensure_vault_asset(source)

    assert db.find_vault_asset_by_path(source)["id"] == created["id"]
    assert db.ensure_vault_asset(source)["id"] == created["id"]
    db.close()
