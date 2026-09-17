"""Versioned Pillow image variants for the R11 Photo Forge contract."""
from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from typing import Any


PHOTO_PROFILES = {
    "instagram_post": {"min_width": 320, "min_height": 320, "min_aspect": 0.8, "max_aspect": 1.91},
    "instagram_story": {"min_width": 320, "min_height": 568, "min_aspect": 0.5, "max_aspect": 0.7},
    "source": {"min_width": 2, "min_height": 2, "min_aspect": 0.05, "max_aspect": 20.0},
}
SUPPORTED_OPERATIONS = {"brightness", "contrast", "color", "sharpness", "rotate", "flip", "crop", "resize", "grayscale"}


def build_photo_forge_job_spec(
    image_paths: list[str | os.PathLike],
    *,
    output_dir: str | os.PathLike,
    variants: list[dict[str, Any]],
    profile: str = "instagram_post",
) -> dict[str, Any]:
    """Freeze image inputs and deterministic outputs into an R09 recipe."""
    _profile_rule(profile)
    paths = [str(Path(path).resolve()) for path in image_paths]
    if not paths or any(not Path(path).is_file() for path in paths):
        raise ValueError("todas las imagenes Photo Forge deben existir")
    if not variants:
        raise ValueError("variants debe contener al menos una variante")
    normalized = [_normalize_operations(item) for item in variants]
    root = Path(output_dir).resolve()
    steps = []
    for source_index, source in enumerate(paths, start=1):
        for variant_index, operations in enumerate(normalized, start=1):
            suffix = Path(source).suffix.lower()
            if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                suffix = ".png"
            output = root / f"{Path(source).stem}__pf{variant_index:02d}{suffix}"
            steps.append(
                {
                    "step_id": f"photo-forge-{source_index:04d}-{variant_index:02d}",
                    "kind": "photo_forge.variant",
                    "payload": {
                        "source_path": source,
                        "output_path": str(output),
                        "operations": operations,
                        "profile": profile,
                        "variant_id": f"v{variant_index:02d}",
                    },
                }
            )
    return {
        "job_type": "photo_forge.variant.v1",
        "recipe": {
            "recipe_version": 1,
            "producer": "photo_forge",
            "profile": profile,
            "output_dir": str(root),
            "variants": normalized,
            "image_paths": paths,
        },
        "steps": steps,
    }


def submit_photo_forge_job(connection, image_paths, *, output_dir, variants, profile="instagram_post", idempotency_key=None):
    from durable_jobs import create_job

    spec = build_photo_forge_job_spec(image_paths, output_dir=output_dir, variants=variants, profile=profile)
    return create_job(connection, **spec, idempotency_key=idempotency_key)


def validate_image(path: str | os.PathLike, *, profile: str = "source") -> dict[str, Any]:
    rule = _profile_rule(profile)
    target = Path(path)
    try:
        from PIL import Image

        with Image.open(target) as image:
            image.verify()
        with Image.open(target) as image:
            width, height = image.size
            image_format = image.format or target.suffix.lstrip(".").upper()
            mode = image.mode
    except Exception as exc:
        raise ValueError(f"imagen corrupta o ilegible: {target}") from exc
    aspect = width / height if height else 0
    if width < rule["min_width"] or height < rule["min_height"]:
        raise ValueError(f"La imagen no cumple dimensiones del perfil {profile}")
    if not rule["min_aspect"] <= aspect <= rule["max_aspect"]:
        raise ValueError(f"La imagen no cumple aspect ratio del perfil {profile}")
    return {"path": str(target), "width": width, "height": height, "aspect_ratio": round(aspect, 6), "format": image_format, "mode": mode}


def render_photo_variant(input_path, output_path, operations, *, profile="source") -> dict[str, Any]:
    """Render atomically so a failed Pillow write never leaves a false output."""
    source_info = validate_image(input_path, profile=profile)
    normalized = _normalize_operations(operations)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        from PIL import Image, ImageEnhance, ImageOps

        with Image.open(input_path) as opened:
            image = ImageOps.exif_transpose(opened).copy()
        if normalized.get("grayscale"):
            image = ImageOps.grayscale(image).convert("RGB")
        if normalized.get("flip"):
            image = ImageOps.mirror(image)
        if normalized.get("crop"):
            crop = normalized["crop"]
            image = image.crop((crop["left"], crop["top"], crop["right"], crop["bottom"]))
        for key, enhancer in (("brightness", ImageEnhance.Brightness), ("contrast", ImageEnhance.Contrast), ("color", ImageEnhance.Color), ("sharpness", ImageEnhance.Sharpness)):
            if key in normalized:
                image = enhancer(image).enhance(float(normalized[key]))
        if normalized.get("rotate"):
            image = image.rotate(float(normalized["rotate"]), expand=True, resample=Image.Resampling.BICUBIC)
        if normalized.get("resize"):
            size = normalized["resize"]
            image.thumbnail((size["width"], size["height"]), Image.Resampling.LANCZOS)
        suffix = target.suffix.lower()
        save_format = "JPEG" if suffix in {".jpg", ".jpeg"} else ("WEBP" if suffix == ".webp" else "PNG")
        if save_format == "JPEG" and image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=target.suffix or ".tmp", dir=str(target.parent))
        os.close(fd)
        save_kwargs = {"format": save_format}
        if save_format == "JPEG":
            save_kwargs.update(quality=95, optimize=True)
        image.save(temp_name, **save_kwargs)
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    output_info = validate_image(target, profile=profile)
    output_info["perceptual_signature"] = perceptual_signature(target)
    return {"output_path": str(target), "path": str(target), "source_info": source_info, "output_info": output_info, "operations": normalized}


def render_photo_preview(input_path, output_path, operations, *, max_size=(640, 640)) -> dict[str, Any]:
    preview_ops = dict(operations or {})
    preview_ops["resize"] = {"width": int(max_size[0]), "height": int(max_size[1])}
    return render_photo_variant(input_path, output_path, preview_ops, profile="source")


def perceptual_signature(path: str | os.PathLike, *, hash_size: int = 8) -> str:
    """Return a deterministic average-hash signature for visual reuse checks."""
    if int(hash_size) < 2 or int(hash_size) > 32:
        raise ValueError("hash_size fuera de rango")
    try:
        from PIL import Image

        with Image.open(path) as opened:
            image = opened.convert("L").resize((int(hash_size), int(hash_size)), Image.Resampling.LANCZOS)
            flattened = getattr(image, "get_flattened_data", None)
            pixels = list(flattened()) if flattened is not None else list(image.getdata())
    except Exception as exc:
        raise ValueError(f"no se pudo calcular firma perceptual: {path}") from exc
    average = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= average else "0" for pixel in pixels)
    width = int(hash_size) * int(hash_size)
    return f"{int(bits, 2):0{(width + 3) // 4}x}"


def perceptual_distance(first: str, second: str) -> int:
    """Return Hamming distance for equal-size hexadecimal perceptual hashes."""
    left, right = str(first or "").strip().lower(), str(second or "").strip().lower()
    if not left or not right or len(left) != len(right):
        raise ValueError("firmas perceptuales incompatibles")
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError as exc:
        raise ValueError("firma perceptual invalida") from exc


def audit_photo_forge_reuse(db, assignments, *, max_distance: int = 4) -> dict[str, Any]:
    """Evaluate Vault reuse for a Photo Forge preview without mutating state."""
    if int(max_distance) < 0:
        raise ValueError("max_distance no puede ser negativo")
    from vault.lineage import VaultLineage
    from vault.reuse import VaultReuseAudit
    from vault.signatures import VaultSignatures

    lineage = VaultLineage(db)
    signatures = VaultSignatures(db)
    exact_reuse = VaultReuseAudit(db)
    normalized = []
    conflicts = []
    for assignment in assignments or []:
        if not isinstance(assignment, dict):
            raise ValueError("cada assignment Photo Forge debe ser un objeto")
        try:
            asset_id = int(assignment["asset_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("cada assignment requiere asset_id") from exc
        username = str(assignment.get("username") or "").strip().casefold()
        lane = str(assignment.get("lane") or "").strip().casefold()
        if not username or not lane:
            raise ValueError("cada assignment requiere username y lane")
        normalized.append({**assignment, "asset_id": asset_id, "username": username, "lane": lane})

        candidate_ids = {asset_id}
        candidate_ids.update(int(row["asset_id"]) for row in exact_reuse.candidates_for_asset(asset_id, require_usage=False))
        try:
            candidate_ids.update(int(row["asset_id"]) for row in signatures.find_assets_by_perceptual_similarity(asset_id, max_distance=max_distance))
        except ValueError:
            pass
        for matched_asset_id in sorted(candidate_ids):
            for usage in lineage.usages_for_asset(matched_asset_id):
                details = _usage_details(usage.get("details_json"))
                used_username = str(details.get("username") or "").strip().casefold()
                used_lane = str(details.get("lane") or details.get("publication_target") or "").strip().casefold()
                if matched_asset_id == asset_id and used_username == username and used_lane == lane:
                    reason = "same_account_lane"
                elif used_username and used_username != username:
                    reason = "cross_account_reuse"
                else:
                    continue
                conflicts.append({
                    "asset_id": asset_id,
                    "matched_asset_id": matched_asset_id,
                    "username": username,
                    "lane": lane,
                    "reason": reason,
                    "usage": usage,
                })
    status = "blocked" if any(row["reason"] == "same_account_lane" for row in conflicts) else ("warning" if conflicts else "ready")
    return {"status": status, "assignments": normalized, "conflicts": conflicts, "max_distance": int(max_distance)}


def _usage_details(value):
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def make_photo_forge_handler(db=None, *, vault_storage=None):
    def handler(step, checkpoint, save_checkpoint):
        from vault.integration import register_transform_output

        payload = step["payload"]
        source, output = payload["source_path"], payload["output_path"]
        profile = payload.get("profile") or "instagram_post"
        if Path(output).is_file() and Path(output).stat().st_size > 0:
            result = {"output_path": output, "resumed": True, "profile": validate_image(output, profile=profile)}
            log_id = _record_transform(db, vault_storage, source, output, payload, result)
            if log_id and vault_storage is not None:
                register_transform_output(db, vault_storage, log_id)
            return result
        save_checkpoint({"phase": "rendering", "variant_id": payload.get("variant_id")})
        result = render_photo_variant(source, output, payload.get("operations") or {}, profile=profile)
        log_id = _record_transform(db, vault_storage, source, output, payload, result)
        if log_id and vault_storage is not None:
            register_transform_output(db, vault_storage, log_id)
        result["resumed"] = False
        return result
    return handler


def _record_transform(db, vault_storage, source, output, payload, result):
    if db is None or not hasattr(db, "save_video_transform_log"):
        return None
    existing = db.get_video_transform_log_id(output) if hasattr(db, "get_video_transform_log_id") else None
    if existing:
        return existing
    details = {"profile": payload.get("profile", "source"), "variant_id": payload.get("variant_id"), "operations": result.get("operations", payload.get("operations") or {}), "source_info": result.get("source_info"), "output_info": result.get("output_info")}
    return db.save_video_transform_log("photo_forge", os.path.abspath(source), os.path.abspath(output), details)


def _normalize_operations(operations):
    if not isinstance(operations, dict):
        raise ValueError("operations debe ser un objeto")
    unknown = set(operations) - SUPPORTED_OPERATIONS
    if unknown:
        raise ValueError(f"operaciones no soportadas: {sorted(unknown)}")
    normalized = {}
    for key, value in operations.items():
        if key in {"brightness", "contrast", "color", "sharpness"}:
            number = float(value)
            if not 0.0 < number <= 4.0:
                raise ValueError(f"{key} fuera de rango")
            normalized[key] = number
        elif key in {"rotate"}:
            normalized[key] = float(value)
        elif key in {"flip", "grayscale"}:
            normalized[key] = bool(value)
        elif key in {"crop", "resize"}:
            if not isinstance(value, dict):
                raise ValueError(f"{key} debe ser un objeto")
            fields = ("left", "top", "right", "bottom") if key == "crop" else ("width", "height")
            if any(int(value.get(field, 0)) <= 0 for field in fields):
                raise ValueError(f"{key} tiene dimensiones invalidas")
            normalized[key] = {field: int(value[field]) for field in fields}
    if "crop" in normalized and normalized["crop"]["right"] <= normalized["crop"]["left"]:
        raise ValueError("crop tiene coordenadas invalidas")
    if "crop" in normalized and normalized["crop"]["bottom"] <= normalized["crop"]["top"]:
        raise ValueError("crop tiene coordenadas invalidas")
    return normalized


def _profile_rule(profile):
    try:
        return PHOTO_PROFILES[str(profile)]
    except KeyError as exc:
        raise ValueError(f"Perfil de imagen no soportado: {profile}") from exc
