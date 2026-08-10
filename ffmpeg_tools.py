"""Resolve bundled FFmpeg tools before falling back to PATH."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
_KNOWN_TOOLS = {"ffmpeg", "ffprobe"}


def bundled_tool_path(tool_name: str) -> Path:
    if tool_name not in _KNOWN_TOOLS:
        raise ValueError(f"Herramienta FFmpeg desconocida: {tool_name}")
    executable_name = f"{tool_name}.exe" if os.name == "nt" else tool_name
    return APP_DIR / "tools" / "ffmpeg" / "bin" / executable_name


def tool_command(tool_name: str) -> str:
    bundled = bundled_tool_path(tool_name)
    if bundled.is_file():
        return str(bundled)
    return tool_name


def tool_exists(tool_name: str) -> bool:
    command = tool_command(tool_name)
    return Path(command).is_file() or shutil.which(command) is not None


def ffmpeg_command() -> str:
    return tool_command("ffmpeg")


def ffprobe_command() -> str:
    return tool_command("ffprobe")
