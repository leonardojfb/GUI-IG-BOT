import json
import sqlite3

import pytest

from workflow_queue import (
    append_queue_step,
    list_queue_steps,
    remove_queue_step,
    reorder_queue_steps,
    set_telegram_mode,
    snapshot_queue,
)


def db():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def test_append_queue_step_preserves_order_and_recipe_snapshot():
    conn = db()
    first = append_queue_step(
        conn,
        "wf-1",
        job_type="forge.tanda",
        recipe={"tanda": "SPAM"},
        input_contract="AssetList",
        output_contract="TandaOutput",
    )
    second = append_queue_step(
        conn,
        "wf-1",
        job_type="logistica.tanda",
        recipe={"accounts": ["spam-1"]},
        input_contract="TandaOutput",
        output_contract="ManifestOutput",
        input_binding={"kind": "previous_output", "step_id": first["step_id"]},
    )

    assert [item["position"] for item in list_queue_steps(conn, "wf-1")] == [1, 2]
    assert second["input_binding"] == {"kind": "previous_output", "step_id": first["step_id"]}
    first["recipe"]["tanda"] = "MUTATED"
    assert list_queue_steps(conn, "wf-1")[0]["recipe"]["tanda"] == "SPAM"


def test_queue_rejects_unknown_or_incompatible_bindings():
    conn = db()
    with pytest.raises(ValueError, match="anterior"):
        append_queue_step(
            conn,
            "wf-1",
            job_type="telegram.send",
            recipe={"mode": "queue_only"},
            input_contract="ManifestOutput",
            output_contract="TelegramOutput",
            input_binding={"kind": "step_output", "step_id": "missing"},
        )

    forge = append_queue_step(
        conn,
        "wf-1",
        job_type="forge.tanda",
        recipe={"tanda": "SPAM"},
        input_contract="AssetList",
        output_contract="TandaOutput",
    )
    with pytest.raises(ValueError, match="incompatible"):
        append_queue_step(
            conn,
            "wf-1",
            job_type="telegram.send",
            recipe={"mode": "queue_only"},
            input_contract="ManifestOutput",
            output_contract="TelegramOutput",
            input_binding={"kind": "step_output", "step_id": forge["step_id"]},
        )


def test_queue_can_reorder_and_remove_steps():
    conn = db()
    ids = [
        append_queue_step(
            conn,
            "wf-1",
            job_type=f"step-{index}",
            recipe={"index": index},
            input_contract="Any",
            output_contract="Any",
        )["step_id"]
        for index in range(3)
    ]

    reordered = reorder_queue_steps(conn, "wf-1", [ids[2], ids[0], ids[1]])
    assert [item["step_id"] for item in reordered] == [ids[2], ids[0], ids[1]]
    removed = remove_queue_step(conn, "wf-1", ids[0])
    assert removed["step_id"] == ids[0]
    assert [item["position"] for item in list_queue_steps(conn, "wf-1")] == [1, 2]


def test_snapshot_freezes_queue_and_telegram_mode():
    conn = db()
    set_telegram_mode(conn, "wf-1", "send_on_run")
    append_queue_step(
        conn,
        "wf-1",
        job_type="telegram.send",
        recipe={"task_ids": ["task-1"]},
        input_contract="ManifestOutput",
        output_contract="TelegramOutput",
    )

    snapshot = snapshot_queue(conn, "wf-1", actor="test")
    payload = json.loads(snapshot["snapshot_json"])
    assert snapshot["telegram_mode"] == "send_on_run"
    assert payload["steps"][0]["recipe"] == {"task_ids": ["task-1"]}
    assert snapshot["snapshot_hash"]

    set_telegram_mode(conn, "wf-1", "queue_only")
    assert json.loads(snapshot["snapshot_json"])["telegram_mode"] == "send_on_run"
