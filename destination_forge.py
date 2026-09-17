"""Destination-aware Forge previews and reservations built on R08 contracts."""
from __future__ import annotations

from pathlib import Path

from planner_reservations import reserve_shared_preview


SUPPORTED_CONTAINERS = {"feed", "story", "reel"}
SUPPORTED_PROFILES = {"instagram_reel", "instagram_story"}


def preview_destination_forge(video_paths, destinations):
    paths = [str(Path(path).resolve()) for path in video_paths]
    if not paths or any(not Path(path).is_file() for path in paths):
        raise ValueError("todos los videos destino deben existir")
    if not destinations:
        raise ValueError("destinations debe contener al menos un destino")
    assignments = []
    for destination in destinations:
        username = str(destination.get("username") or "").strip().casefold()
        container = str(destination.get("container") or "").strip().lower()
        profile = str(destination.get("profile") or "").strip()
        copies = int(destination.get("copies", 1))
        if not username or container not in SUPPORTED_CONTAINERS or profile not in SUPPORTED_PROFILES or copies < 1:
            raise ValueError("destino incompleto o invalido")
        lane = f"{container}:{profile}"
        for source in paths:
            for copy_number in range(1, copies + 1):
                assignments.append({"source_id": source, "source_path": source, "username": username, "container": container, "profile": profile, "lane": lane, "copy_number": copy_number})
    return {"status": "ready", "scope": {"lane": "destination"}, "assignments": assignments, "requested": len(assignments)}


def reserve_destination_preview(connection, preview, *, owner, now, ttl_seconds=900):
    return reserve_shared_preview(connection, preview, owner=owner, now=now, ttl_seconds=ttl_seconds)
