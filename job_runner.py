"""Small resumable executor for the R09 durable job state machine."""
from __future__ import annotations

from durable_jobs import claim_next_step, complete_step, fail_step, record_step_checkpoint, recover_expired_steps


class RetryableJobError(RuntimeError):
    """Handler failure that may be retried according to the recipe."""


def run_one_step(connection, *, worker_id: str, handlers: dict[str, callable], now: int | None = None) -> dict | None:
    step = claim_next_step(connection, worker_id=worker_id, now=now)
    if step is None:
        return None
    checkpoint = step.get("checkpoint") or {}

    def save_checkpoint(value):
        nonlocal checkpoint
        checkpoint = dict(value or {})
        record_step_checkpoint(connection, job_id=step["job_id"], step_id=step["step_id"], worker_id=worker_id, lease_token=step["lease_token"], checkpoint=checkpoint, now=now)

    handler = handlers.get(step["kind"])
    if handler is None:
        result = fail_step(connection, job_id=step["job_id"], step_id=step["step_id"], worker_id=worker_id, lease_token=step["lease_token"], error={"type": "missing_handler", "kind": step["kind"]}, retryable=False, now=now)
        return {"action": "failed", "step": result}
    try:
        output = handler(step, checkpoint, save_checkpoint) or {}
    except RetryableJobError as exc:
        result = fail_step(connection, job_id=step["job_id"], step_id=step["step_id"], worker_id=worker_id, lease_token=step["lease_token"], error={"type": "retryable", "message": str(exc)}, retryable=True, now=now)
        return {"action": result["state"], "step": result}
    except Exception as exc:
        result = fail_step(connection, job_id=step["job_id"], step_id=step["step_id"], worker_id=worker_id, lease_token=step["lease_token"], error={"type": type(exc).__name__, "message": str(exc)}, retryable=False, now=now)
        return {"action": "failed", "step": result}
    result = complete_step(connection, job_id=step["job_id"], step_id=step["step_id"], worker_id=worker_id, lease_token=step["lease_token"], result=output, now=now)
    return {"action": "completed", "step": result}


def run_until_idle(connection, *, worker_id: str, handlers: dict[str, callable], max_steps: int = 100, now: int | None = None) -> dict:
    summary = {"completed": 0, "retry_wait": 0, "failed": 0, "steps": 0}
    recover_expired_steps(connection, now=now)
    for _ in range(int(max_steps)):
        result = run_one_step(connection, worker_id=worker_id, handlers=handlers, now=now)
        if result is None:
            break
        summary["steps"] += 1
        action = result["action"]
        if action == "completed":
            summary["completed"] += 1
        elif action == "retry_wait":
            summary["retry_wait"] += 1
            break
        elif action == "failed":
            summary["failed"] += 1
    return summary


def recover_and_run(connection, *, worker_id: str, handlers: dict[str, callable], now: int | None = None) -> dict:
    recovery = recover_expired_steps(connection, now=now)
    result = run_until_idle(connection, worker_id=worker_id, handlers=handlers, now=now)
    result["recovered"] = recovery["requeued"]
    return result
