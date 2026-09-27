import json

from calendar_manifest import (
    append_scheduled_entries,
    build_entry,
    load_entries,
    manifest_path,
    publication_target_for_entry,
    remove_entries_for_accounts,
    replace_entries,
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


def test_manifest_defaults_trial_entry_to_explicit_trial_target(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")

    entry = build_entry("eve", 7, "trial", 1, 1, "T", str(source), "clip.mp4")

    assert entry["publication_target"] == "instagram_trial_reel"
    assert publication_target_for_entry({"delivery_kind": "trial"}) == "instagram_trial_reel"
    assert entry["manual_status"] == "planned"


def test_replace_entries_keeps_other_normal_target_for_same_account(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    manifest = tmp_path / "calendar_manifest.json"
    reel = build_entry("alice", 1, "normal", 1, 1, "T", str(source), "reel.mp4")
    post = build_entry(
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
    replace_entries(manifest, [reel, post], {"alice"}, "normal")

    newer = build_entry(
        "alice",
        1,
        "normal",
        2,
        1,
        "T",
        str(source),
        "new.mp4",
        publication_target="instagram_post",
    )
    rows = replace_entries(
        manifest,
        [newer],
        {"alice"},
        "normal",
        publication_target="instagram_post",
    )

    assert [row["publication_target"] for row in rows] == [
        "instagram_reel",
        "instagram_post",
    ]
    assert [row["telegram_filename"] for row in rows] == ["reel.mp4", "new.mp4"]


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


def test_append_scheduled_entries_preserves_existing_calendar_and_inserts_by_time(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    early = build_entry(
        "alice", 1, "normal", 1, 1, "T", str(source), "early.mp4",
        scheduled_date="2026-10-05", scheduled_time="10:00",
    )
    late = build_entry(
        "alice", 1, "normal", 1, 2, "T", str(source), "late.mp4",
        scheduled_date="2026-10-05", scheduled_time="13:00",
    )
    middle = build_entry(
        "alice", 1, "normal", 1, 3, "T", str(source), "middle.jpg",
        publication_target="instagram_post",
        scheduled_date="2026-10-05", scheduled_time="12:00",
    )
    replace_entries(manifest, [early, late], {"alice"}, "normal")

    result = append_scheduled_entries(manifest, [middle])

    assert result.conflicts == []
    assert [entry["telegram_filename"] for entry in load_entries(manifest)] == [
        "early.mp4", "middle.jpg", "late.mp4",
    ]


def test_append_scheduled_entries_does_not_write_when_a_time_is_occupied(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    existing = build_entry(
        "alice", 1, "normal", 1, 1, "T", str(source), "reel.mp4",
        scheduled_date="2026-10-05", scheduled_time="12:00",
    )
    candidate = build_entry(
        "alice", 1, "normal", 1, 2, "T", str(source), "story.jpg",
        publication_target="instagram_post",
        scheduled_date="2026-10-05", scheduled_time="12:00",
    )
    replace_entries(manifest, [existing], {"alice"}, "normal")

    result = append_scheduled_entries(manifest, [candidate])

    assert len(result.conflicts) == 1
    assert [entry["telegram_filename"] for entry in load_entries(manifest)] == ["reel.mp4"]
