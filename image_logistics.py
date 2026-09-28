"""Manual image-publication planning over neutral Photo Forge finals."""

from __future__ import annotations

import os
from collections import Counter, defaultdict, deque
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from calendar_manifest import build_entry
from photo_forge import validated_neutral_outputs
from publication_schedule import expand_lane_slots, merge_scheduled_entries


IMAGE_TARGETS = {
    "instagram_story", "facebook_story", "instagram_post", "facebook_page_post",
    "facebook_marketplace_listing", "instagram_photo_reel",
}


def _key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)).casefold()


def _platform(target: str) -> str:
    return "facebook" if target.startswith("facebook_") else "instagram"


def _slots(block: dict):
    times = list(block.get("times") or [])
    daily = int(block.get("quantity_daily", len(times)))
    if not 1 <= daily <= 24 or len(times) != daily:
        raise ValueError("Cantidad diaria y numero de horas deben coincidir (1-24).")
    slots = expand_lane_slots(
        str(block.get("start_date") or ""), int(block.get("horizon_days") or 0),
        int(block.get("every_days") or 0), times,
    )
    total = block.get("total")
    if total is not None:
        if int(total) <= 0:
            raise ValueError("La cantidad total debe ser positiva.")
        slots = slots[:int(total)]
    if not slots:
        raise ValueError("El bloque no produce publicaciones en el periodo.")
    return slots


def _validate_block(block: dict, source_ids: set[str]) -> tuple[list[str], list[str], list]:
    sources = [str(value) for value in block.get("source_ids") or []]
    targets = [str(value) for value in block.get("targets") or []]
    if not sources or any(value not in source_ids for value in sources):
        raise ValueError("Selecciona fuentes existentes en la tanda Photo Forge.")
    if len(sources) > 10:
        raise ValueError("Un carrusel o album admite hasta 10 imagenes.")
    if not targets or len(targets) != len(set(targets)) or any(value not in IMAGE_TARGETS for value in targets):
        raise ValueError("Selecciona destinos de imagen compatibles.")
    for target in targets:
        if len(sources) > 1 and target not in {"instagram_post", "facebook_page_post"}:
            raise ValueError("Solo Post Instagram o Post Facebook permite carrusel/album.")
        if target in {"instagram_story", "facebook_story"}:
            if not str(block.get("story_announcement_text") or "").strip():
                raise ValueError("La Story necesita texto de anuncio.")
        if target == "facebook_marketplace_listing":
            for field in ("title", "price", "condition", "description"):
                if not str((block.get("marketplace") or {}).get(field) or "").strip():
                    raise ValueError(f"Marketplace necesita {field}.")
    timezone = str(block.get("timezone") or "")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(f"Zona horaria no valida: {timezone}") from error
    return sources, targets, _slots(block)


def build_image_plan(
    batch_dir: str | os.PathLike,
    category: str,
    accounts: list[dict],
    blocks: list[dict],
    existing_entries: list[dict],
) -> list[dict]:
    """Return complete candidate units or fail before reserving anything."""
    if not category.strip() or not accounts or not blocks:
        raise ValueError("Selecciona tanda, categoria, cuentas y al menos un bloque.")
    usernames = [str(row.get("username") or "").strip() for row in accounts]
    if any(not username for username in usernames) or len(usernames) != len(set(usernames)):
        raise ValueError("La categoria contiene cuentas vacias o duplicadas.")
    outputs = validated_neutral_outputs(batch_dir)
    known_sources = {row["source_id"] for row in outputs}
    used = {
        _key(str(item.get("source_path")))
        for entry in existing_entries
        for item in (entry.get("media_items") or [entry])
        if item.get("source_path")
    }
    available = defaultdict(deque)
    for row in sorted(outputs, key=lambda item: (item["source_id"], item["copy_index"])):
        if _key(row["output_path"]) not in used:
            available[row["source_id"]].append(row)
    requirements = Counter()
    normalized = []
    for block in blocks:
        sources, targets, slots = _validate_block(block, known_sources)
        for source_id in sources:
            requirements[source_id] += len(accounts) * len(targets) * len(slots)
        normalized.append((block, sources, targets, slots))
    deficits = [
        f"{source_id}: necesarios {count}, disponibles {len(available[source_id])}, deficit {count - len(available[source_id])}"
        for source_id, count in requirements.items() if len(available[source_id]) < count
    ]
    if deficits:
        raise ValueError("Capacidad insuficiente: " + "; ".join(deficits))

    entries = []
    for block_index, (block, sources, targets, slots) in enumerate(normalized):
        for account in accounts:
            username = str(account["username"])
            for target in targets:
                for slot_index, slot in enumerate(slots):
                    media = []
                    for order, source_id in enumerate(sources):
                        output = available[source_id].popleft()
                        media.append({
                            "source_id": source_id, "source_path": output["output_path"],
                            "sha256": output["output_sha256"], "order": order,
                            "telegram_filename": Path(output["output_path"]).name,
                        })
                    story_link = ""
                    if target.endswith("_story"):
                        story_link = str((block.get("story_links") or {}).get(username) or "")
                        if not story_link:
                            raise ValueError(f"Falta el enlace Story de @{username}.")
                    payload = dict(block.get("marketplace") or {}) if target == "facebook_marketplace_listing" else {}
                    if len(media) > 1:
                        payload["publication_format"] = "album" if _platform(target) == "facebook" else "carousel"
                    entry = build_entry(
                        username=username, account_id=account.get("id"), delivery_kind="normal",
                        day=block_index + 1, slot=slot_index + 1,
                        tanda=Path(batch_dir).name, source_path=media[0]["source_path"],
                        telegram_filename=media[0]["telegram_filename"],
                        publication_target=target, caption=str(block.get("caption") or ""),
                        story_link_url=story_link,
                        story_announcement_text=str(block.get("story_announcement_text") or ""),
                        platform_payload=payload, media_kind="image",
                        scheduled_date=slot.scheduled_date, scheduled_time=slot.scheduled_time,
                        timezone=str(block["timezone"]), plan_id=str(block.get("plan_id") or ""),
                    )
                    entry.update({
                        "category": category, "platform": _platform(target),
                        "publication_id": entry["id"], "media_items": media,
                        "publication_format": payload.get("publication_format", "single"),
                        "photo_batch": str(Path(batch_dir).resolve()),
                    })
                    entries.append(entry)
    result = merge_scheduled_entries(existing_entries, entries)
    if result.conflicts:
        conflict = result.conflicts[0]
        raise ValueError(
            f"Choque de horario para @{conflict.username} el {conflict.scheduled_date} "
            f"a las {conflict.scheduled_time}."
        )
    return entries
