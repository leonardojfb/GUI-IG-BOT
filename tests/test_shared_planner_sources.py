from shared_planner_sources import (
    collect_tanda_candidates,
    load_planner_accounts,
    load_candidate_usage_rows,
    preview_schedule_from_sources,
    preview_schedule_by_account_from_sources,
)


class FakeDatabase:
    def __init__(self, accounts):
        self._accounts = accounts

    def get_all_accounts(self):
        return list(self._accounts)


def test_load_planner_accounts_filters_explicit_scope_without_mutating_rows():
    rows = [
        {"id": 1, "username": "Alice", "assigned_va": "VA1", "account_type": "MAIN"},
        {"id": 2, "username": "Bob", "assigned_va": "VA2", "account_type": "SPAM"},
        {"id": 3, "username": "Carol", "assigned_va": None, "account_type": "MAIN"},
    ]
    original = [dict(row) for row in rows]

    result = load_planner_accounts(FakeDatabase(rows), usernames=[" bob ", "ALICE"])

    assert result == [
        {"account_id": 1, "username": "Alice", "assigned_va": "VA1", "account_type": "MAIN"},
        {"account_id": 2, "username": "Bob", "assigned_va": "VA2", "account_type": "SPAM"},
    ]
    assert rows == original


def test_collect_tanda_candidates_returns_stable_concrete_sources_and_missing_report(tmp_path):
    root = tmp_path / "videos_finales"
    (root / "T2").mkdir(parents=True)
    (root / "T1").mkdir()
    (root / "T2" / "b.MP4").write_bytes(b"b")
    (root / "T2" / "a.mov").write_bytes(b"a")
    (root / "T2" / "ignore.txt").write_text("x", encoding="utf-8")

    result = collect_tanda_candidates(root, ["T2", "T1", "MISSING"])

    assert [item["display_filename"] for item in result["candidates"]] == ["a.mov", "b.MP4"]
    assert [item["tanda"] for item in result["candidates"]] == ["T2", "T2"]
    assert all(item["media_class"] == "video" for item in result["candidates"])
    assert result["empty_tandas"] == ["T1"]
    assert result["missing_tandas"] == ["MISSING"]
    assert result["skipped_files"] == 1


def test_preview_schedule_from_sources_combines_readers_and_keeps_inventory_report(tmp_path):
    root = tmp_path / "videos_finales"
    (root / "T1").mkdir(parents=True)
    (root / "T1" / "clip.mp4").write_bytes(b"clip")
    db = FakeDatabase([{"id": 9, "username": "alice", "assigned_va": "VA1", "account_type": "MAIN"}])

    preview = preview_schedule_from_sources(
        db,
        root,
        ["T1", "MISSING"],
        usernames=["alice"],
        daily_quota=1,
        days=1,
        seed=3,
    )

    assert preview["status"] == "ready"
    assert preview["summary"]["assignable"] == 1
    assert preview["assignments"][0]["source_id"] == "T1:clip.mp4"
    assert preview["inventory"] == {
        "missing_tandas": ["MISSING"],
        "empty_tandas": [],
        "skipped_files": 0,
    }


def test_preview_schedule_by_account_from_sources_keeps_account_scope(tmp_path):
    root = tmp_path / "videos_finales"
    (root / "T1").mkdir(parents=True)
    (root / "T1" / "clip.mp4").write_bytes(b"clip")
    db = FakeDatabase([
        {"id": 9, "username": "alice", "assigned_va": "VA1", "account_type": "MAIN"},
        {"id": 10, "username": "bob", "assigned_va": "VA1", "account_type": "MAIN"},
    ])

    preview = preview_schedule_by_account_from_sources(
        db,
        root,
        ["T1"],
        usernames=["alice", "bob"],
        daily_quota=1,
        days=1,
        seed=5,
    )

    assert preview["status"] == "ready"
    assert preview["summary"]["assignable"] == 2
    assert {row["username"] for row in preview["assignments"]} == {"alice", "bob"}
    assert preview["inventory"]["missing_tandas"] == []


def test_load_candidate_usage_rows_enriches_candidates_without_writing(tmp_path):
    import json
    import sqlite3

    path = str((tmp_path / "clip.mp4").resolve())
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE vault_assets (id INTEGER PRIMARY KEY, display_name TEXT);
        CREATE TABLE vault_locations (asset_id INTEGER, path TEXT, managed INTEGER DEFAULT 0);
        CREATE TABLE vault_asset_usages (
            id INTEGER PRIMARY KEY, asset_id INTEGER, usage_kind TEXT,
            external_ref TEXT, details_json TEXT
        );
        """
    )
    conn.execute("INSERT INTO vault_assets VALUES (7, 'clip.mp4')")
    conn.execute("INSERT INTO vault_locations VALUES (7, ?, 1)", (path,))
    conn.execute(
        "INSERT INTO vault_asset_usages VALUES (3, 7, 'calendar', 'entry-3', ?)",
        (json.dumps({"username": "alice", "lane": "reel"}),),
    )
    conn.commit()

    class FakeDb:
        def __init__(self, connection):
            self.conn = connection

    candidates = [{"source_id": "T1:clip.mp4", "source_path": path}]
    result = load_candidate_usage_rows(FakeDb(conn), candidates)

    assert result[0]["used_in"] == [
        {"username": "alice", "lane": "reel", "usage_kind": "calendar", "external_ref": "entry-3"}
    ]
    assert result[0]["source_id"] == candidates[0]["source_id"]
