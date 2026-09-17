import zipfile

from manual_calendar_export import export_manual_package, verify_manual_package


def test_manual_package_contains_checksums_and_verifies(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"media")
    package = tmp_path / "calendar.zip"
    entries = [{"day": 1, "slot": "10:00", "username": "alice", "media_path": str(media), "caption": "hola", "target": "instagram_manual"}]

    result = export_manual_package(entries, package)
    verified = verify_manual_package(package)

    assert result["entries"] == 1
    assert verified["status"] == "ok"
    with zipfile.ZipFile(package) as archive:
        assert "package_manifest.json" in archive.namelist()
        assert any(name.startswith("media/") for name in archive.namelist())


def test_manual_package_rejects_missing_media(tmp_path):
    try:
        export_manual_package([{"media_path": str(tmp_path / "missing.mp4")}], tmp_path / "bad.zip")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("missing media should block manual export")
