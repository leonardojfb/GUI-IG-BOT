"""
🔮 METADATA POOL - Generador de fingerprints iPhone únicos para videos IG
 Forge usa únicamente modelos iPhone 17 o superiores y versiones iOS 26 o superiores.
"""
import hashlib
import itertools
import json
import math
import os
import random
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Windows: the GUI runs windowless (pythonw), so every ffmpeg/ffprobe child would
# otherwise pop its own console window and steal focus. On a big Forge batch that
# means hundreds of flashing consoles that freeze the machine. Suppress it.
# 0 on non-Windows platforms, where CREATE_NO_WINDOW does not exist.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
FFMPEG_METADATA_CLEAN_ARGS = [
    "-map_metadata", "-1",
    "-map_chapters", "-1",
    "-metadata", "encoder=",
    "-metadata:s:v:0", "encoder=",
    "-metadata:s:a:0", "encoder=",
    "-fflags", "+bitexact",
    "-flags:v", "+bitexact",
    "-flags:a", "+bitexact",
]


def _ffmpeg_tool_command(tool_name: str) -> str:
    executable_name = f"{tool_name}.exe" if os.name == "nt" else tool_name
    bundled = Path(__file__).resolve().parent / "tools" / "ffmpeg" / "bin" / executable_name
    if bundled.is_file():
        return str(bundled)
    return tool_name

IPHONE_MODELS = [
    "iPhone 17",
    "iPhone 17 Pro",
    "iPhone 17 Pro Max",
]

MIN_IPHONE_GENERATION = 17
MIN_IOS_VERSION = (26, 0)

US_CITIES = [
    ("New York",          "+40.7128", "-074.0060"),
    ("Los Angeles",       "+34.0522", "-118.2437"),
    ("Chicago",           "+41.8781", "-087.6298"),
    ("Houston",           "+29.7604", "-095.3698"),
    ("Phoenix",           "+33.4484", "-112.0740"),
    ("Philadelphia",      "+39.9526", "-075.1652"),
    ("San Antonio",       "+29.4241", "-098.4936"),
    ("San Diego",         "+32.7157", "-117.1611"),
    ("Dallas",            "+32.7767", "-096.7970"),
    ("San Jose",          "+37.3382", "-121.8863"),
    ("Austin",            "+30.2672", "-097.7431"),
    ("Jacksonville",      "+30.3322", "-081.6557"),
    ("Fort Worth",        "+32.7555", "-097.3308"),
    ("Columbus",          "+39.9612", "-082.9988"),
    ("Charlotte",         "+35.2271", "-080.8431"),
    ("Indianapolis",      "+39.7684", "-086.1581"),
    ("San Francisco",     "+37.7749", "-122.4194"),
    ("Seattle",           "+47.6062", "-122.3321"),
    ("Denver",            "+39.7392", "-104.9903"),
    ("Nashville",         "+36.1627", "-086.7816"),
    ("Miami",             "+25.7617", "-080.1918"),
    ("Atlanta",           "+33.7490", "-084.3880"),
    ("Portland",          "+45.5051", "-122.6750"),
    ("Las Vegas",         "+36.1699", "-115.1398"),
    ("Memphis",           "+35.1495", "-090.0490"),
    ("Louisville",        "+38.2527", "-085.7585"),
    ("Baltimore",         "+39.2904", "-076.6122"),
    ("Milwaukee",         "+43.0389", "-087.9065"),
    ("Boston",            "+42.3601", "-071.0589"),
    ("Detroit",           "+42.3314", "-083.0458"),
    ("El Paso",           "+31.7619", "-106.4850"),
    ("Oklahoma City",     "+35.4676", "-097.5164"),
    ("Tucson",            "+32.2226", "-110.9747"),
    ("Fresno",            "+36.7378", "-119.7871"),
    ("Sacramento",        "+38.5816", "-121.4944"),
    ("Mesa",              "+33.4152", "-111.8315"),
    ("Kansas City",       "+39.0997", "-094.5786"),
    ("Omaha",             "+41.2565", "-095.9345"),
    ("Colorado Springs",  "+38.8339", "-104.8214"),
    ("Raleigh",           "+35.7796", "-078.6382"),
    ("Long Beach",        "+33.7701", "-118.1937"),
    ("Virginia Beach",    "+36.8529", "-075.9780"),
    ("Minneapolis",       "+44.9778", "-093.2650"),
    ("Tampa",             "+27.9506", "-082.4572"),
    ("New Orleans",       "+29.9511", "-090.0715"),
    ("Arlington",         "+32.7357", "-097.1081"),
    ("Bakersfield",       "+35.3733", "-119.0187"),
    ("Honolulu",          "+21.3069", "-157.8583"),
    ("Anaheim",           "+33.8366", "-117.9143"),
    ("Aurora",            "+39.7294", "-104.8319"),
]

CARRIERS = [
    "AT&T",
    "Verizon",
    "T-Mobile",
    "Cricket",
    "Metro by T-Mobile",
    "Boost Mobile",
    "Mint Mobile",
    "Visible",
    "US Cellular",
    "Consumer Cellular",
]

IOS_VERSIONS = [
    # Ramas usables por iPhone 14 (mín 16.0) e iPhone 15 (mín 17.0)
    "16.0", "16.1", "16.2", "16.3", "16.4", "16.5", "16.6", "16.7",
    "17.0", "17.1", "17.2", "17.3", "17.4", "17.5", "17.6", "17.7",
    # iOS 18 — compartido por todos los modelos del pool
    "18.0", "18.1", "18.2", "18.3", "18.4", "18.5", "18.6", "18.7",
    # Rama legacy (parches de seguridad, coexiste con iOS 26)
    "18.7.1", "18.7.2", "18.7.3", "18.7.4", "18.7.5",
    "18.7.6", "18.7.7", "18.7.8", "18.7.9",
    # Rama moderna iOS 26 (sucesor directo de iOS 18, año calendario 2026)
    "26.0", "26.0.1", "26.1", "26.1.1", "26.2", "26.3", "26.4", "26.5", "26.5.1",
]

def _v(s: str) -> tuple:
    return tuple(int(x) for x in s.split("."))


def _iphone_generation(model: str) -> int:
    match = re.match(r"^iPhone\s+(\d+)", str(model).strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Modelo iPhone inválido: {model!r}")
    return int(match.group(1))


def _ios_version(version: str) -> tuple:
    try:
        parts = tuple(int(part) for part in str(version).strip().split("."))
    except (TypeError, ValueError):
        parts = ()
    if not parts:
        raise ValueError(f"Versión iOS inválida: {version!r}")
    if len(parts) == 1:
        parts += (0,)
    return parts


def validate_iphone_metadata(meta: dict) -> None:
    """Reject fingerprints below Forge's current device and iOS floors."""
    model = meta.get("iphone_model")
    if _iphone_generation(model) < MIN_IPHONE_GENERATION:
        raise ValueError(
            f"Forge solo permite iPhone {MIN_IPHONE_GENERATION} o superior; recibido: {model}"
        )
    version = meta.get("ios_version")
    if _ios_version(version) < MIN_IOS_VERSION:
        raise ValueError(
            f"Forge solo permite iOS {MIN_IOS_VERSION[0]} o superior; recibido: {version}"
        )


def current_creation_tags(now: datetime | None = None) -> dict[str, str]:
    """Return QuickTime creation tags for the instant Forge is processing."""
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    utc = instant.astimezone(timezone.utc)
    local = utc.astimezone()
    return {
        "creation_time": utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "com.apple.quicktime.creationdate": local.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

# (min_ios, max_ios) por modelo — límites de hardware reales + reglas de configuración
_MODEL_IOS_RANGE: dict[str, tuple[str, str]] = {
    "iPhone 17":         ("26.0", "26.5.1"),
    "iPhone 17 Pro":     ("26.0", "26.5.1"),
    "iPhone 17 Pro Max": ("26.0", "26.5.1"),
}

def _ios_pool_for(model: str) -> list[str]:
    lo, hi = _MODEL_IOS_RANGE[model]
    return [v for v in IOS_VERSIONS
            if MIN_IOS_VERSION <= _v(v) and _v(lo) <= _v(v) <= _v(hi)]


def get_video_hash(file_path: str) -> str:
    """SHA256 de los primeros 8 MB del video (rápido, suficiente para fingerprint)."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        chunk = f.read(8 * 1024 * 1024)
        h.update(chunk)
    return h.hexdigest()


def generate_unique_metadata(db_manager, n: int) -> list:
    """
    Genera n combinaciones únicas de metadata verificadas contra DB.
    Cada modelo usa solo el rango iOS compatible con su hardware.
    """
    used = db_manager.get_all_used_metadata_combos()

    all_combos = []
    for model in IPHONE_MODELS:
        if _iphone_generation(model) < MIN_IPHONE_GENERATION:
            continue
        ios_pool = _ios_pool_for(model)
        all_combos.extend(itertools.product([model], US_CITIES, CARRIERS, ios_pool))
    random.shuffle(all_combos)

    result = []
    for model, (city, lat, lon), carrier, ios in all_combos:
        combo_key = (model, city, carrier, ios)
        if combo_key not in used:
            metadata = {
                "iphone_model": model,
                "city": city,
                "lat": lat,
                "lon": lon,
                "carrier": carrier,
                "ios_version": ios,
            }
            validate_iphone_metadata(metadata)
            result.append(metadata)
            used.add(combo_key)
            if len(result) == n:
                break

    if len(result) < n:
        raise ValueError(
            f"No hay suficientes combinaciones únicas disponibles. "
            f"Pediste {n}, disponibles: {len(result)}"
        )

    return result


def apply_metadata_to_video(input_path: str, output_path: str, meta: dict,
                            *, output_profile: "str | None" = None,
                            source_color: "str | None" = None,
                            ffmpeg_threads: "int | None" = None) -> None:
    """
    Inyecta metadata de iPhone vía FFmpeg (-c copy, sin re-encodear).
    meta = {iphone_model, lat, lon, carrier, ios_version}
    """
    validate_iphone_metadata(meta)
    if output_profile:
        from forge_iphone_profile import render_iphone_video
        render_iphone_video(input_path, output_path, meta, output_profile,
                            source_color or "unknown", threads=ffmpeg_threads)
        return
    creation_tags = current_creation_tags()
    cmd = [
        _ffmpeg_tool_command("ffmpeg"), "-y", "-i", input_path,
        "-c", "copy",
        *FFMPEG_METADATA_CLEAN_ARGS,
        "-movflags", "use_metadata_tags",
        "-metadata", "make=Apple",
        "-metadata", f"model={meta['iphone_model']}",
        "-metadata", f"location={meta['lat']}{meta['lon']}/",
        "-metadata", f"com.apple.quicktime.software=iOS {meta['ios_version']}",
        "-metadata", f"com.apple.quicktime.model={meta['iphone_model']}",
        "-metadata", f"com.apple.quicktime.network={meta['carrier']}",
        "-metadata", f"creation_time={creation_tags['creation_time']}",
        "-metadata", f"com.apple.quicktime.creationdate={creation_tags['com.apple.quicktime.creationdate']}",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"FFmpeg falló en '{os.path.basename(input_path)}':\n{stderr[-500:]}")


# ══════════════════════════════════════════════════════════════════════════════
# VARIANT ENGINE — micro-ediciones para generar copias 99% idénticas pero únicas
# (recorte de bordes, espejo, zoom, rotación mínima, filtro de color, grano,
#  recorte de milisegundos, micro-velocidad) combinadas al azar por copia.
# ══════════════════════════════════════════════════════════════════════════════

def _probe_video_info(path: str) -> tuple:
    """Devuelve (width, height, duration_seg, has_audio) del video vía ffprobe."""
    cmd = [
        _ffmpeg_tool_command("ffprobe"), "-v", "error",
        "-show_entries", "stream=codec_type,width,height",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, creationflags=_NO_WINDOW)
    data = json.loads(result.stdout or "{}")
    width = height = 0
    has_audio = False
    for stream in data.get("streams") or []:
        ctype = stream.get("codec_type")
        if ctype == "video" and not width:
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
        elif ctype == "audio":
            has_audio = True
    duration = float((data.get("format") or {}).get("duration") or 0.0)
    return width, height, duration, has_audio


# Efectos disponibles y su estado por defecto. Las GUIs pueden pasar un dict
# `enabled` con estas claves para prender/apagar cada micro-edición.
DEFAULT_VARIANT_EFFECTS = {
    "crop":   True,   # recorte sutil de bordes
    "mirror": True,   # espejo horizontal
    "zoom":   True,   # zoom leve al centro
    "rotate": True,   # rotación mínima
    "color":  True,   # brillo/contraste/saturación/gamma
    "noise":  True,   # grano sutil
    "speed":  True,   # micro-variación de velocidad
    "trim":   True,   # recorte de milisegundos al inicio/fin
}


# ── Presets de los dos ejes de Forge ─────────────────────────────────────────
EFECTOS_PRESETS = {
    "Default": {"crop", "zoom", "rotate", "color", "noise", "speed", "trim"},   # 7, sin mirror
    "Light":   {"color", "trim"},
    "Medio":   {"crop", "color", "noise", "speed", "trim"},
    "Alto":    {"crop", "mirror", "zoom", "rotate", "color", "noise", "speed", "trim"},
}
FUERZA_PRESETS = {"Default": 1.0, "Light": 0.5, "Medio": 1.0, "Alto": 2.4}


def efectos_to_enabled(level: str, fx_vars: "dict | None" = None) -> dict:
    """Traduce un nivel del eje 'Efectos' (o 'Custom') al dict `enabled` de 8 claves.
    'Custom' lee los 8 on/off de `fx_vars` (clave->bool). Nivel desconocido -> Default."""
    if level == "Custom":
        vals = fx_vars or {}
        return {k: bool(vals.get(k, DEFAULT_VARIANT_EFFECTS[k])) for k in DEFAULT_VARIANT_EFFECTS}
    on = EFECTOS_PRESETS.get(level, EFECTOS_PRESETS["Default"])
    return {k: (k in on) for k in DEFAULT_VARIANT_EFFECTS}


def fuerza_to_strength(level: str, slider_pct: float = 50.0) -> float:
    """Traduce un nivel del eje 'Fuerza' (o 'Custom') a un float strength.
    'Custom' mapea slider_pct∈[0,100] a strength centrado en el neutro: 0→0.0, 50→1.0, 100→2.0. Nivel desconocido -> 1.0."""
    if level == "Custom":
        pct = max(0.0, min(100.0, float(slider_pct)))
        return round(pct / 50.0, 3)
    return FUERZA_PRESETS.get(level, 1.0)


def parse_custom_ranges(raw: "dict | None") -> dict:
    """Valida las entradas min/max del panel Fuerza=Custom.
    `raw` = {param: (min_str, max_str)}. Devuelve {param: (lo, hi)} float.
    Omite un param si algún lado es vacío/inválido; ordena lo<=hi."""
    out = {}
    for param, pair in (raw or {}).items():
        try:
            lo = float(str(pair[0]).strip())
            hi = float(str(pair[1]).strip())
        except (TypeError, ValueError, IndexError):
            continue
        if lo > hi:
            lo, hi = hi, lo
        out[param] = (lo, hi)
    return out


def generate_variant_params(
    rng: "random.Random | None" = None,
    enabled: "dict | None" = None,
    strength: float = 1.0,
    overrides: "dict | None" = None,
) -> dict:
    """
    Sortea micro-ediciones. `enabled` prende/apaga cada efecto; `strength` escala
    la magnitud (desde el neutro) y la probabilidad de disparo; `overrides`
    (dict param->(lo,hi) en unidades del motor) reemplaza el rango base de ese
    param antes de escalar por strength. strength=1.0 y overrides=None reproducen
    el comportamiento histórico exacto.
    """
    r = rng or random
    en = {**DEFAULT_VARIANT_EFFECTS, **(enabled or {})}
    s = max(0.0, float(strength))
    ov = overrides or {}

    def fires(p: float) -> bool:
        return r.random() < min(1.0, p * s)

    def base(param: str, lo: float, hi: float, neutral: float):
        # override reemplaza el rango base; strength escala la desviación del neutro.
        if param in ov:
            lo, hi = ov[param]
        return neutral + (lo - neutral) * s, neutral + (hi - neutral) * s

    crop_lo, crop_hi = base("crop", 2, 10, 0)
    zoom_lo, zoom_hi = base("zoom", 1.0, 1.05, 1.0)
    rot_lo, rot_hi   = base("rotate", -1.5, 1.5, 0)
    br_lo, br_hi     = base("brightness", -0.03, 0.03, 0)
    co_lo, co_hi     = base("contrast", 0.94, 1.06, 1.0)
    sa_lo, sa_hi     = base("saturation", 0.90, 1.10, 1.0)
    ga_lo, ga_hi     = base("gamma", 0.95, 1.05, 1.0)
    no_lo, no_hi     = base("noise", 4, 8, 0)
    sp_lo, sp_hi     = base("speed", 0.985, 1.015, 1.0)
    tr_lo, tr_hi     = base("trim", 0, 150, 0)

    return {
        "crop_px":       r.randint(round(crop_lo), round(crop_hi)) if en["crop"] else 0,
        "mirror":        bool(en["mirror"] and fires(0.5)),
        "zoom_pct":      r.uniform(zoom_lo, zoom_hi) if (en["zoom"] and fires(0.7)) else 1.0,
        "rotate_deg":    r.uniform(rot_lo, rot_hi) if (en["rotate"] and fires(0.6)) else 0.0,
        "brightness":    r.uniform(br_lo, br_hi) if en["color"] else 0.0,
        "contrast":      r.uniform(co_lo, co_hi) if en["color"] else 1.0,
        "saturation":    r.uniform(sa_lo, sa_hi) if en["color"] else 1.0,
        "gamma":         r.uniform(ga_lo, ga_hi) if en["color"] else 1.0,
        # Piso 4: niveles 2-3 quedan casi borrados por la compresión CRF 20.
        "noise":         max(4, r.randint(round(no_lo), round(no_hi))) if (en["noise"] and fires(0.4)) else 0,
        "speed":         r.uniform(sp_lo, sp_hi) if (en["speed"] and fires(0.5)) else 1.0,
        "trim_start_ms": r.randint(round(tr_lo), round(tr_hi)) if en["trim"] else 0,
        "trim_end_ms":   r.randint(round(tr_lo), round(tr_hi)) if en["trim"] else 0,
    }


def _build_video_filters(params: dict, width: int, height: int) -> str:
    filters = []

    # 1. Recorte sutil de bordes (si está activo).
    cp = params["crop_px"]
    if cp > 0:
        filters.append(f"crop=iw-{cp * 2}:ih-{cp * 2}:{cp}:{cp}")

    # 2. Zoom leve (recorta el centro un poco más) o reescala de vuelta si solo hubo crop.
    # Se escala respecto al tamaño ORIGINAL (no al recortado por el paso 1),
    # así el frame siempre queda >= width x height antes del crop de reencuadre.
    z = params["zoom_pct"]
    if z > 1.001 and width and height:
        zw = max(width, int(round(width * z / 2)) * 2)
        zh = max(height, int(round(height * z / 2)) * 2)
        filters.append(f"scale={zw}:{zh}")
        filters.append(f"crop={width}:{height}")
    elif cp > 0 and width and height:
        filters.append(f"scale={width}:{height}")

    # 3. Espejo horizontal.
    if params["mirror"]:
        filters.append("hflip")

    # 4. Rotación mínima (relleno negro, luego reencuadre al tamaño original).
    if abs(params["rotate_deg"]) > 0.01:
        rad = params["rotate_deg"] * math.pi / 180
        filters.append(f"rotate={rad:.5f}:c=black@0")
        if width and height:
            filters.append(f"crop={width}:{height}")

    # 5. Filtro de color (brillo/contraste/saturación/gamma) — solo si no es neutro.
    if (abs(params["brightness"]) > 1e-6 or abs(params["contrast"] - 1.0) > 1e-6
            or abs(params["saturation"] - 1.0) > 1e-6 or abs(params["gamma"] - 1.0) > 1e-6):
        filters.append(
            f"eq=brightness={params['brightness']:.4f}:contrast={params['contrast']:.4f}:"
            f"saturation={params['saturation']:.4f}:gamma={params['gamma']:.4f}"
        )

    # 6. Grano sutil.
    if params["noise"] > 0:
        filters.append(f"noise=alls={params['noise']}:allf=t")

    # 7. Micro-variación de velocidad.
    speed = params["speed"]
    if abs(speed - 1.0) > 0.001:
        filters.append(f"setpts=PTS/{speed:.4f}")

    return ",".join(filters)


def _build_audio_filter(params: dict) -> "str | None":
    speed = params["speed"]
    if abs(speed - 1.0) > 0.001:
        return f"atempo={speed:.4f}"
    return None


def apply_variant_and_metadata(
    input_path: str,
    output_path: str,
    meta: dict,
    rng: "random.Random | None" = None,
    enabled: "dict | None" = None,
    strength: float = 1.0,
    overrides: "dict | None" = None,
    ffmpeg_threads: "int | None" = None,
    output_profile: "str | None" = None,
    source_color: "str | None" = None,
) -> dict:
    """
    Genera una copia realmente distinta a nivel de píxeles (recorte de bordes,
    espejo, zoom, rotación, filtro de color, grano y recorte de milisegundos,
    mezclados al azar) y le inyecta metadata iPhone única.
    `enabled` (claves de DEFAULT_VARIANT_EFFECTS) prende/apaga cada efecto.
    Requiere reencodear, salvo que todos los efectos queden apagados: en ese
    caso cae al camino rápido -c copy (solo metadata, sin re-encode).
    Devuelve los parámetros usados (útil para logging/depuración).
    """
    validate_iphone_metadata(meta)
    width, height, duration, has_audio = _probe_video_info(input_path)
    params = generate_variant_params(rng, enabled, strength, overrides)

    start = params["trim_start_ms"] / 1000.0
    end = params["trim_end_ms"] / 1000.0
    clip_duration = None
    if duration:
        clip_duration = max(duration - start - end, 1.0)

    vf = _build_video_filters(params, width, height)
    # atempo requiere stream de audio; si el video no tiene, se omite.
    af = _build_audio_filter(params) if has_audio else None

    # Sin ninguna edición activa → no hay motivo para reencodear.
    if not vf and not af and start == 0 and end == 0:
        apply_metadata_to_video(input_path, output_path, meta,
                                output_profile=output_profile, source_color=source_color,
                                ffmpeg_threads=ffmpeg_threads)
        return params

    if output_profile:
        from forge_iphone_profile import render_iphone_video
        if source_color == "hlg":
            # eq/noise have not passed a 10-bit HLG accuracy check. The
            # spatial/temporal edits stay active; record every skipped edit.
            skipped = []
            if any((abs(params["brightness"]) > 1e-6,
                    abs(params["contrast"] - 1) > 1e-6,
                    abs(params["saturation"] - 1) > 1e-6,
                    abs(params["gamma"] - 1) > 1e-6)):
                skipped.append("color")
            if params["noise"]:
                skipped.append("noise")
            if skipped:
                adjusted = dict(params, brightness=0.0, contrast=1.0,
                                saturation=1.0, gamma=1.0, noise=0)
                vf = _build_video_filters(adjusted, width, height)
                params["iphone_effects_skipped"] = skipped
        render_iphone_video(input_path, output_path, meta, output_profile,
                            source_color or "unknown", video_filters=vf,
                            audio_filter=af, start=start, duration=clip_duration,
                            threads=ffmpeg_threads)
        return params

    # libx264/yuv420p exige dimensiones pares: garantizarlo siempre que se
    # reencodea (fuentes con resolución impar fallarían sin esto).
    even_guard = "crop=trunc(iw/2)*2:trunc(ih/2)*2"
    square_pixel_guard = "setsar=1"
    output_guards = f"{even_guard},{square_pixel_guard}"
    vf = f"{vf},{output_guards}" if vf else output_guards

    base_cmd = [_ffmpeg_tool_command("ffmpeg"), "-y"]
    if start > 0:
        base_cmd += ["-ss", f"{start:.3f}"]
    base_cmd += ["-i", input_path]
    common_args = []
    if clip_duration:
        common_args += ["-t", f"{clip_duration:.3f}"]
    if vf:
        common_args += ["-vf", vf]
    if af:
        common_args += ["-af", af]
    metadata_args = [
        "-c:a", "aac", "-b:a", "128k",
        *FFMPEG_METADATA_CLEAN_ARGS,
        "-movflags", "use_metadata_tags",
        "-metadata", "make=Apple",
        "-metadata", f"model={meta['iphone_model']}",
        "-metadata", f"location={meta['lat']}{meta['lon']}/",
        "-metadata", f"com.apple.quicktime.software=iOS {meta['ios_version']}",
        "-metadata", f"com.apple.quicktime.model={meta['iphone_model']}",
        "-metadata", f"com.apple.quicktime.network={meta['carrier']}",
        output_path,
    ]
    encoder_attempts = [
        ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p"],
    ]
    last_stderr = b""
    for encoder_args in encoder_attempts:
        cmd = base_cmd + common_args + encoder_args
        if ffmpeg_threads and "libx264" in encoder_args:
            cmd += ["-threads", str(ffmpeg_threads)]
        cmd += metadata_args
        result = subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW)
        if result.returncode == 0:
            return params
        if os.path.exists(output_path):
            os.remove(output_path)
        last_stderr = result.stderr or b""

    stderr = last_stderr.decode("utf-8", errors="replace")
    raise RuntimeError(f"FFmpeg falló en '{os.path.basename(input_path)}':\n{stderr[-500:]}")
