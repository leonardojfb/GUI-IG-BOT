"""Video overlays: place one or more images on selected frame ranges.

The GUI uses this module for both the single-frame preview and the final
render, so the coordinates, opacity and timing have one source of truth.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import tempfile
from pathlib import Path

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
EXTERNAL_PROCESS_TIMEOUT_SECONDS = 300


def _ffmpeg_tool_command(tool_name: str) -> str:
    executable_name = f"{tool_name}.exe" if os.name == "nt" else tool_name
    bundled = Path(__file__).resolve().parent / "tools" / "ffmpeg" / "bin" / executable_name
    if bundled.is_file():
        return str(bundled)
    return tool_name


def build_photo_video_pairs(videos: list[str], overlays: list[dict]) -> list[tuple[str, dict, int]]:
    return [
        (video, overlay, photo_index)
        for photo_index, overlay in enumerate(overlays, start=1)
        for video in videos
    ]


def describe_overlay_log(overlays: list[dict]) -> list[dict]:
    result = []
    for overlay in overlays or []:
        result.append({
            "photo_path": overlay.get("photo_path") or overlay.get("photo"),
            "start_frame": overlay.get("start_frame"),
            "end_frame": overlay.get("end_frame"),
            "start_time": overlay.get("start_time"),
            "end_time": overlay.get("end_time"),
            "position": overlay.get("position"),
            "x": overlay.get("x"),
            "y": overlay.get("y"),
            "size": overlay.get("size"),
            "opacity": overlay.get("opacity"),
        })
    return result


def timestamp_to_source_frame(timestamp: float, fps: float) -> int:
    """Convert a shared timeline instant into the frame number of one source."""
    return max(0, round(max(0.0, float(timestamp)) * max(0.0, float(fps))))


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=_NO_WINDOW,
            timeout=EXTERNAL_PROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "El proceso de FFmpeg/FFprobe superó el tiempo límite de "
            f"{EXTERNAL_PROCESS_TIMEOUT_SECONDS} segundos. Revisá el archivo e intentá nuevamente."
        ) from error
    except OSError as error:
        executable = cmd[0] if cmd else "FFmpeg/FFprobe"
        raise RuntimeError(
            f"No se pudo iniciar FFmpeg/FFprobe ({executable}). "
            f"Verificá que esté instalado y disponible. Detalle: {error}"
        ) from error


def probe_video(path: str) -> dict:
    result = _run([
        _ffmpeg_tool_command("ffprobe"), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,avg_frame_rate,duration",
        "-show_entries", "format=duration", "-of", "json", path,
    ])
    if result.returncode:
        detail = (result.stderr or "").strip()[-600:]
        message = f"No se pudo leer el video '{path}' con FFprobe."
        if detail:
            message += f" Detalle: {detail}"
        raise RuntimeError(message)
    data = json.loads(result.stdout)
    stream = (data.get("streams") or [{}])[0]
    def number(value, fallback=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
    rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "30/1"
    try:
        num, den = rate.split("/")
        fps = number(num) / max(number(den), 1)
    except (AttributeError, ValueError):
        fps = 30.0
    duration = number(stream.get("duration"), 0.0) or number(data.get("format", {}).get("duration"), 0.0)
    return {"width": int(number(stream.get("width"))), "height": int(number(stream.get("height"))),
            "fps": fps or 30.0, "duration": duration}


def _ratio_size(width: int, height: int, size_percent: float, ratio: str) -> tuple[int, int]:
    """Return an overlay canvas where 100% covers the entire video frame."""
    scale = max(0.01, min(1.0, size_percent / 100))
    base_w = max(2, round(width * scale))
    base_h = max(2, round(height * scale))
    if ratio == "Original":
        return base_w, base_h
    try:
        rw, rh = (float(x) for x in ratio.split(":"))
        # The selected ratio covers the requested percentage of the video.
        # At 100%, at least one side may exceed the frame; it is intentionally
        # cropped on that side so the visible result fills the entire video.
        return max(base_w, round(base_h * rw / rh)), max(base_h, round(base_w * rh / rw))
    except (ValueError, TypeError):
        return base_w, base_h


def _xy(width: int, height: int, ow: int, oh: int, position: str, x: float, y: float) -> tuple[int, int]:
    positions = {
        "Centro": ((width - ow) / 2, (height - oh) / 2),
        "Arriba izquierda": (0, 0), "Arriba centro": ((width - ow) / 2, 0),
        "Arriba derecha": (width - ow, 0), "Abajo izquierda": (0, height - oh),
        "Abajo centro": ((width - ow) / 2, height - oh), "Abajo derecha": (width - ow, height - oh),
    }
    # Manual percentages refer to the available placement range, not to the
    # top-left corner: 0 = left/top, 50 = centered, 100 = right/bottom.
    # Negative coordinates are valid when a 100%-sized overlay is larger than
    # one side of the video and must be cropped symmetrically.
    px, py = positions.get(position, ((width - ow) * x / 100, (height - oh) * y / 100))
    return round(px), round(py)


def _overlay_filter(info: dict, item: dict, input_index: int) -> str:
    ow, oh = _ratio_size(info["width"], info["height"], float(item["size"]), item["ratio"])
    x, y = _xy(info["width"], info["height"], ow, oh, item["position"], float(item["x"]), float(item["y"]))
    start = max(0, int(item["frame"]))
    end = start + max(1, round(float(item["duration_ms"]) * info["fps"] / 1000)) - 1
    opacity = 0 if float(item["size"]) <= 0 else max(0, min(1, float(item["opacity"]) / 100))
    return (f"[{input_index}:v]scale={ow}:{oh}:force_original_aspect_ratio=increase,"
            f"crop={ow}:{oh},format=rgba,"
            f"colorchannelmixer=aa={opacity}[ov{input_index}];"
            f"[v{input_index - 1}][ov{input_index}]overlay={x}:{y}:"
            f"enable='between(n,{start},{end})'[v{input_index}]")


def render_video(input_path: str, output_path: str, overlays: list[dict], ffmpeg_threads=None) -> str:
    info = probe_video(input_path)
    if not overlays:
        raise ValueError("Agregá al menos una foto.")
    base_cmd = [_ffmpeg_tool_command("ffmpeg"), "-y", "-i", input_path]
    for item in overlays:
        base_cmd += ["-loop", "1", "-i", item["photo"]]
    filters = [f"[0:v]format=yuv420p[v0]"]
    for index, item in enumerate(overlays, start=1):
        filters.append(_overlay_filter(info, item, index))
    common_args = [
        "-filter_complex", ";".join(filters), "-map", f"[v{len(overlays)}]", "-map", "0:a?",
    ]
    encoder_attempts = [
        ["-c:v", "h264_nvenc", "-preset", "p4", "-cq:v", "20", "-pix_fmt", "yuv420p"],
        ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"],
    ]
    last_stderr = ""
    for encoder_args in encoder_attempts:
        cmd = base_cmd + common_args + encoder_args + ["-c:a", "aac", "-b:a", "192k"]
        if ffmpeg_threads and "libx264" in encoder_args:
            cmd += ["-threads", str(ffmpeg_threads)]
        cmd += ["-t", f"{info['duration']:.6f}", output_path]
        result = _run(cmd)
        if result.returncode == 0:
            return output_path
        if os.path.exists(output_path):
            os.remove(output_path)
        last_stderr = (result.stderr or "")[-1800:]
    raise RuntimeError(
        f"FFmpeg no pudo renderizar '{input_path}' en '{output_path}': "
        f"{last_stderr or 'sin detalle de stderr.'}"
    )


def render_preview(
    input_path: str,
    overlays: list[dict],
    output_path: str | None = None,
    timestamp: float | None = None,
) -> tuple[str, float]:
    """Extract a selected (or useful random) frame and composite the photos."""
    from PIL import Image, ImageOps
    info = probe_video(input_path)
    if info["duration"] <= 0:
        raise ValueError("El video no tiene una duración válida.")
    total_frames = max(1, round(info["duration"] * info["fps"]))
    if timestamp is None:
        active_frames = []
        for item in overlays:
            start = max(0, int(item["frame"]))
            count = max(1, round(float(item["duration_ms"]) * info["fps"] / 1000))
            active_frames.extend(range(start, min(total_frames, start + count)))
        # A useful random preview should normally show at least one selected photo.
        frame = random.choice(active_frames) if active_frames else random.randrange(total_frames)
        timestamp = frame / info["fps"]
    else:
        timestamp = max(0.0, min(float(timestamp), info["duration"]))
    if output_path is None:
        handle, output_path = tempfile.mkstemp(prefix="ig_preview_", suffix=".png")
        os.close(handle)
    result = _run([_ffmpeg_tool_command("ffmpeg"), "-y", "-ss", str(timestamp), "-i", input_path, "-frames:v", "1", output_path])
    if result.returncode:
        stderr = (result.stderr or "")[-1800:]
        raise RuntimeError(
            f"FFmpeg no pudo generar el preview de '{input_path}': "
            f"{stderr or 'sin detalle de stderr.'}"
        )
    canvas = Image.open(output_path).convert("RGBA")
    for item in overlays:
        if float(item["size"]) <= 0:
            continue
        start = int(item["frame"]) / info["fps"]
        end = start + float(item["duration_ms"]) / 1000
        if not start <= timestamp <= end:
            continue
        photo = Image.open(item["photo"]).convert("RGBA")
        ow, oh = _ratio_size(canvas.width, canvas.height, float(item["size"]), item["ratio"])
        photo = ImageOps.fit(photo, (ow, oh), method=Image.Resampling.LANCZOS)
        x, y = _xy(canvas.width, canvas.height, ow, oh, item["position"], float(item["x"]), float(item["y"]))
        alpha = photo.getchannel("A").point(lambda value: round(value * float(item["opacity"]) / 100))
        photo.putalpha(alpha)
        canvas.alpha_composite(photo, (x, y))
    canvas.convert("RGB").save(output_path)
    return output_path, timestamp
