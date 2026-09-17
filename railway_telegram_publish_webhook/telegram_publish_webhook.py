from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PENDING_CALLBACK = "pub"
PUBLISHED_CALLBACK = "published"


def is_authorized(headers, expected_secret: str) -> bool:
    if not expected_secret:
        return True
    for key, value in headers.items():
        if key.lower() == "x-telegram-bot-api-secret-token":
            return str(value) == expected_secret
    return False


def post_telegram_method(token: str, method: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"ok": False, "description": raw or str(exc)}


def _published_markup() -> dict:
    return {
        "inline_keyboard": [[{"text": "✅ Ya publicado", "disabled": {}}]]
    }


def _remove_publish_buttons(reply_markup: dict | None, extra_callbacks=()) -> dict | None:
    callbacks = {PENDING_CALLBACK, PUBLISHED_CALLBACK, *extra_callbacks}
    keyboard = []
    for row in (reply_markup or {}).get("inline_keyboard") or []:
        kept = [
            button for button in row
            if button.get("callback_data") not in callbacks
        ]
        if kept:
            keyboard.append(kept)
    if not keyboard:
        return None
    return {"inline_keyboard": keyboard}


def _mark_caption_published(caption: str) -> str:
    caption = str(caption or "").rstrip()
    marker = "✅ Ya publicado"
    if marker in caption:
        return caption
    if caption:
        return f"{caption}\n\n{marker}"
    return marker


def handle_update(update: dict, token: str, *, confirmation_connection=None, authorize_fn=None) -> dict:
    callback = update.get("callback_query")
    if not callback:
        return {"ok": True, "handled": False}

    callback_id = callback.get("id")
    data = callback.get("data")
    versioned = None
    if str(data or "").startswith("v1|"):
        from confirmation_ledger import ingest_callback
        try:
            versioned = ingest_callback(
                confirmation_connection,
                data,
                external_id=str(callback_id or ""),
                user_id=str((callback.get("from") or {}).get("id") or "telegram"),
                payload={"chat_id": (callback.get("message") or {}).get("chat", {}).get("id")},
                authorize_fn=authorize_fn,
            ) if confirmation_connection is not None else None
        except (ValueError, TypeError):
            versioned = {"status": "invalid"}
        if versioned and versioned.get("status") == "unauthorized":
            if callback_id:
                post_telegram_method(token, "answerCallbackQuery", {"callback_query_id": callback_id, "text": "No autorizado."})
            return {"ok": True, "handled": True, "unauthorized": True}
        if versioned and versioned.get("status") == "duplicate":
            if callback_id:
                post_telegram_method(token, "answerCallbackQuery", {"callback_query_id": callback_id, "text": "Ya estaba marcado."})
            return {"ok": True, "handled": True, "duplicate": True}
        if not versioned or versioned.get("status") == "invalid":
            if callback_id:
                post_telegram_method(token, "answerCallbackQuery", {"callback_query_id": callback_id})
            return {"ok": True, "handled": False}
        data = PENDING_CALLBACK

    if data == PUBLISHED_CALLBACK:
        if callback_id:
            post_telegram_method(
                token,
                "answerCallbackQuery",
                {"callback_query_id": callback_id, "text": "Ya estaba marcado."},
            )
        return {"ok": True, "handled": True}

    if data != PENDING_CALLBACK:
        if callback_id:
            post_telegram_method(token, "answerCallbackQuery", {"callback_query_id": callback_id})
        return {"ok": True, "handled": False}

    if callback_id:
        post_telegram_method(token, "answerCallbackQuery", {"callback_query_id": callback_id})

    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return {"ok": True, "handled": False}

    remaining_markup = _remove_publish_buttons(message.get("reply_markup"), {data} if versioned else ())
    caption = message.get("caption")
    if caption is not None:
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": _mark_caption_published(caption),
        }
        if remaining_markup:
            payload["reply_markup"] = remaining_markup
        post_telegram_method(token, "editMessageCaption", payload)
    else:
        payload = {"chat_id": chat_id, "message_id": message_id}
        if remaining_markup:
            payload["reply_markup"] = remaining_markup
        post_telegram_method(token, "editMessageReplyMarkup", payload)
    return {"ok": True, "handled": True}


def download_file(token: str, file_id: str) -> tuple[int, dict, bytes]:
    file_info = post_telegram_method(token, "getFile", {"file_id": file_id})
    if not file_info.get("ok"):
        return 502, {"Content-Type": "application/json"}, json.dumps(file_info).encode("utf-8")
    file_path = (file_info.get("result") or {}).get("file_path")
    if not file_path:
        return 404, {"Content-Type": "application/json"}, b'{"ok": false, "error": "file_not_found"}'

    url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as response:
        body = response.read()
        headers = {
            "Content-Type": response.headers.get("Content-Type", "application/octet-stream"),
            "Content-Disposition": f'attachment; filename="{os.path.basename(file_path)}"',
        }
        return 200, headers, body


class TelegramCallbackHandler(BaseHTTPRequestHandler):
    server_version = "TelegramPublishWebhook/1.0"

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._send_json(200, {"ok": True})
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/telegram/download":
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            file_id = (urllib.parse.parse_qs(parsed.query).get("file_id") or [""])[0]
            if not token or not file_id:
                self._send_json(400, {"ok": False, "error": "missing_file"})
                return
            try:
                status, headers, body = download_file(token, file_id)
            except Exception as exc:
                print(f"download error: {exc}", file=sys.stderr, flush=True)
                self._send_json(500, {"ok": False, "error": "download_failed"})
                return
            self._send_bytes(status, headers, body)
            return
        self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path != "/telegram/callback":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        secret = os.environ.get("WEBHOOK_SECRET", "")
        if not is_authorized(self.headers, secret):
            self._send_json(403, {"ok": False, "error": "forbidden"})
            return
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            self._send_json(500, {"ok": False, "error": "missing_token"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length).decode("utf-8")
            update = json.loads(payload or "{}")
            confirmation_path = os.environ.get("CONFIRMATION_DB_PATH", "").strip()
            confirmation_connection = None
            if confirmation_path:
                confirmation_connection = sqlite3.connect(confirmation_path)
            try:
                result = handle_update(update, token, confirmation_connection=confirmation_connection)
            finally:
                if confirmation_connection is not None:
                    confirmation_connection.close()
        except Exception as exc:
            print(f"webhook error: {exc}", file=sys.stderr, flush=True)
            self._send_json(500, {"ok": False, "error": "internal_error"})
            return
        self._send_json(200, result)

    def log_message(self, format, *args):
        print(format % args, flush=True)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send_bytes(status, {"Content-Type": "application/json"}, body)

    def _send_bytes(self, status: int, headers: dict, body: bytes) -> None:
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), TelegramCallbackHandler)
    print(f"telegram publish webhook listening on :{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
