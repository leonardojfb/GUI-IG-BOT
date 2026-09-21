import json
import urllib.error
import urllib.parse
import urllib.request

import database

from local_web import LocalWebService


def request(url, token, *, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": f"Bearer {token}"})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def forge_fields():
    return {
        "video_paths": ["real.mp4"], "tanda_name": "SPAM", "copies": 1,
        "days": "7", "trial_mode": "Normal", "effects": "Default",
        "strength": "Default", "fx_enabled": {}, "forge_strength": 0.5,
        "overrides": None, "metadata_assignments": [{"source": "form"}],
    }


def manual_steps():
    return [
        {"module_type": "forge", "subtype": "normal", "fields": forge_fields()},
        {
            "module_type": "logistica", "subtype": "por_tandas",
            "fields": {"tanda_name": "SPAM", "tanda_name_2": "", "category_dest": "destino", "daily_quota": 2, "days": "7", "fillup": False},
            "input_binding": {"kind": "previous_output"},
        },
        {
            "module_type": "telegram", "subtype": "send",
            "fields": {"account_names": ["cuenta-real"], "date": "2026-09-21", "express": False, "reset_topics": False},
            "input_binding": {"kind": "previous_output"},
        },
    ]


def test_profile_api_filters_by_explicit_module_and_subtype(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    service = LocalWebService(db, token="web-token").start()
    try:
        status, saved = request(
            f"{service.base_url}/api/workflow-profiles", "web-token", method="POST",
            payload={"module_type": "forge", "subtype": "trials", "name": "Trials real", "recipe": {"trial_mode": "Trials"}},
        )
        assert status == 201

        query = urllib.parse.urlencode({"module_type": "forge", "subtype": "trials"})
        status, listed = request(f"{service.base_url}/api/workflow-profiles?{query}", "web-token")
        assert status == 200
        assert [item["name"] for item in listed["items"]] == ["Trials real"]
    finally:
        service.stop()
        db.close()


def test_manual_workflow_api_creates_ordered_steps_with_previous_output_bindings(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    service = LocalWebService(db, token="web-token").start()
    try:
        status, response = request(
            f"{service.base_url}/api/workflows/manual", "web-token", method="POST",
            payload={"name": "Cadena real", "steps": manual_steps()},
        )
        assert status == 201
        steps = response["data"]["queue"]["steps"]
        assert [step["job_type"] for step in steps] == ["forge.tanda", "logistica.tanda", "telegram.send"]
        assert steps[1]["input_binding"]["step_id"] == steps[0]["step_id"]
        assert steps[2]["input_binding"]["step_id"] == steps[1]["step_id"]
    finally:
        service.stop()
        db.close()


def test_invalid_manual_workflow_does_not_create_partial_workflow(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    service = LocalWebService(db, token="web-token").start()
    try:
        status, response = request(
            f"{service.base_url}/api/workflows/manual", "web-token", method="POST",
            payload={"name": "Invalido", "steps": [{"module_type": "forge", "subtype": "no-existe", "fields": {}}]},
        )
        assert status == 400
        assert "subtipo" in response["message"]
        assert db.conn.execute("select count(*) from workflows").fetchone()[0] == 0
    finally:
        service.stop()
        db.close()
