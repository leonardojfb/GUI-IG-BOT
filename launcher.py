"""Open the GUI after a silent, non-blocking update check.

Runs windowless (launched via pythonw): the update check happens in-process so
no console window ever appears, and its result is written to a small status file
that the GUI reads to show a friendly in-app notice instead of a console error.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
GUI = APP_DIR / "gui_premium_v7.py"
STATUS_FILE = APP_DIR / ".update_status.json"


def _run_update_check() -> None:
    """Check for updates in-process (no console) and record the outcome.

    Any failure is non-fatal: the local app still opens. The GUI reads
    STATUS_FILE and, if the check failed, shows a gentle "configure your token"
    notice rather than dumping an error to a console.
    """
    messages: list[str] = []
    try:
        from updater import check_and_apply

        check_and_apply(APP_DIR, status_callback=messages.append)
    except Exception as exc:  # noqa: BLE001 - update check must never block launch
        messages.append(f"{exc}. Se abrira la version local.")

    # The updater only appends "Se abrira la version local." on a real failure
    # (bad/missing token, no connection), not for "already up to date".
    error = next((m for m in messages if "Se abrira la version local" in m), "")
    try:
        STATUS_FILE.write_text(json.dumps({"error": error}), encoding="utf-8")
    except OSError:
        pass


def _windowless_python() -> str:
    """Return pythonw.exe next to the current interpreter if it exists, so the
    GUI child also runs without a console; fall back to the interpreter."""
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return str(candidate) if candidate.exists() else sys.executable


def main() -> int:
    _run_update_check()
    try:
        subprocess.Popen([_windowless_python(), str(GUI)], cwd=str(APP_DIR))
    except OSError as exc:
        # No console to print to; record it so the GUI can surface it if needed.
        try:
            STATUS_FILE.write_text(
                json.dumps({"error": f"No se pudo abrir la GUI: {exc}"}), encoding="utf-8"
            )
        except OSError:
            pass
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
