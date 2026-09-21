import sqlite3

from workflow_queue import append_queue_step, set_telegram_mode
from workflow_queue_runner import create_queue_execution, run_queue_execution


def db():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def build_flow(conn, workflow_id):
    forge = append_queue_step(
        conn,
        workflow_id,
        job_type="forge.tanda",
        recipe={"tanda": "SPAM", "output_root": "run-output"},
        input_contract="AssetList",
        output_contract="TandaOutput",
    )
    logistics = append_queue_step(
        conn,
        workflow_id,
        job_type="logistica.tanda",
        recipe={"accounts": ["spam-1", "spam-2"]},
        input_contract="TandaOutput",
        output_contract="ManifestOutput",
        input_binding={"kind": "previous_output", "step_id": forge["step_id"]},
    )
    append_queue_step(
        conn,
        workflow_id,
        job_type="telegram.send",
        recipe={"task_ids": ["task-1", "task-2"]},
        input_contract="ManifestOutput",
        output_contract="TelegramOutput",
        input_binding={"kind": "previous_output", "step_id": logistics["step_id"]},
    )


def test_full_forge_logistics_telegram_flow_is_ordered_and_delivery_mode_is_explicit():
    conn = db()
    build_flow(conn, "workflow-spam")
    set_telegram_mode(conn, "workflow-spam", "send_on_run")
    calls = []
    delivered = []

    def forge(step, _checkpoint, _save_checkpoint):
        calls.append("forge")
        return {"tanda": step["payload"]["tanda"], "files": ["spam-c01.mp4"]}

    def logistics(step, _checkpoint, _save_checkpoint):
        calls.append(("logistica", step["payload"]["input"]["files"]))
        return {"manifest": "manifest-spam.json", "task_ids": ["task-1", "task-2"]}

    def telegram_sender(recipe, input_value):
        delivered.append((recipe["task_ids"], input_value["manifest"]))
        return {"sent": len(recipe["task_ids"]), "already_sent": 0}

    handlers = {"forge.tanda": forge, "logistica.tanda": logistics}
    execution = create_queue_execution(conn, "workflow-spam", actor="test")
    result = run_queue_execution(conn, execution["execution_id"], worker_id="e2e", handlers=handlers, telegram_sender=telegram_sender)

    assert result["state"] == "succeeded"
    assert calls == ["forge", ("logistica", ["spam-c01.mp4"])]
    assert delivered == [(["task-1", "task-2"], "manifest-spam.json")]

    again = run_queue_execution(conn, execution["execution_id"], worker_id="e2e", handlers=handlers, telegram_sender=telegram_sender)
    assert again["state"] == "succeeded"
    assert delivered == [(["task-1", "task-2"], "manifest-spam.json")]


def test_queue_only_prepares_the_same_flow_without_sending():
    conn = db()
    build_flow(conn, "workflow-queue-only")
    set_telegram_mode(conn, "workflow-queue-only", "queue_only")
    sent = []
    execution = create_queue_execution(conn, "workflow-queue-only", actor="test")
    result = run_queue_execution(
        conn,
        execution["execution_id"],
        worker_id="e2e",
        handlers={
            "forge.tanda": lambda *_: {"tanda": "SPAM", "files": ["output.mp4"]},
            "logistica.tanda": lambda step, *_: {"manifest": "manifest.json", "task_ids": ["task-1"]},
        },
        telegram_sender=lambda *_: sent.append(True) or {"sent": 1},
    )
    assert result["state"] == "succeeded"
    assert sent == []
