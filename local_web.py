"""Small authenticated loopback read API for the local legacy installation."""
from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class LocalWebService:
    def __init__(self, db, *, token: str | None = None, host: str = "127.0.0.1", port: int = 0, manifest_path: str = ""):
        self.db = db
        self.host = host
        self.port = int(port)
        self.token = token or secrets.token_urlsafe(32)
        self.manifest_path = str(manifest_path or "")
        self._server = None
        self._thread = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            return f"http://{self.host}:{self.port}"
        return f"http://{self.host}:{self._server.server_address[1]}"

    def start(self):
        service = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                service._handle(self)

            def log_message(self, *_args):
                return

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="metodo-ig-local-web", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _handle(self, request):
        if request.path == "/":
            self._respond_html(request, 200, _INDEX_HTML)
            return
        if request.path == "/health":
            self._respond(request, 200, {"status": "ok", "service": "local_web", "read_only": True})
            return
        if not self._authorized(request):
            self._respond(request, 401, {"error": "unauthorized"})
            return
        routes = {
            "/api/accounts": self._accounts,
            "/api/content": self._content,
            "/api/calendar": self._calendar,
            "/api/history": self._history,
        }
        producer = routes.get(request.path)
        if producer is None:
            self._respond(request, 404, {"error": "not_found"})
            return
        try:
            self._respond(request, 200, {"items": producer()})
        except Exception as exc:
            self._respond(request, 500, {"error": type(exc).__name__, "message": str(exc)})

    def _authorized(self, request) -> bool:
        value = request.headers.get("Authorization", "")
        scheme, _, supplied = value.partition(" ")
        return scheme.lower() == "bearer" and secrets.compare_digest(supplied, self.token)

    def _accounts(self) -> list[dict[str, Any]]:
        return list(self.db.get_all_accounts() or []) if hasattr(self.db, "get_all_accounts") else []

    def _content(self) -> list[dict[str, Any]]:
        if not hasattr(self.db, "list_video_transform_logs"):
            return []
        return list(self.db.list_video_transform_logs(limit=500) or [])

    def _calendar(self) -> list[dict[str, Any]]:
        return _read_json_items(self.manifest_path or getattr(self.db, "calendar_manifest_path", ""))

    def _history(self) -> list[dict[str, Any]]:
        return self._content()

    @staticmethod
    def _respond(request, status: int, payload: dict[str, Any]):
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        request.send_response(status)
        request.send_header("Content-Type", "application/json; charset=utf-8")
        request.send_header("Content-Length", str(len(data)))
        request.send_header("Cache-Control", "no-store")
        request.end_headers()
        request.wfile.write(data)

    @staticmethod
    def _respond_html(request, status: int, body: str):
        data = body.encode("utf-8")
        request.send_response(status)
        request.send_header("Content-Type", "text/html; charset=utf-8")
        request.send_header("Content-Length", str(len(data)))
        request.send_header("Cache-Control", "no-store")
        request.end_headers()
        request.wfile.write(data)


_INDEX_HTML = """<!doctype html>
<html lang=\"es\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Metodo IG local</title><h1>Metodo IG</h1>
<nav><a href=\"/api/accounts\">Cuentas</a> <a href=\"/api/content\">Contenido</a>
<a href=\"/api/calendar\">Calendario</a> <a href=\"/api/history\">Historial</a></nav>
</html>"""


def _read_json_items(path: str) -> list[dict[str, Any]]:
    if not path:
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        return [item for item in payload["entries"] if isinstance(item, dict)]
    return []
