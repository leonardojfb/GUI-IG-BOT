from types import SimpleNamespace

import launcher


def test_ensure_pillow_installs_missing_pil(monkeypatch):
    calls = []
    specs = iter([None, object()])

    monkeypatch.setattr(launcher.importlib.util, "find_spec", lambda name: next(specs))
    monkeypatch.setattr(
        launcher.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or SimpleNamespace(returncode=0),
    )

    assert launcher._ensure_pillow() == ""
    assert calls
    assert calls[0][0][:5] == [
        launcher.sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
    ]
    assert calls[0][0][-1] == "Pillow==12.2.0"


def test_ensure_pillow_skips_pip_when_pil_exists(monkeypatch):
    calls = []

    monkeypatch.setattr(launcher.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        launcher.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or SimpleNamespace(returncode=0),
    )

    assert launcher._ensure_pillow() == ""
    assert calls == []


def test_launcher_still_opens_gui_when_optional_dependency_repair_fails(monkeypatch, tmp_path):
    opened = []
    status_file = tmp_path / ".update_status.json"

    monkeypatch.setattr(launcher, "STATUS_FILE", status_file)
    monkeypatch.setattr(launcher, "_ensure_timezone_data", lambda: "")
    monkeypatch.setattr(launcher, "_ensure_pillow", lambda: "No se pudo instalar Pillow.")
    monkeypatch.setattr(launcher, "_ensure_database", lambda: None)
    monkeypatch.setattr(launcher, "_run_update_check", lambda: None)
    monkeypatch.setattr(launcher, "_windowless_python", lambda: "pythonw.exe")
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        lambda command, **kwargs: opened.append((command, kwargs)) or SimpleNamespace(pid=1234),
    )

    assert launcher.main() == 0
    assert opened
    assert "No se pudo instalar Pillow." in status_file.read_text(encoding="utf-8")


def test_launcher_does_not_open_gui_when_update_requires_recovery(monkeypatch):
    opened = []

    monkeypatch.setattr(launcher, "_ensure_timezone_data", lambda: "")
    monkeypatch.setattr(launcher, "_ensure_pillow", lambda: "")
    monkeypatch.setattr(launcher, "_ensure_database", lambda: None)
    monkeypatch.setattr(launcher, "_run_update_check", lambda: False)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        lambda command, **kwargs: opened.append((command, kwargs)),
    )

    assert launcher.main() == 2
    assert opened == []


def test_recovery_required_marker_blocks_later_launch_without_being_cleared(
    monkeypatch, tmp_path
):
    status_file = tmp_path / ".update_status.json"
    status_file.write_text(
        '{"error":"RECOVERY_REQUIRED: reparar","recovery_required":true}',
        encoding="utf-8",
    )
    monkeypatch.setattr(launcher, "APP_DIR", tmp_path)
    monkeypatch.setattr(launcher, "STATUS_FILE", status_file)

    assert launcher._run_update_check() is False
    persisted = status_file.read_text(encoding="utf-8")
    assert '"recovery_required":true' in persisted.replace(" ", "")
