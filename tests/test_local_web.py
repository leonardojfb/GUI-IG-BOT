import json
import urllib.error
import urllib.request

import database

from local_web import LocalWebService


def _request(url, token=None):
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=5) as response:
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
            assert "Contenido" in response.read().decode("utf-8")
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
