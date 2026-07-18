"""Open the GUI after attempting a non-blocking update check."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
UPDATER = APP_DIR / "updater.py"
GUI = APP_DIR / "gui_premium_v7.py"


def main() -> int:
    try:
        subprocess.run(
            [sys.executable, str(UPDATER), "--check-and-apply"],
            cwd=str(APP_DIR),
            check=False,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"No se pudo comprobar actualizaciones: {exc}")

    try:
        subprocess.Popen([sys.executable, str(GUI)], cwd=str(APP_DIR))
    except OSError as exc:
        print(f"No se pudo abrir la GUI: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
