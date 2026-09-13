import json

import pytest

from calendar_manifest import (
    build_entry,
    build_entry_v2,
    load_entries,
    manifest_path,
    publication_target_for_entry,
    remove_entries_for_accounts,
    replace_entries,
    replace_entries_v2,
)


def test_manifest_path_is_app_root_json(tmp_path):
    assert manifest_path(tmp_path) == tmp_path / "calendar_manifest.json"


def test_replace_entries_preserves_unrelated_account_and_kind(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source_a = tmp_path / "a.mp4"
    source_b = tmp_path / "b.mp4"
    source_c = tmp_path / "c.mp4"
    source_a.write_bytes(b"a")
    source_b.write_bytes(b"b")
    source_c.write_bytes(b"c")

    existing = [
        build_entry("alice", 1, "normal", 1, 1, "T1", str(source_a), "a__TANDA_T1.mp4"),
        build_entry("bob", 2, "trial", 1, 1, "T2", str(source_b), "b__TANDA_T2.mp4"),
    ]
    replace_entries(manifest, existing, {"alice", "bob"}, "normal")

    new_entry = build_entry("alice", 1, "normal", 2, 3, "T3", str(source_c), "c__TANDA_T3.mp4")
    merged = replace_entries(manifest, [new_entry], {"alice"}, "normal")

    assert [(e["username"], e["delivery_kind"], e["tanda"]) for e in merged] == [
        ("bob", "trial", "T2"),
        ("alice", "normal", "T3"),
    ]
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert len(payload["entries"]) == 2


def test_load_entries_skips_missing_source_when_required(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    present = tmp_path / "present.mp4"
    missing = tmp_path / "missing.mp4"
    present.write_bytes(b"video")
    entries = [
        build_entry("ok", 10, "normal", 1, 1, "T", str(present), "ok__TANDA_T.mp4"),
        build_entry("skip", 11, "normal", 1, 2, "T", str(missing), "skip__TANDA_T.mp4"),
    ]
    replace_entries(manifest, entries, {"ok", "skip"}, "normal")

    loaded = load_entries(manifest, require_source=True)

    assert [e["username"] for e in loaded] == ["ok"]


def test_load_entries_accepts_manifest_v2_without_rewriting(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    entry = {
        "id": "entry-v2",
        "username": "alice",
        "account_id": 1,
        "delivery_kind": "normal",
        "day": 1,
        "slot": 2,
        "tanda": "T",
        "source_path": str(source),
        "telegram_filename": "clip.mp4",
        "publication_target": "instagram_reel",
        "lane": "reel",
        "placement": "feed",
        "media_class": "video",
        "method": "telegram",
        "policy_snapshot": {"reuse": "legacy-v1"},
    }
    manifest.write_text(
        json.dumps({"version": 2, "entries": [entry], "lanes": {"reel": {"enabled": True}}}),
        encoding="utf-8",
    )

    loaded = load_entries(manifest)

    assert loaded == [entry]
    assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == 2


def test_manifest_defaults_trial_entry_to_explicit_trial_target(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")

    entry = build_entry("eve", 7, "trial", 1, 1, "T", str(source), "clip.mp4")

    assert entry["publication_target"] == "instagram_trial_reel"
    assert publication_target_for_entry({"delivery_kind": "trial"}) == (
        "instagram_trial_reel"
    )
    assert entry["manual_status"] == "planned"


def test_manifest_entry_can_store_caption_snapshot_literal(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")

    entry = build_entry(
        "eve",
        7,
        "normal",
        1,
        1,
        "T",
        str(source),
        "clip.mp4",
        caption="Caption frozen",
        caption_snapshot={
            "caption_id": "caption-1",
            "caption_version": 3,
            "resolution_mode": "general",
            "resolution_source_id": "pool-1",
        },
    )

    assert entry["caption"] == "Caption frozen"
    assert entry["caption_snapshot"] == {
        "caption_id": "caption-1",
        "caption_version": 3,
        "resolution_mode": "general",
        "resolution_source_id": "pool-1",
    }


def test_manifest_v1_rejects_new_manual_publication_entries(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")

    with pytest.raises(ValueError, match="manifest v2"):
        build_entry(
            "alice",
            1,
            "normal",
            1,
            2,
            "T",
            str(source),
            "post.mp4",
            publication_target="instagram_post",
        )


def test_build_entry_v2_stores_lane_dimensions_and_manual_target(tmp_path):
    source = tmp_path / "story.jpg"
    source.write_bytes(b"image")

    entry = build_entry_v2(
        username="alice",
        account_id=1,
        delivery_kind="normal",
        day=3,
        slot=4,
        tanda="STORY",
        source_path=str(source),
        display_filename="story.jpg",
        publication_target="instagram_story",
        lane="story",
        placement="story",
        media_class="image",
        method="manual",
        policy_snapshot={"reuse_policy": "same_lane_block"},
        story_link_url="https://example.test",
        story_announcement_text="Nuevo post",
    )

    assert entry["manifest_entry_version"] == 2
    assert entry["publication_target"] == "instagram_story"
    assert entry["telegram_filename"] == "story.jpg"
    assert entry["lane"] == "story"
    assert entry["placement"] == "story"
    assert entry["media_class"] == "image"
    assert entry["method"] == "manual"
    assert entry["policy_snapshot"] == {"reuse_policy": "same_lane_block"}
    assert entry["story_link_url"] == "https://example.test"
    assert entry["story_announcement_text"] == "Nuevo post"


def test_replace_entries_v2_replaces_only_target_lane_and_window(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    reel = build_entry_v2(
        "alice",
        1,
        "normal",
        1,
        1,
        "T",
        str(source),
        "reel.mp4",
        publication_target="instagram_reel",
        lane="reel",
        placement="feed",
        media_class="video",
        method="telegram",
        policy_snapshot={"version": 1},
    )
    story = build_entry_v2(
        "alice",
        1,
        "normal",
        1,
        2,
        "T",
        str(source),
        "story.jpg",
        publication_target="instagram_story",
        lane="story",
        placement="story",
        media_class="image",
        method="manual",
        policy_snapshot={"version": 1},
        story_link_url="https://example.test/a",
        story_announcement_text="Story",
    )
    bob_reel = build_entry_v2(
        "bob",
        2,
        "normal",
        1,
        1,
        "T",
        str(source),
        "bob.mp4",
        publication_target="instagram_reel",
        lane="reel",
        placement="feed",
        media_class="video",
        method="telegram",
        policy_snapshot={"version": 1},
    )
    manifest.write_text(
        json.dumps({"version": 2, "entries": [reel, story, bob_reel]}),
        encoding="utf-8",
    )
    replacement = {
        **reel,
        "id": "replacement",
        "telegram_filename": "reel-new.mp4",
        "display_filename": "reel-new.mp4",
    }

    rows = replace_entries_v2(
        manifest,
        [replacement],
        usernames={"alice"},
        lane="reel",
        window={"start_day": 1, "end_day": 1},
    )

    assert [row["id"] for row in rows] == [story["id"], bob_reel["id"], "replacement"]
    assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == 2


def test_default_replace_only_replaces_default_target(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    manifest = tmp_path / "calendar_manifest.json"
    manual = {
        "id": "manual-post",
        "username": "alice",
        "delivery_kind": "normal",
        "publication_target": "instagram_post",
        "source_path": str(source),
        "telegram_filename": "post.mp4",
    }
    manifest.write_text(
        json.dumps({"version": 1, "entries": [manual]}),
        encoding="utf-8",
    )

    reel = build_entry("alice", 1, "normal", 2, 1, "T", str(source), "reel.mp4")
    rows = replace_entries(manifest, [reel], {"alice"}, "normal")

    assert [row["publication_target"] for row in rows] == [
        "instagram_post",
        "instagram_reel",
    ]
    assert [row["telegram_filename"] for row in rows] == ["post.mp4", "reel.mp4"]


def test_remove_entries_for_accounts_removes_all_kinds(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source = tmp_path / "v.mp4"
    source.write_bytes(b"v")
    entries = [
        build_entry("alice", 1, "normal", 1, 1, "T", str(source), "a__TANDA_T.mp4"),
        build_entry("alice", 1, "trial", 1, 1, "T", str(source), "at__TANDA_T.mp4"),
        build_entry("bob", 2, "normal", 1, 1, "T", str(source), "b__TANDA_T.mp4"),
    ]
    replace_entries(manifest, entries, {"alice", "bob"}, "normal")

    removed = remove_entries_for_accounts(manifest, {"alice"})

    assert removed == 2
    assert [e["username"] for e in load_entries(manifest)] == ["bob"]
