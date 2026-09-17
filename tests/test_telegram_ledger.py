import sqlite3

from telegram_ledger import build_telegram_bot_api_sender, deliver_media, ensure_telegram_ledger_schema, find_delivery, media_method, record_confirmed_delivery


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


def test_bot_api_sender_uses_native_file_field_and_thread(tmp_path):
    media = tmp_path / "photo.jpg"
    media.write_bytes(b"image")
    calls = []

    class Response:
        def json(self):
            return {"ok": True}

    sender = build_telegram_bot_api_sender("token-from-env", request_fn=lambda *args, **kwargs: calls.append((args, kwargs)) or Response())
    result = sender("sendPhoto", {"chat_id": "-1", "caption": "hola", "message_thread_id": 9, "media_path": str(media)})

    assert result["ok"] is True
    assert calls[0][0][0].endswith("/sendPhoto")
    assert "photo" in calls[0][1]["files"]
    assert calls[0][1]["data"]["message_thread_id"] == 9


def test_confirmed_delivery_record_is_idempotent_for_legacy_worker(tmp_path):
    connection = sqlite3.connect(":memory:")
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"video")
    first = record_confirmed_delivery(connection, asset_ref="asset", path=media, chat_id="-1", topic_id=4, bot_id="legacy-bot", idempotency_key="day1", message_id=12, method="sendVideo")
    second = record_confirmed_delivery(connection, asset_ref="asset", path=media, chat_id="-1", topic_id=4, bot_id="legacy-bot", idempotency_key="day1", message_id=13, method="sendVideo")
    assert first["status"] == "recorded"
    assert second["status"] == "already_sent"
    assert find_delivery(connection, asset_ref="asset", chat_id="-1", topic_id=4, bot_id="legacy-bot", idempotency_key="day1")["message_id"] == "12"
