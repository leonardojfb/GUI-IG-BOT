from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from social_publishing import default_publication_target, validate_publication_metadata

MANIFEST_VERSION = 1
MANIFEST_FILENAME = "calendar_manifest.json"


def manifest_path(base_dir: str | os.PathLike) -> Path:
    return Path(base_dir) / MANIFEST_FILENAME


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_entry(
    username: str,
    account_id: int | None,
    delivery_kind: str,
    day: int,
    slot: int,
    tanda: str,
    source_path: str,
    telegram_filename: str,
    transform_log_id: int | None = None,
    created_at: str | None = None,
    *,
    publication_target: str | None = None,
    caption: str = "",
    story_link_url: str = "",
    story_announcement_text: str = "",
    platform_payload: dict | None = None,
    manual_status: str = "planned",
) -> dict:
    target = publication_target or default_publication_target(delivery_kind)
    metadata = validate_publication_metadata(
        target,
        str(delivery_kind),
        caption,
        story_link_url,
        story_announcement_text,
        platform_payload,
    )
    return {
        "id": str(uuid.uuid4()),
        "username": str(username),
        "account_id": account_id,
        "delivery_kind": str(delivery_kind),
        "day": int(day),
        "slot": int(slot),
        "tanda": str(tanda),
        "source_path": str(Path(source_path).resolve()),
        "telegram_filename": str(telegram_filename),
        "transform_log_id": transform_log_id,
        "created_at": created_at or _now_utc(),
        "publication_target": target,
        "caption": metadata["caption"],
        "story_link_url": metadata["story_link_url"],
        "story_announcement_text": metadata["story_announcement_text"],
        "platform_payload": metadata["platform_payload"],
        "manual_status": str(manual_status or "planned"),
    }


def _read_payload(path: Path) -> dict:
    if not path.exists():
        return {"version": MANIFEST_VERSION, "entries": []}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("version") != MANIFEST_VERSION:
        raise ValueError(f"Unsupported calendar manifest version: {payload.get('version')}")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("calendar_manifest.json must contain an entries list")
    return payload


def _write_payload(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": MANIFEST_VERSION, "entries": entries}
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def load_entries(path: str | os.PathLike, require_source: bool = True) -> list[dict]:
    manifest = Path(path)
    entries = list(_read_payload(manifest)["entries"])
    if not require_source:
        return entries
    return [entry for entry in entries if Path(entry.get("source_path", "")).exists()]


def publication_target_for_entry(entry: dict) -> str:
    return entry.get("publication_target") or default_publication_target(
        entry.get("delivery_kind", "normal")
    )


def replace_entries(
    path: str | os.PathLike,
    entries: list[dict],
    usernames: set[str],
    delivery_kind: str,
    publication_target: str | None = None,
) -> list[dict]:
    manifest = Path(path)
    current = list(_read_payload(manifest)["entries"])
    affected = {str(name) for name in usernames}
    kept = [
        entry
        for entry in current
        if not (
            entry.get("username") in affected
            and entry.get("delivery_kind") == delivery_kind
            and (
                publication_target is None
                or publication_target_for_entry(entry) == publication_target
            )
        )
    ]
    merged = kept + list(entries)
    _write_payload(manifest, merged)
    return merged


def remove_entries_for_accounts(path: str | os.PathLike, usernames: set[str]) -> int:
    manifest = Path(path)
    current = list(_read_payload(manifest)["entries"])
    affected = {str(name) for name in usernames}
    kept = [entry for entry in current if entry.get("username") not in affected]
    removed = len(current) - len(kept)
    _write_payload(manifest, kept)
    return removed
