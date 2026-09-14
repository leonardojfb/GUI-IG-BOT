import json
import subprocess
import sys
from pathlib import Path

from calendar_manifest import build_entry, replace_entries


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "manifest_migration_cli.py"), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_manifest_migration_cli_preview_prints_json_without_writing(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    entry = build_entry("alice", 1, "normal", 1, 1, "T", str(source), "clip.mp4")
    replace_entries(manifest, [entry], {"alice"}, "normal")
    before = manifest.read_text(encoding="utf-8")

    result = _run_cli("preview", str(manifest))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["operation"] == "migrate_manifest_v1_to_v2"
    assert payload["summary"] == {"migrated": 1, "total": 1}
    assert payload["merged_entries"][0]["lane"] == "reel"
    assert manifest.read_text(encoding="utf-8") == before


def test_manifest_migration_cli_apply_converts_manifest_to_v2(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    entry = build_entry("alice", 1, "normal", 1, 1, "T", str(source), "clip.mp4")
    replace_entries(manifest, [entry], {"alice"}, "normal")

    result = _run_cli("apply", str(manifest))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["applied"] is True
    assert payload["summary"] == {"migrated": 1, "total": 1}
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["version"] == 2
    assert manifest_payload["entries"][0]["id"] == entry["id"]


def test_manifest_migration_cli_rejects_apply_without_confirm(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    entry = build_entry("alice", 1, "normal", 1, 1, "T", str(source), "clip.mp4")
    replace_entries(manifest, [entry], {"alice"}, "normal")

    result = _run_cli("apply", str(manifest), "--require-confirmation")

    assert result.returncode == 2
    assert "requiere --yes" in result.stderr
    assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == 1


def test_manifest_migration_cli_journal_inspect_reports_pending(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    manifest.write_text(json.dumps({"version": 2, "entries": []}), encoding="utf-8")
    (tmp_path / ".calendar_manifest_journal.json").write_text(
        json.dumps({"operation": "write_manifest_v2"}),
        encoding="utf-8",
    )

    result = _run_cli("journal-inspect", str(manifest))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "pending"
    assert payload["journal"]["operation"] == "write_manifest_v2"


def test_manifest_migration_cli_journal_clear_requires_yes(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    journal = tmp_path / ".calendar_manifest_journal.json"
    manifest.write_text(json.dumps({"version": 2, "entries": []}), encoding="utf-8")
    journal.write_text(json.dumps({"operation": "write_manifest_v2"}), encoding="utf-8")

    result = _run_cli("journal-clear", str(manifest))

    assert result.returncode == 2
    assert "requiere --yes" in result.stderr
    assert journal.exists()


def test_manifest_migration_cli_journal_clear_removes_pending_journal(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    journal = tmp_path / ".calendar_manifest_journal.json"
    manifest.write_text(json.dumps({"version": 2, "entries": []}), encoding="utf-8")
    journal.write_text(json.dumps({"operation": "write_manifest_v2"}), encoding="utf-8")

    result = _run_cli("journal-clear", str(manifest), "--yes")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["cleared"] is True
    assert not journal.exists()
