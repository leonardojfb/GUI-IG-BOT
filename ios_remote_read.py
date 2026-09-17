"""Read-only, secret-free snapshots from iOS remote tooling."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


SENSITIVE_KEY_PARTS = ("cookie", "session", "token", "authorization", "password", "secret", "csrf", "header", "x-ig-")


def sanitize_snapshot(payload):
    if not isinstance(payload, dict):
        raise ValueError("el snapshot debe ser un objeto")
    return _sanitize(payload)


def read_snapshot(path: str | os.PathLike) -> dict:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError(f"snapshot iOS ilegible: {path}") from exc
    return sanitize_snapshot(payload)


def write_sanitized_snapshot(source_path, target_path) -> dict:
    sanitized = read_snapshot(source_path)
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"schema_version": 1, "source": "ios_remote_read", "snapshot": sanitized}, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return {"path": str(target), "schema_version": 1, "keys_removed": True}


def _sanitize(value):
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items() if not _is_sensitive_key(key)}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _is_sensitive_key(key) -> bool:
    normalized = str(key).strip().lower().replace("_", "-")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
