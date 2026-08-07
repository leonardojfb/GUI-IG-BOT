# Static import and executable inventory

## Method

The inventory was produced from non-test Python sources with these searches:

```powershell
rg -n '^(import|from) ' --glob '*.py' --glob '!tests/**' .
rg -n -i 'importlib|__import__|subprocess|Popen|ffmpeg|ffprobe|shell=True|os\.system' --glob '*.py' --glob '!tests/**' .
rg -n -i 'requests\.|urllib|api\.telegram\.org|github\.com|raw\.githubusercontent\.com' --glob '*.py' --glob '!tests/**' .
```

Results are summarized by module group rather than copying source lines. Literal configuration and credential values are intentionally excluded.

## Local import graph

```text
launcher.py -> updater.py -> urllib / archive / package-apply boundary
launcher.py -> gui_premium_v7.py (child process)

gui_premium_v7.py -> database.py
                  -> Organizador.py -> database.py, console_encoding.py
                  -> organizadortg.py -> database.py, console_encoding.py
                  -> videos.py -> database.py, console_encoding.py
                  -> video_editor.py
                  -> metadata_pool.py
                  -> updater.py
                  -> styles.colors / styles.components

telegram_core.py -> database.py
debug_db.py, make_default_db.py, vercuentas.py -> database.py
gui_unificada.py -> database.py, Organizador.py, organizadortg.py, videos.py, metadata_pool.py
```

`gui_unificada.py` is included because it is tracked source discovered by the static inventory; it is not the documented launch child for this baseline.

## External Python dependencies by group

| Module group | External imports observed |
| --- | --- |
| GUI | `customtkinter`, `tkinter`, `requests`, `PIL`, `google.generativeai`, standard-library threading/filesystem/JSON/time modules |
| Storage | `sqlite3`, standard-library `json` and filesystem modules |
| Telegram | `requests`, `pyrogram`, standard-library scheduling, temporary-file, subprocess, and zone-info modules |
| Multimedia | `PIL`, standard-library `subprocess`, filesystem, JSON, temporary-file, hashing, random, and math modules |
| Updater | standard-library `urllib`, `hashlib`, `zipfile`, `tempfile`, filesystem, JSON, and argument parsing modules |

## Dynamic import and executable boundaries

| Boundary | Importers / callers | Static result |
| --- | --- | --- |
| Dynamic imports | All non-test Python files searched | No `importlib.import_module` or `__import__` use found. |
| GUI launch | `launcher.py` | `subprocess.Popen` starts the GUI child. |
| Dependency/time-zone recovery | `launcher.py` | `subprocess.run` is used before normal launch when needed. |
| Media tooling | `videos.py`, `video_editor.py`, `metadata_pool.py`, `organizadortg.py` | `subprocess.run` creates the FFmpeg/FFprobe-style child-process boundary. |
| Shell execution | All non-test Python files searched | No `os.system` or `shell=True` result was identified by the prescribed static search. |

## Network call boundaries

| Components | Client family | Purpose at the boundary |
| --- | --- | --- |
| `gui_premium_v7.py` | `requests` | GUI account-checking HTTP workflow. |
| `organizadortg.py` | `requests` | Telegram-facing HTTP workflow. |
| `updater.py` | `urllib.request` | Configured update metadata and release asset retrieval. |

The inventory identifies code boundaries, not a live call trace. No network or Telegram action was started during this audit task.
