import sqlite3

from workflow_queue import append_queue_step, set_telegram_mode
from workflow_queue_runner import (
    create_queue_execution,
    get_queue_execution,
    resume_queue_execution,
    run_queue_execution,
)


def db():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def add_three_steps(conn, workflow_id="wf-1"):
    forge = append_queue_step(
        conn,
        workflow_id,
        job_type="forge.tanda",
        recipe={"tanda": "SPAM"},
        input_contract="AssetList",
        output_contract="TandaOutput",
    )
    logistics = append_queue_step(
        conn,
        workflow_id,
        job_type="logistica.tanda",
        recipe={"accounts": ["spam"]},
        input_contract="TandaOutput",
        output_contract="ManifestOutput",
        input_binding={"kind": "previous_output", "step_id": forge["step_id"]},
    )
    telegram = append_queue_step(
        conn,
        workflow_id,
        job_type="telegram.send",
        recipe={"task_ids": ["task-1"]},
        input_contract="ManifestOutput",
        output_contract="TelegramOutput",
        input_binding={"kind": "previous_output", "step_id": logistics["step_id"]},
    )
    return forge, logistics, telegram


def test_execution_passes_forge_output_to_logistica_and_telegram():
    conn = db()
    forge, logistics, telegram = add_three_steps(conn)
    seen = []

    def forge_handler(step, _checkpoint, _save_checkpoint):
        seen.append((step["step_id"], step["payload"].get("input")))
        return {"tanda": "SPAM", "files": ["out-1.mp4"]}

    def logistics_handler(step, _checkpoint, _save_checkpoint):
        seen.append((step["step_id"], step["payload"]["input"]))
        return {"manifest": "manifest.json", "task_ids": ["task-1"]}

    def telegram_handler(step, _checkpoint, _save_checkpoint):
        seen.append((step["step_id"], step["payload"]["input"]))
        return {"queued": 1}

    execution = create_queue_execution(conn, "wf-1", actor="test")
    result = run_queue_execution(
        conn,
        execution["execution_id"],
        worker_id="test",
        handlers={
            "forge.tanda": forge_handler,
            "logistica.tanda": logistics_handler,
            "telegram.send": telegram_handler,
        },
    )

    assert result["state"] == "succeeded"
    assert [item[0] for item in seen] == [forge["step_id"], logistics["step_id"], telegram["step_id"]]
    assert seen[1][1]["tanda"] == "SPAM"
    assert seen[2][1]["manifest"] == "manifest.json"


def test_failed_step_blocks_descendants_and_resume_keeps_successful_output():
    conn = db()
    forge, logistics, telegram = add_three_steps(conn)
    calls = []

    def forge_handler(_step, _checkpoint, _save_checkpoint):
        calls.append("forge")
        return {"tanda": "SPAM"}

    def failing_logistics(_step, _checkpoint, _save_checkpoint):
        calls.append("logistica")
        raise RuntimeError("cuentas invalidas")

    def telegram_handler(_step, _checkpoint, _save_checkpoint):
        calls.append("telegram")
        return {"sent": 1}

    execution = create_queue_execution(conn, "wf-1", actor="test")
    first = run_queue_execution(
        conn,
        execution["execution_id"],
        worker_id="w1",
        handlers={
            "forge.tanda": forge_handler,
            "logistica.tanda": failing_logistics,
            "telegram.send": telegram_handler,
        },
    )
    assert first["state"] == "blocked"
    assert [step["state"] for step in get_queue_execution(conn, execution["execution_id"])["steps"]] == ["succeeded", "failed", "blocked"]

    def working_logistics(_step, _checkpoint, _save_checkpoint):
        calls.append("logistica")
        return {"manifest": "manifest.json"}

    second = resume_queue_execution(
        conn,
        execution["execution_id"],
        worker_id="w2",
        handlers={
            "forge.tanda": forge_handler,
            "logistica.tanda": working_logistics,
            "telegram.send": telegram_handler,
        },
    )
    assert second["state"] == "succeeded"
    assert calls == ["forge", "logistica", "logistica", "telegram"]


def test_telegram_mode_controls_delivery_side_effect():
    conn = db()
    append_queue_step(
        conn,
        "queue-only",
        job_type="telegram.send",
        recipe={"task_ids": ["task-1"]},
        input_contract="ManifestOutput",
        output_contract="TelegramOutput",
    )
    set_telegram_mode(conn, "queue-only", "queue_only")
    sent = []
    execution = create_queue_execution(conn, "queue-only", actor="test")
    queue_result = run_queue_execution(
        conn,
        execution["execution_id"],
        worker_id="w1",
        telegram_sender=lambda _recipe, _input: sent.append(True) or {"sent": 1},
    )
    assert queue_result["state"] == "succeeded"
    assert sent == []

    append_queue_step(
        conn,
        "send-now",
        job_type="telegram.send",
        recipe={"task_ids": ["task-2"]},
        input_contract="ManifestOutput",
        output_contract="TelegramOutput",
    )
    set_telegram_mode(conn, "send-now", "send_on_run")
    execution = create_queue_execution(conn, "send-now", actor="test")
    send_result = run_queue_execution(
        conn,
        execution["execution_id"],
        worker_id="w1",
        telegram_sender=lambda _recipe, _input: sent.append(True) or {"sent": 1},
    )
    assert send_result["state"] == "succeeded"
    assert sent == [True]
