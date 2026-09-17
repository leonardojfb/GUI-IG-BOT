import json
import urllib.error
import urllib.request

import database

from local_web import LocalWebService
from manual_calendar_export import export_manual_package


def _request(url, token=None):
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _post(url, token, payload):
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    try:
        response = urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    with response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_local_web_requires_token_and_exposes_read_models(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    db.add_category("Fans")
    service = LocalWebService(db, token="test-token")
    service.start()
    try:
        url = f"{service.base_url}/api/accounts"
        try:
            _request(url)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("protected endpoint accepted missing token")

        status, payload = _request(url, "test-token")
        assert status == 200
        assert payload["items"] == []
        assert _request(f"{service.base_url}/health")[1]["status"] == "ok"
        with urllib.request.urlopen(f"{service.base_url}/", timeout=5) as response:
            body = response.read().decode("utf-8")
            assert "Contenido" in body
            assert "loadView" in body
    finally:
        service.stop()
        db.close()


def test_local_web_read_endpoints_are_json_and_read_only(tmp_path):
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    service = LocalWebService(db, token="abc")
    service.start()
    try:
        for route in ("content", "calendar", "history"):
            status, payload = _request(f"{service.base_url}/api/{route}", "abc")
            assert status == 200
            assert isinstance(payload["items"], list)
    finally:
        service.stop()
        db.close()


def test_local_web_exposes_authenticated_crm_metric_series(tmp_path):
    from crm_insights import record_metric_snapshot

    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    record_metric_snapshot(db.conn, "acc-1", {"posts": 2, "likes": 8, "token": "secret"}, observed_at="2026-09-17T10:00:00Z")
    service = LocalWebService(db, token="crm-token").start()
    try:
        status, payload = _request(f"{service.base_url}/api/crm/metrics?account_id=acc-1", "crm-token")
        assert status == 200
        assert payload["items"] == [
            {"account_id": "acc-1", "observed_at": "2026-09-17T10:00:00Z", "metrics": {"likes": 8, "posts": 2}}
        ]
    finally:
        service.stop()
        db.close()


def test_legacy_gui_exposes_opt_in_local_panel_without_replacing_entrypoints():
    source = open("gui_premium_v7.py", encoding="utf-8").read()
    assert 'text="Abrir panel local"' in source
    assert "def _open_local_web" in source
    assert 'self.show_frame("Forge")' not in source[source.index("def _open_local_web"):source.index("def _on_close")]
    assert "calendar_import_root=UPDATE_APP_DIR" in source
    assert "manual_import_audit.jsonl" in source


def test_legacy_gui_exposes_read_only_ios_snapshot_loader():
    source = open("gui_premium_v7.py", encoding="utf-8").read()
    assert "Cargar snapshot ios-remote" in source
    assert "def destination_load_ios_snapshot" in source
    assert "load_ios_remote_snapshot" in source


def test_local_web_calendar_import_is_previewed_confirmed_and_scoped(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"media")
    package = tmp_path / "calendar.zip"
    export_manual_package([{"media_path": str(media), "username": "alice"}], package)
    import_root = tmp_path / "imports"
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    audit = tmp_path / "calendar-imports.jsonl"
    service = LocalWebService(db, token="web-token", calendar_import_root=str(import_root), calendar_audit_path=str(audit)).start()
    try:
        status, preview = _post(f"{service.base_url}/api/calendar/import-preview", "web-token", {"package_path": str(package), "destination": "day-1"})
        assert status == 200
        assert preview["status"] == "ready"
        assert not import_root.exists()

        status, denied = _post(f"{service.base_url}/api/calendar/import", "web-token", {"package_path": str(package), "destination": "day-1", "confirm": False})
        assert status == 400
        assert denied["error"] == "confirmation_required"

        status, imported = _post(f"{service.base_url}/api/calendar/import", "web-token", {"package_path": str(package), "destination": "day-1", "confirm": True})
        assert status == 200
        assert imported["status"] == "imported"
        assert (import_root / "day-1" / "media" / "0001.mp4").read_bytes() == b"media"
        assert '"event": "manual_calendar_import"' in audit.read_text(encoding="utf-8")
    finally:
        service.stop()
        db.close()
