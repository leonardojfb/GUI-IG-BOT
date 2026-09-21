"""Persistent ordered job steps attached to a Legacy workflow."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid


TELEGRAM_MODES = frozenset({"queue_only", "send_on_run"})
_BINDING_KINDS = frozenset({"asset", "step_output", "previous_output"})


def ensure_workflow_queue_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS workflow_job_queues (
            workflow_id TEXT PRIMARY KEY,
            telegram_mode TEXT NOT NULL DEFAULT 'queue_only'
                CHECK (telegram_mode IN ('queue_only', 'send_on_run')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS workflow_job_queue_steps (
            workflow_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            job_type TEXT NOT NULL,
            recipe_json TEXT NOT NULL,
            input_contract TEXT NOT NULL,
            output_contract TEXT NOT NULL,
            input_binding_json TEXT NOT NULL DEFAULT '{}',
            source_job_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workflow_id, step_id),
            UNIQUE (workflow_id, position)
        );
        CREATE INDEX IF NOT EXISTS idx_workflow_job_queue_steps_position
            ON workflow_job_queue_steps(workflow_id, position);
        """
    )
    connection.commit()


def list_queue_steps(connection: sqlite3.Connection, workflow_id: str) -> list[dict]:
    ensure_workflow_queue_schema(connection)
    rows = connection.execute(
        """SELECT workflow_id, step_id, position, job_type, recipe_json,
                  input_contract, output_contract, input_binding_json,
                  source_job_id, created_at
           FROM workflow_job_queue_steps
           WHERE workflow_id = ? ORDER BY position""",
        (str(workflow_id),),
    ).fetchall()
    return [_step_dict(row) for row in rows]


def get_queue(connection: sqlite3.Connection, workflow_id: str) -> dict:
    ensure_workflow_queue_schema(connection)
    row = connection.execute(
        "SELECT workflow_id, telegram_mode, created_at, updated_at FROM workflow_job_queues WHERE workflow_id = ?",
        (str(workflow_id),),
    ).fetchone()
    if row is None:
        return {
            "workflow_id": str(workflow_id),
            "telegram_mode": "queue_only",
            "steps": [],
        }
    result = dict(row)
    result["steps"] = list_queue_steps(connection, workflow_id)
    return result


def append_queue_step(
    connection: sqlite3.Connection,
    workflow_id: str,
    *,
    job_type: str,
    recipe: dict,
    input_contract: str,
    output_contract: str,
    input_binding: dict | None = None,
    source_job_id: str | None = None,
) -> dict:
    ensure_workflow_queue_schema(connection)
    workflow_id = str(workflow_id or "").strip()
    job_type = str(job_type or "").strip()
    input_contract = str(input_contract or "").strip()
    output_contract = str(output_contract or "").strip()
    if not workflow_id or not job_type:
        raise ValueError("workflow_id y job_type son obligatorios")
    if not isinstance(recipe, dict) or not recipe:
        raise ValueError("recipe debe ser un objeto no vacio")
    if not input_contract or not output_contract:
        raise ValueError("input_contract y output_contract son obligatorios")

    binding = dict(input_binding or {})
    _validate_binding(connection, workflow_id, input_contract, binding)
    row = connection.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 FROM workflow_job_queue_steps WHERE workflow_id = ?",
        (workflow_id,),
    ).fetchone()
    position = int(row[0])
    step_id = f"step-{position:04d}-{uuid.uuid4().hex[:8]}"
    encoded_recipe = _dump(recipe)
    encoded_binding = _dump(binding)
    connection.execute(
        "INSERT OR IGNORE INTO workflow_job_queues(workflow_id) VALUES (?)",
        (workflow_id,),
    )
    connection.execute(
        """INSERT INTO workflow_job_queue_steps
           (workflow_id, step_id, position, job_type, recipe_json,
            input_contract, output_contract, input_binding_json, source_job_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            workflow_id,
            step_id,
            position,
            job_type,
            encoded_recipe,
            input_contract,
            output_contract,
            encoded_binding,
            str(source_job_id).strip() if source_job_id else None,
        ),
    )
    connection.execute(
        "UPDATE workflow_job_queues SET updated_at=CURRENT_TIMESTAMP WHERE workflow_id=?",
        (workflow_id,),
    )
    connection.commit()
    return next(item for item in list_queue_steps(connection, workflow_id) if item["step_id"] == step_id)


def remove_queue_step(connection: sqlite3.Connection, workflow_id: str, step_id: str) -> dict:
    ensure_workflow_queue_schema(connection)
    workflow_id = str(workflow_id)
    step_id = str(step_id)
    row = connection.execute(
        "SELECT * FROM workflow_job_queue_steps WHERE workflow_id=? AND step_id=?",
        (workflow_id, step_id),
    ).fetchone()
    if row is None:
        raise KeyError(f"step desconocido: {step_id}")
    for item in list_queue_steps(connection, workflow_id):
        binding = item["input_binding"]
        if binding.get("step_id") == step_id:
            raise ValueError("no se puede quitar un step con dependientes")
    removed = _step_dict(row)
    connection.execute(
        "DELETE FROM workflow_job_queue_steps WHERE workflow_id=? AND step_id=?",
        (workflow_id, step_id),
    )
    _compact_positions(connection, workflow_id)
    connection.execute(
        "UPDATE workflow_job_queues SET updated_at=CURRENT_TIMESTAMP WHERE workflow_id=?",
        (workflow_id,),
    )
    connection.commit()
    return removed


def reorder_queue_steps(connection: sqlite3.Connection, workflow_id: str, step_ids: list[str]) -> list[dict]:
    ensure_workflow_queue_schema(connection)
    workflow_id = str(workflow_id)
    current = list_queue_steps(connection, workflow_id)
    expected = [item["step_id"] for item in current]
    requested = [str(item) for item in step_ids]
    if sorted(requested) != sorted(expected):
        raise ValueError("step_ids no coincide con la cola")
    by_id = {item["step_id"]: item for item in current}
    for position, step_id in enumerate(requested, start=1):
        binding = by_id[step_id]["input_binding"]
        if binding.get("kind") in {"step_output", "previous_output"}:
            try:
                target_position = requested.index(str(binding.get("step_id"))) + 1
            except ValueError as exc:
                raise ValueError("binding apunta a un step inexistente") from exc
            if target_position >= position:
                raise ValueError("binding debe apuntar a un step anterior")
            target = by_id[str(binding["step_id"])]
            if target["output_contract"] != by_id[step_id]["input_contract"] and by_id[step_id]["input_contract"] != "Any":
                raise ValueError("binding incompatible")
    connection.execute(
        "UPDATE workflow_job_queue_steps SET position=position+100000 WHERE workflow_id=?",
        (workflow_id,),
    )
    for position, step_id in enumerate(requested, start=1):
        connection.execute(
            "UPDATE workflow_job_queue_steps SET position=? WHERE workflow_id=? AND step_id=?",
            (position, workflow_id, step_id),
        )
    connection.execute(
        "UPDATE workflow_job_queues SET updated_at=CURRENT_TIMESTAMP WHERE workflow_id=?",
        (workflow_id,),
    )
    connection.commit()
    return list_queue_steps(connection, workflow_id)


def set_telegram_mode(connection: sqlite3.Connection, workflow_id: str, mode: str) -> dict:
    ensure_workflow_queue_schema(connection)
    workflow_id = str(workflow_id or "").strip()
    mode = str(mode or "").strip()
    if not workflow_id or mode not in TELEGRAM_MODES:
        raise ValueError("telegram_mode debe ser queue_only o send_on_run")
    connection.execute(
        """INSERT INTO workflow_job_queues(workflow_id, telegram_mode)
           VALUES (?, ?)
           ON CONFLICT(workflow_id) DO UPDATE SET telegram_mode=excluded.telegram_mode,
             updated_at=CURRENT_TIMESTAMP""",
        (workflow_id, mode),
    )
    connection.commit()
    return get_queue(connection, workflow_id)


def snapshot_queue(connection: sqlite3.Connection, workflow_id: str, *, actor: str) -> dict:
    actor = str(actor or "").strip()
    if not actor:
        raise ValueError("actor es obligatorio")
    queue = get_queue(connection, workflow_id)
    payload = {
        "workflow_id": queue["workflow_id"],
        "telegram_mode": queue["telegram_mode"],
        "steps": queue["steps"],
    }
    encoded = _dump(payload)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return {
        "snapshot_id": str(uuid.uuid4()),
        "workflow_id": queue["workflow_id"],
        "telegram_mode": queue["telegram_mode"],
        "snapshot_json": encoded,
        "snapshot_hash": digest,
        "actor": actor,
    }


def _validate_binding(connection, workflow_id: str, input_contract: str, binding: dict) -> None:
    if not binding:
        return
    kind = str(binding.get("kind") or "").strip()
    if kind not in _BINDING_KINDS:
        raise ValueError("binding kind no soportado")
    if kind == "asset":
        return
    step_id = str(binding.get("step_id") or "").strip()
    if not step_id:
        raise ValueError("binding requiere step_id")
    current = connection.execute(
        "SELECT position, output_contract FROM workflow_job_queue_steps WHERE workflow_id=? AND step_id=?",
        (workflow_id, step_id),
    ).fetchone()
    if current is None:
        raise ValueError("binding debe apuntar a un step anterior")
    last_position = connection.execute(
        "SELECT COALESCE(MAX(position), 0) FROM workflow_job_queue_steps WHERE workflow_id=?",
        (workflow_id,),
    ).fetchone()[0]
    if int(current["position"]) > int(last_position):
        raise ValueError("binding debe apuntar a un step anterior")
    if input_contract != "Any" and str(current["output_contract"]) != input_contract:
        raise ValueError("binding incompatible")


def _compact_positions(connection, workflow_id: str) -> None:
    rows = connection.execute(
        "SELECT step_id FROM workflow_job_queue_steps WHERE workflow_id=? ORDER BY position",
        (workflow_id,),
    ).fetchall()
    connection.execute(
        "UPDATE workflow_job_queue_steps SET position=position+100000 WHERE workflow_id=?",
        (workflow_id,),
    )
    for position, row in enumerate(rows, start=1):
        connection.execute(
            "UPDATE workflow_job_queue_steps SET position=? WHERE workflow_id=? AND step_id=?",
            (position, workflow_id, row[0]),
        )


def _step_dict(row) -> dict:
    result = dict(row)
    result["recipe"] = json.loads(result.pop("recipe_json"))
    result["input_binding"] = json.loads(result.pop("input_binding_json"))
    return result


def _dump(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
