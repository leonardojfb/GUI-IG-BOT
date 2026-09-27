from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
import re

from calendar_manifest import build_entry
from publication_schedule import expand_lane_slots


@dataclass(frozen=True)
class LaneRequest:
    username: str
    account_id: int | None
    tanda: str
    delivery_kind: str
    publication_target: str
    timezone: str
    media_kind: str
    lane_id: str
    plan_id: str
    start_date: str
    horizon_days: int
    every_days: int
    times: list[str]
    caption: str = ""
    story_link_url: str = ""
    story_announcement_text: str = ""
    platform_payload: dict = field(default_factory=dict)


def _telegram_filename(path: Path, request: LaneRequest, scheduled_date: str, scheduled_time: str) -> str:
    safe_target = re.sub(r"[^A-Za-z0-9_-]+", "-", request.publication_target)
    safe_username = re.sub(r"[^A-Za-z0-9_-]+", "-", request.username)
    return (
        f"{path.stem}__{safe_target}__ACC{request.account_id or 0}"
        f"__{safe_username}__{scheduled_date.replace('-', '')}"
        f"__{scheduled_time.replace(':', '')}{path.suffix.lower()}"
    )


def build_lane_entries(request: LaneRequest, final_paths: list[str | Path]) -> list[dict]:
    """Materialize one manifest row per lane slot from already-produced finals."""
    slots = expand_lane_slots(
        request.start_date,
        request.horizon_days,
        request.every_days,
        request.times,
    )
    paths = [Path(path).resolve() for path in final_paths]
    if len(paths) < len(slots):
        raise ValueError(
            f"El carril necesita {len(slots)} finales existentes y recibió {len(paths)}."
        )
    missing = [str(path) for path in paths[:len(slots)] if not path.is_file()]
    if missing:
        raise ValueError(f"Final inexistente: {missing[0]}")

    start = date.fromisoformat(request.start_date)
    entries: list[dict] = []
    for index, (slot, path) in enumerate(zip(slots, paths), start=1):
        day = (date.fromisoformat(slot.scheduled_date) - start).days + 1
        entries.append(
            build_entry(
                username=request.username,
                account_id=request.account_id,
                delivery_kind=request.delivery_kind,
                day=day,
                slot=index,
                tanda=request.tanda,
                source_path=str(path),
                telegram_filename=_telegram_filename(path, request, slot.scheduled_date, slot.scheduled_time),
                publication_target=request.publication_target,
                caption=request.caption,
                story_link_url=request.story_link_url,
                story_announcement_text=request.story_announcement_text,
                platform_payload=request.platform_payload,
                scheduled_date=slot.scheduled_date,
                scheduled_time=slot.scheduled_time,
                timezone=request.timezone,
                media_kind=request.media_kind,
                lane_id=request.lane_id,
                plan_id=request.plan_id,
            )
        )
    return entries


def resolve_legacy_reel_schedule(
    entry: dict,
    start_date: str,
    db_manager,
    resolution_cache: dict | None = None,
) -> dict:
    """Resolve day/slot-only Reel rows using the existing VA/category schedule."""
    if entry.get("scheduled_date") and entry.get("scheduled_time"):
        return {}
    target = entry.get("publication_target")
    if target and target not in {"instagram_reel", "instagram_trial_reel"}:
        return {}
    try:
        day_number = int(entry.get("day") or 0)
        slot_number = int(entry.get("slot") or 0)
        if day_number < 1 or slot_number < 1:
            raise ValueError("La entrada legacy no tiene dia/slot resoluble.")
        local_date = date.fromisoformat(start_date) + timedelta(days=day_number - 1)
        cache = resolution_cache if resolution_cache is not None else {}
        accounts = cache.get("accounts")
        if accounts is None:
            accounts = {row["username"]: row for row in db_manager.get_all_accounts()}
            cache["accounts"] = accounts
        account = accounts.get(entry.get("username"))
        if not account:
            raise ValueError(f"No existe la cuenta @{entry.get('username')} para resolver el horario.")
        va_name = account.get("assigned_va") or "Sin Asignar"
        category = (account.get("account_type") or "general").strip().lower()
        import organizadortg

        schedules = cache.setdefault("schedules", {})
        schedule_key = (va_name, category, local_date.weekday())
        configured = schedules.get(schedule_key)
        if configured is None:
            configured = organizadortg.get_slots_for_set(
                va_name, category, local_date.weekday(), db_manager
            )
            schedules[schedule_key] = configured
        raw_time = configured[slot_number - 1]
        source_time = datetime.strptime(raw_time.strip(), "%I:%M %p").time()
        from zoneinfo import ZoneInfo

        timezones = cache.setdefault("timezones", {})
        timezone = timezones.get(va_name)
        if timezone is None:
            timezone = db_manager.get_va_timezone(va_name)
            timezones[va_name] = timezone
        eastern = ZoneInfo("America/New_York")
        local_zone = ZoneInfo(timezone)
        eastern_datetime = datetime.combine(local_date, source_time, tzinfo=eastern)
        local_datetime = eastern_datetime.astimezone(local_zone)
    except (IndexError, KeyError, TypeError, ValueError, OSError) as error:
        raise ValueError(
            f"No se pudo resolver fecha/hora legacy de @{entry.get('username')} "
            f"(dia {entry.get('day')}, slot {entry.get('slot')}): {error}"
        ) from error
    return {
        "scheduled_date": local_datetime.date().isoformat(),
        "scheduled_time": local_datetime.strftime("%H:%M"),
        "timezone": timezone,
        "media_kind": entry.get("media_kind") or "video",
    }
