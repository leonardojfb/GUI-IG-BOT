"""Codec and color contract for Forge's iPhone-style MOV outputs."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from console_encoding import ffmpeg_tool_command


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# Initial SDR→HLG grade: ~matching SDR-view midtones on the supplied pilot.
# User HDR/SDR display calibration may adjust this value before release.
SDR_TO_HLG_NPL = 291

# Broad initial gates until the HDR/SDR display pilot establishes final values.
VISUAL_GATE_LIMITS = {"YAVG": (12.0, 0.18), "YLOW": (15.0, 0.30),
                      "YHIGH": (15.0, 0.20), "SATAVG": (5.0, 0.30)}


def probe_file(path: str | Path) -> dict:
    """Read all stream and format fields needed by preflight and output QC."""
    result = subprocess.run([
        ffmpeg_tool_command("ffprobe"), "-v", "error", "-show_error",
        "-show_format", "-show_streams", "-of", "json", str(path),
    ], capture_output=True, text=True, creationflags=_NO_WINDOW)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe falló en {os.path.basename(path)}: {result.stderr[-500:]}")
    return json.loads(result.stdout)


def top_level_boxes(path: str | Path) -> list[str]:
    """Read MOV top-level atom order without loading the media payload."""
    boxes = []
    total = Path(path).stat().st_size
    with open(path, "rb") as file:
        while file.tell() < total:
            start = file.tell()
            header = file.read(8)
            if len(header) != 8:
                raise ValueError(f"Átomo MOV truncado en {start}")
            size = int.from_bytes(header[:4], "big")
            name = header[4:].decode("ascii", errors="replace")
            header_size = 8
            if size == 1:
                extended = file.read(8)
                if len(extended) != 8:
                    raise ValueError(f"Átomo MOV extendido truncado en {start}")
                size = int.from_bytes(extended, "big")
                header_size = 16
            elif size == 0:
                size = total - start
            if size < header_size or start + size > total:
                raise ValueError(f"Tamaño inválido para átomo MOV {name}")
            boxes.append(name)
            file.seek(start + size)
    return boxes


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


def next_copy_number(output_dir: str | Path, source_id: str) -> int:
    """Reserve after both legacy MP4 and new MOV siblings of a source."""
    pattern = re.compile(rf"^{re.escape(source_id)}__c(\d+)\.(?:mp4|mov)$", re.I)
    maximum = 0
    for item in Path(output_dir).iterdir():
        if item.is_file():
            match = pattern.match(item.name)
            if match:
                maximum = max(maximum, int(match.group(1)))
    return maximum + 1


def classify_color(data: dict) -> str:
    video = next((stream for stream in data.get("streams", [])
                  if stream.get("codec_type") == "video"), {})
    triplet = (video.get("color_primaries"), video.get("color_transfer"),
               video.get("color_space"))
    if triplet == ("bt709", "bt709", "bt709"):
        return "sdr"
    if triplet == ("bt2020", "arib-std-b67", "bt2020nc"):
        return "hlg"
    return "unknown"


def preflight_batch(
    probes: dict[str, dict], profile: str, *,
    known_untagged_sdr: set[str] | None = None,
) -> dict:
    """Classify every source; never silently infer color from an unknown file."""
    if profile not in PROFILES:
        raise ValueError(f"Perfil de Forge desconocido: {profile}")
    known_untagged_sdr = known_untagged_sdr or set()
    counts = {"sdr": 0, "hlg": 0, "unknown": 0}
    blocked: dict[str, str] = {}
    assumptions: dict[str, str] = {}
    sources: dict[str, str] = {}
    for name, data in probes.items():
        color = classify_color(data)
        if color == "unknown" and name in known_untagged_sdr:
            video = next((stream for stream in data.get("streams", [])
                          if stream.get("codec_type") == "video"), {})
            if not any(video.get(field) for field in
                       ("color_primaries", "color_transfer", "color_space")):
                color = "sdr"
                assumptions[name] = "SDR BT.709 sin tags (calibrado)"
        counts[color] += 1
        sources[name] = color
        if color == "unknown":
            blocked[name] = "Color ausente, parcial o no soportado"
        elif color == "hlg" and profile == "iphone_sdr":
            blocked[name] = "Conversión HLG→SDR aún no calibrada"
    return {"counts": counts, "sources": sources, "blocked": blocked,
            "assumptions": assumptions}


def _visual_metric_frames(path: str | Path, color: str) -> dict[str, list[float]]:
    """Measure sampled video in one common 8-bit SDR viewing transform."""
    if color not in {"sdr", "hlg"}:
        raise ValueError(f"Color no medible: {color}")
    filters = ["fps=1"]
    if color == "hlg":
        filters += ["zscale=t=linear:npl=100", "format=gbrpf32le",
                    "tonemap=tonemap=hable:desat=0",
                    "zscale=t=bt709:p=bt709:m=bt709:r=limited", "format=yuv420p"]
    filters += ["scale=256:-2", "signalstats", "metadata=mode=print"]
    result = subprocess.run([
        ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "info",
        "-i", str(path), "-an", "-vf", ",".join(filters),
        "-f", "null", os.devnull,
    ], capture_output=True, text=True, creationflags=_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(f"No se pudo medir color en {Path(path).name}: {result.stderr[-500:]}")
    values = {field: [float(number) for number in re.findall(
        rf"lavfi\.signalstats\.{field}=([0-9.]+)", result.stderr)]
        for field in VISUAL_GATE_LIMITS}
    if any(not numbers for numbers in values.values()):
        raise RuntimeError(f"No hay métricas visuales en {Path(path).name}")
    return values


def visual_metrics(path: str | Path, color: str) -> dict[str, float]:
    """Summarize samples spanning the full video."""
    frames = _visual_metric_frames(path, color)
    return {field: sum(numbers) / len(numbers) for field, numbers in frames.items()}


def assess_visual_change(
    source: str | Path, output: str | Path, *, source_color: str, output_color: str,
) -> tuple[list[str], dict]:
    """Reject large changes in brightness, contrast distribution or saturation."""
    before_frames = _visual_metric_frames(source, source_color)
    after_frames = _visual_metric_frames(output, output_color)
    before = {field: sum(values) / len(values) for field, values in before_frames.items()}
    after = {field: sum(values) / len(values) for field, values in after_frames.items()}
    errors = []
    for field, (absolute, relative) in VISUAL_GATE_LIMITS.items():
        gap = abs(after[field] - before[field])
        if gap > max(absolute, before[field] * relative):
            errors.append(f"{field}: fuente {before[field]:.1f}, salida {after[field]:.1f}")
        source_samples = before_frames[field]
        output_samples = after_frames[field]
        if abs(len(source_samples) - len(output_samples)) > 1:
            errors.append(f"{field}: distinta cantidad de muestras visuales")
        for index, (source_value, output_value) in enumerate(
                zip(source_samples, output_samples)):
            if abs(output_value - source_value) > max(absolute, source_value * relative):
                errors.append(f"{field}: diferencia en segundo {index}")
                break
    return errors, {"source": before, "output": after,
                    "limits": VISUAL_GATE_LIMITS, "errors": errors}


def render_iphone_video(
    input_path: str | Path,
    output_path: str | Path,
    meta: dict,
    profile: str,
    source_color: str,
    *,
    video_filters: str = "",
    audio_filter: str | None = None,
    start: float = 0.0,
    duration: float | None = None,
    threads: int | None = None,
    include_location: bool = False,
) -> None:
    """Encode a MOV from an explicitly classified color source."""
    if profile not in PROFILES or source_color not in {"sdr", "hlg"}:
        raise ValueError(f"Perfil/color no admitido: {profile}/{source_color}")
    if profile == "iphone_sdr" and source_color == "hlg":
        raise ValueError("Conversión HLG→SDR no calibrada; use iPhone HLG")
    if Path(output_path).suffix.lower() != ".mov":
        raise ValueError("El perfil iPhone requiere un archivo .mov")

    filters = [(
        "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709"
        if source_color == "sdr" else
        "setparams=color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc"
    )]
    if video_filters:
        filters.append(video_filters)
    if source_color == "sdr" and profile == "iphone_hlg":
        # Decode BT.709 to linear light, convert primaries, then encode HLG.
        filters.append("zscale=transfer=linear:npl=100,format=gbrpf32le,"
                       "zscale=primaries=bt2020:transfer=arib-std-b67:matrix=bt2020nc:"
                       f"range=limited:npl={SDR_TO_HLG_NPL}")
    filters.extend(["crop=trunc(iw/2)*2:trunc(ih/2)*2", "setsar=1",
                    f"format={PROFILES[profile]['pix_fmt']}"])
    spec = PROFILES[profile]
    command = [ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y"]
    if start:
        command += ["-ss", f"{start:.3f}"]
    command += ["-i", str(input_path), "-map", "0:v:0", "-map", "0:a:0?", "-dn", "-sn"]
    if duration is not None:
        command += ["-t", f"{duration:.3f}"]
    command += ["-vf", ",".join(filters)]
    if audio_filter:
        command += ["-af", audio_filter]
    command += ["-r", "24", "-c:v", "libx265", "-preset", "medium", "-crf", "18",
                "-profile:v", "main10" if profile == "iphone_hlg" else "main",
                "-x265-params", ("colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc:info=0"
                                 if profile == "iphone_hlg" else
                                 "colorprim=bt709:transfer=bt709:colormatrix=bt709:info=0"),
                "-pix_fmt", spec["pix_fmt"], "-tag:v", "hvc1", "-g", "20", "-keyint_min", "20",
                "-color_range", "tv", "-color_primaries", spec["color_primaries"],
                "-color_trc", spec["color_transfer"], "-colorspace", spec["color_space"],
                "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
    if threads:
        command += ["-threads", str(threads)]
    command += ["-map_metadata", "-1", "-map_chapters", "-1",
                "-movflags", "use_metadata_tags", "-metadata", "encoder=",
                "-metadata:s:v:0", "encoder=", "-metadata:s:a:0", "encoder=",
                "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
                "-metadata", "com.apple.quicktime.make=Apple",
                "-metadata", f"com.apple.quicktime.model={meta['iphone_model']}",
                "-metadata", f"com.apple.quicktime.software={meta['ios_version']}"]
    if include_location and meta.get("lat") and meta.get("lon"):
        command += ["-metadata", f"com.apple.quicktime.location.ISO6709={meta['lat']}{meta['lon']}/"]
    command.append(str(output_path))
    result = subprocess.run(command, capture_output=True, creationflags=_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(f"FFmpeg iPhone falló en {Path(input_path).name}: "
                           f"{result.stderr.decode('utf-8', errors='replace')[-1200:]}")


def render_validated_copy(
    input_path: str | Path,
    output_path: str | Path,
    meta: dict,
    profile: str,
    source_color: str,
    *,
    enabled: dict | None = None,
    strength: float = 1.0,
    overrides: dict | None = None,
    threads: int | None = None,
) -> dict:
    """Publish only a fully encoded and decodable copy; never overwrite one."""
    from metadata_pool import DEFAULT_VARIANT_EFFECTS, apply_variant_and_metadata

    output = Path(output_path)
    if output.exists():
        raise FileExistsError(output)
    if source_color not in {"sdr", "hlg"}:
        raise ValueError(f"color de entrada desconocido: {source_color}")
    if profile not in PROFILES:
        raise ValueError(f"perfil de salida desconocido: {profile}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = output.parent / ".forge_tmp"
    temporary_dir.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=temporary_dir, prefix=f".{output.stem}.",
                                     suffix=".mov", delete=False) as file:
        temporary = Path(file.name)
    try:
        params = apply_variant_and_metadata(
            str(input_path), str(temporary), meta,
            enabled=enabled if enabled is not None else
            {key: False for key in DEFAULT_VARIANT_EFFECTS},
            strength=strength, overrides=overrides, ffmpeg_threads=threads,
            output_profile=profile, source_color=source_color,
        )
        params.update(validate_existing_copy(input_path, temporary, meta, profile, source_color))
        if output.exists():
            raise FileExistsError(output)
        os.rename(temporary, output)
        return params
    finally:
        temporary.unlink(missing_ok=True)


def validate_existing_copy(input_path, output_path, meta, profile, source_color):
    """Revalidate a published pending copy before crash recovery; never overwrite it."""
    data = probe_file(output_path)
    has_audio = any(stream.get("codec_type") == "audio" for stream in
                    probe_file(input_path).get("streams", []))
    problems = validate_probe(data, profile, expect_audio=has_audio, expected_meta=meta)
    boxes = top_level_boxes(output_path)
    if not boxes or boxes[0] != "ftyp" or "mdat" not in boxes or "moov" not in boxes \
            or boxes.index("moov") < boxes.index("mdat"):
        problems.append(f"format.boxes: orden MOV inesperado {boxes}")
    if problems:
        raise RuntimeError("Salida iPhone inválida: " + "; ".join(problems))
    result = subprocess.run([
        ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error",
        "-xerror", "-err_detect", "explode", "-i", str(output_path),
        "-map", "0:v:0", "-map", "0:a:0?", "-f", "null", os.devnull,
    ], capture_output=True, creationflags=_NO_WINDOW)
    if result.returncode:
        raise RuntimeError("La copia iPhone no se decodifica: " +
                           result.stderr.decode("utf-8", errors="replace")[-500:])
    visual_errors, visual_report = assess_visual_change(
        input_path, output_path, source_color=source_color,
        output_color="hlg" if profile == "iphone_hlg" else "sdr")
    if visual_errors:
        raise RuntimeError("QC visual iPhone rechazó la copia: " + "; ".join(visual_errors))
    return {"iphone_visual_qc": visual_report}


def validate_probe(data: dict, profile: str, *, expect_audio: bool,
                   expected_meta: dict | None = None) -> list[str]:
    """Return field-level mismatches for a probed Forge output."""
    if profile not in PROFILES:
        raise ValueError(f"Perfil de Forge desconocido: {profile}")
    problems: list[str] = []
    tags = (data.get("format") or {}).get("tags") or {}
    if tags.get("major_brand") != "qt  ":
        problems.append("format.major_brand: se esperaba qt")
    if expected_meta is not None:
        expected_tags = {
            "com.apple.quicktime.make": "Apple",
            "com.apple.quicktime.model": expected_meta["iphone_model"],
            "com.apple.quicktime.software": expected_meta["ios_version"],
        }
        for field, value in expected_tags.items():
            if tags.get(field) != value:
                problems.append(f"format.{field}: {tags.get(field)!r} != {value!r}")
        for field in ("com.apple.quicktime.network", "encoder"):
            if tags.get(field):
                problems.append(f"format.{field}: tag inesperado")

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
