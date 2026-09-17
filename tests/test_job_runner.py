import sqlite3

from durable_jobs import create_job, get_job
from job_runner import RetryableJobError, run_until_idle


def test_runner_executes_dependencies_and_persists_outputs():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    job = create_job(conn, job_type="demo", recipe={"version": 1}, steps=[
        {"step_id": "a", "kind": "prepare"},
        {"step_id": "b", "kind": "render", "depends_on": ["a"]},
    ], now=10)
    seen = []

    def prepare(step, checkpoint, save_checkpoint):
        seen.append(step["step_id"])
        save_checkpoint({"phase": "prepared"})
        return {"value": 3}

    def render(step, checkpoint, save_checkpoint):
        seen.append((step["step_id"], checkpoint))
        return {"output": "done"}

    summary = run_until_idle(conn, worker_id="worker-1", handlers={"prepare": prepare, "render": render}, now=10)

    assert summary["completed"] == 2
    assert seen == ["a", ("b", {})]
    assert get_job(conn, job["job_id"])["state"] == "succeeded"


def test_runner_retryable_error_keeps_checkpoint_and_unknown_kind_fails():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    job = create_job(conn, job_type="demo", recipe={"version": 1, "max_attempts": 2}, steps=[{"step_id": "a", "kind": "retry"}], now=10)
    calls = []

    def retry(step, checkpoint, save_checkpoint):
        calls.append(checkpoint)
        save_checkpoint({"offset": len(calls)})
        raise RetryableJobError("temporary")

    first = run_until_idle(conn, worker_id="worker-1", handlers={"retry": retry}, now=10)
    assert first["retry_wait"] == 1
    assert calls == [{}]
    second = run_until_idle(conn, worker_id="worker-2", handlers={"retry": retry}, now=11)
    assert second["failed"] == 1
    assert calls == [{}, {"offset": 1}]

    unknown = create_job(conn, job_type="demo", recipe={"version": 1}, steps=[{"step_id": "x", "kind": "missing"}], now=20)
    result = run_until_idle(conn, worker_id="worker-3", handlers={}, now=20)
    assert result["failed"] == 1
    assert get_job(conn, unknown["job_id"])["state"] == "failed"

