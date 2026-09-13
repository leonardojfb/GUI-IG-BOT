from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from social_publishing import (
    PUBLICATION_TARGETS,
    TELEGRAM_PUBLICATION_TARGETS,
    default_publication_target,
    validate_publication_metadata,
)

MANIFEST_VERSION = 1
SUPPORTED_MANIFEST_VERSIONS = {1, 2}
MANIFEST_FILENAME = "calendar_manifest.json"
MANIFEST_LOCK_FILENAME = ".calendar_manifest.lock"
MANIFEST_JOURNAL_FILENAME = ".calendar_manifest_journal.json"


def manifest_path(base_dir: str | os.PathLike) -> Path:
    return Path(base_dir) / MANIFEST_FILENAME


def manifest_lock_path(path: str | os.PathLike) -> Path:
    return Path(path).with_name(MANIFEST_LOCK_FILENAME)


def manifest_journal_path(path: str | os.PathLike) -> Path:
    return Path(path).with_name(MANIFEST_JOURNAL_FILENAME)


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
    caption_mode: str | None = None,
    created_at: str | None = None,
    *,
    publication_target: str | None = None,
    caption: str = "",
    story_link_url: str = "",
    story_announcement_text: str = "",
    caption_snapshot: dict | None = None,
    platform_payload: dict | None = None,
    manual_status: str = "planned",
) -> dict:
    target = publication_target or default_publication_target(delivery_kind)
    if target not in TELEGRAM_PUBLICATION_TARGETS:
        raise ValueError(
            "Los destinos manuales requieren manifest v2 y permanecen desactivados."
        )
    metadata = validate_publication_metadata(
        target,
        str(delivery_kind),
        caption,
        story_link_url,
        story_announcement_text,
        platform_payload,
    )
    entry = {
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
    if caption_mode:
        entry["caption_mode"] = str(caption_mode)
    if caption_snapshot:
        entry["caption_snapshot"] = dict(caption_snapshot)
    return entry


def build_entry_v2(
    username: str,
    account_id: int | None,
    delivery_kind: str,
    day: int,
    slot: int,
    tanda: str,
    source_path: str,
    display_filename: str,
    *,
    publication_target: str,
    lane: str,
    placement: str,
    media_class: str,
    method: str,
    policy_snapshot: dict,
    transform_log_id: int | None = None,
    caption_mode: str | None = None,
    created_at: str | None = None,
    caption: str = "",
    story_link_url: str = "",
    story_announcement_text: str = "",
    caption_snapshot: dict | None = None,
    platform_payload: dict | None = None,
    manual_status: str = "planned",
) -> dict:
    if publication_target not in PUBLICATION_TARGETS:
        raise ValueError(f"publication_target no soportado: {publication_target}")
    metadata = validate_publication_metadata(
        publication_target,
        str(delivery_kind),
        caption,
        story_link_url,
        story_announcement_text,
        platform_payload,
    )
    entry = {
        "id": str(uuid.uuid4()),
        "manifest_entry_version": 2,
        "username": str(username),
        "account_id": account_id,
        "delivery_kind": str(delivery_kind),
        "day": int(day),
        "slot": int(slot),
        "tanda": str(tanda),
        "source_path": str(Path(source_path).resolve()),
        "telegram_filename": str(display_filename),
        "display_filename": str(display_filename),
        "transform_log_id": transform_log_id,
        "created_at": created_at or _now_utc(),
        "publication_target": publication_target,
        "lane": _required_label(lane, "lane"),
        "placement": _required_label(placement, "placement"),
        "media_class": _required_label(media_class, "media_class"),
        "method": _required_label(method, "method"),
        "policy_snapshot": dict(policy_snapshot or {}),
        "caption": metadata["caption"],
        "story_link_url": metadata["story_link_url"],
        "story_announcement_text": metadata["story_announcement_text"],
        "platform_payload": metadata["platform_payload"],
        "manual_status": str(manual_status or "planned"),
    }
    if caption_mode:
        entry["caption_mode"] = str(caption_mode)
    if caption_snapshot:
        entry["caption_snapshot"] = dict(caption_snapshot)
    return entry


def _required_label(value: str, field: str) -> str:
    label = str(value or "").strip()
    if not label:
        raise ValueError(f"{field} no puede estar vacio")
    return label


def _read_payload(path: Path) -> dict:
    if not path.exists():
        return {"version": MANIFEST_VERSION, "entries": []}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("version") not in SUPPORTED_MANIFEST_VERSIONS:
        raise ValueError(f"Unsupported calendar manifest version: {payload.get('version')}")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("calendar_manifest.json must contain an entries list")
    return payload


def assert_manifest_ready(path: str | os.PathLike) -> None:
    manifest = Path(path)
    if manifest_journal_path(manifest).exists():
        raise RuntimeError(
            "calendar manifest journal pendiente; requiere reconciliacion antes de escribir"
        )
    if manifest_lock_path(manifest).exists():
        raise RuntimeError("calendar manifest lock activo; otro escritor esta trabajando")


def _acquire_manifest_lock(path: Path, operation: str) -> Path:
    lock_path = manifest_lock_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(
            "calendar manifest lock activo; otro escritor esta trabajando"
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "operation": operation,
                    "manifest_path": str(path),
                    "created_at": _now_utc(),
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
    except Exception:
        if lock_path.exists():
            lock_path.unlink()
        raise
    return lock_path


def _write_manifest_journal(
    path: Path,
    *,
    operation: str,
    version: int,
    entries_count: int,
) -> Path:
    journal_path = manifest_journal_path(path)
    with journal_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "operation": operation,
                "manifest_path": str(path),
                "version": int(version),
                "entries_count": int(entries_count),
                "created_at": _now_utc(),
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")
    return journal_path


def _atomic_write_payload(path: Path, payload: dict) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _write_guarded_payload(
    path: Path,
    entries: list[dict],
    version: int,
    *,
    operation: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_manifest_ready(path)
    lock_path = _acquire_manifest_lock(path, operation)
    journal_path = manifest_journal_path(path)
    payload = {"version": int(version), "entries": entries}
    write_completed = False
    try:
        _write_manifest_journal(
            path,
            operation=operation,
            version=version,
            entries_count=len(entries),
        )
        _atomic_write_payload(path, payload)
        write_completed = True
    finally:
        if write_completed and journal_path.exists():
            journal_path.unlink()
        if lock_path.exists():
            lock_path.unlink()


def _write_payload(path: Path, entries: list[dict]) -> None:
    _write_guarded_payload(path, entries, MANIFEST_VERSION, operation="write_manifest_v1")


def _write_payload_version(path: Path, entries: list[dict], version: int) -> None:
    _write_guarded_payload(
        path,
        entries,
        int(version),
        operation=f"write_manifest_v{int(version)}",
    )


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
    target = publication_target or default_publication_target(delivery_kind)
    if target not in TELEGRAM_PUBLICATION_TARGETS:
        raise ValueError(
            "Los destinos manuales requieren manifest v2 y permanecen desactivados."
        )
    if any(
        publication_target_for_entry(entry) not in TELEGRAM_PUBLICATION_TARGETS
        for entry in entries
    ):
        raise ValueError(
            "Los destinos manuales requieren manifest v2 y permanecen desactivados."
        )
    kept = [
        entry
        for entry in current
        if not (
            entry.get("username") in affected
            and entry.get("delivery_kind") == delivery_kind
            and publication_target_for_entry(entry) == target
        )
    ]
    merged = kept + list(entries)
    _write_payload(manifest, merged)
    return merged


def replace_entries_v2(
    path: str | os.PathLike,
    entries: list[dict],
    usernames: set[str],
    lane: str,
    window: dict | None = None,
) -> list[dict]:
    manifest = Path(path)
    payload = _read_payload(manifest)
    if payload.get("version") != 2:
        raise ValueError("replace_entries_v2 requiere calendar_manifest version 2")
    affected = {str(name) for name in usernames}
    target_lane = _required_label(lane, "lane")
    start_day = int((window or {}).get("start_day", 1))
    end_day = int((window or {}).get("end_day", 999999))
    kept = [
        entry
        for entry in payload["entries"]
        if not (
            entry.get("username") in affected
            and entry.get("lane") == target_lane
            and start_day <= int(entry.get("day") or 0) <= end_day
        )
    ]
    merged = kept + list(entries)
    _write_payload_version(manifest, merged, 2)
    return merged


def remove_entries_for_accounts(
    path: str | os.PathLike,
    usernames: set[str],
    publication_targets: set[str] | frozenset[str] | None = None,
) -> int:
    manifest = Path(path)
    current = list(_read_payload(manifest)["entries"])
    affected = {str(name) for name in usernames}
    targets = set(publication_targets) if publication_targets is not None else None
    kept = [
        entry
        for entry in current
        if not (
            entry.get("username") in affected
            and (
                targets is None
                or publication_target_for_entry(entry) in targets
            )
        )
    ]
    removed = len(current) - len(kept)
    _write_payload(manifest, kept)
    return removed
