"""Regression tests for EMOJI_PRINT_CRASH.

videos.py, Organizador.py, organizadortg.py and gui_premium_v7.py all print
emoji unconditionally (progress messages like "Renderizando...", "Enviando
a...", warnings, etc). On a Windows console whose codepage isn't UTF-8 --
this machine's default is codepage 850, and PYTHONIOENCODING/PYTHONUTF8 are
unset -- print() of an emoji raises UnicodeEncodeError, which videos.py's
render_tanda() re-raises as a hard Exception, aborting the whole Tandas
render. tests/smoke_execute_plan.py already had a `sys.stdout.reconfigure`
workaround (someone already hit this once); nothing in production code
guarded against it.
"""
import importlib
import io
import sys
import subprocess

import pytest


def _strict_cp1252_stream():
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")


def test_ensure_stdout_utf8_makes_emoji_print_safe(monkeypatch):
    import console_encoding

    fake_stdout = _strict_cp1252_stream()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    with pytest.raises(UnicodeEncodeError):
        print("\U0001f3ac reproduction check")

    console_encoding.ensure_stdout_utf8()

    print("\U0001f3ac should not raise anymore")
    sys.stdout.flush()
    assert sys.stdout.encoding.lower().replace("-", "") == "utf8"


def test_missing_stderr_descriptor_cannot_be_reused_for_database(tmp_path):
    """Tk writes errors to fd 2 even when a GUI has no console stream."""
    target = tmp_path / "database-like-file"
    script = (
        "import os,sys; from console_encoding import ensure_stdout_utf8; "
        "os.close(2); ensure_stdout_utf8(); "
        "fd=os.open(sys.argv[1],os.O_CREAT|os.O_WRONLY); "
        "os.write(2,b'Tk callback error'); os.close(fd); os._exit(0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(target)],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == b""


@pytest.mark.parametrize("module_name", ["videos", "Organizador"])
def test_module_import_leaves_stdout_emoji_safe(module_name, monkeypatch):
    """videos.py and Organizador.py have no module-level stateful side effects
    (no DB connections opened at import time), so reload-testing them is safe
    and gives real behavioral proof instead of a source-string match.
    """
    fake_stdout = _strict_cp1252_stream()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    module = importlib.import_module(module_name)
    importlib.reload(module)

    print("\U0001f3ac emoji smoke check after reload")
    sys.stdout.flush()


def _method_source_from(path, marker):
    text = path.read_text(encoding="utf-8")
    idx = text.index(marker)
    return text[max(0, idx - 200):idx + 200]


def test_organizadortg_and_gui_call_ensure_stdout_utf8():
    """organizadortg.py has a module-level `db = DatabaseManager()`, and
    gui_premium_v7.py builds a real Tk app on import of its top-level code
    paths -- reload()ing either mid-test-session risks corrupting global
    state for every test that runs afterward (this is exactly the class of
    bug fixed in tests/support/e2e_pipeline.py's patched_modules() this same
    pass). A static check that they call the shared guard is enough here;
    the reload-based test above already proves the guard itself works.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    organizadortg_src = (repo_root / "organizadortg.py").read_text(encoding="utf-8")
    gui_src = (repo_root / "gui_premium_v7.py").read_text(encoding="utf-8")

    assert "ensure_stdout_utf8" in organizadortg_src
    assert "ensure_stdout_utf8" in gui_src


def test_ffmpeg_tool_command_prefers_bundled_windows_binary(tmp_path, monkeypatch):
    import console_encoding

    bundled_bin = tmp_path / "tools" / "ffmpeg" / "bin"
    bundled_bin.mkdir(parents=True)
    ffmpeg_path = bundled_bin / "ffmpeg.exe"
    ffmpeg_path.write_bytes(b"binary")
    monkeypatch.setattr(console_encoding, "APP_DIR", tmp_path)

    assert console_encoding.ffmpeg_tool_command("ffmpeg") == str(ffmpeg_path)


def test_ffmpeg_tool_command_falls_back_to_path_name_when_bundled_binary_is_missing(
    tmp_path, monkeypatch,
):
    import console_encoding

    monkeypatch.setattr(console_encoding, "APP_DIR", tmp_path)

    assert console_encoding.ffmpeg_tool_command("ffprobe") == "ffprobe"
