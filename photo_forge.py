from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


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


def validate_sources(source_paths: list[str | os.PathLike]) -> list[Path]:
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
    return paths


def plan_photo_copies(
    source_paths: list[str | os.PathLike],
    accounts: list[dict],
    output_root: str | os.PathLike,
    batch_name: str,
) -> list[dict]:
    sources = validate_sources(source_paths)
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
            filename = f"{source.stem[:100]}__ACC{account_id or 0}_{username}__{digest[:10]}{source.suffix.lower()}"
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
                "output_path": str(destination),
            })
    return rows


def create_photo_copies(plan: list[dict], output_root: str | os.PathLike, batch_name: str) -> dict:
    """Create byte-preserving per-account image files and an atomic provenance manifest."""
    root = Path(output_root).resolve() / _safe_name(batch_name)
    manifest_path = root / MANIFEST_NAME
    previous_entries = []
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as stream:
            previous = json.load(stream)
        if not isinstance(previous, dict) or previous.get("version") != 1 or not isinstance(previous.get("entries"), list):
            raise ValueError("El manifiesto existente de Photo Forge no es válido.")
        previous_entries = previous["entries"]
    created = []
    existing = []
    try:
        for row in plan:
            source = Path(row["source_path"])
            destination = Path(row["output_path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if _sha256(destination) != row["source_sha256"]:
                    raise FileExistsError(f"La salida ya existe con otro contenido: {destination}")
                existing.append(row)
                continue
            fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".part", dir=destination.parent)
            os.close(fd)
            try:
                shutil.copy2(source, temp_name)
                if _sha256(Path(temp_name)) != row["source_sha256"]:
                    raise OSError(f"La copia no coincide con la imagen fuente: {source.name}")
                if destination.exists():
                    raise FileExistsError(f"La salida apareció durante la generación: {destination}")
                os.rename(temp_name, destination)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            created.append(row)
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
