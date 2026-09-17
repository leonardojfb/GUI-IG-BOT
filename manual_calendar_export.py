"""Portable, checksum-verified manual calendar packages."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
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


def export_manifest_v2_package(manifest_path, target_path):
    try:
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"manifest ilegible: {manifest_path}") from exc
    if payload.get("version") != 2:
        raise ValueError("el export manual requiere manifest v2")
    entries = []
    for entry in payload.get("entries") or []:
        if not isinstance(entry, dict) or entry.get("manifest_entry_version") != 2:
            raise ValueError("entry incompatible con manifest v2")
        entries.append({**entry, "media_path": entry.get("source_path")})
    return export_manual_package(entries, target_path)


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


def preview_manual_package_import(package_path, destination_root):
    """Verify a package and report the exact files that an import would create."""
    verification = verify_manual_package(package_path)
    if verification["status"] != "ok":
        return {"status": "error", "error": verification["error"], "entries": 0, "conflicts": []}
    destination = Path(destination_root).resolve()
    conflicts = []
    entries = []
    try:
        with zipfile.ZipFile(package_path) as archive:
            manifest = json.loads(archive.read("package_manifest.json").decode("utf-8"))
            for entry in manifest.get("entries") or []:
                relative = _safe_archive_path(entry.get("media_path"))
                target = destination / relative
                if target.exists():
                    conflicts.append(relative.as_posix())
                entries.append({"media_path": relative.as_posix(), "target_path": str(target)})
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        return {"status": "error", "error": str(exc), "entries": 0, "conflicts": []}
    return {"status": "conflict" if conflicts else "ready", "entries": len(entries), "conflicts": conflicts, "files": entries}


def import_manual_package(package_path, destination_root, *, confirm=False, audit_path=None, actor="local"):
    if not confirm:
        raise PermissionError("la importacion requiere confirm=True")
    preview = preview_manual_package_import(package_path, destination_root)
    if preview["status"] != "ready":
        raise FileExistsError("el paquete no esta listo para importar: " + ", ".join(preview.get("conflicts", [])))
    destination = Path(destination_root).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.import-", dir=str(destination.parent)))
    try:
        with zipfile.ZipFile(package_path) as archive:
            for item in preview["files"]:
                relative = Path(item["media_path"])
                target = temporary / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(relative.as_posix()) as source, target.open("wb") as output:
                    output.write(source.read())
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            import shutil
            shutil.rmtree(temporary)
    if audit_path:
        _append_import_audit(
            audit_path,
            {
                "event": "manual_calendar_import",
                "actor": str(actor or "local"),
                "package_sha256": _sha256(package_path),
                "destination": str(destination),
                "entries": int(preview["entries"]),
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )
    return {"status": "imported", "entries": preview["entries"], "path": str(destination)}


def _sha256(path):
    return _sha256_bytes(Path(path).read_bytes())


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _append_import_audit(path, event):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _safe_archive_path(value):
    relative = Path(str(value or ""))
    if not str(value) or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("ruta de archivo no segura en el paquete")
    return relative
