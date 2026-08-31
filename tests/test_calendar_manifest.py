import json

from calendar_manifest import (
    build_entry,
    load_entries,
    manifest_path,
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


def test_manifest_scan_keeps_entry_for_delivery_state(tmp_path, monkeypatch):
    import organizadortg

    source = tmp_path / "a.mp4"
    source.write_bytes(b"a")
    entry = build_entry(
        "ana",
        7,
        "normal",
        1,
        1,
        "T1",
        str(source),
        "a__TANDA_T1.mp4",
    )
    replace_entries(tmp_path / "calendar_manifest.json", [entry], {"ana"}, "normal")
    monkeypatch.setattr(organizadortg, "base_dir", str(tmp_path))
    monkeypatch.setattr(organizadortg, "get_accounts_with_va_info", lambda: [
        {"username": "ana", "account_type": "main"},
    ])

    scanned = organizadortg.scan_calendar_structure()

    assert scanned[0]["manifest_entry"] == entry


def test_distribute_reconciles_only_affected_normal_manifest_entries(tmp_path, monkeypatch):
    import Organizador

    class FakeDatabase:
        def __init__(self):
            self.closed = False

        def get_all_accounts(self):
            return [{"id": 7, "username": "ana", "account_type": "MAIN"}]

        def get_video_transform_log_id(self, _path):
            return 33

        def add_video_to_history(self, *_args):
            return None

        def close(self):
            self.closed = True

    db = FakeDatabase()
    tanda_dir = tmp_path / "videos_finales" / "T1"
    tanda_dir.mkdir(parents=True)
    (tanda_dir / "T1__P1__P2.mp4").write_bytes(b"clip")
    calls = []

    def fake_reconcile(received_db, entries, account_ids, delivery_kind):
        calls.append((received_db, entries, account_ids, delivery_kind, received_db.closed))

    monkeypatch.setattr(Organizador, "DatabaseManager", lambda: db)
    monkeypatch.setattr(Organizador, "base_dir", str(tmp_path))
    monkeypatch.setattr(Organizador, "source_root", str(tmp_path / "videos_finales"))
    monkeypatch.setattr(Organizador, "get_account_used_combinations_for_tandas", lambda *_args: set())
    monkeypatch.setattr(Organizador, "reconcile_calendar_entries", fake_reconcile, raising=False)

    Organizador.distribute_tanda("T1", "MAIN", 1, False, "1")

    assert len(calls) == 1
    received_db, entries, account_ids, delivery_kind, db_was_closed = calls[0]
    assert received_db is db
    assert account_ids == {7}
    assert delivery_kind == "normal"
    assert db_was_closed is False
    assert [(entry["username"], entry["delivery_kind"]) for entry in entries] == [("ana", "normal")]
