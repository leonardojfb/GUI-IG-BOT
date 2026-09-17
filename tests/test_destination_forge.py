import database

from destination_forge import (
    build_destination_forge_job_spec,
    parse_destination_specs,
    preview_destination_forge,
    reconcile_destination_reservation,
    reserve_destination_preview,
    submit_destination_forge_job,
)


def test_destination_specs_parse_explicit_manual_fallback():
    specs = parse_destination_specs("alice|reel|instagram_reel|2\n bob | story | instagram_story | 1")
    assert specs == [
        {"username": "alice", "container": "reel", "profile": "instagram_reel", "copies": 2},
        {"username": "bob", "container": "story", "profile": "instagram_story", "copies": 1},
    ]
    try:
        parse_destination_specs("alice|reel|instagram_reel")
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete destination rows must be rejected")
from planner_reservations import reservation_covers_preview


def test_destination_preview_keeps_account_container_profile_and_lane(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    preview = preview_destination_forge(
        [source],
        [{"username": "Alice", "container": "feed", "profile": "instagram_reel", "copies": 2}],
    )

    assert preview["status"] == "ready"
    assert len(preview["assignments"]) == 2
    row = preview["assignments"][0]
    assert row["username"] == "alice"
    assert row["container"] == "feed"
    assert row["profile"] == "instagram_reel"
    assert row["lane"] == "feed:instagram_reel"


def test_destination_reservation_is_atomic_and_covers_same_preview(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    preview = preview_destination_forge([source], [{"username": "alice", "container": "story", "profile": "instagram_story", "copies": 1}])
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    try:
        reserved = reserve_destination_preview(db.conn, preview, owner="worker-a", now=100)
        conflict = reserve_destination_preview(db.conn, preview, owner="worker-b", now=100)
        assert reserved["status"] == "reserved"
        assert conflict["status"] == "conflict"
        assert reservation_covers_preview(db.conn, reserved, preview, now=101)
    finally:
        db.close()


def test_destination_preview_becomes_durable_job_and_reservation_reconciles(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    preview = preview_destination_forge([source], [{"username": "alice", "container": "reel", "profile": "instagram_reel", "copies": 1}])
    spec = build_destination_forge_job_spec(preview, output_root=tmp_path / "out", metadata={"iphone_model": "iPhone"})
    assert spec["job_type"] == "forge.destination.v1"
    assert spec["steps"][0]["payload"]["username"] == "alice"
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    try:
        reservation = reserve_destination_preview(db.conn, preview, owner="worker", now=100)
        job = submit_destination_forge_job(db.conn, preview, output_root=tmp_path / "out", metadata={"iphone_model": "iPhone"})
        reconciled = reconcile_destination_reservation(db.conn, reservation, preview, owner="worker", now=101)
        assert job["recipe"]["destination_mode"] is True
        assert reconciled["status"] == "released"
    finally:
        db.close()
