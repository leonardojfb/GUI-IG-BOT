"""Idempotent native-format Telegram delivery ledger."""
from __future__ import annotations

import os
from pathlib import Path


def ensure_telegram_ledger_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS telegram_delivery_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_ref TEXT NOT NULL,
        bot_id TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        topic_id TEXT,
        media_path TEXT NOT NULL,
        method TEXT NOT NULL,
        caption TEXT NOT NULL DEFAULT '',
        message_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(asset_ref, bot_id, chat_id, topic_id, idempotency_key)
    )""")
    connection.commit()


def media_method(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return "sendPhoto"
    if suffix in {".mp4", ".mov", ".mkv", ".avi"}:
        return "sendVideo"
    return "sendDocument"


def deliver_media(connection, sender, *, asset_ref, path, chat_id, topic_id, bot_id, caption="", idempotency_key):
    ensure_telegram_ledger_schema(connection)
    key = _required(idempotency_key, "idempotency_key")
    identity = (str(asset_ref), str(bot_id), str(chat_id), _optional(topic_id), key)
    existing = connection.execute("SELECT message_id, method FROM telegram_delivery_ledger WHERE asset_ref=? AND bot_id=? AND chat_id=? AND topic_id IS ? AND idempotency_key=?", identity).fetchone()
    if existing:
        return {"status": "already_sent", "message_id": existing[0], "method": existing[1]}
    method = media_method(path)
    payload = {"chat_id": str(chat_id), "caption": str(caption or ""), "media_path": os.path.abspath(path)}
    if topic_id is not None:
        payload["message_thread_id"] = int(topic_id)
    response = sender(method, payload) or {}
    if not response.get("ok"):
        return {"status": "failed", "method": method, "error": response.get("description", "telegram rechazó el envío")}
    result = response.get("result") or {}
    message_id = result.get("message_id")
    if message_id is None:
        return {"status": "failed", "method": method, "error": "Telegram no devolvió message_id"}
    connection.execute("INSERT INTO telegram_delivery_ledger (asset_ref, bot_id, chat_id, topic_id, media_path, method, caption, message_id, idempotency_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (*identity[:4], os.path.abspath(path), method, str(caption or ""), str(message_id), key))
    connection.commit()
    return {"status": "sent", "method": method, "message_id": str(message_id)}


def _optional(value):
    return None if value is None else str(value)


def _required(value, field):
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} no puede estar vacio")
    return normalized
