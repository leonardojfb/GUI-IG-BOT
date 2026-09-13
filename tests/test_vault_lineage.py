from database import DatabaseManager
from vault.lineage import VaultLineage
from vault.query import VaultQuery
from vault.storage import VaultStorage


def test_lineage_records_multiple_parents_without_duplicates(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    src_a = tmp_path / "a.mp4"
    src_b = tmp_path / "b.jpg"
    out = tmp_path / "out.mp4"
    src_a.write_bytes(b"a")
    src_b.write_bytes(b"b")
    out.write_bytes(b"out")
    asset_a = storage.import_managed(src_a)["asset_id"]
    asset_b = storage.import_managed(src_b)["asset_id"]
    output = storage.import_managed(out)["asset_id"]

    lineage = VaultLineage(db)
    assert lineage.record_derivation(output, [asset_a, asset_b], "forge", {"preset": "soft"}) == 2
    assert lineage.record_derivation(output, [asset_a, asset_b], "forge", {"preset": "soft"}) == 0

    parents = lineage.parents_for_asset(output)
    assert [row["parent_asset_id"] for row in parents] == [asset_a, asset_b]
    assert {row["relation_kind"] for row in parents} == {"forge"}
    children = lineage.children_for_asset(asset_a)
    assert [row["child_asset_id"] for row in children] == [output]
    db.close()


def test_lineage_rejects_self_and_direct_cycles(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    src = tmp_path / "source.mp4"
    out = tmp_path / "out.mp4"
    src.write_bytes(b"source")
    out.write_bytes(b"out")
    source = storage.import_managed(src)["asset_id"]
    output = storage.import_managed(out)["asset_id"]
    lineage = VaultLineage(db)

    try:
        lineage.record_derivation(source, [source], "edit")
    except ValueError as exc:
        assert "padre de si mismo" in str(exc)
    else:
        raise AssertionError("self lineage should be rejected")

    lineage.record_derivation(output, [source], "edit")
    try:
        lineage.record_derivation(source, [output], "edit")
    except ValueError as exc:
        assert "ciclo" in str(exc)
    else:
        raise AssertionError("direct cycle should be rejected")
    db.close()


def test_usage_events_are_append_only_and_queryable(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    src = tmp_path / "asset.mp4"
    src.write_bytes(b"asset")
    asset_id = storage.import_managed(src)["asset_id"]
    lineage = VaultLineage(db)

    first = lineage.record_usage(asset_id, "calendar", "entry-1", {"username": "alice"})
    second = lineage.record_usage(asset_id, "telegram", "message-1", {"chat": "group"})

    assert second > first
    usages = lineage.usages_for_asset(asset_id)
    assert [(row["usage_kind"], row["external_ref"]) for row in usages] == [
        ("telegram", "message-1"),
        ("calendar", "entry-1"),
    ]
    db.close()


def test_usage_once_is_idempotent_for_same_external_ref(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    src = tmp_path / "asset.mp4"
    src.write_bytes(b"asset")
    asset_id = storage.import_managed(src)["asset_id"]
    lineage = VaultLineage(db)

    first = lineage.record_usage_once(asset_id, "calendar", "entry-1", {"username": "alice"})
    second = lineage.record_usage_once(asset_id, "calendar", "entry-1", {"username": "alice"})

    assert second == first
    assert [(row["usage_kind"], row["external_ref"]) for row in lineage.usages_for_asset(asset_id)] == [
        ("calendar", "entry-1")
    ]
    db.close()


def test_vault_inspector_includes_lineage_and_usage(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    parent_file = tmp_path / "parent.mp4"
    child_file = tmp_path / "child.mp4"
    parent_file.write_bytes(b"parent")
    child_file.write_bytes(b"child")
    parent = storage.import_managed(parent_file)["asset_id"]
    child = storage.import_managed(child_file)["asset_id"]
    lineage = VaultLineage(db)
    lineage.record_derivation(child, [parent], "edit", {"tool": "forge"})
    lineage.record_usage(child, "calendar", "entry-1", {"day": 1})

    inspected = VaultQuery(db).inspect_asset(child, storage=storage, thumbnail_cache=tmp_path / "thumbs")

    assert [row["parent_asset_id"] for row in inspected["parents"]] == [parent]
    assert inspected["children"] == []
    assert [(row["usage_kind"], row["external_ref"]) for row in inspected["usages"]] == [
        ("calendar", "entry-1")
    ]
    db.close()
