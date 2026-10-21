import json
import pytest

from calendar_manifest import (
    build_entry,
    load_entries,
    manifest_path,
    publication_target_for_entry,
    remove_entries_for_accounts,
    replace_entries,
)


def test_manifest_path_is_app_root_json(tmp_path):
    assert manifest_path(tmp_path) == tmp_path / "calendar_manifest.json"


def test_build_entry_persists_optional_origin_identity(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")

    entry = build_entry(
        "eve", 7, "normal", 1, 1, "T", str(source), "clip.mp4",
        origin_identity="origin-123",
    )
    legacy_entry = build_entry("eve", 7, "normal", 1, 2, "T", str(source), "clip-2.mp4")

    assert entry["origin_identity"] == "origin-123"
    assert "origin_identity" not in legacy_entry


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


def test_replace_entries_can_scope_to_selected_tandas(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source = tmp_path / "v.mp4"
    source.write_bytes(b"v")
    existing = [
        build_entry("alice", 1, "normal", 1, 1, "T1", str(source), "old-t1.mp4"),
        build_entry("alice", 1, "normal", 1, 2, "T2", str(source), "keep-t2.mp4"),
        build_entry("bob", 2, "normal", 1, 1, "T1", str(source), "keep-bob.mp4"),
    ]
    replace_entries(manifest, existing, {"alice", "bob"}, "normal")

    replacement = build_entry(
        "alice", 1, "normal", 2, 1, "T1", str(source), "new-t1.mp4"
    )
    merged = replace_entries(
        manifest,
        [replacement],
        {"alice"},
        "normal",
        tanda_names={"T1"},
    )

    assert {(entry["username"], entry["telegram_filename"]) for entry in merged} == {
        ("alice", "keep-t2.mp4"),
        ("alice", "new-t1.mp4"),
        ("bob", "keep-bob.mp4"),
    }


def test_replace_entries_keeps_same_origin_for_telegram_send_filter(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    first_source = tmp_path / "tjp.mp4"
    second_source = tmp_path / "talking.mp4"
    first_source.write_bytes(b"one")
    second_source.write_bytes(b"two")
    first = build_entry(
        "alice", 1, "normal", 1, 1, "TJP OCT", str(first_source), "tjp.mp4",
        origin_identity="shared-origin",
    )
    replace_entries(manifest, [first], {"alice"}, "normal", tanda_names={"TJP OCT"})
    duplicate = build_entry(
        "alice", 1, "normal", 6, 1, "Talking", str(second_source), "talking.mp4",
        origin_identity="shared-origin",
    )

    merged = replace_entries(manifest, [duplicate], {"alice"}, "normal", tanda_names={"Talking"})

    assert {(entry["tanda"], entry["origin_identity"]) for entry in merged} == {
        ("TJP OCT", "shared-origin"),
        ("Talking", "shared-origin"),
    }
