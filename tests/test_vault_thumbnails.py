import database

from vault.storage import VaultStorage
from vault.thumbnails import VaultThumbnailer


def test_thumbnailer_creates_cached_image_thumbnail(tmp_path):
    Image = __import__("PIL.Image", fromlist=["Image"])
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "photo.png"
        Image.new("RGB", (640, 360), "red").save(source)
        storage = VaultStorage(db, tmp_path / "vault")
        asset = storage.import_managed(source)
        thumbnailer = VaultThumbnailer(storage, tmp_path / "thumbs")

        first = thumbnailer.ensure_thumbnail(asset["asset_id"], size=(160, 90))
        second = thumbnailer.ensure_thumbnail(asset["asset_id"], size=(160, 90))

        assert first["status"] == "ok"
        assert first["path"] == second["path"]
        assert first["width"] <= 160
        assert first["height"] <= 90
    finally:
        db.close()


def test_thumbnailer_reports_corrupt_image_without_crashing(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "broken.png"
        source.write_bytes(b"not-image")
        storage = VaultStorage(db, tmp_path / "vault")
        asset = storage.import_managed(source)
        thumbnailer = VaultThumbnailer(storage, tmp_path / "thumbs")

        result = thumbnailer.ensure_thumbnail(asset["asset_id"])

        assert result["status"] == "error"
        assert result["path"] == ""
        assert result["display_name"] == "broken.png"
    finally:
        db.close()


def test_thumbnailer_skips_video_until_frame_extractor_exists(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        source = tmp_path / "clip.mp4"
        source.write_bytes(b"video")
        storage = VaultStorage(db, tmp_path / "vault")
        asset = storage.import_managed(source)
        thumbnailer = VaultThumbnailer(storage, tmp_path / "thumbs")

        result = thumbnailer.ensure_thumbnail(asset["asset_id"])

        assert result["status"] == "unsupported"
        assert result["path"] == ""
    finally:
        db.close()
