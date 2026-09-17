"""Versioned, idempotent confirmation inbox with one-shot undo."""
from __future__ import annotations

import json
import re
import uuid


_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]+$")


def ensure_confirmation_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS confirmation_inbox (
        event_id TEXT PRIMARY KEY,
        external_id TEXT NOT NULL UNIQUE,
        version INTEGER NOT NULL,
        action TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'confirmed',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        undone_at TEXT
    )""")
    connection.commit()


def build_callback(action: str, entity_id: str, *, version: int = 1) -> str:
    action = _required(action, "action")
    entity_id = _required(entity_id, "entity_id")
    if int(version) != 1 or not _SAFE_ID.fullmatch(action) or not _SAFE_ID.fullmatch(entity_id):
        raise ValueError("callback invalido")
    return f"v{int(version)}|{action}|{entity_id}"


def parse_callback(callback: str) -> dict:
    parts = str(callback or "").split("|")
    if len(parts) != 3 or parts[0] != "v1" or not _SAFE_ID.fullmatch(parts[1]) or not _SAFE_ID.fullmatch(parts[2]):
        raise ValueError("callback versionado invalido")
    return {"version": 1, "action": parts[1], "entity_id": parts[2]}


def ingest_callback(connection, callback: str, *, external_id: str, user_id: str, payload: dict | None = None) -> dict:
    ensure_confirmation_schema(connection)
    parsed = parse_callback(callback)
    external = _required(external_id, "external_id")
    user = _required(user_id, "user_id")
    existing = connection.execute("SELECT event_id, status FROM confirmation_inbox WHERE external_id=?", (external,)).fetchone()
    if existing:
        return {"status": "duplicate", "event_id": existing[0], "state": existing[1]}
    event_id = str(uuid.uuid4())
    connection.execute("INSERT INTO confirmation_inbox (event_id, external_id, version, action, entity_id, user_id, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)", (event_id, external, parsed["version"], parsed["action"], parsed["entity_id"], user, json.dumps(payload or {}, sort_keys=True, ensure_ascii=False)))
    connection.commit()
    return {"status": "recorded", "event_id": event_id, **parsed}


def undo_confirmation(connection, event_id: str, undo_fn) -> dict:
    ensure_confirmation_schema(connection)
    row = connection.execute("SELECT * FROM confirmation_inbox WHERE event_id=?", (str(event_id),)).fetchone()
    if not row:
        raise ValueError("confirmation event no encontrado")
    if row["status"] == "undone" if hasattr(row, "keys") else row[7] == "undone":
        return {"status": "already_undone", "event_id": str(event_id)}
    keys = ["event_id", "external_id", "version", "action", "entity_id", "user_id", "payload_json", "status", "created_at", "undone_at"]
    event = dict(zip(keys, row))
    undo_fn(event)
    connection.execute("UPDATE confirmation_inbox SET status='undone', undone_at=CURRENT_TIMESTAMP WHERE event_id=? AND status='confirmed'", (str(event_id),))
    connection.commit()
    return {"status": "undone", "event_id": str(event_id)}


def _required(value, field):
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} no puede estar vacio")
    return normalized
