"""Short-lived, account-scoped reservations for R08 previews."""
from __future__ import annotations

import uuid


def ensure_reservation_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS planner_reservations (
        reservation_id TEXT NOT NULL, owner TEXT NOT NULL, source_id TEXT NOT NULL,
        username TEXT NOT NULL, lane TEXT NOT NULL, expires_at INTEGER NOT NULL,
        created_at INTEGER NOT NULL, PRIMARY KEY(reservation_id, source_id, username, lane),
        UNIQUE(source_id, username, lane)
    )""")
    connection.commit()


def _purge_expired(connection, now: int) -> None:
    connection.execute("DELETE FROM planner_reservations WHERE expires_at <= ?", (int(now),))


def reserve_shared_preview(connection, preview: dict, *, owner: str, now: int, ttl_seconds: int = 900) -> dict:
    if preview.get("status") not in {"ready", "partial"}:
        raise ValueError("Solo se puede reservar un preview ready o partial")
    owner = str(owner or "").strip()
    if not owner or int(ttl_seconds) <= 0:
        raise ValueError("owner y ttl_seconds positivo son obligatorios")
    ensure_reservation_schema(connection)
    reservation_id = str(uuid.uuid4())
    rows = []
    scope_lane = (preview.get("scope") or {}).get("lane")
    for assignment in preview.get("assignments") or []:
        rows.append((str(assignment.get("source_id") or assignment.get("source_path") or ""), str(assignment.get("username") or "").casefold(), str(assignment.get("lane") or scope_lane or "")))
    if any(not all(row) for row in rows):
        raise ValueError("El preview contiene una reserva incompleta")
    connection.execute("BEGIN IMMEDIATE")
    try:
        _purge_expired(connection, now)
        conflicts = []
        for source_id, username, lane in rows:
            hit = connection.execute("SELECT owner, expires_at FROM planner_reservations WHERE source_id=? AND username=? AND lane=?", (source_id, username, lane)).fetchone()
            if hit:
                conflicts.append({"source_id": source_id, "username": username, "lane": lane, "owner": hit[0], "expires_at": hit[1]})
        if conflicts:
            connection.rollback()
            return {"status": "conflict", "conflicts": conflicts}
        for source_id, username, lane in rows:
            connection.execute("INSERT INTO planner_reservations VALUES (?, ?, ?, ?, ?, ?, ?)", (reservation_id, owner, source_id, username, lane, int(now) + int(ttl_seconds), int(now)))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"status": "reserved", "reservation_id": reservation_id, "owner": owner, "expires_at": int(now) + int(ttl_seconds), "count": len(rows)}


def inspect_reservations(connection, *, now: int) -> list[dict]:
    ensure_reservation_schema(connection)
    connection.execute("BEGIN IMMEDIATE")
    _purge_expired(connection, now)
    rows = connection.execute("SELECT reservation_id, owner, source_id, username, lane, expires_at FROM planner_reservations ORDER BY reservation_id").fetchall()
    connection.commit()
    keys = ("reservation_id", "owner", "source_id", "username", "lane", "expires_at")
    return [dict(zip(keys, row)) for row in rows]


def release_reservation(connection, reservation_id: str, *, owner: str) -> bool:
    ensure_reservation_schema(connection)
    cursor = connection.execute("DELETE FROM planner_reservations WHERE reservation_id=? AND owner=?", (str(reservation_id), str(owner)))
    connection.commit()
    return cursor.rowcount > 0


def reservation_covers_preview(connection, reservation: dict, preview: dict, *, now: int) -> bool:
    if not reservation or reservation.get("status") != "reserved":
        return False
    scope_lane = (preview.get("scope") or {}).get("lane")
    expected = {
        (str(row.get("source_id") or row.get("source_path") or ""), str(row.get("username") or "").casefold(), str(row.get("lane") or scope_lane or ""))
        for row in preview.get("assignments") or []
    }
    if not expected:
        return False
    ensure_reservation_schema(connection)
    _purge_expired(connection, now)
    found_rows = connection.execute(
        "SELECT source_id, username, lane FROM planner_reservations WHERE reservation_id=? AND owner=? AND expires_at>?",
        (reservation.get("reservation_id"), reservation.get("owner"), int(now)),
    ).fetchall()
    found = {(str(row[0]), str(row[1]), str(row[2])) for row in found_rows}
    return found == expected and len(found) == len(expected)
