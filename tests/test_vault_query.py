import database

from vault.query import VaultQuery
from vault.storage import VaultStorage


def _temporary_db(tmp_path):
    previous = database.DB_PATH
    database.DB_PATH = str(tmp_path / "organizador.db")
    return database.DatabaseManager(), previous


def test_collections_and_families_link_assets_without_moving_bytes(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        source = tmp_path / "clip.mp4"
        source.write_bytes(b"video")
        storage = VaultStorage(db, tmp_path / "vault")
        query = VaultQuery(db)
        asset = storage.import_managed(source)
        original_path = asset["path"]

        family = query.create_family("Late night")
        collection = query.create_collection("Ideas")
        assert query.add_asset_to_family(family["id"], asset["asset_id"], role="original") is True
        assert query.add_asset_to_family(family["id"], asset["asset_id"], role="original") is False
        assert query.add_asset_to_collection(collection["id"], asset["asset_id"]) is True

        family_assets = query.assets_for_family(family["id"])
        collection_assets = query.assets_for_collection(collection["id"])

        assert family_assets[0]["sha256"] == asset["sha256"]
        assert family_assets[0]["role"] == "original"
        assert collection_assets[0]["id"] == asset["asset_id"]
        assert storage.locations_for_asset(asset["asset_id"])[0]["path"] == original_path
    finally:
        db.close()
        database.DB_PATH = previous


def test_library_query_filters_status_type_family_collection_and_paginates(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        storage = VaultStorage(db, tmp_path / "vault")
        query = VaultQuery(db)
        family = query.create_family("Root")
        collection = query.create_collection("Keep")
        kept = []
        for index in range(5):
            source = tmp_path / f"clip_{index}.mp4"
            source.write_bytes(f"video-{index}".encode("ascii"))
            asset = storage.import_managed(source)
            query.add_asset_to_family(family["id"], asset["asset_id"], role="original")
            if index % 2 == 0:
                query.add_asset_to_collection(collection["id"], asset["asset_id"])
                kept.append(asset["asset_id"])

        page = query.search_assets(
            media_type="video",
            status="ok",
            family_id=family["id"],
            collection_id=collection["id"],
            limit=2,
            offset=1,
        )

        assert page["total"] == 3
        assert [row["id"] for row in page["items"]] == kept[1:3]
        assert page["limit"] == 2
        assert page["offset"] == 1
    finally:
        db.close()
        database.DB_PATH = previous
