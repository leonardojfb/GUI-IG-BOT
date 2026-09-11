"""Open the GUI after a silent, non-blocking update check.

Runs windowless (launched via pythonw): the update check happens in-process so
no console window ever appears, and its result is written to a small status file
that the GUI reads to show a friendly in-app notice instead of a console error.
"""
from __future__ import annotations

import json
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


APP_DIR = Path(__file__).resolve().parent
GUI = APP_DIR / "gui_premium_v7.py"
STATUS_FILE = APP_DIR / ".update_status.json"


def _ensure_timezone_data() -> str:
    """Install tzdata once when Windows/Python lacks IANA timezone data.

    Fresh installations receive it through requirements.txt. This fallback also
    repairs existing installations after an automatic code-only update, without
    asking the partner to open a terminal or know about pip.
    """
    try:
        ZoneInfo("America/New_York")
        return ""
    except ZoneInfoNotFoundError:
        pass

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "tzdata",
            ],
            cwd=str(APP_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"No se pudo instalar el soporte horario requerido: {exc}"

    if result.returncode:
        return "No se pudo instalar el soporte horario requerido (tzdata)."

    try:
        ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        return "El soporte horario requerido (tzdata) no quedó disponible."
    return ""


def _ensure_pillow() -> str:
    """Install Pillow once when an updated installation lacks PIL.

    Automatic updates copy requirements.txt but do not execute the installer
    batch file. This repairs existing environments before the preview code
    imports PIL.
    """
    if importlib.util.find_spec("PIL") is not None:
        return ""

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "Pillow==12.2.0",
            ],
            cwd=str(APP_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"No se pudo instalar Pillow, requerido para Preview: {exc}"

    if result.returncode:
        return "No se pudo instalar Pillow, requerido para Preview."

    if importlib.util.find_spec("PIL") is None:
        return "Pillow se instalo, pero PIL no quedo disponible para Preview."
    return ""


def _run_update_check() -> bool:
    """Check for updates in-process (no console) and record the outcome.

    Any failure is non-fatal: the local app still opens. The GUI reads
    STATUS_FILE and, if the check failed, shows a gentle "configure your token"
    notice rather than dumping an error to a console.
    """
    try:
        previous_status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous_status = {}
    if isinstance(previous_status, dict) and previous_status.get("recovery_required") is True:
        return False

    messages: list[str] = []
    recovery_required = False
    try:
        from updater import check_and_apply

        check_and_apply(APP_DIR, status_callback=messages.append)
    except Exception as exc:  # noqa: BLE001 - update check must never block launch
        recovery_required = "RECOVERY_REQUIRED" in str(exc)
        if recovery_required:
            if not any("RECOVERY_REQUIRED" in message for message in messages):
                messages.append(str(exc))
        else:
            messages.append(f"{exc}. Se abrira la version local.")

    # The updater only appends "Se abrira la version local." on a real failure
    # (bad/missing token, no connection), not for "already up to date".
    error = next(
        (
            message
            for message in messages
            if "RECOVERY_REQUIRED" in message or "Se abrira la version local" in message
        ),
        "",
    )
    try:
        STATUS_FILE.write_text(
            json.dumps(
                {"error": error, "recovery_required": recovery_required},
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
    return not recovery_required


def _ensure_database() -> None:
    """Siembra la base de un cliente NUEVO desde la plantilla empaquetada, una sola vez.

    Copia organizador.default.db -> organizador.db SOLO si organizador.db no existe.
    Nunca sobrescribe la base de un cliente existente, así que sus datos (cuentas,
    tandas, historial) se conservan tras reinstalar o descomprimir encima. Si no hay
    plantilla, la app crea una base vacía sola al conectar (database.initialize)."""
    db = APP_DIR / "organizador.db"
    template = APP_DIR / "organizador.default.db"
    if db.exists() or not template.exists():
        return
    try:
        shutil.copy2(template, db)
    except OSError:
        pass  # la app creará una base vacía al conectar como respaldo


def _windowless_python() -> str:
    """Return pythonw.exe next to the current interpreter if it exists, so the
    GUI child also runs without a console; fall back to the interpreter."""
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return str(candidate) if candidate.exists() else sys.executable


def main() -> int:
    update_ready = _run_update_check()
    if update_ready is False:
        return 2

    timezone_error = _ensure_timezone_data()
    dependency_error = timezone_error or _ensure_pillow()

    _ensure_database()
    if dependency_error:
        try:
            STATUS_FILE.write_text(json.dumps({"error": dependency_error}), encoding="utf-8")
        except OSError:
            pass
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
