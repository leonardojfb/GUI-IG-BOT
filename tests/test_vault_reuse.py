from database import DatabaseManager
from vault.lineage import VaultLineage
from vault.query import VaultQuery
from vault.reuse import VaultReuseAudit
from vault.signatures import VaultSignatures
from vault.storage import VaultStorage


def test_reuse_candidates_match_signatures_and_include_usage(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    current_file = tmp_path / "current.mp4"
    used_file = tmp_path / "used.mp4"
    current_file.write_bytes(b"current")
    used_file.write_bytes(b"used")
    current = storage.import_managed(current_file)["asset_id"]
    used = storage.import_managed(used_file)["asset_id"]
    signatures = VaultSignatures(db)
    signatures.record_signature(current, "visual_bucket", "scene-1", algorithm="manual")
    signatures.record_signature(used, "visual_bucket", "scene-1", algorithm="manual")
    VaultLineage(db).record_usage(used, "calendar", "entry-1", {"username": "alice"})

    candidates = VaultReuseAudit(db).candidates_for_asset(current)

    assert [row["asset_id"] for row in candidates] == [used]
    assert candidates[0]["usage_count"] == 1
    assert [(row["usage_kind"], row["external_ref"]) for row in candidates[0]["usages"]] == [
        ("calendar", "entry-1")
    ]
    assert candidates[0]["matched_signatures"] == [
        {
            "signature_kind": "visual_bucket",
            "algorithm": "manual",
            "signature_value": "scene-1",
        }
    ]
    db.close()


def test_reuse_candidates_can_include_unused_matches(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    current_file = tmp_path / "current.mp4"
    unused_file = tmp_path / "unused.mp4"
    current_file.write_bytes(b"current")
    unused_file.write_bytes(b"unused")
    current = storage.import_managed(current_file)["asset_id"]
    unused = storage.import_managed(unused_file)["asset_id"]
    signatures = VaultSignatures(db)
    signatures.record_signature(current, "visual_bucket", "scene-1", algorithm="manual")
    signatures.record_signature(unused, "visual_bucket", "scene-1", algorithm="manual")

    default_candidates = VaultReuseAudit(db).candidates_for_asset(current)
    inclusive_candidates = VaultReuseAudit(db).candidates_for_asset(current, require_usage=False)

    assert default_candidates == []
    assert [row["asset_id"] for row in inclusive_candidates] == [unused]
    assert inclusive_candidates[0]["usage_count"] == 0
    db.close()


def test_vault_inspector_includes_reuse_candidates(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    current_file = tmp_path / "current.mp4"
    used_file = tmp_path / "used.mp4"
    current_file.write_bytes(b"current")
    used_file.write_bytes(b"used")
    current = storage.import_managed(current_file)["asset_id"]
    used = storage.import_managed(used_file)["asset_id"]
    signatures = VaultSignatures(db)
    signatures.record_signature(current, "visual_bucket", "scene-1", algorithm="manual")
    signatures.record_signature(used, "visual_bucket", "scene-1", algorithm="manual")
    VaultLineage(db).record_usage(used, "telegram", "message-1")

    inspected = VaultQuery(db).inspect_asset(
        current,
        storage=storage,
        thumbnail_cache=tmp_path / "thumbs",
    )

    assert [row["asset_id"] for row in inspected["reuse_candidates"]] == [used]
    db.close()
