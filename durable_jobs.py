"""Durable local job state machine for R09.

The module is import-safe: SQLite schema creation is explicit and no work is
started until one of the public functions is called.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone


TERMINAL_STEPS = {"succeeded", "failed", "cancelled"}


def ensure_job_schema(connection) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS durable_jobs (
        job_id TEXT PRIMARY KEY,
        job_type TEXT NOT NULL,
        recipe_json TEXT NOT NULL,
        state TEXT NOT NULL,
        idempotency_key TEXT UNIQUE,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS durable_job_steps (
        job_id TEXT NOT NULL,
        step_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        state TEXT NOT NULL,
        depends_on_json TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        checkpoint_json TEXT NOT NULL,
        result_json TEXT NOT NULL,
        error_json TEXT NOT NULL,
        attempt INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 1,
        backoff_seconds INTEGER NOT NULL DEFAULT 0,
        next_attempt_at INTEGER NOT NULL DEFAULT 0,
        lease_owner TEXT,
        lease_token TEXT,
        lease_expires_at INTEGER,
        PRIMARY KEY(job_id, step_id),
        FOREIGN KEY(job_id) REFERENCES durable_jobs(job_id)
    );
    CREATE TABLE IF NOT EXISTS durable_job_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        step_id TEXT,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_durable_steps_claim
      ON durable_job_steps(state, next_attempt_at, lease_expires_at);
    CREATE INDEX IF NOT EXISTS idx_durable_events_job
      ON durable_job_events(job_id, id);
    """)
    step_columns = {row[1] for row in connection.execute("PRAGMA table_info(durable_job_steps)")}
    if "lease_token" not in step_columns:
        connection.execute("ALTER TABLE durable_job_steps ADD COLUMN lease_token TEXT")
    connection.commit()


def create_job(connection, *, job_type: str, recipe: dict, steps: list[dict], idempotency_key: str | None = None, now: int | None = None) -> dict:
    ensure_job_schema(connection)
    kind = str(job_type or "").strip()
    if not kind or not isinstance(recipe, dict):
        raise ValueError("job_type y recipe son obligatorios")
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps debe contener al menos un paso")
    ids = [str(step.get("step_id") or "").strip() for step in steps]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("step_id duplicado o vacio")
    known = set(ids)
    normalized = []
    for step in steps:
        deps = [str(dep) for dep in (step.get("depends_on") or [])]
        if any(dep not in known for dep in deps):
            raise ValueError("dependencia de step desconocida")
        max_attempts = int(step.get("max_attempts", recipe.get("max_attempts", 1)))
        if max_attempts < 1:
            raise ValueError("max_attempts debe ser positivo")
        normalized.append((
            str(step["step_id"]), str(step.get("kind") or "").strip(), deps,
            dict(step.get("payload") or {}), max_attempts,
            int(step.get("backoff_seconds", recipe.get("backoff_seconds", 0))),
        ))
        if not normalized[-1][1]:
            raise ValueError("kind de step es obligatorio")
        if normalized[-1][5] < 0:
            raise ValueError("backoff_seconds no puede ser negativo")
    timestamp = int(now if now is not None else datetime.now(timezone.utc).timestamp())
    idem = str(idempotency_key).strip() if idempotency_key else None
    job_id = str(uuid.uuid4())
    connection.execute("BEGIN IMMEDIATE")
    try:
        if idem:
            existing = connection.execute("SELECT job_id FROM durable_jobs WHERE idempotency_key=?", (idem,)).fetchone()
            if existing:
                connection.commit()
                return get_job(connection, existing[0])
        connection.execute("INSERT INTO durable_jobs VALUES (?, ?, ?, 'pending', ?, ?, ?)", (job_id, kind, _dump(recipe), idem, timestamp, timestamp))
        for step_id, step_kind, deps, payload, max_attempts, backoff in normalized:
            connection.execute(
                "INSERT INTO durable_job_steps (job_id, step_id, kind, state, depends_on_json, payload_json, checkpoint_json, result_json, error_json, max_attempts, backoff_seconds) VALUES (?, ?, ?, 'pending', ?, ?, '{}', '{}', '{}', ?, ?)",
                (job_id, step_id, step_kind, _dump(deps), _dump(payload), max_attempts, backoff),
            )
        _event(connection, job_id, None, "created", {"job_type": kind}, timestamp)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return get_job(connection, job_id)


def get_job(connection, job_id: str) -> dict | None:
    ensure_job_schema(connection)
    row = connection.execute("SELECT * FROM durable_jobs WHERE job_id=?", (str(job_id),)).fetchone()
    if not row:
        return None
    job = _row_dict(row)
    job["recipe"] = _load(job.pop("recipe_json"), {})
    steps = connection.execute("SELECT * FROM durable_job_steps WHERE job_id=? ORDER BY rowid", (str(job_id),)).fetchall()
    job["steps"] = [_step_dict(step) for step in steps]
    return job


def list_jobs(connection, *, states: set[str] | None = None, limit: int = 100) -> list[dict]:
    ensure_job_schema(connection)
    params = []
    query = "SELECT * FROM durable_jobs"
    if states:
        labels = sorted(str(state) for state in states)
        query += " WHERE state IN (" + ",".join("?" for _ in labels) + ")"
        params.extend(labels)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    return [get_job(connection, row["job_id"]) for row in connection.execute(query, params)]


def claim_next_step(connection, *, worker_id: str, lease_seconds: int = 300, now: int | None = None) -> dict | None:
    ensure_job_schema(connection)
    owner = str(worker_id or "").strip()
    timestamp = _timestamp(now)
    if not owner or int(lease_seconds) <= 0:
        raise ValueError("worker_id y lease_seconds positivo son obligatorios")
    connection.execute("BEGIN IMMEDIATE")
    try:
        blocked_jobs = set()
        while True:
            blocked_rows = connection.execute("""SELECT s.job_id, s.step_id FROM durable_job_steps s
                WHERE s.state IN ('pending', 'retry_wait') AND EXISTS (
                    SELECT 1 FROM durable_job_steps d
                    WHERE d.job_id=s.job_id AND d.state IN ('failed', 'cancelled', 'blocked')
                      AND EXISTS (SELECT 1 FROM json_each(s.depends_on_json) x WHERE x.value=d.step_id)
                )""").fetchall()
            if not blocked_rows:
                break
            for blocked in blocked_rows:
                connection.execute("UPDATE durable_job_steps SET state='blocked' WHERE job_id=? AND step_id=? AND state IN ('pending', 'retry_wait')", (blocked["job_id"], blocked["step_id"]))
                _event(connection, blocked["job_id"], blocked["step_id"], "blocked", {"reason": "dependency_not_succeeded"}, timestamp)
                blocked_jobs.add(blocked["job_id"])
        for blocked_job in blocked_jobs:
            _refresh_job_state(connection, blocked_job, timestamp)
        query = """SELECT s.* FROM durable_job_steps s
            WHERE s.state IN ('pending', 'retry_wait') AND s.next_attempt_at <= ?
            AND NOT EXISTS (SELECT 1 FROM durable_job_steps d WHERE d.job_id=s.job_id
                AND d.state != 'succeeded'
                AND EXISTS (SELECT 1 FROM json_each(s.depends_on_json) x WHERE x.value=d.step_id)
                AND d.state != 'succeeded')
            ORDER BY s.rowid LIMIT 1"""
        row = connection.execute(query, (timestamp,)).fetchone()
        if not row:
            connection.commit()
            return None
        new_attempt = int(row["attempt"]) + 1
        lease_token = str(uuid.uuid4())
        connection.execute("UPDATE durable_job_steps SET state='running', attempt=?, lease_owner=?, lease_token=?, lease_expires_at=?, next_attempt_at=0 WHERE job_id=? AND step_id=? AND state IN ('pending','retry_wait')", (new_attempt, owner, lease_token, timestamp + int(lease_seconds), row["job_id"], row["step_id"]))
        connection.execute("UPDATE durable_jobs SET state='running', updated_at=? WHERE job_id=?", (timestamp, row["job_id"]))
        _event(connection, row["job_id"], row["step_id"], "claimed", {"worker_id": owner, "attempt": new_attempt}, timestamp)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return _step_dict(connection.execute("SELECT * FROM durable_job_steps WHERE job_id=? AND step_id=?", (row["job_id"], row["step_id"])).fetchone())


def record_step_checkpoint(connection, *, job_id: str, step_id: str, worker_id: str, lease_token: str, checkpoint: dict, now: int | None = None) -> dict:
    return _mutate_running(connection, job_id, step_id, worker_id, lease_token, "checkpoint", checkpoint, _timestamp(now))


def complete_step(connection, *, job_id: str, step_id: str, worker_id: str, lease_token: str, result: dict | None = None, now: int | None = None) -> dict:
    return _mutate_running(connection, job_id, step_id, worker_id, lease_token, "succeeded", result or {}, _timestamp(now))


def fail_step(connection, *, job_id: str, step_id: str, worker_id: str, lease_token: str, error: dict, retryable: bool, now: int | None = None) -> dict:
    ensure_job_schema(connection)
    timestamp = _timestamp(now)
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = _owned_step(connection, job_id, step_id, worker_id, lease_token, timestamp)
        retry = bool(retryable) and int(row["attempt"]) < int(row["max_attempts"])
        state = "retry_wait" if retry else "failed"
        next_at = timestamp + int(row["backoff_seconds"]) * (2 ** max(0, int(row["attempt"]) - 1)) if retry else 0
        connection.execute("UPDATE durable_job_steps SET state=?, error_json=?, next_attempt_at=?, lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL WHERE job_id=? AND step_id=?", (state, _dump(error), next_at, job_id, step_id))
        _event(connection, job_id, step_id, "failed", {"retryable": bool(retryable), "state": state, "error": error}, timestamp)
        _refresh_job_state(connection, job_id, timestamp)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return _step_dict(connection.execute("SELECT * FROM durable_job_steps WHERE job_id=? AND step_id=?", (job_id, step_id)).fetchone())


def recover_expired_steps(connection, *, now: int | None = None) -> dict:
    ensure_job_schema(connection)
    timestamp = _timestamp(now)
    connection.execute("BEGIN IMMEDIATE")
    count = 0
    try:
        rows = connection.execute("SELECT * FROM durable_job_steps WHERE state='running' AND lease_expires_at <= ?", (timestamp,)).fetchall()
        for row in rows:
            retry = int(row["attempt"]) < int(row["max_attempts"])
            state = "retry_wait" if retry else "failed"
            next_at = timestamp + int(row["backoff_seconds"]) * (2 ** max(0, int(row["attempt"]) - 1)) if retry else 0
            connection.execute("UPDATE durable_job_steps SET state=?, next_attempt_at=?, lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL WHERE job_id=? AND step_id=? AND state='running'", (state, next_at, row["job_id"], row["step_id"]))
            _event(connection, row["job_id"], row["step_id"], "lease_expired", {"state": state}, timestamp)
            _refresh_job_state(connection, row["job_id"], timestamp)
            count += 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"requeued": count}


def retry_job_step(connection, *, job_id: str, step_id: str, now: int | None = None) -> dict:
    ensure_job_schema(connection)
    timestamp = _timestamp(now)
    connection.execute("BEGIN IMMEDIATE")
    row = connection.execute("SELECT * FROM durable_job_steps WHERE job_id=? AND step_id=?", (job_id, step_id)).fetchone()
    if not row or row["state"] != "failed" or int(row["attempt"]) >= int(row["max_attempts"]):
        connection.rollback()
        raise ValueError("step no puede reintentarse")
    connection.execute("UPDATE durable_job_steps SET state='retry_wait', next_attempt_at=? WHERE job_id=? AND step_id=?", (timestamp, job_id, step_id))
    _event(connection, job_id, step_id, "retry_requested", {}, timestamp)
    connection.commit()
    return _step_dict(connection.execute("SELECT * FROM durable_job_steps WHERE job_id=? AND step_id=?", (job_id, step_id)).fetchone())


def cancel_job(connection, *, job_id: str, reason: str, now: int | None = None) -> dict:
    ensure_job_schema(connection)
    timestamp = _timestamp(now)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("UPDATE durable_job_steps SET state='cancelled', lease_owner=NULL, lease_expires_at=NULL WHERE job_id=? AND state NOT IN ('succeeded','failed','cancelled')", (job_id,))
    connection.execute("UPDATE durable_jobs SET state='cancelled', updated_at=? WHERE job_id=?", (timestamp, job_id))
    _event(connection, job_id, None, "cancelled", {"reason": str(reason)}, timestamp)
    connection.commit()
    return get_job(connection, job_id)


def inspect_job_events(connection, *, job_id: str, limit: int = 500) -> list[dict]:
    ensure_job_schema(connection)
    return [_row_dict(row) | {"payload": _load(row["payload_json"], {})} for row in connection.execute("SELECT * FROM durable_job_events WHERE job_id=? ORDER BY id LIMIT ?", (job_id, int(limit)))]


def _mutate_running(connection, job_id, step_id, worker_id, lease_token, event_type, payload, timestamp):
    ensure_job_schema(connection)
    connection.execute("BEGIN IMMEDIATE")
    try:
        _owned_step(connection, job_id, step_id, worker_id, lease_token, timestamp)
        if event_type == "checkpoint":
            connection.execute("UPDATE durable_job_steps SET checkpoint_json=? WHERE job_id=? AND step_id=?", (_dump(payload), job_id, step_id))
        else:
            connection.execute("UPDATE durable_job_steps SET state='succeeded', result_json=?, lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL WHERE job_id=? AND step_id=?", (_dump(payload), job_id, step_id))
            _refresh_job_state(connection, job_id, timestamp)
        _event(connection, job_id, step_id, event_type, payload, timestamp)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return _step_dict(connection.execute("SELECT * FROM durable_job_steps WHERE job_id=? AND step_id=?", (job_id, step_id)).fetchone())


def _owned_step(connection, job_id, step_id, worker_id, lease_token, timestamp):
    row = connection.execute("SELECT * FROM durable_job_steps WHERE job_id=? AND step_id=?", (job_id, step_id)).fetchone()
    if not row or row["state"] != "running" or row["lease_owner"] != worker_id or row["lease_token"] != lease_token or int(row["lease_expires_at"] or 0) <= int(timestamp):
        raise RuntimeError("step sin lease valido para este worker")
    return row


def _refresh_job_state(connection, job_id, timestamp):
    states = [row[0] for row in connection.execute("SELECT state FROM durable_job_steps WHERE job_id=?", (job_id,))]
    state = "succeeded" if states and all(item == "succeeded" for item in states) else "blocked" if any(item == "blocked" for item in states) else "failed" if any(item == "failed" for item in states) else "cancelled" if states and all(item == "cancelled" for item in states) else "running"
    connection.execute("UPDATE durable_jobs SET state=?, updated_at=? WHERE job_id=?", (state, timestamp, job_id))


def _event(connection, job_id, step_id, event_type, payload, timestamp):
    connection.execute("INSERT INTO durable_job_events (job_id, step_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)", (job_id, step_id, event_type, _dump(payload), timestamp))


def _step_dict(row):
    result = _row_dict(row)
    for key, default in (("depends_on_json", []), ("payload_json", {}), ("checkpoint_json", {}), ("result_json", {}), ("error_json", {})):
        result[key.removesuffix("_json")] = _load(result.pop(key), default)
    return result


def _row_dict(row):
    return dict(row) if hasattr(row, "keys") else dict(zip(range(len(row)), row))


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load(value, default):
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default
    return parsed


def _timestamp(value):
    return int(value if value is not None else datetime.now(timezone.utc).timestamp())
