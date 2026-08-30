from database import DatabaseManager


def test_root_and_collection_keep_one_asset_without_duplicate_membership(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    asset = db.upsert_vault_asset(source)

    collection = db.create_vault_collection("Ideas agosto")
    root = db.create_content_root("Late night 01", tags=["night"], notes="source set")
    db.add_asset_to_collection(collection["id"], asset["id"])
    db.add_asset_to_collection(collection["id"], asset["id"])
    db.add_asset_to_content_root(root["id"], asset["id"], "original_video")
    db.add_asset_to_content_root(root["id"], asset["id"], "original_video")

    assert [row["display_name"] for row in db.list_root_assets(root["id"])] == ["source.mp4"]
    assert db.list_asset_roots(asset["id"])[0]["name"] == "Late night 01"
    assert db.list_collection_assets(collection["id"])[0]["id"] == asset["id"]
    db.close()
