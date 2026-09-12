import os

import database

from vault.storage import VaultStorage, hash_file


def _temporary_db(tmp_path):
    previous = database.DB_PATH
    database.DB_PATH = str(tmp_path / "organizador.db")
    return database.DatabaseManager(), previous


def test_import_managed_dedupes_bytes_and_survives_source_delete(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        source = tmp_path / "incoming" / "clip.mp4"
        source.parent.mkdir()
        source.write_bytes(b"same-video")
        vault_root = tmp_path / "vault"
        storage = VaultStorage(db, vault_root)

        first = storage.import_managed(source)
        second = storage.import_managed(source)

        assert first["asset_id"] == second["asset_id"]
        assert first["sha256"] == hash_file(source)
        assert os.path.exists(first["path"])
        assert first["managed"] is True
        assert len(storage.locations_for_asset(first["asset_id"])) == 1

        source.unlink()
        health = storage.verify_location(first["location_id"])

        assert health["status"] == "ok"
        assert health["sha256"] == first["sha256"]
    finally:
        db.close()
        database.DB_PATH = previous


def test_register_external_keeps_missing_location_as_reviewable_history(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        source = tmp_path / "external.mp4"
        source.write_bytes(b"external")
        storage = VaultStorage(db, tmp_path / "vault")

        location = storage.register_external(source)
        source.unlink()
        health = storage.verify_location(location["location_id"])

        assert health["status"] == "missing"
        assert health["asset_id"] == location["asset_id"]
        assert storage.locations_for_asset(location["asset_id"])[0]["path"] == str(source)
    finally:
        db.close()
        database.DB_PATH = previous


def test_managed_import_rejects_source_changed_during_copy(tmp_path, monkeypatch):
    db, previous = _temporary_db(tmp_path)
    try:
        source = tmp_path / "clip.mp4"
        source.write_bytes(b"before")
        storage = VaultStorage(db, tmp_path / "vault")
        original_hash_file = hash_file
        calls = {"count": 0}

        def changing_hash(path):
            calls["count"] += 1
            if calls["count"] == 2:
                source.write_bytes(b"after")
            return original_hash_file(path)

        monkeypatch.setattr("vault.storage.hash_file", changing_hash)

        try:
            storage.import_managed(source)
        except ValueError as exc:
            assert "cambio durante la copia" in str(exc)
        else:
            raise AssertionError("changing source should reject managed import")

        assert not list((tmp_path / "vault").rglob("*.tmp"))
        assert storage.list_assets() == []
    finally:
        db.close()
        database.DB_PATH = previous
