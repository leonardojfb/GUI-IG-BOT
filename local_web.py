"""Small authenticated loopback read API for the local legacy installation."""
from __future__ import annotations

import json
from pathlib import Path
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit


class LocalWebService:
    def __init__(self, db, *, token: str | None = None, host: str = "127.0.0.1", port: int = 0, manifest_path: str = "", calendar_import_root: str = "", calendar_audit_path: str = ""):
        self.db = db
        self.host = host
        self.port = int(port)
        self.token = token or secrets.token_urlsafe(32)
        self.manifest_path = str(manifest_path or "")
        self.calendar_import_root = Path(calendar_import_root).resolve() if calendar_import_root else None
        self.calendar_audit_path = str(calendar_audit_path or "")
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

            def do_POST(self):
                service._handle_post(self)

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
        parsed = urlsplit(request.path)
        route = parsed.path
        if route == "/":
            self._respond_html(request, 200, _INDEX_HTML)
            return
        if route == "/health":
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
        producer = routes.get(route)
        if route == "/api/crm/metrics":
            producer = lambda: self._crm_metrics(parsed.query)
        if producer is None:
            self._respond(request, 404, {"error": "not_found"})
            return
        try:
            self._respond(request, 200, {"items": producer()})
        except Exception as exc:
            self._respond(request, 500, {"error": type(exc).__name__, "message": str(exc)})

    def _handle_post(self, request):
        if not self._authorized(request):
            self._respond(request, 401, {"error": "unauthorized"})
            return
        if request.path not in {"/api/calendar/import-preview", "/api/calendar/import"}:
            self._respond(request, 404, {"error": "not_found"})
            return
        try:
            length = int(request.headers.get("Content-Length", "0"))
            payload = json.loads(request.rfile.read(length).decode("utf-8") or "{}")
            package = Path(str(payload.get("package_path") or "")).resolve()
            if self.calendar_import_root is None:
                self._respond(request, 400, {"error": "calendar_import_disabled"})
                return
            destination_name = str(payload.get("destination") or "").strip()
            destination_path = Path(destination_name)
            if not destination_name or destination_path.is_absolute() or ".." in destination_path.parts:
                self._respond(request, 400, {"error": "invalid_destination"})
                return
            destination = (self.calendar_import_root / destination_path).resolve()
            if self.calendar_import_root not in destination.parents:
                self._respond(request, 400, {"error": "invalid_destination"})
                return
            from manual_calendar_export import import_manual_package, preview_manual_package_import
            if request.path.endswith("/import"):
                if payload.get("confirm") is not True:
                    self._respond(request, 400, {"error": "confirmation_required"})
                    return
                result = import_manual_package(
                    package,
                    destination,
                    confirm=True,
                    audit_path=self.calendar_audit_path or None,
                    actor="local_web",
                )
            else:
                result = preview_manual_package_import(package, destination)
            self._respond(request, 200, result)
        except FileExistsError as exc:
            self._respond(request, 409, {"error": "conflict", "message": str(exc)})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})

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

    def _crm_metrics(self, query: str) -> list[dict[str, Any]]:
        account_id = (parse_qs(query).get("account_id") or [""])[0].strip()
        if not account_id:
            return []
        from crm_insights import list_metric_snapshots

        return list_metric_snapshots(self.db.conn, account_id)

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
<title>Metodo IG local</title><style>body{font:15px system-ui;margin:2rem;max-width:70rem}button{margin:.25rem;padding:.45rem}.status{min-height:1.5rem}table{border-collapse:collapse;margin-top:1rem}td,th{border:1px solid #ccc;padding:.35rem;text-align:left}</style>
<h1>Metodo IG</h1><label>Token local <input id=\"token\" type=\"password\" autocomplete=\"off\"></label>
<button onclick=\"loadView('accounts')\">Cuentas</button><button onclick=\"loadView('content')\">Contenido</button>
<button onclick=\"loadView('calendar')\">Calendario</button><button onclick=\"loadView('history')\">Historial</button><button onclick=\"loadView('crm/metrics?account_id='+encodeURIComponent(prompt('Account ID')||''))\">CRM</button>
<div class=\"status\" id=\"status\"></div><div id=\"result\"></div>
<script>
async function loadView(name){const status=document.getElementById('status');status.textContent='';try{const r=await fetch('/api/'+name,{headers:{Authorization:'Bearer '+document.getElementById('token').value}});const data=await r.json();if(!r.ok)throw Error(data.error||'request failed');render(data.items||[])}catch(e){status.textContent=e.message}}
function render(items){const root=document.getElementById('result');root.innerHTML='';if(!items.length){root.textContent='Sin registros';return}const table=document.createElement('table');const keys=[...new Set(items.flatMap(x=>Object.keys(x)))].slice(0,8);table.innerHTML='<thead><tr>'+keys.map(k=>'<th>'+escapeHtml(k)+'</th>').join('')+'</tr></thead><tbody>'+items.map(x=>'<tr>'+keys.map(k=>'<td>'+escapeHtml(x[k])+'</td>').join('')+'</tr>').join('')+'</tbody>';root.appendChild(table)}
function escapeHtml(v){return String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]))}
</script></html>"""


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
