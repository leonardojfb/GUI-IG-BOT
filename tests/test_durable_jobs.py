import sqlite3

import pytest

from durable_jobs import (
    cancel_job,
    claim_next_step,
    complete_step,
    create_job,
    fail_step,
    get_job,
    inspect_job_events,
    record_step_checkpoint,
    recover_expired_steps,
)


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def steps():
    return [
        {"step_id": "prepare", "kind": "prepare", "payload": {"input": "a"}},
        {"step_id": "render", "kind": "render", "depends_on": ["prepare"], "payload": {"quality": "high"}},
    ]


def test_job_persists_immutable_recipe_and_idempotency():
    conn = db()
    recipe = {"version": 1, "max_attempts": 2, "backoff_seconds": 5, "source": "a.mp4"}

    first = create_job(conn, job_type="video.transform", recipe=recipe, steps=steps(), idempotency_key="k1", now=100)
    again = create_job(conn, job_type="video.transform", recipe={"version": 99}, steps=steps(), idempotency_key="k1", now=200)

    assert again["job_id"] == first["job_id"]
    stored = get_job(conn, first["job_id"])
    assert stored["recipe"] == recipe
    assert [step["step_id"] for step in stored["steps"]] == ["prepare", "render"]
    with pytest.raises(ValueError, match="dependencia"):
        create_job(conn, job_type="x", recipe={}, steps=[{"step_id": "a", "kind": "x", "depends_on": ["missing"]}])


def test_claim_checkpoint_complete_and_dependency_unlock():
    conn = db()
    job = create_job(conn, job_type="video.transform", recipe={"version": 1}, steps=steps(), now=100)

    claimed = claim_next_step(conn, worker_id="w1", now=100)
    assert claimed["step_id"] == "prepare"
    assert claim_next_step(conn, worker_id="w2", now=100) is None
    record_step_checkpoint(conn, job_id=job["job_id"], step_id="prepare", worker_id="w1", lease_token=claimed["lease_token"], checkpoint={"frame": 30}, now=101)
    complete_step(conn, job_id=job["job_id"], step_id="prepare", worker_id="w1", lease_token=claimed["lease_token"], result={"output": "x"}, now=102)
    next_step = claim_next_step(conn, worker_id="w2", now=103)
    assert next_step["step_id"] == "render"
    assert next_step["checkpoint"] == {}


def test_retry_and_recovery_preserve_checkpoint_and_event_order():
    conn = db()
    job = create_job(conn, job_type="video.transform", recipe={"version": 1, "max_attempts": 3, "backoff_seconds": 5}, steps=steps(), now=100)
    claimed = claim_next_step(conn, worker_id="w1", now=100, lease_seconds=10)
    record_step_checkpoint(conn, job_id=job["job_id"], step_id=claimed["step_id"], worker_id="w1", lease_token=claimed["lease_token"], checkpoint={"frame": 9}, now=105)
    recovered = recover_expired_steps(conn, now=111)
    assert recovered["requeued"] == 1
    retried = claim_next_step(conn, worker_id="w2", now=116)
    assert retried["attempt"] == 2
    assert retried["checkpoint"] == {"frame": 9}
    failed = fail_step(conn, job_id=job["job_id"], step_id="prepare", worker_id="w2", lease_token=retried["lease_token"], error={"message": "temporary"}, retryable=True, now=117)
    assert failed["state"] == "retry_wait"
    assert failed["next_attempt_at"] == 127
    events = inspect_job_events(conn, job_id=job["job_id"])
    assert [event["event_type"] for event in events][:3] == ["created", "claimed", "checkpoint"]


def test_non_retryable_failure_and_cancel_are_terminal():
    conn = db()
    job = create_job(conn, job_type="x", recipe={"version": 1}, steps=[{"step_id": "a", "kind": "x"}], now=1)
    claimed = claim_next_step(conn, worker_id="w", now=1)
    result = fail_step(conn, job_id=job["job_id"], step_id=claimed["step_id"], worker_id="w", lease_token=claimed["lease_token"], error={"message": "bad"}, retryable=False, now=2)
    assert result["state"] == "failed"
    cancelled = cancel_job(conn, job_id=job["job_id"], reason="user", now=3)
    assert cancelled["state"] == "cancelled"


def test_failed_dependency_marks_downstream_step_blocked():
    conn = db()
    job = create_job(conn, job_type="x", recipe={"version": 1}, steps=steps(), now=1)
    claimed = claim_next_step(conn, worker_id="w", now=1)
    fail_step(conn, job_id=job["job_id"], step_id=claimed["step_id"], worker_id="w", lease_token=claimed["lease_token"], error={"message": "bad"}, retryable=False, now=2)

    assert claim_next_step(conn, worker_id="w2", now=3) is None
    stored = get_job(conn, job["job_id"])
    assert stored["state"] == "blocked"
    assert stored["steps"][1]["state"] == "blocked"


def test_expired_worker_token_cannot_write_after_recovery():
    conn = db()
    job = create_job(conn, job_type="x", recipe={"version": 1, "max_attempts": 2}, steps=[{"step_id": "a", "kind": "x"}], now=1)
    old = claim_next_step(conn, worker_id="w", lease_seconds=2, now=1)
    recover_expired_steps(conn, now=4)
    new = claim_next_step(conn, worker_id="w2", now=4)

    with pytest.raises(RuntimeError, match="lease valido"):
        complete_step(conn, job_id=job["job_id"], step_id="a", worker_id="w", lease_token=old["lease_token"], result={}, now=5)
    complete_step(conn, job_id=job["job_id"], step_id="a", worker_id="w2", lease_token=new["lease_token"], result={}, now=5)


def test_recovery_preserves_backoff_and_blocks_transitive_dependencies():
    conn = db()
    job = create_job(conn, job_type="x", recipe={"version": 1, "max_attempts": 2, "backoff_seconds": 5}, steps=[
        {"step_id": "a", "kind": "x"},
        {"step_id": "b", "kind": "x", "depends_on": ["a"]},
        {"step_id": "c", "kind": "x", "depends_on": ["b"]},
    ], now=1)
    claimed = claim_next_step(conn, worker_id="w", lease_seconds=2, now=1)
    recover_expired_steps(conn, now=4)
    assert claim_next_step(conn, worker_id="w2", now=4) is None
    retry = claim_next_step(conn, worker_id="w2", now=9)
    assert retry["step_id"] == "a"
    fail_step(conn, job_id=job["job_id"], step_id="a", worker_id="w2", lease_token=retry["lease_token"], error={"message": "bad"}, retryable=False, now=10)
    assert claim_next_step(conn, worker_id="w3", now=11) is None
    stored = get_job(conn, job["job_id"])
    assert [step["state"] for step in stored["steps"]] == ["failed", "blocked", "blocked"]
