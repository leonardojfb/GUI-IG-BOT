"""Destination-aware Forge previews and reservations built on R08 contracts."""
from __future__ import annotations

from pathlib import Path

from planner_reservations import release_reservation, reservation_covers_preview, reserve_shared_preview


SUPPORTED_CONTAINERS = {"feed", "story", "reel"}
SUPPORTED_PROFILES = {"instagram_reel", "instagram_story"}


def parse_destination_specs(text):
    """Parse explicit GUI fallback rows: username|container|profile|copies."""
    result = []
    for line_number, raw_line in enumerate(str(text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 4:
            raise ValueError(f"destino invalido en linea {line_number}: usa cuenta|contenedor|perfil|copias")
        username, container, profile, copies = parts
        try:
            copies = int(copies)
        except ValueError as exc:
            raise ValueError(f"copias invalidas en linea {line_number}") from exc
        if not username or container not in SUPPORTED_CONTAINERS or profile not in SUPPORTED_PROFILES or copies < 1:
            raise ValueError(f"destino invalido en linea {line_number}")
        result.append({"username": username, "container": container, "profile": profile, "copies": copies})
    if not result:
        raise ValueError("debe existir al menos un destino")
    return result


def bind_destinations_to_snapshot(destinations, snapshot):
    """Resolve each destination to exactly one read-only ios-remote container."""
    if not isinstance(snapshot, dict) or not snapshot.get("snapshot_hash"):
        raise ValueError("snapshot ios-remote invalido")
    containers = snapshot.get("containers") or []
    bound = []
    for destination in destinations or []:
        username = str(destination.get("username") or "").strip().casefold()
        profile = str(destination.get("profile") or "").strip()
        matches = []
        for container in containers:
            accounts = container.get("accounts") or []
            has_account = any(str(account.get("username") or "").strip().casefold() == username for account in accounts)
            actual_profile = (container.get("device_profile") or {}).get("profile_id")
            if has_account and actual_profile == profile:
                matches.append(container)
        if not matches:
            raise ValueError(f"@{username} no tiene contenedor unico para {profile}")
        if len(matches) > 1:
            raise ValueError(f"@{username} tiene multiples contenedores para {profile}")
        container = matches[0]
        enriched = dict(destination)
        enriched["remote_container_id"] = container.get("container_id")
        enriched["snapshot_hash"] = snapshot["snapshot_hash"]
        enriched["profile_version"] = (container.get("device_profile") or {}).get("version")
        bound.append(enriched)
    return bound


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
                assignments.append({"source_id": source, "source_path": source, "username": username, "container": container, "profile": profile, "lane": lane, "copy_number": copy_number, **{key: value for key, value in destination.items() if key.startswith("remote_") or key.startswith("snapshot_") or key == "profile_version"}})
    return {"status": "ready", "scope": {"lane": "destination"}, "assignments": assignments, "requested": len(assignments)}


def reserve_destination_preview(connection, preview, *, owner, now, ttl_seconds=900):
    return reserve_shared_preview(connection, preview, owner=owner, now=now, ttl_seconds=ttl_seconds)


def build_destination_forge_job_spec(preview, *, output_root, metadata):
    """Translate a reserved destination preview into R09 Forge steps."""
    if preview.get("status") not in {"ready", "partial"}:
        raise ValueError("el preview destino no esta listo")
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError("metadata debe ser un objeto no vacio")
    root = Path(output_root).resolve()
    steps = []
    for index, assignment in enumerate(preview.get("assignments") or [], start=1):
        source = Path(assignment["source_path"])
        destination_dir = root / assignment["username"] / assignment["container"] / assignment["profile"]
        output = destination_dir / f"{source.stem}__{assignment['username']}__c{assignment['copy_number']:02d}{source.suffix}"
        payload = {"source_path": str(source), "output_path": str(output), "metadata": dict(metadata), "copy_number": assignment["copy_number"], "username": assignment["username"], "container": assignment["container"], "profile": assignment["profile"], "lane": assignment["lane"]}
        for key in ("remote_container_id", "snapshot_hash", "profile_version"):
            if key in assignment:
                payload[key] = assignment[key]
        steps.append({"step_id": f"destination-forge-{index:04d}", "kind": "forge.copy", "payload": payload})
    if not steps:
        raise ValueError("el preview no contiene assignments")
    return {"job_type": "forge.destination.v1", "recipe": {"recipe_version": 1, "producer": "forge", "destination_mode": True, "output_root": str(root), "metadata": dict(metadata), "assignment_count": len(steps)}, "steps": steps}


def submit_destination_forge_job(connection, preview, *, output_root, metadata, idempotency_key=None):
    from durable_jobs import create_job

    spec = build_destination_forge_job_spec(preview, output_root=output_root, metadata=metadata)
    return create_job(connection, **spec, idempotency_key=idempotency_key)


def reconcile_destination_reservation(connection, reservation, preview, *, owner, now):
    """Release a short-lived reservation only after verifying its exact scope."""
    if str(reservation.get("owner") or "") != str(owner or ""):
        raise ValueError("el owner no coincide con la reserva destino")
    if not reservation_covers_preview(connection, reservation, preview, now=now):
        raise ValueError("la reserva no cubre el preview destino")
    history_count = _record_reconciliation_history(connection, reservation, preview, now=now)
    released = release_reservation(connection, reservation["reservation_id"], owner=owner)
    return {"status": "released" if released else "already_released", "reservation_id": reservation["reservation_id"], "history_count": history_count}


def _record_reconciliation_history(connection, reservation, preview, *, now):
    connection.execute(
        """CREATE TABLE IF NOT EXISTS destination_forge_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reservation_id TEXT NOT NULL,
            owner TEXT NOT NULL,
            source_id TEXT NOT NULL,
            username TEXT NOT NULL,
            lane TEXT NOT NULL,
            remote_container_id TEXT,
            snapshot_hash TEXT,
            status TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            UNIQUE(reservation_id, source_id, username, lane)
        )"""
    )
    inserted = 0
    for assignment in preview.get("assignments") or []:
        source_id = str(assignment.get("source_id") or assignment.get("source_path") or "")
        username = str(assignment.get("username") or "").strip().casefold()
        lane = str(assignment.get("lane") or "").strip()
        cursor = connection.execute(
            """INSERT OR IGNORE INTO destination_forge_history
                (reservation_id, owner, source_id, username, lane,
                 remote_container_id, snapshot_hash, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(reservation.get("reservation_id") or ""),
                str(reservation.get("owner") or ""),
                source_id,
                username,
                lane,
                assignment.get("remote_container_id"),
                assignment.get("snapshot_hash"),
                "reconciled",
                int(now),
            ),
        )
        inserted += int(cursor.rowcount > 0)
    connection.commit()
    return inserted
