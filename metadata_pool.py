"""
🔮 METADATA POOL - Generador de fingerprints iPhone únicos para videos IG
Rangos iOS por modelo según compatibilidad real de hardware:
  iPhone 12/13   → 18.7–18.7.9 (legacy) + 26.0–26.5.1 (moderno)
  iPhone 14      → 16.0–18.7.9 (legacy) + 26.0–26.5.1 (moderno)
  iPhone 15      → 17.0–18.7.9 (legacy) + 26.0–26.5.1 (moderno)
  iPhone 16      → 18.0–18.7.9 (legacy) + 26.0–26.5.1 (moderno)
Apple saltó de iOS 18 → iOS 26 (skip 19-25) para alinear con año calendario 2026.
"""
import hashlib
import itertools
import json
import math
import os
import random
import subprocess

# Windows: the GUI runs windowless (pythonw), so every ffmpeg/ffprobe child would
# otherwise pop its own console window and steal focus. On a big Forge batch that
# means hundreds of flashing consoles that freeze the machine. Suppress it.
# 0 on non-Windows platforms, where CREATE_NO_WINDOW does not exist.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

IPHONE_MODELS = [
    "iPhone 12",
    "iPhone 12 Mini",
    "iPhone 12 Pro",
    "iPhone 12 Pro Max",
    "iPhone 13",
    "iPhone 13 Mini",
    "iPhone 13 Pro",
    "iPhone 13 Pro Max",
    "iPhone 14",
    "iPhone 14 Plus",
    "iPhone 14 Pro",
    "iPhone 14 Pro Max",
    "iPhone 15",
    "iPhone 15 Plus",
    "iPhone 15 Pro",
    "iPhone 15 Pro Max",
    "iPhone 16",
    "iPhone 16 Plus",
    "iPhone 16 Pro",
    "iPhone 16 Pro Max",
]

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

# (min_ios, max_ios) por modelo — límites de hardware reales + reglas de configuración
_MODEL_IOS_RANGE: dict[str, tuple[str, str]] = {
    # iPhone 12/13: mínimo 18.7 (soportan iOS 18 y iOS 26)
    "iPhone 12":         ("18.7", "26.5.1"),
    "iPhone 12 Mini":    ("18.7", "26.5.1"),
    "iPhone 12 Pro":     ("18.7", "26.5.1"),
    "iPhone 12 Pro Max": ("18.7", "26.5.1"),
    "iPhone 13":         ("18.7", "26.5.1"),
    "iPhone 13 Mini":    ("18.7", "26.5.1"),
    "iPhone 13 Pro":     ("18.7", "26.5.1"),
    "iPhone 13 Pro Max": ("18.7", "26.5.1"),
    # iPhone 14: lanzado con iOS 16
    "iPhone 14":         ("16.0", "26.5.1"),
    "iPhone 14 Plus":    ("16.0", "26.5.1"),
    "iPhone 14 Pro":     ("16.0", "26.5.1"),
    "iPhone 14 Pro Max": ("16.0", "26.5.1"),
    # iPhone 15: lanzado con iOS 17
    "iPhone 15":         ("17.0", "26.5.1"),
    "iPhone 15 Plus":    ("17.0", "26.5.1"),
    "iPhone 15 Pro":     ("17.0", "26.5.1"),
    "iPhone 15 Pro Max": ("17.0", "26.5.1"),
    # iPhone 16: lanzado con iOS 18
    "iPhone 16":         ("18.0", "26.5.1"),
    "iPhone 16 Plus":    ("18.0", "26.5.1"),
    "iPhone 16 Pro":     ("18.0", "26.5.1"),
    "iPhone 16 Pro Max": ("18.0", "26.5.1"),
}

def _ios_pool_for(model: str) -> list[str]:
    lo, hi = _MODEL_IOS_RANGE[model]
    return [v for v in IOS_VERSIONS if _v(lo) <= _v(v) <= _v(hi)]


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
        ios_pool = _ios_pool_for(model)
        all_combos.extend(itertools.product([model], US_CITIES, CARRIERS, ios_pool))
    random.shuffle(all_combos)

    result = []
    for model, (city, lat, lon), carrier, ios in all_combos:
        combo_key = (model, city, carrier, ios)
        if combo_key not in used:
            result.append({
                "iphone_model": model,
                "city": city,
                "lat": lat,
                "lon": lon,
                "carrier": carrier,
                "ios_version": ios,
            })
            used.add(combo_key)
            if len(result) == n:
                break

    if len(result) < n:
        raise ValueError(
            f"No hay suficientes combinaciones únicas disponibles. "
            f"Pediste {n}, disponibles: {len(result)}"
        )

    return result


def apply_metadata_to_video(input_path: str, output_path: str, meta: dict) -> None:
    """
    Inyecta metadata de iPhone vía FFmpeg (-c copy, sin re-encodear).
    meta = {iphone_model, lat, lon, carrier, ios_version}
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c", "copy",
        "-movflags", "use_metadata_tags",
        "-metadata", "make=Apple",
        "-metadata", f"model={meta['iphone_model']}",
        "-metadata", f"location={meta['lat']}{meta['lon']}/",
        "-metadata", f"com.apple.quicktime.software=iOS {meta['ios_version']}",
        "-metadata", f"com.apple.quicktime.model={meta['iphone_model']}",
        "-metadata", f"com.apple.quicktime.network={meta['carrier']}",
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
        "ffprobe", "-v", "error",
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


def generate_variant_params(
    rng: "random.Random | None" = None,
    enabled: "dict | None" = None,
) -> dict:
    """
    Sortea una combinación de micro-ediciones. Cada llamada produce una mezcla
    distinta (no todas las variantes se aplican siempre) para que el resultado
    final de cada copia sea único por poco, no por una fórmula fija.
    `enabled` permite apagar efectos individuales (claves de DEFAULT_VARIANT_EFFECTS);
    un efecto apagado queda en su valor neutro y nunca se aplica.
    """
    r = rng or random
    en = {**DEFAULT_VARIANT_EFFECTS, **(enabled or {})}
    return {
        "crop_px":       r.randint(2, 10) if en["crop"] else 0,
        "mirror":        bool(en["mirror"] and r.random() < 0.5),
        "zoom_pct":      r.uniform(1.0, 1.05) if (en["zoom"] and r.random() < 0.7) else 1.0,
        "rotate_deg":    r.uniform(-1.5, 1.5) if (en["rotate"] and r.random() < 0.6) else 0.0,
        "brightness":    r.uniform(-0.03, 0.03) if en["color"] else 0.0,
        "contrast":      r.uniform(0.94, 1.06) if en["color"] else 1.0,
        "saturation":    r.uniform(0.90, 1.10) if en["color"] else 1.0,
        "gamma":         r.uniform(0.95, 1.05) if en["color"] else 1.0,
        # Mínimo 4: niveles 2-3 quedan casi borrados por la compresión CRF 20.
        "noise":         r.randint(4, 8) if (en["noise"] and r.random() < 0.4) else 0,
        "speed":         r.uniform(0.985, 1.015) if (en["speed"] and r.random() < 0.5) else 1.0,
        "trim_start_ms": r.randint(0, 150) if en["trim"] else 0,
        "trim_end_ms":   r.randint(0, 150) if en["trim"] else 0,
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
    width, height, duration, has_audio = _probe_video_info(input_path)
    params = generate_variant_params(rng, enabled)

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
        apply_metadata_to_video(input_path, output_path, meta)
        return params

    # libx264/yuv420p exige dimensiones pares: garantizarlo siempre que se
    # reencodea (fuentes con resolución impar fallarían sin esto).
    even_guard = "crop=trunc(iw/2)*2:trunc(ih/2)*2"
    vf = f"{vf},{even_guard}" if vf else even_guard

    cmd = ["ffmpeg", "-y"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", input_path]
    if clip_duration:
        cmd += ["-t", f"{clip_duration:.3f}"]
    if vf:
        cmd += ["-vf", vf]
    if af:
        cmd += ["-af", af]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "use_metadata_tags",
        "-metadata", "make=Apple",
        "-metadata", f"model={meta['iphone_model']}",
        "-metadata", f"location={meta['lat']}{meta['lon']}/",
        "-metadata", f"com.apple.quicktime.software=iOS {meta['ios_version']}",
        "-metadata", f"com.apple.quicktime.model={meta['iphone_model']}",
        "-metadata", f"com.apple.quicktime.network={meta['carrier']}",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"FFmpeg falló en '{os.path.basename(input_path)}':\n{stderr[-500:]}")

    return params
