"""Codec and color contract for Forge's iPhone-style MOV outputs."""

from __future__ import annotations

import json
import os
import re
import subprocess
from fractions import Fraction
from pathlib import Path

from console_encoding import ffmpeg_tool_command


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def probe_file(path: str | Path) -> dict:
    """Read all stream and format fields needed by preflight and output QC."""
    result = subprocess.run([
        ffmpeg_tool_command("ffprobe"), "-v", "error", "-show_error",
        "-show_format", "-show_streams", "-of", "json", str(path),
    ], capture_output=True, text=True, creationflags=_NO_WINDOW)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe falló en {os.path.basename(path)}: {result.stderr[-500:]}")
    return json.loads(result.stdout)


def runtime_capabilities() -> set[str]:
    """Report the required FFmpeg encoders and color filters actually present."""
    ffmpeg = ffmpeg_tool_command("ffmpeg")
    available: set[str] = set()
    for argument, names in (("-encoders", ("libx265", "aac")), ("-filters", ("zscale",))):
        result = subprocess.run([ffmpeg, "-hide_banner", argument], capture_output=True,
                                text=True, creationflags=_NO_WINDOW)
        if result.returncode != 0:
            raise RuntimeError(f"No se pudieron consultar las capacidades de FFmpeg: {result.stderr[-500:]}")
        for name in names:
            if re.search(rf"(?m)^\s*\S+\s+{re.escape(name)}\s", result.stdout):
                available.add(name)
    return available


PROFILES = {
    "iphone_hlg": {
        "profile": "Main 10",
        "pix_fmt": "yuv420p10le",
        "color_primaries": "bt2020",
        "color_transfer": "arib-std-b67",
        "color_space": "bt2020nc",
    },
    "iphone_sdr": {
        "profile": "Main",
        "pix_fmt": "yuv420p",
        "color_primaries": "bt709",
        "color_transfer": "bt709",
        "color_space": "bt709",
    },
}


def validate_probe(data: dict, profile: str, *, expect_audio: bool) -> list[str]:
    """Return field-level mismatches for a probed Forge output."""
    if profile not in PROFILES:
        raise ValueError(f"Perfil de Forge desconocido: {profile}")
    problems: list[str] = []
    tags = (data.get("format") or {}).get("tags") or {}
    if tags.get("major_brand") != "qt  ":
        problems.append("format.major_brand: se esperaba qt")

    streams = data.get("streams") or []
    videos = [item for item in streams if item.get("codec_type") == "video"]
    audios = [item for item in streams if item.get("codec_type") == "audio"]
    if len(videos) != 1:
        problems.append(f"streams.video: se esperaba 1, hay {len(videos)}")
    if len(audios) != int(expect_audio):
        problems.append(f"streams.audio: se esperaba {int(expect_audio)}, hay {len(audios)}")
    if any(item.get("codec_type") not in ("video", "audio") for item in streams):
        problems.append("streams.data: pista de datos inesperada")

    if videos:
        video = videos[0]
        expected = {
            "codec_name": "hevc",
            "codec_tag_string": "hvc1",
            "color_range": "tv",
            **PROFILES[profile],
        }
        for field, value in expected.items():
            if video.get(field) != value:
                problems.append(f"video.{field}: {video.get(field)!r} != {value!r}")
        if not video.get("width") or not video.get("height"):
            problems.append("video.dimensions: faltan ancho o alto")
        try:
            fps = float(Fraction(video.get("avg_frame_rate") or "0"))
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        if not 23.5 <= fps <= 24.5:
            problems.append(f"video.frame_rate: {fps:.3f} fuera de ~24 fps")

    if audios:
        audio = audios[0]
        for field, value in {"codec_name": "aac", "profile": "LC", "sample_rate": "48000", "channels": 2}.items():
            if audio.get(field) != value:
                problems.append(f"audio.{field}: {audio.get(field)!r} != {value!r}")
    return problems
