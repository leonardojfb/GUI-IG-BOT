"""Read-only adapter for an exported ios-remote container snapshot."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ios_remote_read import sanitize_snapshot


_PROFILE_FIELDS = ("profile_id", "version", "model", "os", "carrier", "locale", "timezone", "location", "updated_at")
_ACCOUNT_FIELDS = ("account_id", "username")
_CONTAINER_FIELDS = ("container_id", "name", "status", "accounts", "device_profile")


def load_ios_remote_snapshot(path):
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"export ios-remote ilegible: {path}") from exc
    clean = sanitize_snapshot(payload)
    containers = clean.get("containers")
    if not isinstance(containers, list) or not containers:
        raise ValueError("el export ios-remote debe contener containers")
    normalized = []
    for index, container in enumerate(containers, start=1):
        if not isinstance(container, dict):
            raise ValueError(f"contenedor invalido en posicion {index}")
        normalized_container = {key: container.get(key) for key in _CONTAINER_FIELDS if key in container}
        if not normalized_container.get("container_id"):
            raise ValueError(f"container_id faltante en posicion {index}")
        if not normalized_container.get("device_profile"):
            raise ValueError(f"device_profile faltante en posicion {index}")
        profile = normalized_container["device_profile"]
        if not isinstance(profile, dict) or not profile.get("profile_id") or not profile.get("version"):
            raise ValueError(f"device_profile incompleto en posicion {index}")
        normalized_container["device_profile"] = {key: profile.get(key) for key in _PROFILE_FIELDS if key in profile}
        accounts = normalized_container.get("accounts") or []
        if not isinstance(accounts, list):
            raise ValueError(f"accounts invalido en posicion {index}")
        normalized_container["accounts"] = [
            {key: account.get(key) for key in _ACCOUNT_FIELDS if key in account}
            for account in accounts if isinstance(account, dict) and account.get("account_id")
        ]
        normalized.append(normalized_container)
    snapshot = {"schema_version": 1, "source": "ios_remote_read", "containers": normalized}
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**snapshot, "snapshot_hash": f"sha256:{hashlib.sha256(encoded).hexdigest()}"}
