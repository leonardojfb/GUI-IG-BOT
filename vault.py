import hashlib
import itertools
import json
import math
import os
import random
import uuid


VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

FORGE_EFFECT_KEYS = ("crop", "mirror", "zoom", "rotate", "color", "noise", "speed", "trim")
FORGE_PARAM_KEYS = (
    "crop_px",
    "mirror",
    "zoom_pct",
    "rotate_deg",
    "brightness",
    "contrast",
    "saturation",
    "gamma",
    "noise",
    "speed",
    "trim_start_ms",
    "trim_end_ms",
)
NEUTRAL_PARAMS = {
    "crop_px": 0,
    "mirror": False,
    "zoom_pct": 1.0,
    "rotate_deg": 0.0,
    "brightness": 0.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "gamma": 1.0,
    "noise": 0,
    "speed": 1.0,
    "trim_start_ms": 0,
    "trim_end_ms": 0,
}


def media_type_for_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in IMAGE_EXTS:
        return "image"
    return "file"


def hash_asset(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clamp_strength(strength) -> float:
    try:
        return max(0.0, float(strength))
    except (TypeError, ValueError):
        return 1.0


def _range(overrides, param, lo, hi, neutral, strength):
    if overrides and param in overrides:
        lo, hi = overrides[param]
    s = _clamp_strength(strength)
    a = neutral + (float(lo) - neutral) * s
    b = neutral + (float(hi) - neutral) * s
    return (a, b) if a <= b else (b, a)


def _int_values(lo, hi, minimum=None):
    start = int(round(lo))
    end = int(round(hi))
    if start > end:
        start, end = end, start
    values = []
    for value in range(start, end + 1):
        if minimum is not None:
            value = max(minimum, value)
        values.append(int(value))
    return sorted(set(values))


def _decimal_values(lo, hi, places, neutral=None, inactive_below=None):
    scale = 10 ** int(places)
    start = int(math.ceil((min(lo, hi) * scale) - 1e-9))
    end = int(math.floor((max(lo, hi) * scale) + 1e-9))
    values = [round(value / scale, places) for value in range(start, end + 1)]
    if neutral is not None:
        values.append(round(float(neutral), places))
    if inactive_below is not None:
        collapsed = []
        for value in values:
            if inactive_below(value):
                collapsed.append(round(float(neutral), places))
            else:
                collapsed.append(value)
        values = collapsed
    return sorted(set(values))


def effective_enabled(enabled: dict | None) -> dict:
    return {key: bool((enabled or {}).get(key)) for key in FORGE_EFFECT_KEYS}


def normalize_forge_params(params: dict | None) -> dict:
    raw = {**NEUTRAL_PARAMS, **(params or {})}
    zoom = round(float(raw.get("zoom_pct", 1.0)), 4)
    rotate = round(float(raw.get("rotate_deg", 0.0)), 3)
    speed = round(float(raw.get("speed", 1.0)), 4)
    if zoom <= 1.001:
        zoom = 1.0
    if abs(rotate) <= 0.01:
        rotate = 0.0
    if abs(speed - 1.0) <= 0.001:
        speed = 1.0
    return {
        "crop_px": max(0, int(round(float(raw.get("crop_px", 0))))),
        "mirror": bool(raw.get("mirror")),
        "zoom_pct": zoom,
        "rotate_deg": rotate,
        "brightness": round(float(raw.get("brightness", 0.0)), 4),
        "contrast": round(float(raw.get("contrast", 1.0)), 4),
        "saturation": round(float(raw.get("saturation", 1.0)), 4),
        "gamma": round(float(raw.get("gamma", 1.0)), 4),
        "noise": max(0, int(round(float(raw.get("noise", 0))))),
        "speed": speed,
        "trim_start_ms": max(0, int(round(float(raw.get("trim_start_ms", 0))))),
        "trim_end_ms": max(0, int(round(float(raw.get("trim_end_ms", 0))))),
    }


def _effective_params_for_enabled(enabled: dict | None, params: dict | None) -> dict:
    en = effective_enabled(enabled)
    normalized = normalize_forge_params(params)
    if not en["crop"]:
        normalized["crop_px"] = 0
    if not en["mirror"]:
        normalized["mirror"] = False
    if not en["zoom"]:
        normalized["zoom_pct"] = 1.0
    if not en["rotate"]:
        normalized["rotate_deg"] = 0.0
    if not en["color"]:
        normalized["brightness"] = 0.0
        normalized["contrast"] = 1.0
        normalized["saturation"] = 1.0
        normalized["gamma"] = 1.0
    if not en["noise"]:
        normalized["noise"] = 0
    if not en["speed"]:
        normalized["speed"] = 1.0
    if not en["trim"]:
        normalized["trim_start_ms"] = 0
        normalized["trim_end_ms"] = 0
    return normalized


def forge_variant_signature(asset_hash: str, process_kind: str, enabled: dict, params: dict) -> str:
    payload = {
        "asset_hash": asset_hash,
        "process_kind": str(process_kind),
        "enabled": effective_enabled(enabled),
        "params": _effective_params_for_enabled(enabled, params),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _domain_values(enabled, strength, overrides):
    en = effective_enabled(enabled)
    crop_lo, crop_hi = _range(overrides, "crop", 2, 10, 0, strength)
    zoom_lo, zoom_hi = _range(overrides, "zoom", 1.0, 1.05, 1.0, strength)
    rot_lo, rot_hi = _range(overrides, "rotate", -1.5, 1.5, 0, strength)
    br_lo, br_hi = _range(overrides, "brightness", -0.03, 0.03, 0, strength)
    co_lo, co_hi = _range(overrides, "contrast", 0.94, 1.06, 1.0, strength)
    sa_lo, sa_hi = _range(overrides, "saturation", 0.90, 1.10, 1.0, strength)
    ga_lo, ga_hi = _range(overrides, "gamma", 0.95, 1.05, 1.0, strength)
    no_lo, no_hi = _range(overrides, "noise", 4, 8, 0, strength)
    sp_lo, sp_hi = _range(overrides, "speed", 0.985, 1.015, 1.0, strength)
    tr_lo, tr_hi = _range(overrides, "trim", 0, 150, 0, strength)

    values = {
        "crop_px": _int_values(crop_lo, crop_hi) if en["crop"] else [0],
        "mirror": [False, True] if en["mirror"] else [False],
        "zoom_pct": _decimal_values(
            zoom_lo, zoom_hi, 4, neutral=1.0, inactive_below=lambda value: value <= 1.001
        ) if en["zoom"] else [1.0],
        "rotate_deg": _decimal_values(
            rot_lo, rot_hi, 3, neutral=0.0, inactive_below=lambda value: abs(value) <= 0.01
        ) if en["rotate"] else [0.0],
        "brightness": _decimal_values(br_lo, br_hi, 4, neutral=0.0) if en["color"] else [0.0],
        "contrast": _decimal_values(co_lo, co_hi, 4, neutral=1.0) if en["color"] else [1.0],
        "saturation": _decimal_values(sa_lo, sa_hi, 4, neutral=1.0) if en["color"] else [1.0],
        "gamma": _decimal_values(ga_lo, ga_hi, 4, neutral=1.0) if en["color"] else [1.0],
        "noise": ([0] + _int_values(no_lo, no_hi, minimum=4)) if en["noise"] else [0],
        "speed": _decimal_values(
            sp_lo, sp_hi, 4, neutral=1.0, inactive_below=lambda value: abs(value - 1.0) <= 0.001
        ) if en["speed"] else [1.0],
        "trim_start_ms": _int_values(tr_lo, tr_hi) if en["trim"] else [0],
        "trim_end_ms": _int_values(tr_lo, tr_hi) if en["trim"] else [0],
    }
    return {key: sorted(set(values[key])) for key in FORGE_PARAM_KEYS}


def forge_variant_capacity(db, vault_asset, process_kind, enabled, strength, overrides) -> dict:
    domains = _domain_values(enabled, strength, overrides)
    total = math.prod(len(domains[key]) for key in FORGE_PARAM_KEYS)
    used = len(db.used_variant_signatures(vault_asset["id"], process_kind))
    available = max(0, total - used)
    return {"total": total, "used": min(used, total), "available": available}


def _deterministic_domains(vault_asset, process_kind, enabled, strength, overrides):
    domains = _domain_values(enabled, strength, overrides)
    seed_payload = {
        "asset_hash": vault_asset.get("asset_hash"),
        "process_kind": process_kind,
        "enabled": effective_enabled(enabled),
        "strength": _clamp_strength(strength),
        "overrides": overrides or {},
    }
    seed = hashlib.sha256(
        json.dumps(seed_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    shuffled = {}
    for key in FORGE_PARAM_KEYS:
        values = list(domains[key])
        random.Random(f"{seed}:{key}").shuffle(values)
        shuffled[key] = values
    return shuffled


def iter_forge_variant_params(vault_asset, process_kind, enabled, strength, overrides):
    domains = _deterministic_domains(vault_asset, process_kind, enabled, strength, overrides)
    for combo in itertools.product(*(domains[key] for key in FORGE_PARAM_KEYS)):
        yield normalize_forge_params(dict(zip(FORGE_PARAM_KEYS, combo)))


def reserve_forge_variants(
    db,
    vault_asset,
    process_kind,
    count,
    enabled,
    strength,
    overrides,
    run_id=None,
):
    target = max(0, int(count))
    run_id = run_id or str(uuid.uuid4())
    used = set(db.used_variant_signatures(vault_asset["id"], process_kind))
    capacity = forge_variant_capacity(db, vault_asset, process_kind, enabled, strength, overrides)
    reserved = []

    for params in iter_forge_variant_params(vault_asset, process_kind, enabled, strength, overrides):
        if len(reserved) >= target:
            break
        signature = forge_variant_signature(vault_asset["asset_hash"], process_kind, enabled, params)
        if signature in used:
            continue
        reservation_id = db.reserve_forge_variant_signature(
            vault_asset["id"], process_kind, signature, params, run_id=run_id
        )
        if reservation_id is None:
            used.add(signature)
            continue
        used.add(signature)
        reserved.append(
            {
                "params": params,
                "signature": signature,
                "reservation_id": reservation_id,
            }
        )

    shortfall = max(0, target - len(reserved))
    message = ""
    if shortfall:
        message = (
            f"No quedan variantes nuevas para {vault_asset['display_name']} "
            "con los rangos actuales. Aumenta fuerza, activa mas efectos o amplia rangos custom."
        )
    return {
        "asset": vault_asset,
        "reserved": reserved,
        "shortfall": shortfall,
        "capacity": capacity,
        "message": message,
        "run_id": run_id,
    }
