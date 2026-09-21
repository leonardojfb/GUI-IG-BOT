"""Materialize and run ordered workflow queue snapshots."""
from __future__ import annotations

import json
import sqlite3
import time

from durable_jobs import create_job, get_job
from job_runner import run_until_idle
from workflow_queue import ensure_workflow_queue_schema, snapshot_queue


def ensure_queue_execution_schema(connection: sqlite3.Connection) -> None:
    ensure_workflow_queue_schema(connection)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS workflow_job_executions (
            execution_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            durable_job_id TEXT NOT NULL UNIQUE,
            snapshot_json TEXT NOT NULL,
            snapshot_hash TEXT NOT NULL,
            actor TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )"""
    )
    connection.commit()


def create_queue_execution(connection: sqlite3.Connection, workflow_id: str, *, actor: str) -> dict:
    ensure_queue_execution_schema(connection)
    snapshot = snapshot_queue(connection, workflow_id, actor=actor)
    payload = json.loads(snapshot["snapshot_json"])
    queue_steps = payload["steps"]
    if not queue_steps:
        raise ValueError("workflow no tiene steps")
    execution_id = snapshot["snapshot_id"]
    durable_steps = []
    previous_step_id = None
    for queue_step in queue_steps:
        durable_steps.append(
            {
                "step_id": queue_step["step_id"],
                "kind": "workflow.queue_step",
                "depends_on": [previous_step_id] if previous_step_id else [],
                "payload": {"execution_id": execution_id, "queue_step": queue_step},
            }
        )
        previous_step_id = queue_step["step_id"]
    durable = create_job(
        connection,
        job_type="workflow.queue.v1",
        recipe={
            "workflow_id": str(workflow_id),
            "snapshot_hash": snapshot["snapshot_hash"],
            "telegram_mode": snapshot["telegram_mode"],
        },
        steps=durable_steps,
        idempotency_key=f"workflow-execution:{execution_id}",
    )
    now = int(time.time())
    connection.execute(
        """INSERT INTO workflow_job_executions
           (execution_id, workflow_id, durable_job_id, snapshot_json,
            snapshot_hash, actor, state, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (
            execution_id,
            str(workflow_id),
            durable["job_id"],
            snapshot["snapshot_json"],
            snapshot["snapshot_hash"],
            str(actor),
            now,
            now,
        ),
    )
    connection.commit()
    return get_queue_execution(connection, execution_id)


def get_queue_execution(connection: sqlite3.Connection, execution_id: str) -> dict:
    ensure_queue_execution_schema(connection)
    row = connection.execute(
        "SELECT * FROM workflow_job_executions WHERE execution_id=?",
        (str(execution_id),),
    ).fetchone()
    if row is None:
        raise KeyError(f"execution desconocida: {execution_id}")
    result = dict(row)
    result["snapshot"] = json.loads(result.pop("snapshot_json"))
    durable = get_job(connection, result["durable_job_id"])
    result["durable_job"] = durable
    result["steps"] = durable["steps"] if durable else []
    return result


def run_queue_execution(
    connection: sqlite3.Connection,
    execution_id: str,
    *,
    worker_id: str,
    handlers: dict | None = None,
    telegram_sender=None,
) -> dict:
    execution = get_queue_execution(connection, execution_id)
    durable = execution["durable_job"]
    if durable is None:
        raise KeyError(f"durable job no encontrado: {execution['durable_job_id']}")
    dispatchers = default_queue_handlers(connection, telegram_sender=telegram_sender)
    dispatchers.update(handlers or {})

    def queue_step_handler(step, checkpoint, save_checkpoint):
        queue_step = step["payload"]["queue_step"]
        input_value = resolve_input_binding(connection, step["job_id"], queue_step.get("input_binding") or {})
        dispatch_step = dict(step)
        dispatch_step["step_id"] = queue_step["step_id"]
        dispatch_step["kind"] = queue_step["job_type"]
        dispatch_step["payload"] = dict(queue_step["recipe"])
        dispatch_step["payload"]["input"] = input_value
        dispatch_step["payload"]["_telegram_mode"] = execution["snapshot"].get("telegram_mode", "queue_only")
        handler = dispatchers.get(queue_step["job_type"])
        if handler is None:
            raise ValueError(f"handler no encontrado: {queue_step['job_type']}")
        return handler(dispatch_step, checkpoint, save_checkpoint) or {}

    summary = run_until_idle(
        connection,
        worker_id=worker_id,
        handlers={"workflow.queue_step": queue_step_handler},
        max_steps=max(1, len(durable["steps"]) + 1),
    )
    return _sync_execution(connection, execution_id, summary)


def resume_queue_execution(
    connection: sqlite3.Connection,
    execution_id: str,
    *,
    worker_id: str,
    handlers: dict | None = None,
    telegram_sender=None,
) -> dict:
    execution = get_queue_execution(connection, execution_id)
    durable_id = execution["durable_job_id"]
    failed = [step for step in execution["steps"] if step["state"] == "failed"]
    if not failed:
        return run_queue_execution(connection, execution_id, worker_id=worker_id, handlers=handlers, telegram_sender=telegram_sender)
    now = int(time.time())
    connection.execute("BEGIN IMMEDIATE")
    for step in failed:
        connection.execute(
            """UPDATE durable_job_steps
               SET state='pending', error_json='{}', next_attempt_at=0,
                   lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL
               WHERE job_id=? AND step_id=? AND state='failed'""",
            (durable_id, step["step_id"]),
        )
        connection.execute(
            "INSERT INTO durable_job_events(job_id, step_id, event_type, payload_json, created_at) VALUES (?, ?, 'manual_resume', '{}', ?)",
            (durable_id, step["step_id"], now),
        )
    _unblock_ready_steps(connection, durable_id, now)
    connection.commit()
    return run_queue_execution(connection, execution_id, worker_id=worker_id, handlers=handlers, telegram_sender=telegram_sender)


def resolve_input_binding(connection: sqlite3.Connection, durable_job_id: str, binding: dict) -> dict | None:
    if not binding:
        return None
    kind = str(binding.get("kind") or "")
    if kind == "asset":
        return binding.get("value")
    source_step_id = str(binding.get("step_id") or "")
    job = get_job(connection, durable_job_id)
    if job is None:
        raise KeyError(f"durable job no encontrado: {durable_job_id}")
    source = next((step for step in job["steps"] if step["step_id"] == source_step_id), None)
    if source is None or source["state"] != "succeeded":
        raise ValueError("input upstream no esta disponible")
    return source.get("result") or {}


def default_queue_handlers(connection: sqlite3.Connection, *, telegram_sender=None) -> dict:
    def telegram_handler(step, _checkpoint, _save_checkpoint):
        recipe = step["payload"]
        tasks = _telegram_tasks(connection, recipe.get("task_ids"))
        if step["payload"].get("_telegram_mode") == "queue_only":
            return {"queued": len(tasks), "sent": 0, "task_ids": [item.get("task_id") for item in tasks]}
        if telegram_sender is not None:
            return telegram_sender(recipe, step["payload"].get("input"))
        from telegram_universal_queue import deliver_with_legacy_telegram

        return deliver_with_legacy_telegram(connection, tasks=tasks)

    return {"telegram.send": telegram_handler}


def _sync_execution(connection, execution_id: str, summary: dict) -> dict:
    execution = get_queue_execution(connection, execution_id)
    durable_state = execution["durable_job"]["state"]
    now = int(time.time())
    connection.execute(
        "UPDATE workflow_job_executions SET state=?, updated_at=? WHERE execution_id=?",
        (durable_state, now, str(execution_id)),
    )
    connection.commit()
    result = get_queue_execution(connection, execution_id)
    result["summary"] = summary
    return result


def _unblock_ready_steps(connection, durable_job_id: str, now: int) -> None:
    rows = connection.execute(
        "SELECT * FROM durable_job_steps WHERE job_id=? AND state='blocked' ORDER BY rowid",
        (durable_job_id,),
    ).fetchall()
    for row in rows:
        deps = json.loads(row["depends_on_json"])
        states = {
            item[0]: item[1]
            for item in connection.execute(
                "SELECT step_id, state FROM durable_job_steps WHERE job_id=?",
                (durable_job_id,),
            ).fetchall()
        }
        if not any(states.get(dep) in {"failed", "cancelled"} for dep in deps):
            connection.execute(
                "UPDATE durable_job_steps SET state='pending', error_json='{}', next_attempt_at=0 WHERE job_id=? AND step_id=?",
                (durable_job_id, row["step_id"]),
            )
            connection.execute(
                "INSERT INTO durable_job_events(job_id, step_id, event_type, payload_json, created_at) VALUES (?, ?, 'unblocked', '{}', ?)",
                (durable_job_id, row["step_id"], now),
            )


def _telegram_tasks(connection, task_ids) -> list[dict]:
    from telegram_universal_queue import list_telegram_queue

    tasks = list_telegram_queue(connection)
    wanted = {str(item) for item in (task_ids or [])}
    return [task for task in tasks if not wanted or str(task.get("task_id")) in wanted]
