import importlib.util
import io
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_VERSION = "1.0.42"


def _git_lines(*args):
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_show_text(ref):
    result = subprocess.run(
        ["git", "show", ref],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def _zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _load_updater(source_path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _version_key(tag):
    return tuple(int(part) for part in tag.removeprefix("v").split("."))


def _legacy_updater_tags():
    tags = _git_lines("tag", "--list", "v1.0.*")
    updater_tags = []
    for tag in tags:
        if _version_key(tag) <= (1, 0, 1):
            continue
        try:
            _git_show_text(f"{tag}:updater.py")
        except subprocess.CalledProcessError:
            continue
        updater_tags.append(tag)
    return sorted(updater_tags, key=_version_key)


def test_every_historical_updater_tag_can_apply_bootstrap_without_user_data_loss():
    bootstrap_files = {
        "updater.py": "new updater bridge",
        "version.json": json.dumps(
            {"version": BOOTSTRAP_VERSION, "update_phase": "bootstrap"}
        ),
    }
    manifest = {
        "version": BOOTSTRAP_VERSION,
        "package_kind": "bootstrap",
        "files": sorted(bootstrap_files),
    }
    package = _zip_bytes(bootstrap_files)
    failures = []
    checked = []

    for tag in _legacy_updater_tags():
        with tempfile.TemporaryDirectory(prefix="legacy_updater_tag_") as temp_name:
            install_root = Path(temp_name)
            updater_source = install_root / "updater.py"
            updater_source.write_text(_git_show_text(f"{tag}:updater.py"), encoding="utf-8")
            (install_root / "version.json").write_text(
                json.dumps({"version": tag.removeprefix("v")}),
                encoding="utf-8",
            )
            (install_root / "organizador.db").write_bytes(b"client database")
            (install_root / "telegram_state_v11.json").write_text(
                '{"session":"client"}',
                encoding="utf-8",
            )
            package_path = install_root / "bootstrap.zip"
            package_path.write_bytes(package)

            module_name = f"legacy_updater_{tag.replace('.', '_')}"
            updater = _load_updater(updater_source, module_name)
            try:
                installed_version = updater.apply_package(
                    install_root,
                    package_path,
                    manifest,
                )
            except Exception as exc:
                failures.append(f"{tag}: {type(exc).__name__}: {exc}")
                continue

            checked.append(tag)
            if installed_version != BOOTSTRAP_VERSION:
                failures.append(f"{tag}: returned {installed_version}")
            if updater_source.read_text(encoding="utf-8") != "new updater bridge":
                failures.append(f"{tag}: updater.py was not replaced")
            if (install_root / "organizador.db").read_bytes() != b"client database":
                failures.append(f"{tag}: organizador.db changed")
            if (install_root / "telegram_state_v11.json").read_text(encoding="utf-8") != '{"session":"client"}':
                failures.append(f"{tag}: telegram_state_v11.json changed")

    assert checked, "No historical updater tags were found"
    assert failures == []
