import json
import urllib.request

import database

from local_web import LocalWebService


def post(url, token, payload):
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode())


def get(url, token):
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode())


def create_workflow(service, token):
    _, recipe = post(
        f"{service.base_url}/api/modules",
        token,
        {"kind": "production_recipe", "name": "Queue recipe", "payload": {}},
    )
    _, publication = post(
        f"{service.base_url}/api/modules",
        token,
        {"kind": "publication_template", "name": "Queue publication", "payload": {"rules": [{"target": "instagram_reel", "times": ["12:00"]}]}},
    )
    _, telegram = post(
        f"{service.base_url}/api/modules",
        token,
        {"kind": "telegram_template", "name": "Queue telegram", "payload": {}},
    )
    _, workflow = post(
        f"{service.base_url}/api/workflows",
        token,
        {
            "name": "Workflow queue",
            "production_ref": [recipe["data"]["module_id"], 1],
            "publication_refs": [[publication["data"]["module_id"], 1]],
            "telegram_ref": [telegram["data"]["module_id"], 1],
        },
    )
    return workflow["data"]


def test_web_adds_job_to_workflow_selects_telegram_mode_and_executes_it(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    service = LocalWebService(db, token="web-token").start()
    try:
        workflow = create_workflow(service, "web-token")
        workflow_id = workflow["workflow_id"]
        status, added = post(
            f"{service.base_url}/api/workflows/{workflow_id}/queue/steps",
            "web-token",
            {"job_type": "telegram.send", "recipe": {"task_ids": ["task-1"]}, "input_contract": "ManifestOutput", "output_contract": "TelegramOutput"},
        )
        assert status == 201
        assert added["data"]["steps"][0]["job_type"] == "telegram.send"

        status, settings = post(
            f"{service.base_url}/api/workflows/{workflow_id}/queue/settings",
            "web-token",
            {"telegram_mode": "queue_only"},
        )
        assert status == 200
        assert settings["data"]["telegram_mode"] == "queue_only"

        status, execution = post(
            f"{service.base_url}/api/workflows/{workflow_id}/queue/execute",
            "web-token",
            {},
        )
        assert status == 202
        assert execution["data"]["state"] == "succeeded"

        status, stored = get(f"{service.base_url}/api/executions/{execution['data']['execution_id']}", "web-token")
        assert status == 200
        assert stored["data"]["steps"][0]["state"] == "succeeded"
    finally:
        service.stop()
        db.close()
