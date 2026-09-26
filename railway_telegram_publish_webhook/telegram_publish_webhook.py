from __future__ import annotations

import json
import base64
import binascii
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PENDING_CALLBACK = "pub"
PUBLISHED_CALLBACK = "published"
CALLBACK_PATH = "/telegram/callback"
ALLOWED_UPDATES = [
    "message",
    "edited_message",
    "channel_post",
    "edited_channel_post",
    "callback_query",
]
WEBHOOK_RECONCILE_SECONDS = 300


def webhook_registration_payload(base_url: str, secret: str = "") -> dict:
    base_url = str(base_url or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("webhook base URL is required")
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    payload = {
        "url": f"{base_url}{CALLBACK_PATH}",
        "allowed_updates": list(ALLOWED_UPDATES),
    }
    if secret:
        payload["secret_token"] = str(secret)
    return payload


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


def reconcile_webhook(token: str, base_url: str, secret: str = "") -> dict:
    desired = webhook_registration_payload(base_url, secret)
    current_response = post_telegram_method(token, "getWebhookInfo", {})
    if not current_response.get("ok"):
        return current_response

    current = current_response.get("result") or {}
    current_updates = set(current.get("allowed_updates") or [])
    if current.get("url") == desired["url"] and "callback_query" in current_updates:
        return current_response

    return post_telegram_method(token, "setWebhook", desired)


def start_webhook_guard(token: str, base_url: str, secret: str = "") -> threading.Thread:
    def guard() -> None:
        while True:
            try:
                result = reconcile_webhook(token, base_url, secret)
                if not result.get("ok"):
                    print(f"webhook reconciliation failed: {result}", file=sys.stderr, flush=True)
            except Exception as exc:
                print(f"webhook reconciliation error: {exc}", file=sys.stderr, flush=True)
            time.sleep(WEBHOOK_RECONCILE_SECONDS)

    thread = threading.Thread(target=guard, name="telegram-webhook-guard", daemon=True)
    thread.start()
    return thread


def published_markup(reply_markup: dict | None) -> dict | None:
    """Remove the publish action while preserving copy/download controls."""
    keyboard = []
    for row in (reply_markup or {}).get("inline_keyboard") or []:
        kept = [
            button for button in row
            if button.get("callback_data") not in {PENDING_CALLBACK, PUBLISHED_CALLBACK}
            and not str(button.get("callback_data") or "").startswith(f"{PENDING_CALLBACK}:")
        ]
        if kept:
            keyboard.append(kept)
    return {"inline_keyboard": keyboard} if keyboard else None


def mark_caption_published(caption: str) -> str:
    caption = str(caption or "").rstrip()
    marker = "✅ YA PUBLICADO"
    if marker in caption:
        return caption
    return f"{caption}\n\n{marker}" if caption else marker


def published_hash_from_callback(data: str) -> str | None:
    match = re.fullmatch(r"pub:([A-Za-z0-9_-]{43})", str(data or ""))
    if not match:
        return None
    try:
        raw = base64.urlsafe_b64decode(match.group(1) + "=")
    except (ValueError, binascii.Error):
        return None
    return raw.hex() if len(raw) == 32 else None


def upsert_published_video(fields: dict) -> bool:
    token = os.environ.get("AIRTABLE_PAT", "")
    base_id = os.environ.get("AIRTABLE_BASE_ID", "")
    table = os.environ.get("AIRTABLE_PUBLISHED_TABLE", "Videos publicados")
    if not token or not base_id:
        print("Airtable publication store unavailable", file=sys.stderr, flush=True)
        return False
    url = "https://api.airtable.com/v0/{}/{}".format(
        urllib.parse.quote(base_id, safe=""), urllib.parse.quote(table, safe="")
    )
    payload = {
        "records": [{"fields": fields}],
        "performUpsert": {"fieldsToMergeOn": ["SHA-256"]},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
        return bool(result.get("records"))
    except Exception as exc:
        print(
            f"Airtable publication upsert failed: {type(exc).__name__}",
            file=sys.stderr,
            flush=True,
        )
        return False


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

    source_hash = published_hash_from_callback(data)
    if data != PENDING_CALLBACK and source_hash is None:
        if callback_id:
            post_telegram_method(token, "answerCallbackQuery", {"callback_query_id": callback_id})
        return {"ok": True, "handled": False}

    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return {"ok": True, "handled": False}

    if source_hash:
        video = message.get("video") or {}
        fields = {
            "SHA-256": source_hash,
            "Archivo original": str(video.get("file_name") or ""),
            "Chat ID": str(chat_id),
            "Message ID": str(message_id),
        }
        marked_by = (callback.get("from") or {}).get("username")
        if marked_by:
            fields["Marcado por"] = str(marked_by)
        if not upsert_published_video(fields):
            if callback_id:
                post_telegram_method(
                    token,
                    "answerCallbackQuery",
                    {
                        "callback_query_id": callback_id,
                        "text": "No se pudo guardar; intenta de nuevo.",
                    },
                )
            return {"ok": True, "handled": True}

    if callback_id:
        post_telegram_method(token, "answerCallbackQuery", {"callback_query_id": callback_id})

    remaining_markup = published_markup(message.get("reply_markup"))
    safe_markup = remaining_markup or {"inline_keyboard": []}
    if message.get("caption") is not None:
        result = post_telegram_method(
            token,
            "editMessageCaption",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "caption": mark_caption_published(message["caption"]),
                "reply_markup": safe_markup,
            },
        )
        method = "editMessageCaption"
    else:
        result = post_telegram_method(
            token,
            "editMessageReplyMarkup",
            {"chat_id": chat_id, "message_id": message_id, "reply_markup": safe_markup},
        )
        method = "editMessageReplyMarkup"
    if not result.get("ok"):
        print(f"{method} failed: {result}", file=sys.stderr, flush=True)
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
        if self.path != CALLBACK_PATH:
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
            result = handle_update(json.loads(payload or "{}"), token)
        except Exception as exc:
            print(f"webhook error: {exc}", file=sys.stderr, flush=True)
            self._send_json(500, {"ok": False, "error": "internal_error"})
            return
        self._send_json(200, result)

    def log_message(self, format, *args):
        print(format % args, flush=True)

    def _send_json(self, status: int, payload: dict) -> None:
        self._send_bytes(status, {"Content-Type": "application/json"}, json.dumps(payload).encode("utf-8"))

    def _send_bytes(self, status: int, headers: dict, body: bytes) -> None:
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    base_url = os.environ.get("TELEGRAM_WEBHOOK_BASE_URL", "") or os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if token and base_url:
        start_webhook_guard(token, base_url, secret)
    else:
        print("webhook guard disabled: missing TELEGRAM_BOT_TOKEN or public domain", file=sys.stderr, flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", port), TelegramCallbackHandler)
    print(f"telegram publish webhook listening on :{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
