import json
from io import BytesIO

import telegram_publish_webhook as webhook


def test_publish_callback_marks_button_on_same_message(monkeypatch):
    calls = []

    def fake_post(token, method, payload):
        calls.append((token, method, payload))
        return {"ok": True}

    monkeypatch.setattr(webhook, "post_telegram_method", fake_post)

    update = {
        "callback_query": {
            "id": "cb-1",
            "data": "pub",
            "message": {
                "message_id": 77,
                "chat": {"id": -100123},
                "caption": "Do you like them? 🍒",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Publicado", "callback_data": "pub"},
                            {"text": "📋 Copiar caption", "copy_text": {"text": "Do you like them? 🍒"}},
                        ],
                        [{"text": "⬇️ Descargar documento", "url": "https://example.test/download"}],
                    ]
                },
            },
        }
    }

    result = webhook.handle_update(update, "token-123")

    assert result == {"ok": True, "handled": True}
    assert calls == [
        ("token-123", "answerCallbackQuery", {"callback_query_id": "cb-1"}),
        (
            "token-123",
            "editMessageCaption",
            {
                "chat_id": -100123,
                "message_id": 77,
                "caption": "Do you like them? 🍒\n\n✅ Ya publicado",
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "📋 Copiar caption", "copy_text": {"text": "Do you like them? 🍒"}}],
                        [{"text": "⬇️ Descargar documento", "url": "https://example.test/download"}],
                    ]
                },
            },
        ),
    ]


def test_already_published_callback_only_answers(monkeypatch):
    calls = []
    monkeypatch.setattr(
        webhook,
        "post_telegram_method",
        lambda token, method, payload: calls.append((method, payload)) or {"ok": True},
    )

    result = webhook.handle_update(
        {"callback_query": {"id": "cb-2", "data": "published"}},
        "token-123",
    )

    assert result == {"ok": True, "handled": True}
    assert calls == [
        ("answerCallbackQuery", {"callback_query_id": "cb-2", "text": "Ya estaba marcado."})
    ]


def test_secret_header_rejects_wrong_token():
    assert webhook.is_authorized({"X-Telegram-Bot-Api-Secret-Token": "bad"}, "good") is False
    assert webhook.is_authorized({"X-Telegram-Bot-Api-Secret-Token": "good"}, "good") is True
    assert webhook.is_authorized({}, "") is True


def test_get_accounts_normalizes_telegram_chat_id_labels(monkeypatch):
    import organizadortg

    class Cursor:
        def execute(self, *_args):
            return None

        def fetchone(self):
            return {"tg_group_id": "ID: -1003749971714", "timezone": "America/New_York"}

    class Conn:
        def cursor(self):
            return Cursor()

    class FakeDb:
        conn = Conn()

        def get_all_accounts(self):
            return [{"username": "aaa", "account_type": "2222", "assigned_va": "VA1"}]

        def get_vas(self):
            return []

    monkeypatch.setattr(organizadortg, "db", FakeDb())

    [account] = organizadortg.get_accounts_with_va_info()

    assert account["tg_group_id"] == "-1003749971714"


def test_send_document_sends_native_document_with_publish_button(monkeypatch, tmp_path):
    import organizadortg

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake-video")
    posted = []
    api_calls = []

    class Response:
        status_code = 200
        text = "ok"

        def json(self):
            return {
                "ok": True,
                "result": {
                    "message_id": 456,
                    "document": {"file_id": "file-id-123"},
                },
            }

    def fake_post(url, data, files):
        filename, handle, content_type = files["document"]
        posted.append((url, dict(data), filename, handle.read(), content_type))
        return Response()

    monkeypatch.setattr(organizadortg.requests, "post", fake_post)
    monkeypatch.setattr(
        organizadortg,
        "call_tg",
        lambda method, data, silent=False: api_calls.append((method, data, silent)) or {"ok": True},
    )

    ok, topic_id = organizadortg._send_video_to_topic(
        "-1001",
        123,
        "caption",
        str(video),
        {},
        "eve",
        "MAIN",
    )

    assert ok is True
    assert topic_id == 123
    url, data, filename, contents, content_type = posted[0]
    assert url.endswith("/sendDocument")
    assert filename == "clip.mp4"
    assert contents == b"fake-video"
    assert content_type == "application/octet-stream"
    assert data["disable_content_type_detection"] == "true"
    assert json.loads(data["reply_markup"]) == {
        "inline_keyboard": [
            [
                {"text": "✅ Publicado", "callback_data": "pub"},
                {"text": "📋 Copiar caption", "copy_text": {"text": "caption"}},
            ]
        ]
    }
    assert api_calls == []


def test_send_document_omits_copy_caption_button_without_caption(monkeypatch, tmp_path):
    import organizadortg

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake-video")
    posted = []

    class Response:
        status_code = 200
        text = "ok"

    def fake_post(url, data, files):
        posted.append(dict(data))
        return Response()

    monkeypatch.setattr(organizadortg.requests, "post", fake_post)

    ok, _topic_id = organizadortg._send_video_to_topic(
        "-1001",
        123,
        "",
        str(video),
        {},
        "eve",
        "MAIN",
    )

    assert ok is True
    assert json.loads(posted[0]["reply_markup"]) == {
        "inline_keyboard": [[{"text": "✅ Publicado", "callback_data": "pub"}]]
    }


def test_download_file_fetches_telegram_file_without_exposing_token(monkeypatch):
    opened = []

    class Response:
        headers = {"Content-Type": "video/mp4"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"file-bytes"

    def fake_post(token, method, payload):
        assert token == "token-123"
        assert method == "getFile"
        assert payload == {"file_id": "file-id-123"}
        return {"ok": True, "result": {"file_path": "documents/file.mp4"}}

    def fake_urlopen(request, timeout=30):
        opened.append((request.full_url, timeout))
        return Response()

    monkeypatch.setattr(webhook, "post_telegram_method", fake_post)
    monkeypatch.setattr(webhook.urllib.request, "urlopen", fake_urlopen)

    status, headers, body = webhook.download_file("token-123", "file-id-123")

    assert status == 200
    assert headers["Content-Type"] == "video/mp4"
    assert body == b"file-bytes"
    assert opened == [("https://api.telegram.org/file/bottoken-123/documents/file.mp4", 30)]
