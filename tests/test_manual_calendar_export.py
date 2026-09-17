import json
import zipfile

from manual_calendar_export import export_manifest_v2_package, export_manual_package, import_manual_package, preview_manual_package_import, verify_manual_package


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


def test_manifest_v2_export_preserves_destination_fields(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"media")
    manifest = tmp_path / "calendar_manifest.json"
    manifest.write_text(__import__("json").dumps({"version": 2, "entries": [{"manifest_entry_version": 2, "source_path": str(media), "username": "alice", "lane": "standard", "placement": "feed", "publication_target": "instagram_manual"}]}), encoding="utf-8")
    package = tmp_path / "manifest.zip"

    export_manifest_v2_package(manifest, package)

    assert verify_manual_package(package)["status"] == "ok"
    with __import__("zipfile").ZipFile(package) as archive:
        text = archive.read("package_manifest.json").decode("utf-8")
    assert "instagram_manual" in text


def test_manual_package_import_requires_confirmation_and_reports_conflicts(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"media")
    package = tmp_path / "manifest.zip"
    export_manual_package([{"media_path": str(media), "username": "alice"}], package)
    destination = tmp_path / "calendar"

    preview = preview_manual_package_import(package, destination)
    assert preview["status"] == "ready"
    assert preview["entries"] == 1
    assert preview["conflicts"] == []
    assert not destination.exists()

    try:
        import_manual_package(package, destination)
    except PermissionError:
        pass
    else:
        raise AssertionError("import must require explicit confirmation")

    result = import_manual_package(package, destination, confirm=True)
    assert result["status"] == "imported"
    assert (destination / "media" / "0001.mp4").read_bytes() == b"media"

    conflict = preview_manual_package_import(package, destination)
    assert conflict["status"] == "conflict"
    assert conflict["conflicts"] == ["media/0001.mp4"]


def test_manual_package_import_writes_audit_event_only_after_success(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"media")
    package = tmp_path / "manifest.zip"
    export_manual_package([{"media_path": str(media), "username": "alice"}], package)
    destination = tmp_path / "calendar"
    audit = tmp_path / "audit.jsonl"

    result = import_manual_package(package, destination, confirm=True, audit_path=audit, actor="operator-1")

    assert result["status"] == "imported"
    event = json.loads(audit.read_text(encoding="utf-8").splitlines()[0])
    assert event["actor"] == "operator-1"
    assert event["destination"] == str(destination.resolve())
    assert event["entries"] == 1
