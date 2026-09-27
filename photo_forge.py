from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
MANIFEST_NAME = "photo_forge_manifest.json"


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
        if mirror_horizontal:
            with Image.open(path) as image:
                if getattr(image, "n_frames", 1) > 1:
                    raise ValueError(f"No se admite una imagen animada para espejo: {path.name}")
    return paths


def plan_photo_copies(
    source_paths: list[str | os.PathLike],
    accounts: list[dict],
    output_root: str | os.PathLike,
    batch_name: str,
    mirror_horizontal: bool = False,
) -> list[dict]:
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
            mirror_suffix = "__MIRROR" if mirror_horizontal else ""
            filename = f"{source.stem[:100]}__ACC{account_id or 0}_{username}__{digest[:10]}{mirror_suffix}{source.suffix.lower()}"
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
                "output_path": str(destination),
            })
    return rows


def create_photo_copies(plan: list[dict], output_root: str | os.PathLike, batch_name: str) -> dict:
    """Create account-specific copies/variants and atomically record their lineage."""
    root = Path(output_root).resolve() / _safe_name(batch_name)
    manifest_path = root / MANIFEST_NAME
    previous_entries = []
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as stream:
            previous = json.load(stream)
        if not isinstance(previous, dict) or previous.get("version") != 1 or not isinstance(previous.get("entries"), list):
            raise ValueError("El manifiesto existente de Photo Forge no es válido.")
        previous_entries = previous["entries"]
    previous_by_path = {row.get("output_path"): row for row in previous_entries if isinstance(row, dict)}
    created = []
    existing = []
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
                    and bool(prior.get("mirror_horizontal")) == bool(row.get("mirror_horizontal"))
                    and prior.get("output_sha256") == output_hash
                ):
                    existing.append(prior)
                    continue
                if not row.get("mirror_horizontal") and output_hash == row["source_sha256"]:
                    copied = {**row, "output_sha256": output_hash}
                    existing.append(copied)
                    continue
                else:
                    raise FileExistsError(f"La salida ya existe con otro contenido: {destination}")
            fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".part", dir=destination.parent)
            os.close(fd)
            try:
                if row.get("mirror_horizontal"):
                    if _sha256(source) != row["source_sha256"]:
                        raise OSError(f"La imagen fuente cambió desde la previsualización: {source.name}")
                    _render_mirrored_image(source, Path(temp_name))
                else:
                    shutil.copy2(source, temp_name)
                output_hash = _sha256(Path(temp_name))
                if not row.get("mirror_horizontal") and output_hash != row["source_sha256"]:
                    raise OSError(f"La copia no coincide con la imagen fuente: {source.name}")
                if destination.exists():
                    raise FileExistsError(f"La salida apareció durante la generación: {destination}")
                os.rename(temp_name, destination)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            created.append({**row, "output_sha256": output_hash})
    except Exception:
        for row in created:
            Path(row["output_path"]).unlink(missing_ok=True)
        raise

    entries_by_path = {row.get("output_path"): row for row in previous_entries}
    entries_by_path.update({row["output_path"]: row for row in [*existing, *created]})
    manifest = {
        "version": 1,
        "batch": _safe_name(batch_name),
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "entries": list(entries_by_path.values()),
    }
    fd, temp_name = tempfile.mkstemp(prefix=f".{MANIFEST_NAME}.", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, manifest_path)
    except Exception:
        for row in created:
            Path(row["output_path"]).unlink(missing_ok=True)
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


def validated_account_outputs(batch_dir: str | os.PathLike, username: str) -> list[Path]:
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
        or manifest.get("version") != 1
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
