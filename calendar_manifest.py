from __future__ import annotations

import json
import os
import tempfile
import uuid
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path

from social_publishing import (
    INSTAGRAM_TRIAL_REEL,
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
    schedule_snapshot: dict | None = None,
    platform_payload: dict | None = None,
    manual_status: str = "planned",
) -> dict:
    if publication_target not in PUBLICATION_TARGETS:
        raise ValueError(f"publication_target no soportado: {publication_target}")
    lane_label = _required_label(lane, "lane")
    placement_label = _required_label(placement, "placement")
    _validate_trial_lane_policy(str(delivery_kind), publication_target, lane_label)
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
        "lane": lane_label,
        "placement": placement_label,
        "media_class": _required_label(media_class, "media_class"),
        "method": _required_label(method, "method"),
        "policy_snapshot": _normalize_policy_snapshot(
            policy_snapshot,
            delivery_kind=str(delivery_kind),
            publication_target=publication_target,
            lane=lane_label,
        ),
        "caption": metadata["caption"],
        "story_link_url": metadata["story_link_url"],
        "story_announcement_text": metadata["story_announcement_text"],
        "platform_payload": metadata["platform_payload"],
        "manual_status": str(manual_status or "planned"),
    }
    entry["schedule_snapshot"] = _normalize_schedule_snapshot(
        schedule_snapshot,
        day=int(day),
        slot=int(slot),
        lane=entry["lane"],
        placement=entry["placement"],
    )
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


def _normalize_schedule_snapshot(
    snapshot: dict | None,
    *,
    day: int,
    slot: int,
    lane: str,
    placement: str,
) -> dict:
    normalized = dict(snapshot or {})
    if normalized.get("lane") not in {None, lane}:
        raise ValueError("schedule_snapshot lane no coincide con la entrada")
    if normalized.get("placement") not in {None, placement}:
        raise ValueError("schedule_snapshot placement no coincide con la entrada")
    for key, expected in {
        "day": int(day),
        "slot": int(slot),
    }.items():
        if key in normalized and int(normalized[key]) != expected:
            raise ValueError(f"schedule_snapshot {key} no coincide con la entrada")
        normalized[key] = expected
    normalized["lane"] = lane
    normalized["placement"] = placement
    return normalized


def _validate_trial_lane_policy(delivery_kind: str, publication_target: str, lane: str) -> None:
    if delivery_kind == "trial":
        if publication_target != INSTAGRAM_TRIAL_REEL or lane != "trial_reel":
            raise ValueError("Las publicaciones Trial deben usar carril trial_reel.")
        return
    if lane == "trial_reel" or publication_target == INSTAGRAM_TRIAL_REEL:
        raise ValueError("El carril trial_reel solo acepta publicaciones Trial.")


def _trial_policy_label(delivery_kind: str) -> str:
    return "trial_reel_only" if delivery_kind == "trial" else "standard_reel"


def _normalize_policy_snapshot(
    snapshot: dict | None,
    *,
    delivery_kind: str,
    publication_target: str,
    lane: str,
) -> dict:
    _validate_trial_lane_policy(delivery_kind, publication_target, lane)
    normalized = dict(snapshot or {})
    normalized.setdefault("trial_policy", _trial_policy_label(delivery_kind))
    normalized.setdefault("publication_target", publication_target)
    normalized.setdefault("lane", lane)
    return normalized


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


def _manifest_revision(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


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


def _lane_for_legacy_entry(entry: dict) -> str:
    target = publication_target_for_entry(entry)
    if target == "instagram_trial_reel":
        return "trial_reel"
    if target == "instagram_reel":
        return "reel"
    return str(target)


def _placement_for_publication_target(publication_target: str) -> str:
    if publication_target == "instagram_story":
        return "story"
    return "feed"


def _media_class_for_filename(filename: str) -> str:
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        return "image"
    return "video"


def _migrate_entry_v1_to_v2(entry: dict) -> dict:
    migrated = dict(entry)
    target = publication_target_for_entry(migrated)
    display_filename = migrated.get("display_filename") or migrated.get("telegram_filename") or ""
    migrated["manifest_entry_version"] = 2
    migrated["publication_target"] = target
    migrated["lane"] = _lane_for_legacy_entry(migrated)
    migrated["placement"] = _placement_for_publication_target(target)
    migrated["media_class"] = _media_class_for_filename(display_filename)
    migrated["method"] = migrated.get("method") or "telegram"
    migrated["display_filename"] = str(display_filename)
    migrated["schedule_snapshot"] = _normalize_schedule_snapshot(
        migrated.get("schedule_snapshot"),
        day=int(migrated.get("day") or 0),
        slot=int(migrated.get("slot") or 0),
        lane=migrated["lane"],
        placement=migrated["placement"],
    )
    migrated["schedule_snapshot"].setdefault("source_manifest_version", 1)
    policy_snapshot = dict(migrated.get("policy_snapshot") or {})
    policy_snapshot.setdefault("source_manifest_version", 1)
    policy_snapshot.setdefault("migration", "r07_v1_to_v2")
    migrated["policy_snapshot"] = _normalize_policy_snapshot(
        policy_snapshot,
        delivery_kind=str(migrated.get("delivery_kind") or "normal"),
        publication_target=target,
        lane=migrated["lane"],
    )
    return migrated


def preview_migrate_manifest_v1_to_v2(path: str | os.PathLike) -> dict:
    manifest = Path(path)
    payload = _read_payload(manifest)
    if payload.get("version") != 1:
        raise ValueError("preview_migrate_manifest_v1_to_v2 requiere calendar_manifest version 1")
    migrated_entries = [_migrate_entry_v1_to_v2(entry) for entry in payload["entries"]]
    return {
        "operation": "migrate_manifest_v1_to_v2",
        "base_version": 1,
        "target_version": 2,
        "base_revision": _manifest_revision(payload),
        "summary": {
            "migrated": len(migrated_entries),
            "total": len(migrated_entries),
        },
        "removed_entries": list(payload["entries"]),
        "added_entries": migrated_entries,
        "kept_entries": [],
        "merged_entries": migrated_entries,
    }


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
    preview = preview_replace_entries_v2(path, entries, usernames, lane, window)
    apply_manifest_preview(path, preview)
    return list(preview["merged_entries"])


def preview_replace_entries_v2(
    path: str | os.PathLike,
    entries: list[dict],
    usernames: set[str],
    lane: str,
    window: dict | None = None,
) -> dict:
    manifest = Path(path)
    payload = _read_payload(manifest)
    if payload.get("version") != 2:
        raise ValueError("preview_replace_entries_v2 requiere calendar_manifest version 2")
    affected = {str(name) for name in usernames}
    target_lane = _required_label(lane, "lane")
    for entry in entries:
        _validate_manifest_v2_entry_for_lane(entry, target_lane)
    start_day = int((window or {}).get("start_day", 1))
    end_day = int((window or {}).get("end_day", 999999))
    removed_entries = [
        entry
        for entry in payload["entries"]
        if (
            entry.get("username") in affected
            and entry.get("lane") == target_lane
            and start_day <= int(entry.get("day") or 0) <= end_day
        )
    ]
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
    return {
        "operation": "replace_entries_v2",
        "version": 2,
        "base_revision": _manifest_revision(payload),
        "selector": {
            "usernames": sorted(affected),
            "lane": target_lane,
            "start_day": start_day,
            "end_day": end_day,
        },
        "summary": {
            "added": len(entries),
            "removed": len(removed_entries),
            "kept": len(kept),
            "total": len(merged),
        },
        "removed_entries": removed_entries,
        "added_entries": list(entries),
        "kept_entries": kept,
        "merged_entries": merged,
    }


def _validate_manifest_v2_entry_for_lane(entry: dict, target_lane: str) -> None:
    entry_lane = _required_label(entry.get("lane"), "lane")
    if entry_lane != target_lane:
        raise ValueError("La entrada no coincide con el carril objetivo.")
    _validate_trial_lane_policy(
        str(entry.get("delivery_kind") or "normal"),
        publication_target_for_entry(entry),
        entry_lane,
    )


def apply_manifest_preview(path: str | os.PathLike, preview: dict) -> list[dict]:
    manifest = Path(path)
    payload = _read_payload(manifest)
    base_version = int(preview.get("base_version", preview.get("version")))
    target_version = int(preview.get("target_version", preview.get("version")))
    if payload.get("version") != base_version:
        raise RuntimeError("revision del manifest cambio antes de aplicar el preview")
    if _manifest_revision(payload) != preview.get("base_revision"):
        raise RuntimeError("revision del manifest cambio antes de aplicar el preview")
    entries = list(preview.get("merged_entries") or [])
    _write_payload_version(manifest, entries, target_version)
    return entries


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
