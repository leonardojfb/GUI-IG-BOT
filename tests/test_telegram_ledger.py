import sqlite3

from telegram_ledger import deliver_media, ensure_telegram_ledger_schema, media_method


def test_media_method_uses_native_telegram_formats():
    assert media_method("photo.jpg") == "sendPhoto"
    assert media_method("clip.mp4") == "sendVideo"
    assert media_method("archive.zip") == "sendDocument"


def test_deliver_media_is_idempotent_and_records_message_identity():
    connection = sqlite3.connect(":memory:")
    ensure_telegram_ledger_schema(connection)
    calls = []

    def sender(method, payload):
        calls.append((method, payload))
        return {"ok": True, "result": {"message_id": 42, "chat": {"id": "-1"}}}

    first = deliver_media(connection, sender, asset_ref="asset-1", path="clip.mp4", chat_id="-1", topic_id=7, bot_id="bot-a", caption="hola", idempotency_key="job-1")
    second = deliver_media(connection, sender, asset_ref="asset-1", path="clip.mp4", chat_id="-1", topic_id=7, bot_id="bot-a", caption="hola", idempotency_key="job-1")

    assert first["status"] == "sent"
    assert second["status"] == "already_sent"
    assert len(calls) == 1
    assert calls[0][0] == "sendVideo"
    assert calls[0][1]["message_thread_id"] == 7
    assert connection.execute("SELECT COUNT(*) FROM telegram_delivery_ledger").fetchone()[0] == 1


def test_failed_delivery_does_not_create_success_ledger_row():
    connection = sqlite3.connect(":memory:")
    ensure_telegram_ledger_schema(connection)

    result = deliver_media(connection, lambda *_: {"ok": False, "description": "denied"}, asset_ref="asset-2", path="photo.png", chat_id="-1", topic_id=None, bot_id="bot-a", idempotency_key="job-2")

    assert result["status"] == "failed"
    assert connection.execute("SELECT COUNT(*) FROM telegram_delivery_ledger").fetchone()[0] == 0
