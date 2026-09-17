import database

from destination_forge import preview_destination_forge, reserve_destination_preview
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
