"""Portable, checksum-verified manual calendar packages."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path


def export_manual_package(entries, target_path):
    normalized = []
    files = {}
    for index, entry in enumerate(entries or [], start=1):
        if not isinstance(entry, dict):
            raise ValueError("cada entrada debe ser un objeto")
        source = Path(entry.get("media_path") or "")
        if not source.is_file():
            raise FileNotFoundError(str(source))
        archive_name = f"media/{index:04d}{source.suffix.lower()}"
        files[archive_name] = source
        normalized.append({**{key: value for key, value in entry.items() if key != "media_path"}, "media_path": archive_name, "sha256": _sha256(source)})
    if not normalized:
        raise ValueError("entries debe contener al menos una entrada")
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "package_type": "manual_calendar", "entries": normalized}
    temp_name = ""
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        os.close(fd)
        with zipfile.ZipFile(temp_name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("package_manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2))
            for name, source in files.items():
                archive.write(source, name)
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return {"path": str(target), "entries": len(normalized), "schema_version": 1}


def verify_manual_package(package_path):
    try:
        with zipfile.ZipFile(package_path) as archive:
            manifest = json.loads(archive.read("package_manifest.json").decode("utf-8"))
            if manifest.get("schema_version") != 1:
                raise ValueError("schema de paquete no soportado")
            checked = 0
            for entry in manifest.get("entries") or []:
                name = entry.get("media_path")
                data = archive.read(name)
                if _sha256_bytes(data) != entry.get("sha256"):
                    raise ValueError(f"checksum invalido: {name}")
                checked += 1
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        return {"status": "error", "error": str(exc)}
    return {"status": "ok", "entries": checked, "schema_version": 1}


def _sha256(path):
    return _sha256_bytes(Path(path).read_bytes())


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()
