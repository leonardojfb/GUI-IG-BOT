from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
MANIFEST_NAME = "photo_forge_manifest.json"
PHOTO_PROFILES = {
    "original": (None, None),
    "story_9_16": (9 / 16, 1920),
    "post_4_5": (4 / 5, 1350),
    "square_1_1": (1.0, 1080),
    "cover_16_9": (16 / 9, 1920),
    "photo_reel": (None, 2048),
}
VARIATION_STRENGTHS = {"subtle": 0.025, "standard": 0.06, "strong": 0.12}
PARAMETER_LIMITS = {
    "brightness": (0.1, 3.0),
    "contrast": (0.1, 3.0),
    "color": (0.0, 3.0),
    "sharpness": (0.0, 4.0),
    "gamma": (0.1, 3.0),
    "rotation_degrees": (-45.0, 45.0),
    "crop_center_x": (0.0, 1.0),
    "crop_center_y": (0.0, 1.0),
    "grain_amount": (0.0, 1.0),
    "jpeg_quality": (75.0, 100.0),
    "webp_quality": (75.0, 100.0),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    if not cleaned:
        raise ValueError("El nombre de tanda o cuenta no es válido.")
    return cleaned[:80]


def validate_sources(source_paths: list[str | os.PathLike], mirror_horizontal: bool = False) -> list[Path]:
    if not source_paths:
        raise ValueError("Agrega al menos una imagen.")
    paths = [Path(path).resolve() for path in source_paths]
    for path in paths:
        if not path.is_file():
            raise ValueError(f"No existe la imagen: {path}")
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(f"Formato de imagen no admitido: {path.name}")
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as error:
            raise ValueError(f"Imagen inválida o dañada: {path.name}") from error
        with Image.open(path) as image:
            if getattr(image, "n_frames", 1) > 1:
                raise ValueError(f"Photo Forge requiere imágenes fijas; archivo animado: {path.name}")
    return paths


def normalize_parameter_ranges(parameter_ranges: dict | None) -> dict:
    if parameter_ranges is None:
        return {}
    if not isinstance(parameter_ranges, dict):
        raise ValueError("Los rangos Photo Forge deben ser un objeto de parámetros.")
    normalized = {}
    for key, bounds in parameter_ranges.items():
        if key not in PARAMETER_LIMITS:
            raise ValueError(f"Parámetro Photo Forge no reconocido: {key}")
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise ValueError(f"El rango de {key} debe incluir mínimo y máximo.")
        try:
            minimum, maximum = (float(value) for value in bounds)
        except (TypeError, ValueError) as error:
            raise ValueError(f"El rango de {key} debe ser numérico.") from error
        allowed_minimum, allowed_maximum = PARAMETER_LIMITS[key]
        if not math.isfinite(minimum) or not math.isfinite(maximum):
            raise ValueError(f"El rango de {key} debe ser finito.")
        if minimum > maximum:
            raise ValueError(f"El mínimo de {key} no puede superar el máximo.")
        if minimum < allowed_minimum or maximum > allowed_maximum:
            raise ValueError(
                f"El rango de {key} debe estar entre {allowed_minimum:g} y {allowed_maximum:g}."
            )
        normalized[key] = [minimum, maximum]
    return normalized


def normalize_variant_indices(
    variants_per_image: int,
    variant_indices: list[int] | str | None = None,
) -> list[int]:
    try:
        total = int(variants_per_image)
    except (TypeError, ValueError) as error:
        raise ValueError("Las variantes por imagen deben ser un número entero.") from error
    if not 1 <= total <= 20:
        raise ValueError("Las variantes por imagen deben estar entre 1 y 20.")
    if variant_indices is None:
        return list(range(1, total + 1))
    if isinstance(variant_indices, str):
        tokens = [token.strip() for token in variant_indices.split(",")]
        if not tokens or any(not token for token in tokens):
            raise ValueError("Usa números separados por coma, por ejemplo 1,3-5.")
        expanded = []
        for token in tokens:
            if "-" not in token:
                expanded.append(token)
                continue
            parts = token.split("-")
            if len(parts) != 2 or not all(part.strip().isdigit() for part in parts):
                raise ValueError("Usa números separados por coma, por ejemplo 1,3-5.")
            start, end = (int(part.strip()) for part in parts)
            if start > end:
                raise ValueError("El inicio de un rango no puede superar su final.")
            if start < 1 or end > total:
                raise ValueError(f"Elige variantes entre 1 y {total}.")
            expanded.extend(range(start, end + 1))
        variant_indices = expanded
    if not isinstance(variant_indices, (list, tuple)) or not variant_indices:
        raise ValueError("Selecciona al menos una variante para generar.")
    normalized = []
    for value in variant_indices:
        if isinstance(value, bool):
            raise ValueError("Los números de variante deben ser enteros.")
        try:
            index = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError("Los números de variante deben ser enteros.") from error
        if str(value).strip() not in {str(index), f"{index}.0"}:
            raise ValueError("Los números de variante deben ser enteros.")
        if not 1 <= index <= total:
            raise ValueError(f"Elige variantes entre 1 y {total}.")
        if index in normalized:
            raise ValueError(f"La variante {index} está repetida.")
        normalized.append(index)
    return sorted(normalized)


def _variation_parameters(
    source_hash: str, account: dict, batch: str, index: int, strength: float,
    parameter_ranges: dict | None = None,
) -> dict:
    seed_text = f"{source_hash}:{account.get('id')}:{account.get('username')}:{batch}:{index}"
    rng = random.Random(int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16))
    parameters = {
        "brightness": round(rng.uniform(1 - strength, 1 + strength), 4),
        "contrast": round(rng.uniform(1 - strength, 1 + strength), 4),
        "color": round(rng.uniform(1 - strength * 1.35, 1 + strength * 1.35), 4),
        "sharpness": round(rng.uniform(1, 1 + strength * 2), 4),
        "gamma": round(rng.uniform(1 - strength, 1 + strength), 4),
        "rotation_degrees": round(rng.uniform(-strength * 35, strength * 35), 3),
        "crop_center_x": round(rng.uniform(0.46, 0.54), 4),
        "crop_center_y": round(rng.uniform(0.46, 0.54), 4),
        "grain_amount": round(rng.uniform(0, strength / 0.12), 3) if strength else 0,
        "grain_seed": rng.randrange(0, 2**31),
        "jpeg_quality": max(75, min(99, round(100 - strength * 100 + rng.uniform(-2, 2)))),
        "webp_quality": max(75, min(99, round(100 - strength * 100 + rng.uniform(-2, 2)))),
    }
    for key, (minimum, maximum) in (parameter_ranges or {}).items():
        key_seed = f"{seed_text}:{key}"
        key_rng = random.Random(int(hashlib.sha256(key_seed.encode("utf-8")).hexdigest()[:16], 16))
        value = key_rng.uniform(minimum, maximum)
        parameters[key] = round(value) if key.endswith("_quality") else round(value, 4)
    return parameters


def _crop_to_profile(image: Image.Image, profile: str, center_x: float, center_y: float) -> Image.Image:
    ratio, max_dimension = PHOTO_PROFILES[profile]
    if ratio is not None and image.width and image.height:
        current = image.width / image.height
        if current > ratio:
            width = max(1, round(image.height * ratio))
            left = round((image.width - width) * min(1.0, max(0.0, center_x)))
            left = min(image.width - width, max(0, left))
            image = image.crop((left, 0, left + width, image.height))
        else:
            height = max(1, round(image.width / ratio))
            top = round((image.height - height) * min(1.0, max(0.0, center_y)))
            top = min(image.height - height, max(0, top))
            image = image.crop((0, top, image.width, top + height))
    if max_dimension and max(image.size) > max_dimension:
        scale = max_dimension / max(image.size)
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        image = image.resize(size, Image.Resampling.LANCZOS)
    return image


def _render_variant(source_path: Path, output_path: Path, row: dict) -> str:
    if _sha256(source_path) != row["source_sha256"]:
        raise OSError(f"La imagen fuente cambió desde la previsualización: {source_path.name}")
    with Image.open(source_path) as source:
        image_format = source.format or source_path.suffix.lstrip(".").upper()
        icc_profile = source.info.get("icc_profile") if source.mode in {"RGB", "RGBA"} else None
        image = ImageOps.exif_transpose(source).copy()
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")
    params = row.get("parameters") or {}
    profile = row.get("profile", "original")
    center_x, center_y = params.get("crop_center_x", 0.5), params.get("crop_center_y", 0.5)
    alpha = image.getchannel("A") if "A" in image.getbands() else None
    if alpha is not None:
        alpha = _crop_to_profile(alpha, profile, center_x, center_y)
        image = image.convert("RGB")
    image = _crop_to_profile(image, profile, center_x, center_y).convert("RGB")
    if row.get("mirror_horizontal"):
        image = ImageOps.mirror(image)
        if alpha is not None:
            alpha = ImageOps.mirror(alpha)
    from PIL import ImageEnhance
    for key, enhancer in (
        ("brightness", ImageEnhance.Brightness),
        ("contrast", ImageEnhance.Contrast),
        ("color", ImageEnhance.Color),
        ("sharpness", ImageEnhance.Sharpness),
    ):
        if key in params:
            image = enhancer(image).enhance(float(params[key]))
    gamma = float(params.get("gamma", 1.0))
    if abs(gamma - 1.0) >= 0.001:
        lut = [max(0, min(255, round(255 * ((value / 255) ** (1 / gamma))))) for value in range(256)]
        image = image.point(lut * 3)
    grain_amount = float(params.get("grain_amount") or 0)
    if grain_amount >= 0.05:
        rng = random.Random(int(params.get("grain_seed") or 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        point_count = int(image.width * image.height * min(1.0, grain_amount) * 0.002)
        for _ in range(point_count):
            x = rng.randrange(image.width)
            y = rng.randrange(image.height)
            shade = 0 if rng.randrange(2) else 255
            draw.point((x, y), fill=(shade, shade, shade))
    degrees = float(params.get("rotation_degrees") or 0)
    if abs(degrees) >= 0.01:
        image = image.rotate(degrees, resample=Image.Resampling.BICUBIC, expand=False)
        if alpha is not None:
            alpha = alpha.rotate(degrees, resample=Image.Resampling.BICUBIC, expand=False)
        radians = math.radians(abs(degrees))
        safe_factor = 1 / (math.cos(radians) + math.sin(radians))
        if safe_factor < 1:
            width = max(1, round(image.width * safe_factor))
            height = max(1, round(image.height * safe_factor))
            left, top = (image.width - width) // 2, (image.height - height) // 2
            box = (left, top, left + width, top + height)
            image = image.crop(box)
            if alpha is not None:
                alpha = alpha.crop(box)
    if alpha is not None:
        image.putalpha(alpha)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_options = {"icc_profile": icc_profile} if icc_profile else {}
    suffix = output_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        image = image.convert("RGB")
        save_options.update(quality=int(params.get("jpeg_quality", 94)), optimize=True)
        save_format = "JPEG"
    elif suffix == ".webp":
        save_options.update(quality=int(params.get("webp_quality", 92)), method=6)
        save_format = "WEBP"
    else:
        save_format = image_format
    image.save(output_path, format=save_format, **save_options)
    return _sha256(output_path)


def plan_photo_copies(
    source_paths: list[str | os.PathLike],
    accounts: list[dict],
    output_root: str | os.PathLike,
    batch_name: str,
    mirror_horizontal: bool = False,
    *,
    profile: str = "original",
    variants_per_image: int = 1,
    strength: str = "standard",
    parameter_ranges: dict | None = None,
    variant_indices: list[int] | str | None = None,
) -> list[dict]:
    if profile not in PHOTO_PROFILES:
        raise ValueError("Selecciona un perfil de salida válido.")
    if not 1 <= int(variants_per_image) <= 20:
        raise ValueError("Las variantes por imagen deben estar entre 1 y 20.")
    selected_variants = normalize_variant_indices(variants_per_image, variant_indices)
    if strength not in VARIATION_STRENGTHS:
        raise ValueError("Selecciona una intensidad de variación válida.")
    parameter_ranges = normalize_parameter_ranges(parameter_ranges)
    sources = validate_sources(source_paths, mirror_horizontal=mirror_horizontal)
    if not accounts:
        raise ValueError("Selecciona al menos una identidad.")
    if len({str(source).casefold() for source in sources}) != len(sources):
        raise ValueError("La lista contiene una misma ruta de imagen más de una vez.")
    source_hashes = {source: _sha256(source) for source in sources}
    root = Path(output_root).resolve() / _safe_name(batch_name)
    rows = []
    destinations = set()
    for account in accounts:
        username = _safe_name(account.get("username", ""))
        account_id = account.get("id")
        account_dir = root / username
        for source in sources:
            digest = source_hashes[source]
            for variant_index in selected_variants:
                parameters = _variation_parameters(
                    digest, account, _safe_name(batch_name), variant_index,
                    VARIATION_STRENGTHS[strength], parameter_ranges,
                )
                no_transform = (
                    variants_per_image == 1 and profile == "original"
                    and not mirror_horizontal and not parameter_ranges
                )
                if no_transform:
                    parameters = {
                        "brightness": 1.0, "contrast": 1.0, "color": 1.0,
                        "sharpness": 1.0, "gamma": 1.0, "rotation_degrees": 0.0,
                        "crop_center_x": 0.5, "crop_center_y": 0.5,
                        "grain_amount": 0.0, "grain_seed": 0,
                        "jpeg_quality": 100, "webp_quality": 100,
                    }
                recipe_payload = {
                    "version": 1,
                    "profile": profile,
                    "strength": strength,
                    "mirror_horizontal": bool(mirror_horizontal),
                    "variant_index": variant_index,
                    "parameters": parameters,
                    "metadata_profile": "preserve_source" if no_transform else "strip_exif_keep_icc_if_compatible",
                }
                if parameter_ranges:
                    recipe_payload["parameter_ranges"] = parameter_ranges
                recipe_id = hashlib.sha256(
                    json.dumps(recipe_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                profile_suffix = f"__{profile.upper()}"
                filename = (
                    f"{source.stem[:80]}__ACC{account_id or 0}_{username}__{digest[:10]}"
                    f"__V{variant_index:02d}{profile_suffix}{source.suffix.lower()}"
                )
                destination = account_dir / filename
                key = str(destination).casefold()
                if key in destinations:
                    raise ValueError(f"Dos salidas coinciden en el mismo destino: {destination}")
                destinations.add(key)
                rows.append({
                    "username": str(account.get("username", "")),
                    "account_id": account_id,
                    "source_path": str(source),
                    "source_sha256": digest,
                    "mirror_horizontal": bool(mirror_horizontal),
                    "profile": profile,
                    "variant_index": variant_index,
                    "variant_total": int(variants_per_image),
                    "variant_selection": selected_variants,
                    "recipe_version": 1,
                    "recipe_id": recipe_id,
                    "recipe_strength": strength,
                    "parameter_ranges": parameter_ranges,
                    "metadata_profile": recipe_payload["metadata_profile"],
                    "parameters": parameters,
                    "output_path": str(destination),
                })
    return rows


def render_photo_preview(
    source_path: str | os.PathLike,
    output_path: str | os.PathLike,
    *,
    profile: str = "original",
    variant_index: int = 1,
    strength: str = "standard",
    mirror_horizontal: bool = False,
    account: dict | None = None,
    batch_name: str = "preview",
    variants_per_image: int = 3,
    parameter_ranges: dict | None = None,
) -> dict:
    source = Path(source_path).resolve()
    validate_sources([source], mirror_horizontal=mirror_horizontal)
    if profile not in PHOTO_PROFILES or strength not in VARIATION_STRENGTHS:
        raise ValueError("Perfil o intensidad de Photo Forge no válido.")
    if not 1 <= int(variant_index) <= 20:
        raise ValueError("La variante debe estar entre 1 y 20.")
    parameter_ranges = normalize_parameter_ranges(parameter_ranges)
    digest = _sha256(source)
    if (
        int(variants_per_image) == 1 and profile == "original"
        and not mirror_horizontal and not parameter_ranges
    ):
        params = {
            "brightness": 1.0, "contrast": 1.0, "color": 1.0,
            "sharpness": 1.0, "rotation_degrees": 0.0,
            "crop_center_x": 0.5, "crop_center_y": 0.5,
        }
    else:
        params = _variation_parameters(
            digest, account or {"id": 0, "username": "preview"}, _safe_name(batch_name), int(variant_index),
            VARIATION_STRENGTHS[strength], parameter_ranges,
        )
    row = {
        "source_sha256": digest,
        "profile": profile,
        "parameters": params,
        "mirror_horizontal": bool(mirror_horizontal),
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    _render_variant(source, output, row)
    with Image.open(output) as image:
        return {"path": str(output), "width": image.width, "height": image.height, "parameters": params}


def create_photo_copies(plan: list[dict], output_root: str | os.PathLike, batch_name: str) -> dict:
    """Create account-specific copies/variants and atomically record their lineage."""
    root = Path(output_root).resolve() / _safe_name(batch_name)
    manifest_path = root / MANIFEST_NAME
    previous_entries = []
    previous_recipe = {}
    previous_recipe_runs = []
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as stream:
            previous = json.load(stream)
        if not isinstance(previous, dict) or previous.get("version") not in {1, 2} or not isinstance(previous.get("entries"), list):
            raise ValueError("El manifiesto existente de Photo Forge no es válido.")
        previous_entries = previous["entries"]
        previous_recipe = previous.get("recipe") or {}
        previous_recipe_runs = previous.get("recipe_runs") or []
        if not isinstance(previous_recipe_runs, list) or any(not isinstance(item, dict) for item in previous_recipe_runs):
            raise ValueError("El historial de recetas Photo Forge no es válido.")
    previous_by_path = {row.get("output_path"): row for row in previous_entries if isinstance(row, dict)}
    created = []
    existing = []
    written_outputs = []
    try:
        for row in plan:
            source = Path(row["source_path"])
            destination = Path(row["output_path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                prior = previous_by_path.get(str(destination))
                output_hash = _sha256(destination)
                if (
                    prior
                    and prior.get("source_sha256") == row["source_sha256"]
                    and prior.get("recipe_version", 0) == row.get("recipe_version", 0)
                    and prior.get("recipe_id") == row.get("recipe_id")
                    and prior.get("output_sha256") == output_hash
                ):
                    existing.append(prior)
                    continue
                if row.get("recipe_version", 0) == 0 and not row.get("mirror_horizontal") and output_hash == row["source_sha256"]:
                    copied = {**row, "output_sha256": output_hash}
                    existing.append(copied)
                    continue
                else:
                    raise FileExistsError(f"La salida ya existe con otro contenido: {destination}")
            fd, temp_name = tempfile.mkstemp(prefix=f".{destination.stem}.", suffix=f".tmp{destination.suffix}", dir=destination.parent)
            os.close(fd)
            try:
                parameters = row.get("parameters") or {}
                is_unchanged_copy = (
                    row.get("profile", "original") == "original"
                    and not row.get("mirror_horizontal")
                    and not row.get("parameter_ranges")
                    and all(parameters.get(key) == value for key, value in {
                        "brightness": 1.0, "contrast": 1.0, "color": 1.0,
                        "sharpness": 1.0, "gamma": 1.0, "rotation_degrees": 0.0,
                        "grain_amount": 0.0,
                    }.items())
                )
                if is_unchanged_copy:
                    shutil.copy2(source, temp_name)
                    if _sha256(source) != row["source_sha256"]:
                        raise OSError(f"La imagen fuente cambió desde la previsualización: {source.name}")
                else:
                    _render_variant(source, Path(temp_name), row)
                    if _sha256(source) != row["source_sha256"]:
                        raise OSError(f"La imagen fuente cambió durante el render: {source.name}")
                output_hash = _sha256(Path(temp_name))
                if is_unchanged_copy and output_hash != row["source_sha256"]:
                    raise OSError(f"La copia no coincide con la imagen fuente: {source.name}")
                if destination.exists():
                    raise FileExistsError(f"La salida apareció durante la generación: {destination}")
                os.rename(temp_name, destination)
                written_outputs.append(destination)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            with Image.open(destination) as rendered:
                rendered.load()
                output_info = {
                    "width": rendered.width,
                    "height": rendered.height,
                    "format": rendered.format or destination.suffix.lstrip(".").upper(),
                }
            target_ratio = PHOTO_PROFILES[row.get("profile", "original")][0]
            if target_ratio is not None and abs(output_info["width"] / output_info["height"] - target_ratio) > 0.01:
                raise OSError(f"El render no cumple la proporción del perfil {row['profile']}: {destination.name}")
            created.append({**row, "output_sha256": output_hash, "output_info": output_info})
    except Exception:
        for output in written_outputs:
            output.unlink(missing_ok=True)
        raise

    entries_by_path = {row.get("output_path"): row for row in previous_entries}
    entries_by_path.update({row["output_path"]: row for row in [*existing, *created]})
    current_recipe = {
        "version": 1,
        "profile": plan[0].get("profile", "original") if plan else "original",
        "variants_per_image": max((int(row.get("variant_total", row.get("variant_index", 1))) for row in plan), default=1),
        "variant_selection": plan[0].get("variant_selection", []) if plan else [],
        "strength": plan[0].get("recipe_strength", "standard") if plan else "standard",
        "parameter_ranges": plan[0].get("parameter_ranges", {}) if plan else {},
        "recipe_ids": sorted({str(row.get("recipe_id", "")) for row in plan if row.get("recipe_id")}),
    }

    def unique_output_paths(rows):
        paths = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            output_path = str(row.get("output_path", ""))
            if not output_path:
                continue
            key = os.path.normcase(os.path.abspath(output_path)).casefold()
            paths.setdefault(key, output_path)
        return sorted(paths.values(), key=str.casefold)

    recipe_runs = list(previous_recipe_runs)
    if previous_entries and not recipe_runs:
        legacy_recipe_snapshot = dict(previous_recipe) if isinstance(previous_recipe, dict) else {}
        for field in (
            "profile", "variants_per_image", "variant_selection", "strength",
            "parameter_ranges", "recipe_ids",
        ):
            legacy_recipe_snapshot.setdefault(field, None)
        legacy_run = {
            "legacy": True,
            "scope": "unknown_legacy_mapping",
            "recipe_snapshot": legacy_recipe_snapshot,
            "unassigned_output_paths": unique_output_paths(previous_entries),
        }
        legacy_run["run_id"] = "legacy-" + hashlib.sha256(
            json.dumps(legacy_run, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        recipe_runs.append(legacy_run)

    if plan:
        run_payload = {
            "recipe": current_recipe,
            "requested_output_paths": unique_output_paths(plan),
        }
        recipe_runs.append({
            "run_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            **run_payload,
            "created_output_paths": unique_output_paths(created),
            "reused_output_paths": unique_output_paths(existing),
        })
    retained_entries = list(entries_by_path.values())
    known_variant_totals = {
        int(row["variant_total"])
        for row in retained_entries
        if row.get("variant_total") is not None
    }
    has_unknown_variant_totals = any(row.get("variant_total") is None for row in retained_entries)
    variant_totals = sorted(known_variant_totals)
    if has_unknown_variant_totals:
        variant_totals.append(None)
    known_profiles = {str(row["profile"]) for row in retained_entries if row.get("profile") is not None}
    has_unknown_profiles = any(row.get("profile") is None for row in retained_entries)
    profiles = sorted(known_profiles)
    if has_unknown_profiles:
        profiles.append(None)
    known_variant_indices = {
        int(row["variant_index"])
        for row in retained_entries
        if row.get("variant_index") is not None
    }
    has_unknown_variant_indices = any(row.get("variant_index") is None for row in retained_entries)
    variant_indices = sorted(known_variant_indices)
    if has_unknown_variant_indices:
        variant_indices.append(None)
    recipe_summary = {
        "entry_count": len(retained_entries),
        "profiles": profiles,
        "profile_unknown": has_unknown_profiles,
        "variant_indices": variant_indices,
        "variant_index_unknown": has_unknown_variant_indices,
        "variant_totals": variant_totals,
        "variant_total_unknown": has_unknown_variant_totals,
        "recipe_ids": sorted({str(row.get("recipe_id")) for row in retained_entries if row.get("recipe_id")}),
    }
    manifest = {
        "version": 1,
        "batch": _safe_name(batch_name),
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "recipe": current_recipe if plan else previous_recipe,
        "recipe_scope": "latest_run" if plan else "legacy",
        "recipe_runs": recipe_runs,
        "recipe_summary": recipe_summary,
        "entries": retained_entries,
    }
    fd, temp_name = tempfile.mkstemp(prefix=f".{MANIFEST_NAME}.", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, manifest_path)
    except Exception:
        for output in written_outputs:
            output.unlink(missing_ok=True)
        raise
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return {
        "created": created,
        "existing": existing,
        "manifest_path": str(manifest_path),
        "batch_dir": str(root),
    }


def validated_account_outputs(
    batch_dir: str | os.PathLike,
    username: str,
    profile: str | None = None,
) -> list[Path]:
    """Return this account's Photo Forge outputs in manifest order, fail closed on drift."""
    root = Path(batch_dir).resolve()
    manifest_path = root / MANIFEST_NAME
    try:
        with manifest_path.open("r", encoding="utf-8") as stream:
            manifest = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("El manifiesto de Photo Forge no se puede leer.") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("version") not in {1, 2}
        or not isinstance(manifest.get("entries"), list)
    ):
        raise ValueError("El manifiesto existente de Photo Forge no es válido.")

    expected_dir = (root / _safe_name(username)).resolve()
    outputs = []
    seen = set()
    for row in manifest["entries"]:
        if not isinstance(row, dict):
            raise ValueError("El manifiesto de Photo Forge contiene una entrada inválida.")
        if row.get("username") != username:
            continue
        if profile is not None and row.get("profile", "original") != profile:
            continue
        try:
            recorded_name = Path(str(row["output_path"])).name
            expected_hash = str(row["output_sha256"]).lower()
        except (KeyError, OSError, TypeError, ValueError) as error:
            raise ValueError("Una salida de Photo Forge tiene metadatos inválidos.") from error
        if not recorded_name or recorded_name in {".", ".."}:
            raise ValueError("Una salida de Photo Forge tiene un nombre inválido.")
        output = (expected_dir / recorded_name).resolve()
        if output.parent != expected_dir or output.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(f"La salida de Photo Forge está fuera de la carpeta de @{username}.")
        key = os.path.normcase(str(output)).casefold()
        if key in seen:
            raise ValueError(f"El manifiesto repite una salida de Photo Forge: {output.name}.")
        seen.add(key)
        if not output.is_file():
            raise ValueError(f"Falta una salida de Photo Forge: {output.name}.")
        if len(expected_hash) != 64 or _sha256(output) != expected_hash:
            raise ValueError(f"La salida de Photo Forge cambió desde su validación: {output.name}.")
        outputs.append(output)
    if not outputs:
        raise ValueError(f"Photo Forge no registra finales para @{username} en esta tanda.")
    return outputs


def _render_mirrored_image(source_path: Path, output_path: Path) -> None:
    with Image.open(source_path) as source:
        image_format = source.format
        image = ImageOps.mirror(ImageOps.exif_transpose(source))
        if image_format == "PNG" and source.mode == "P" and "transparency" in source.info:
            image = image.convert("RGBA")
        exif = source.getexif()
        if 274 in exif:
            exif[274] = 1
        save_options = {}
        if exif:
            save_options["exif"] = exif.tobytes()
        if source.info.get("icc_profile"):
            save_options["icc_profile"] = source.info["icc_profile"]
        if image_format == "JPEG":
            image = image.convert("RGB")
            save_options.update(quality=100, subsampling=0, optimize=True)
        elif image_format == "WEBP":
            save_options.update(lossless=True, method=6)
        image.save(output_path, format=image_format, **save_options)
