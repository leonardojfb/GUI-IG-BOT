from database import DatabaseManager
from vault.query import VaultQuery
from vault.signatures import VaultSignatures
from vault.storage import VaultStorage


def test_file_signatures_are_idempotent_and_queryable(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    source = tmp_path / "clip.MP4"
    source.write_bytes(b"same bytes")
    asset = storage.import_managed(source)

    signatures = VaultSignatures(db)
    first = signatures.ensure_file_signatures(asset["asset_id"], asset["path"])
    second = signatures.ensure_file_signatures(asset["asset_id"], asset["path"])

    assert first == second
    assert {row["signature_kind"] for row in first} == {"sha256", "size_bytes", "extension", "media_type"}
    matches = signatures.find_assets_by_signature("sha256", asset["sha256"])
    assert [row["asset_id"] for row in matches] == [asset["asset_id"]]
    db.close()


def test_signature_search_can_exclude_current_asset(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    one = tmp_path / "one.mp4"
    two = tmp_path / "two.mp4"
    one.write_bytes(b"one")
    two.write_bytes(b"two")
    asset_one = storage.import_managed(one)
    asset_two = storage.register_external(two)
    signatures = VaultSignatures(db)
    signatures.record_signature(asset_one["asset_id"], "visual_bucket", "same-scene", algorithm="manual")
    signatures.record_signature(asset_two["asset_id"], "visual_bucket", "same-scene", algorithm="manual")

    matches = signatures.find_assets_by_signature(
        "visual_bucket",
        "same-scene",
        exclude_asset_id=asset_one["asset_id"],
    )

    assert [row["asset_id"] for row in matches] == [asset_two["asset_id"]]
    db.close()


def test_vault_inspector_includes_signatures(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    storage = VaultStorage(db, tmp_path / "vault")
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"image bytes")
    asset = storage.import_managed(source)
    VaultSignatures(db).ensure_file_signatures(asset["asset_id"], asset["path"])

    inspected = VaultQuery(db).inspect_asset(
        asset["asset_id"],
        storage=storage,
        thumbnail_cache=tmp_path / "thumbs",
    )

    assert {row["signature_kind"] for row in inspected["signatures"]} == {
        "sha256",
        "size_bytes",
        "extension",
        "media_type",
    }
    db.close()
