import io
import json
import re
import zipfile
from pathlib import Path

import updater


REPO_ROOT = Path(__file__).resolve().parents[1]
STAGED_VERSION = "1.0.42"


def _release_files_from_build_script():
    script = (REPO_ROOT / "build_release.ps1").read_text(encoding="utf-8")
    match = re.search(r"\$ReleaseFiles\s*=\s*@\((.*?)\)", script, re.S)
    assert match, "build_release.ps1 must define a $ReleaseFiles array"
    return list(re.findall(r'"([^"]+)"', match.group(1)))


def _zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _write_existing_install(app_dir):
    for name in updater.APPLICATION_REQUIRED_FILES:
        path = app_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name == "version.json":
            path.write_text(json.dumps({"version": "1.0.41"}), encoding="utf-8")
        elif name.endswith(".exe"):
            path.write_bytes(b"old binary")
        else:
            path.write_text(f"old {name}", encoding="utf-8")
    (app_dir / "organizador.db").write_bytes(b"client database")
    (app_dir / "telegram_state_v11.json").write_text(
        '{"session":"client"}',
        encoding="utf-8",
    )
    (app_dir / "update_config.json").write_text(
        json.dumps({"manifest_url": "client-local"}),
        encoding="utf-8",
    )


def _bootstrap_package():
    files = {
        "updater.py": (REPO_ROOT / "updater.py").read_text(encoding="utf-8"),
        "version.json": json.dumps(
            {"version": STAGED_VERSION, "update_phase": "bootstrap"}
        ),
    }
    return files, {
        "version": STAGED_VERSION,
        "package_kind": "bootstrap",
        "files": sorted(files),
    }


def _application_package():
    files = {}
    for name in _release_files_from_build_script():
        path = REPO_ROOT / name
        if name == "version.json":
            files[name] = json.dumps({"version": STAGED_VERSION})
        elif name.endswith(".exe"):
            files[name] = path.read_bytes()
        else:
            files[name] = path.read_text(encoding="utf-8")
    return files, {
        "version": STAGED_VERSION,
        "package_kind": "application",
        "files": sorted(files),
    }


def test_staged_bootstrap_then_application_preserves_client_runtime(tmp_path):
    _write_existing_install(tmp_path)
    bootstrap_files, bootstrap_manifest = _bootstrap_package()
    bootstrap_path = tmp_path / "bootstrap.zip"
    bootstrap_path.write_bytes(_zip_bytes(bootstrap_files))

    assert updater.apply_package(tmp_path, bootstrap_path, bootstrap_manifest) == STAGED_VERSION
    assert json.loads((tmp_path / "version.json").read_text(encoding="utf-8"))[
        "update_phase"
    ] == "bootstrap"
    assert (tmp_path / "organizador.db").read_bytes() == b"client database"

    application_files, application_manifest = _application_package()
    application_path = tmp_path / "application.zip"
    application_path.write_bytes(_zip_bytes(application_files))

    assert updater.apply_package(tmp_path, application_path, application_manifest) == STAGED_VERSION

    installed_version = json.loads((tmp_path / "version.json").read_text(encoding="utf-8"))
    assert installed_version == {"version": STAGED_VERSION}
    assert (tmp_path / "organizador.db").read_bytes() == b"client database"
    assert (tmp_path / "telegram_state_v11.json").read_text(encoding="utf-8") == '{"session":"client"}'
    assert (tmp_path / "update_config.json").read_text(encoding="utf-8") == '{"manifest_url": "client-local"}'
    assert not (tmp_path / ".update_journal.json").exists()
    assert not (tmp_path / ".update_status.json").exists()
    assert updater.healthcheck(tmp_path)["ok"]
