from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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
