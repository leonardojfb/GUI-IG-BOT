from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Iterable


@dataclass(frozen=True)
class ScheduleConflict:
    username: str
    scheduled_date: str
    scheduled_time: str
    existing_entry_id: str
    candidate_entry_id: str


@dataclass(frozen=True)
class ScheduleMergeResult:
    entries: list[dict]
    conflicts: list[ScheduleConflict]


@dataclass(frozen=True)
class ScheduledSlot:
    scheduled_date: str
    scheduled_time: str


def _schedule_key(entry: dict) -> tuple[str, str, str, str] | None:
    scheduled_date = str(entry.get("scheduled_date") or "").strip()
    scheduled_time = str(entry.get("scheduled_time") or "").strip()
    username = str(entry.get("username") or "").strip()
    if not scheduled_date or not scheduled_time or not username:
        return None
    target = str(entry.get("publication_target") or "")
    platform = str(entry.get("platform") or ("facebook" if target.startswith("facebook_") else "instagram"))
    return username, platform, scheduled_date, scheduled_time


def _entry_sort_key(entry: dict) -> tuple[int, str, str, str, int, str]:
    key = _schedule_key(entry)
    if key is None:
        return (1, "", "", str(entry.get("username") or ""), int(entry.get("day") or 0), str(entry.get("id") or ""))
    username, _platform, scheduled_date, scheduled_time = key
    return (0, scheduled_date, scheduled_time, username, 0, str(entry.get("id") or ""))


def merge_scheduled_entries(existing: Iterable[dict], candidates: Iterable[dict]) -> ScheduleMergeResult:
    """Merge explicit local-time entries without moving existing publications."""
    merged = list(existing)
    occupied = {key: entry for entry in merged if (key := _schedule_key(entry)) is not None}
    conflicts: list[ScheduleConflict] = []

    for candidate in candidates:
        key = _schedule_key(candidate)
        if key is not None and key in occupied:
            username, _platform, scheduled_date, scheduled_time = key
            conflicts.append(
                ScheduleConflict(
                    username=username,
                    scheduled_date=scheduled_date,
                    scheduled_time=scheduled_time,
                    existing_entry_id=str(occupied[key].get("id") or ""),
                    candidate_entry_id=str(candidate.get("id") or ""),
                )
            )
            continue
        merged.append(candidate)
        if key is not None:
            occupied[key] = candidate

    return ScheduleMergeResult(entries=sorted(merged, key=_entry_sort_key), conflicts=conflicts)


def validate_scheduled_fields(scheduled_date: str | None, scheduled_time: str | None) -> tuple[str, str]:
    date_text = str(scheduled_date or "").strip()
    time_text = str(scheduled_time or "").strip()
    if not date_text and not time_text:
        return "", ""
    if not date_text or not time_text:
        raise ValueError("Fecha y hora local deben informarse juntas.")
    try:
        date.fromisoformat(date_text)
        time.fromisoformat(time_text)
    except ValueError as error:
        raise ValueError("Fecha u hora local invalida.") from error
    if len(time_text) != 5:
        raise ValueError("La hora local debe usar formato HH:MM.")
    return date_text, time_text


def expand_lane_slots(
    start_date: str,
    horizon_days: int,
    every_days: int,
    times: Iterable[str],
) -> list[ScheduledSlot]:
    """Expand a per-account lane into ordered local date/time slots."""
    if every_days <= 0:
        raise ValueError("La regla cada N dias debe ser positiva.")
    if horizon_days <= 0:
        raise ValueError("El periodo debe contener al menos un dia.")
    try:
        start = date.fromisoformat(str(start_date))
    except ValueError as error:
        raise ValueError("La fecha inicial es invalida.") from error

    normalized_times = sorted(
        {validate_scheduled_fields("2000-01-01", value)[1] for value in times}
    )
    if not normalized_times:
        raise ValueError("El carril necesita al menos una hora.")

    slots: list[ScheduledSlot] = []
    for offset in range(horizon_days):
        if offset % every_days:
            continue
        scheduled_date = (start + timedelta(days=offset)).isoformat()
        slots.extend(ScheduledSlot(scheduled_date, value) for value in normalized_times)
    return slots
