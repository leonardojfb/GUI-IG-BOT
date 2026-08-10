import os
import shutil
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
_FFMPEG_TOOLS = {"ffmpeg", "ffprobe"}


def ensure_stdout_utf8():
    """Make stdout/stderr tolerate the emoji this app prints everywhere.

    On a Windows console whose codepage isn't UTF-8 (cp1252/850 are common
    non-English-locale defaults, and this is the case with no PYTHONIOENCODING
    set), print()-ing an emoji raises UnicodeEncodeError and crashes whatever
    was running. errors="replace" means a character neither UTF-8 nor the
    original encoding could show still prints as-is instead of crashing.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def ffmpeg_tool_path(tool_name):
    if tool_name not in _FFMPEG_TOOLS:
        raise ValueError(f"Herramienta FFmpeg desconocida: {tool_name}")
    executable_name = f"{tool_name}.exe" if os.name == "nt" else tool_name
    return APP_DIR / "tools" / "ffmpeg" / "bin" / executable_name


def ffmpeg_tool_command(tool_name):
    bundled = ffmpeg_tool_path(tool_name)
    if bundled.is_file():
        return str(bundled)
    return tool_name


def ffmpeg_tool_exists(tool_name):
    command = ffmpeg_tool_command(tool_name)
    return Path(command).is_file() or shutil.which(command) is not None
