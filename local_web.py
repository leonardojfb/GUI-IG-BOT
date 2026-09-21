"""Small authenticated loopback read API for the local legacy installation."""
from __future__ import annotations

import json
import sqlite3
import ipaddress
import os
import tempfile
import time
from pathlib import Path
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from web_sessions import create_pairing_code, csrf_valid, exchange_pairing_code, revoke_session, validate_session


MAX_WEB_UPLOAD_BYTES = 1024 * 1024 * 1024


class LocalWebService:
    def __init__(self, db, *, token: str | None = None, host: str = "127.0.0.1", port: int = 0, manifest_path: str = "", calendar_import_root: str = "", calendar_audit_path: str = "", vault_root: str = "", photo_output_root: str = "", video_output_root: str = "", lan_enabled: bool = False):
        self.db = db
        self.host = host
        self.lan_enabled = bool(lan_enabled)
        if self.lan_enabled:
            self._validate_lan_host(host)
        self.port = int(port)
        self.token = token or secrets.token_urlsafe(32)
        self.manifest_path = str(manifest_path or "")
        self.calendar_import_root = Path(calendar_import_root).resolve() if calendar_import_root else None
        self.calendar_audit_path = str(calendar_audit_path or "")
        self.vault_root = Path(vault_root).resolve() if vault_root else Path(getattr(db, "db_path", ".")).resolve().parent / "content_vault"
        self.photo_output_root = Path(photo_output_root).resolve() if photo_output_root else Path(getattr(db, "db_path", ".")).resolve().parent / "photo_forge_outputs"
        self.video_output_root = Path(video_output_root).resolve() if video_output_root else Path(getattr(db, "db_path", ".")).resolve().parent / "forge_outputs"
        self._server = None
        self._thread = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            return f"http://{self.host}:{self.port}"
        return f"http://{self.host}:{self._server.server_address[1]}"

    def create_lan_pairing_code(self, *, ttl_seconds: int = 300) -> str:
        if not self.lan_enabled:
            raise RuntimeError("LAN no esta habilitado")
        return create_pairing_code(self.db.conn, ttl_seconds=ttl_seconds)

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
            self._respond_html(request, 200, _read_web_asset("index.html", _INDEX_HTML))
            return
        if route in {"/app.js", "/styles.css"}:
            name = route.lstrip("/")
            body = _read_web_asset(name, "")
            if not body:
                self._respond(request, 404, {"error": "not_found"})
                return
            content_type = "application/javascript; charset=utf-8" if name.endswith(".js") else "text/css; charset=utf-8"
            self._respond_text(request, 200, body, content_type)
            return
        if route == "/health":
            self._respond(request, 200, {"status": "ok", "service": "local_web", "read_only": True, "lan_enabled": self.lan_enabled})
            return
        if route == "/api/auth/status":
            self._respond(request, 200, {"lan_enabled": self.lan_enabled, "authenticated": self._session(request) is not None})
            return
        if not self._authorized(request):
            self._respond(request, 401, {"error": "unauthorized"})
            return
        routes = {
            "/api/accounts": self._accounts,
            "/api/content": self._content,
            "/api/calendar": self._calendar,
            "/api/history": self._history,
            "/api/today": self._today,
            "/api/jobs": self._jobs,
            "/api/telegram": self._telegram_queue,
            "/api/identities": self._identities,
            "/api/workflow-presets": self._workflow_presets,
            "/api/publishing-defaults": self._publishing_defaults,
            "/api/vault/assets": self._vault_assets,
            "/api/vault/families": self._vault_families,
            "/api/vault/collections": self._vault_collections,
        }
        if route == "/api/modules":
            from workflow_store import list_modules
            self._respond(request, 200, {"data": list_modules(self.db.conn)})
            return
        if route == "/api/workflows":
            self._respond(request, 200, {"data": self._workflows()})
            return
        if route == "/api/workflow-profiles":
            try:
                from workflow_profiles import list_profiles

                params = parse_qs(parsed.query)
                module_type = (params.get("module_type") or [None])[0]
                subtype = (params.get("subtype") or [None])[0]
                self._respond(request, 200, {"items": list_profiles(self.db.conn, module_type, subtype)})
            except (KeyError, ValueError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        workflow_prefix = "/api/workflows/"
        if route.startswith(workflow_prefix) and route.endswith("/queue"):
            workflow_id = unquote(route[len(workflow_prefix):-len("/queue")].strip("/"))
            try:
                self._respond(request, 200, {"data": self._workflow_queue(workflow_id)})
            except (KeyError, ValueError, sqlite3.Error) as exc:
                self._respond(request, 404, {"error": type(exc).__name__, "message": str(exc)})
            return
        execution_prefix = "/api/executions/"
        if route.startswith(execution_prefix):
            execution_id = unquote(route[len(execution_prefix):].strip("/"))
            try:
                from workflow_queue_runner import get_queue_execution

                self._respond(request, 200, {"data": get_queue_execution(self.db.conn, execution_id)})
            except (KeyError, ValueError, sqlite3.Error) as exc:
                self._respond(request, 404, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route == "/api/vault/assets":
            self._respond(request, 200, {"data": self._vault_assets()})
            return
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
        route = urlsplit(request.path).path
        if route == "/api/auth/pair":
            try:
                payload = self._json_body(request)
                session = exchange_pairing_code(self.db.conn, payload.get("code", ""))
                self._respond(request, 200, session, headers={"Set-Cookie": f"web_session={session['session_token']}; HttpOnly; SameSite=Strict; Path=/"})
            except (ValueError, sqlite3.Error) as exc:
                self._respond(request, 401, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route == "/api/auth/logout":
            session = self._session(request)
            if session:
                revoke_session(self.db.conn, session["token"])
            self._respond(request, 200, {"status": "logged_out"}, headers={"Set-Cookie": "web_session=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/"})
            return
        if not self._authorized(request):
            self._respond(request, 401, {"error": "unauthorized"})
            return
        if self.lan_enabled:
            session = self._session(request)
            if not csrf_valid(session, request.headers.get("X-CSRF-Token", "")):
                self._respond(request, 403, {"error": "csrf_required"})
                return
        if route == "/api/workflow-profiles":
            try:
                payload = self._json_body(request)
                from workflow_manual_steps import build_manual_step
                from workflow_profiles import save_profile

                normalized = build_manual_step(
                    payload.get("module_type"),
                    payload.get("subtype"),
                    payload.get("recipe") or {},
                )
                result = save_profile(
                    self.db.conn,
                    normalized["module_type"],
                    normalized["subtype"],
                    payload.get("name"),
                    normalized["recipe"],
                )
                self._respond(request, 201, {"data": result})
            except (ValueError, KeyError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route == "/api/workflow-profiles/delete":
            try:
                payload = self._json_body(request)
                from workflow_profiles import delete_profile

                self._respond(request, 200, {"data": delete_profile(self.db.conn, payload.get("profile_id"))})
            except (ValueError, KeyError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route == "/api/workflows/manual":
            try:
                result = self._create_manual_workflow(self._json_body(request))
                self._respond(request, 201, {"data": result})
            except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        workflow_prefix = "/api/workflows/"
        if route.startswith(workflow_prefix) and "/queue" in route:
            suffix = route[len(workflow_prefix):].strip("/").split("/queue", 1)
            workflow_id = unquote(suffix[0].strip("/"))
            action = suffix[1].strip("/")
            try:
                payload = self._json_body(request)
                if action == "steps":
                    result = self._add_workflow_queue_step(workflow_id, payload)
                    self._respond(request, 201, {"data": result})
                    return
                if action == "remove":
                    result = self._remove_workflow_queue_step(workflow_id, payload)
                    self._respond(request, 200, {"data": result})
                    return
                if action == "reorder":
                    result = self._reorder_workflow_queue(workflow_id, payload)
                    self._respond(request, 200, {"data": result})
                    return
                if action == "settings":
                    result = self._set_workflow_queue_settings(workflow_id, payload)
                    self._respond(request, 200, {"data": result})
                    return
                if action == "execute":
                    result = self._execute_workflow_queue(workflow_id, payload)
                    self._respond(request, 202, {"data": result})
                    return
                if action == "resume":
                    result = self._resume_workflow_queue(workflow_id, payload)
                    self._respond(request, 202, {"data": result})
                    return
            except KeyError as exc:
                self._respond(request, 404, {"error": type(exc).__name__, "message": str(exc)})
                return
            except (OSError, ValueError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
                return
        if route == "/api/vault/upload":
            try:
                result = self._vault_upload(request)
                self._respond(request, 201, {"data": result})
            except (OSError, ValueError) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        task_prefix = "/api/tasks/"
        if route.startswith(task_prefix) and route.endswith("/published"):
            task_id = route[len(task_prefix):-len("/published")].strip("/")
            try:
                self._respond(request, 200, {"data": self._mark_task_published(task_id)})
            except ValueError as exc:
                self._respond(request, 404, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route == "/api/tasks/photo-forge":
            try:
                payload = self._json_body(request)
                result = self._produce_photo_tasks(payload.get("task_ids") or [])
                self._respond(request, 200, {"data": result})
            except (OSError, ValueError) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route == "/api/tasks/video-forge":
            try:
                payload = self._json_body(request)
                result = self._produce_video_tasks(payload.get("task_ids") or [])
                self._respond(request, 200, {"data": result})
            except (OSError, ValueError) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route == "/api/telegram/deliver":
            try:
                self._json_body(request)
                self._respond(request, 200, {"data": self._deliver_telegram_queue()})
            except (OSError, ValueError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route == "/api/identities":
            try:
                payload = self._json_body(request)
                self._respond(request, 201, {"data": self._upsert_identity(payload)})
            except (ValueError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        identity_prefix = "/api/identities/"
        if route.startswith(identity_prefix) and route.endswith("/settings"):
            try:
                identity_id = unquote(route[len(identity_prefix):-len("/settings")].strip("/"))
                payload = self._json_body(request)
                self._respond(request, 200, {"data": self._set_identity_settings(identity_id, payload.get("settings") or {})})
            except (ValueError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route == "/api/publishing-defaults":
            try:
                payload = self._json_body(request)
                result = self._set_publishing_default(payload)
                self._respond(request, 200, {"data": result})
            except (ValueError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route == "/api/workflows/composed":
            try:
                payload = self._json_body(request)
                from workflow_composer import create_composed_workflow
                result = create_composed_workflow(
                    self.db.conn,
                    name=payload.get("name"),
                    blocks=payload.get("blocks") or [],
                    telegram_topic_mode=payload.get("telegram_topic_mode") or "identity_daily",
                    actor=payload.get("actor") or "local-web",
                )
                self._respond(request, 201, {"data": result})
            except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        workflow_prefix = "/api/workflows/"
        if route.startswith(workflow_prefix) and route.endswith("/clone"):
            try:
                workflow_id = route[len(workflow_prefix):-len("/clone")].strip("/")
                payload = self._json_body(request)
                from workflow_store import clone_workflow
                result = clone_workflow(self.db.conn, workflow_id, payload.get("name"), actor=payload.get("actor") or "local-web")
                self._respond(request, 201, {"data": result})
            except (ValueError, KeyError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
            return
        if route in {"/api/modules", "/api/workflows", "/api/previews", "/api/previews/apply", "/api/vault/import", "/api/vault/families", "/api/vault/collections"}:
            try:
                length = int(request.headers.get("Content-Length", "0"))
                payload = json.loads(request.rfile.read(length).decode("utf-8") or "{}")
                if route == "/api/modules":
                    from workflow_store import create_module
                    result = create_module(self.db.conn, payload.get("kind"), payload.get("name"), payload.get("payload") or {}, actor=payload.get("actor") or "local-web")
                    self._respond(request, 201, {"data": result})
                    return
                if route == "/api/vault/import":
                    result = self._vault_import(payload)
                    self._respond(request, 201, {"data": result})
                    return
                if route == "/api/vault/families":
                    from vault.query import VaultQuery
                    result = VaultQuery(self.db).create_family(payload.get("name", ""), payload.get("notes", ""))
                    self._respond(request, 201, {"data": result})
                    return
                if route == "/api/vault/collections":
                    from vault.query import VaultQuery
                    result = VaultQuery(self.db).create_collection(payload.get("name", ""), payload.get("notes", ""))
                    self._respond(request, 201, {"data": result})
                    return
                if route == "/api/workflows":
                    from workflow_store import create_workflow
                    result = create_workflow(
                        self.db.conn,
                        payload.get("name"),
                        production_ref=payload.get("production_ref"),
                        publication_refs=payload.get("publication_refs") or [],
                        telegram_ref=payload.get("telegram_ref"),
                        actor=payload.get("actor") or "local-web",
                    )
                    self._respond(request, 201, {"data": result})
                    return
                if route == "/api/previews/apply":
                    result = self._apply_preview(payload.get("preview") or {}, actor=payload.get("actor") or "local-web")
                    self._respond(request, 200, {"data": result})
                    return
                result = self._preview_workflow(payload)
                self._respond(request, 200, {"data": result})
                return
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                self._respond(request, 400, {"error": type(exc).__name__, "message": str(exc)})
                return
        if route not in {"/api/calendar/import-preview", "/api/calendar/import"}:
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
            if route.endswith("/import"):
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
        if self.lan_enabled:
            return self._session(request) is not None
        value = request.headers.get("Authorization", "")
        scheme, _, supplied = value.partition(" ")
        return scheme.lower() == "bearer" and secrets.compare_digest(supplied, self.token)

    def _session(self, request):
        raw = request.headers.get("Cookie", "")
        token = next((part.split("=", 1)[1] for part in raw.split(";") if part.strip().startswith("web_session=") and "=" in part), "")
        if not token:
            return None
        current = validate_session(self.db.conn, token)
        if current is None:
            return None
        current["token"] = token
        return current

    @staticmethod
    def _validate_lan_host(host: str) -> None:
        if host in {"0.0.0.0", "::", ""}:
            raise ValueError("LAN requiere una interfaz privada explicita; no se permite wildcard")
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("LAN requiere una direccion IP privada") from exc
        if not address.is_private and not address.is_loopback:
            raise ValueError("LAN requiere una direccion IP privada")

    @staticmethod
    def _json_body(request):
        length = int(request.headers.get("Content-Length", "0"))
        return json.loads(request.rfile.read(length).decode("utf-8") or "{}")

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

    def _today(self) -> list[dict[str, Any]]:
        try:
            rows = self.db.conn.execute(
                "SELECT t.*, COALESCE(a.output_path, t.source_path) AS delivery_path FROM manual_publication_tasks t LEFT JOIN output_assignments a ON a.task_id=t.task_id ORDER BY t.local_date, t.local_time, t.identity_id"
            ).fetchall()
        except sqlite3.OperationalError:
            try:
                rows = self.db.conn.execute("SELECT t.*, t.source_path AS delivery_path FROM manual_publication_tasks t ORDER BY t.local_date, t.local_time, t.identity_id").fetchall()
            except sqlite3.OperationalError:
                return []
        return [self._with_task_workflow_job(dict(row), "logistica.tanda") for row in rows]

    def _jobs(self) -> list[dict[str, Any]]:
        from durable_jobs import list_jobs

        return [self._with_durable_workflow_job(item) for item in list_jobs(self.db.conn, limit=200)]

    def _telegram_queue(self) -> list[dict[str, Any]]:
        from telegram_universal_queue import list_telegram_queue

        return [self._with_task_workflow_job(item, "telegram.send") for item in list_telegram_queue(self.db.conn)]

    def _deliver_telegram_queue(self) -> dict[str, Any]:
        from telegram_universal_queue import deliver_with_legacy_telegram

        return deliver_with_legacy_telegram(self.db.conn)

    def _identities(self) -> list[dict[str, Any]]:
        from identity_settings import create_identity_settings_schema

        create_identity_settings_schema(self.db.conn)
        rows = self.db.conn.execute(
            "SELECT identity_id, platform, display_name, archived FROM social_identities WHERE archived=0 ORDER BY display_name COLLATE NOCASE"
        ).fetchall()
        settings_rows = self.db.conn.execute(
            "SELECT identity_id, setting_key, setting_value FROM identity_publishing_settings ORDER BY setting_key"
        ).fetchall()
        settings_by_identity: dict[str, dict[str, str]] = {}
        for row in settings_rows:
            settings_by_identity.setdefault(str(row["identity_id"]), {})[str(row["setting_key"])] = str(row["setting_value"])
        return [{**dict(row), "settings": settings_by_identity.get(str(row["identity_id"]), {})} for row in rows]

    def _upsert_identity(self, payload: dict[str, Any]) -> dict[str, Any]:
        identity_id = str(payload.get("identity_id") or "").strip()
        platform = str(payload.get("platform") or "").strip().lower()
        display_name = str(payload.get("display_name") or "").strip()
        if not identity_id or platform not in {"instagram", "facebook"} or not display_name:
            raise ValueError("identity_id, platform instagram/facebook y display_name son obligatorios")
        self.db.conn.execute(
            """INSERT INTO social_identities(identity_id, platform, display_name, archived)
               VALUES (?, ?, ?, 0)
               ON CONFLICT(identity_id) DO UPDATE SET platform=excluded.platform,
                   display_name=excluded.display_name, archived=0, updated_at=CURRENT_TIMESTAMP""",
            (identity_id, platform, display_name),
        )
        self.db.conn.commit()
        return {"identity_id": identity_id, "platform": platform, "display_name": display_name, "archived": 0}

    def _set_identity_settings(self, identity_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        from identity_settings import set_identity_setting

        if not identity_id or not isinstance(settings, dict):
            raise ValueError("identidad y settings son obligatorios")
        exists = self.db.conn.execute("SELECT 1 FROM social_identities WHERE identity_id=? AND archived=0", (identity_id,)).fetchone()
        if exists is None:
            raise ValueError("identidad no encontrada")
        for key, value in settings.items():
            if str(key).strip():
                set_identity_setting(self.db.conn, identity_id, str(key), str(value))
        return next(item for item in self._identities() if item["identity_id"] == identity_id)

    def _publishing_defaults(self) -> list[dict[str, Any]]:
        from identity_settings import list_publishing_defaults

        return list_publishing_defaults(self.db.conn)

    def _set_publishing_default(self, payload: dict[str, Any]) -> dict[str, Any]:
        from identity_settings import set_publishing_default

        scope_kind = str(payload.get("scope_kind") or "")
        scope_id = str(payload.get("scope_id") or "")
        key = str(payload.get("setting_key") or "")
        value = str(payload.get("setting_value") or "")
        set_publishing_default(self.db.conn, scope_kind, scope_id, key, value)
        return {"scope_kind": scope_kind, "scope_id": scope_id, "setting_key": key, "setting_value": value}

    def _crm_metrics(self, query: str) -> list[dict[str, Any]]:
        account_id = (parse_qs(query).get("account_id") or [""])[0].strip()
        if not account_id:
            return []
        from crm_insights import list_metric_snapshots

        return list_metric_snapshots(self.db.conn, account_id)

    def _workflows(self) -> list[dict[str, Any]]:
        rows = self.db.conn.execute("SELECT workflow_id, name, active, created_at FROM workflows ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    def _create_manual_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        from workflow_manual_steps import build_manual_step
        from workflow_store import create_module, create_workflow
        from workflow_queue import append_queue_step, get_queue

        name = str(payload.get("name") or "").strip()
        raw_steps = payload.get("steps") or []
        if not name:
            raise ValueError("el workflow requiere nombre")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError("agrega al menos un paso")

        normalized = []
        for index, raw in enumerate(raw_steps, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"el paso {index} debe ser un objeto")
            step = build_manual_step(raw.get("module_type"), raw.get("subtype"), raw.get("fields") or {})
            binding = dict(raw.get("input_binding") or {})
            if binding and binding.get("kind") not in {"previous_output", "step_output", "asset"}:
                raise ValueError(f"binding invalido en el paso {index}")
            if binding.get("kind") in {"previous_output", "step_output"}:
                previous = normalized[-1] if normalized else None
                if previous is None:
                    raise ValueError(f"el paso {index} no tiene un output anterior")
                if previous["output_contract"] != step["input_contract"] and step["input_contract"] != "Any":
                    raise ValueError(f"input incompatible en el paso {index}")
                binding["kind"] = "previous_output"
            normalized.append({**step, "input_binding": binding})

        telegram_steps = [step for step in normalized if step["module_type"] == "telegram"]
        if not telegram_steps:
            raise ValueError("el workflow requiere un paso Telegram")

        production_ref = None
        publication_refs = []
        telegram_ref = None
        for index, step in enumerate(normalized, start=1):
            label = f"{name} · Paso {index} · {step['module_type']} {step['subtype']}"
            payload_value = {"module_type": step["module_type"], "subtype": step["subtype"], "recipe": step["recipe"]}
            if step["module_type"] == "forge":
                module = create_module(self.db.conn, "production_recipe", label, payload_value, actor=payload.get("actor") or "local-web")
                production_ref = production_ref or [module["module_id"], module["version"]]
            elif step["module_type"] == "logistica":
                module = create_module(self.db.conn, "publication_template", label, payload_value, actor=payload.get("actor") or "local-web")
                publication_refs.append([module["module_id"], module["version"]])
            else:
                module = create_module(self.db.conn, "telegram_template", label, payload_value, actor=payload.get("actor") or "local-web")
                telegram_ref = [module["module_id"], module["version"]]

        workflow = create_workflow(
            self.db.conn,
            name,
            production_ref=production_ref,
            publication_refs=publication_refs,
            telegram_ref=telegram_ref,
            actor=payload.get("actor") or "local-web",
        )
        previous_queue_step = None
        for step in normalized:
            binding = dict(step["input_binding"])
            if binding.get("kind") == "previous_output":
                binding["step_id"] = previous_queue_step["step_id"]
            previous_queue_step = append_queue_step(
                self.db.conn,
                workflow["workflow_id"],
                job_type={"forge": "forge.tanda", "logistica": "logistica.tanda", "telegram": "telegram.send"}[step["module_type"]],
                recipe=step["recipe"],
                input_contract=step["input_contract"],
                output_contract=step["output_contract"],
                input_binding=binding,
            )
        return {**workflow, "queue": get_queue(self.db.conn, workflow["workflow_id"])}

    def _workflow_queue(self, workflow_id: str) -> dict[str, Any]:
        from workflow_queue import get_queue

        exists = self.db.conn.execute(
            "SELECT 1 FROM workflows WHERE workflow_id=?",
            (str(workflow_id),),
        ).fetchone()
        if exists is None:
            raise KeyError(f"workflow desconocido: {workflow_id}")
        return get_queue(self.db.conn, workflow_id)

    def _add_workflow_queue_step(self, workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from workflow_queue import append_queue_step

        self._workflow_queue(workflow_id)
        job = payload.get("workflow_job") or payload
        result = append_queue_step(
            self.db.conn,
            workflow_id,
            job_type=job.get("job_type"),
            recipe=job.get("recipe") or {},
            input_contract=job.get("input_contract") or "Any",
            output_contract=job.get("output_contract") or "Any",
            input_binding=job.get("input_binding"),
            source_job_id=job.get("source_job_id"),
        )
        return self._workflow_queue(workflow_id)

    def _remove_workflow_queue_step(self, workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from workflow_queue import remove_queue_step

        self._workflow_queue(workflow_id)
        remove_queue_step(self.db.conn, workflow_id, payload.get("step_id"))
        return self._workflow_queue(workflow_id)

    def _reorder_workflow_queue(self, workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from workflow_queue import reorder_queue_steps

        self._workflow_queue(workflow_id)
        reorder_queue_steps(self.db.conn, workflow_id, payload.get("step_ids") or [])
        return self._workflow_queue(workflow_id)

    def _set_workflow_queue_settings(self, workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from workflow_queue import set_telegram_mode

        self._workflow_queue(workflow_id)
        return set_telegram_mode(self.db.conn, workflow_id, payload.get("telegram_mode"))

    def _execute_workflow_queue(self, workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from workflow_queue_runner import create_queue_execution, run_queue_execution

        self._workflow_queue(workflow_id)
        execution = create_queue_execution(self.db.conn, workflow_id, actor=payload.get("actor") or "local-web")
        return run_queue_execution(
            self.db.conn,
            execution["execution_id"],
            worker_id=payload.get("worker_id") or "local-web",
        )

    def _resume_workflow_queue(self, workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from workflow_queue_runner import resume_queue_execution

        execution_id = str(payload.get("execution_id") or "").strip()
        if not execution_id:
            raise ValueError("execution_id es obligatorio")
        execution = self._get_execution_for_workflow(execution_id, workflow_id)
        return resume_queue_execution(
            self.db.conn,
            execution["execution_id"],
            worker_id=payload.get("worker_id") or "local-web",
        )

    def _get_execution_for_workflow(self, execution_id: str, workflow_id: str) -> dict[str, Any]:
        from workflow_queue_runner import get_queue_execution

        execution = get_queue_execution(self.db.conn, execution_id)
        if execution["workflow_id"] != str(workflow_id):
            raise KeyError(f"execution no pertenece al workflow: {execution_id}")
        return execution

    @staticmethod
    def _with_durable_workflow_job(item: dict[str, Any]) -> dict[str, Any]:
        return {
            **item,
            "workflow_job": {
                "job_type": item.get("job_type"),
                "recipe": {"durable_job_id": item.get("job_id"), "recipe": item.get("recipe"), "steps": item.get("steps")},
                "input_contract": "Any",
                "output_contract": "Any",
                "source_job_id": item.get("job_id"),
            },
        }

    @staticmethod
    def _with_task_workflow_job(item: dict[str, Any], job_type: str) -> dict[str, Any]:
        task_id = item.get("task_id")
        input_contract = "ManifestOutput" if job_type == "telegram.send" else "TandaOutput"
        output_contract = "TelegramOutput" if job_type == "telegram.send" else "ManifestOutput"
        return {
            **item,
            "workflow_job": {
                "job_type": job_type,
                "recipe": {"task_ids": [task_id]} if task_id else {},
                "input_contract": input_contract,
                "output_contract": output_contract,
                "source_job_id": task_id,
            },
        }

    def _workflow_presets(self) -> list[dict[str, Any]]:
        from workflow_presets import list_workflow_presets

        return list_workflow_presets()

    def _vault_assets(self) -> dict[str, Any]:
        from vault.query import VaultQuery

        return VaultQuery(self.db).search_assets(limit=200)

    def _vault_families(self) -> list[dict[str, Any]]:
        rows = self.db.conn.execute("SELECT * FROM content_families ORDER BY name COLLATE NOCASE").fetchall()
        return [dict(row) for row in rows]

    def _vault_collections(self) -> list[dict[str, Any]]:
        rows = self.db.conn.execute("SELECT * FROM vault_collections ORDER BY name COLLATE NOCASE").fetchall()
        return [dict(row) for row in rows]

    def _vault_import(self, payload: dict[str, Any]) -> dict[str, Any]:
        from vault.storage import VaultStorage

        source = Path(str(payload.get("path") or "")).resolve()
        storage = VaultStorage(self.db, self.vault_root)
        if payload.get("managed") is True:
            return storage.import_managed(source)
        return storage.register_external(source)

    def _vault_upload(self, request) -> dict[str, Any]:
        from vault.storage import VaultStorage

        try:
            size = int(request.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("tamano de upload invalido") from exc
        if size <= 0 or size > MAX_WEB_UPLOAD_BYTES:
            raise ValueError("tamano de upload no permitido")
        filename = Path(unquote(request.headers.get("X-Filename", ""))).name
        if not filename or filename in {".", ".."}:
            raise ValueError("nombre de archivo invalido")
        upload_dir = self.vault_root / ".uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix
        fd, temporary_path = tempfile.mkstemp(prefix="upload-", suffix=suffix, dir=str(upload_dir))
        try:
            with os.fdopen(fd, "wb") as handle:
                remaining = size
                while remaining:
                    chunk = request.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("upload incompleto")
                    handle.write(chunk)
                    remaining -= len(chunk)
            return VaultStorage(self.db, self.vault_root).import_managed(temporary_path)
        finally:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass

    def _apply_preview(self, preview: dict[str, Any], *, actor: str) -> dict[str, Any]:
        from publication_workflow import apply_workflow_preview

        return apply_workflow_preview(self.db.conn, preview, actor=str(actor))

    def _mark_task_published(self, task_id: str) -> dict[str, Any]:
        task_id = str(task_id or "").strip()
        if not task_id:
            raise ValueError("task_id invalido")
        cursor = self.db.conn.execute(
            "UPDATE manual_publication_tasks SET state = 'published_manual' WHERE task_id = ?",
            (task_id,),
        )
        self.db.conn.commit()
        if cursor.rowcount != 1:
            raise ValueError("tarea no encontrada")
        row = self.db.conn.execute("SELECT * FROM manual_publication_tasks WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row)

    def _produce_photo_tasks(self, task_ids: list[str]) -> dict[str, Any]:
        from destination_photo_workflow import produce_photo_tasks

        return produce_photo_tasks(self.db.conn, task_ids, output_root=self.photo_output_root)

    def _produce_video_tasks(self, task_ids: list[str]) -> dict[str, Any]:
        from destination_video_workflow import produce_video_tasks

        return produce_video_tasks(self.db.conn, task_ids, output_root=self.video_output_root)

    def _preview_workflow(self, payload: dict) -> dict:
        from publication_workflow import preview_workflow_tasks

        return preview_workflow_tasks(
            self.db.conn,
            str(payload.get("workflow_id") or ""),
            identities=payload.get("identities") or [],
            candidates=payload.get("candidates") or [],
            start_date=str(payload.get("start_date") or ""),
            timezone=str(payload.get("timezone") or "UTC"),
            days=int(payload.get("days", 1)),
            mode=str(payload.get("mode") or "strict"),
        )

    @staticmethod
    def _respond(request, status: int, payload: dict[str, Any], headers: dict[str, str] | None = None):
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        request.send_response(status)
        request.send_header("Content-Type", "application/json; charset=utf-8")
        request.send_header("Content-Length", str(len(data)))
        request.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            request.send_header(name, value)
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

    @staticmethod
    def _respond_text(request, status: int, body: str, content_type: str):
        data = body.encode("utf-8")
        request.send_response(status)
        request.send_header("Content-Type", content_type)
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


def _read_web_asset(name: str, fallback: str) -> str:
    path = Path(__file__).resolve().parent / "web" / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return fallback
