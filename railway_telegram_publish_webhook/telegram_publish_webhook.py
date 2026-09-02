from __future__ import annotations

import json
import os
import sys
import urllib.error
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


def handle_update(update: dict, token: str) -> dict:
    callback = update.get("callback_query")
    if not callback:
        return {"ok": True, "handled": False}

    callback_id = callback.get("id")
    data = callback.get("data")
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

    post_telegram_method(
        token,
        "editMessageReplyMarkup",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": _published_markup(),
        },
    )
    return {"ok": True, "handled": True}


class TelegramCallbackHandler(BaseHTTPRequestHandler):
    server_version = "TelegramPublishWebhook/1.0"

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._send_json(200, {"ok": True})
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
            result = handle_update(update, token)
        except Exception as exc:
            print(f"webhook error: {exc}", file=sys.stderr, flush=True)
            self._send_json(500, {"ok": False, "error": "internal_error"})
            return
        self._send_json(200, result)

    def log_message(self, format, *args):
        print(format % args, flush=True)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
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
