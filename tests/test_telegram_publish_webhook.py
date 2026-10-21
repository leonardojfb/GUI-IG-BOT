import json

import organizadortg
from railway_telegram_publish_webhook import telegram_publish_webhook as webhook


def test_new_published_callback_round_trips_hash_and_origin_token():
    source_hash = "a" * 64
    origin_token = "b" * 16

    callback = webhook.published_callback_data(source_hash, origin_token)

    assert len(callback) <= 64
    assert webhook.published_callback_values(callback) == (source_hash, origin_token)


def test_account_callback_keeps_full_hash_origin_and_account():
    source_hash = "a" * 64
    origin_token = organizadortg.origin_token_from_identity("forge-origin")
    callback = organizadortg._published_callback_data(source_hash, origin_token, "102")

    assert len(callback) == 64
    assert webhook.published_callback_details(callback) == (source_hash, origin_token, "102")
    assert webhook.published_callback_values(callback) == (source_hash, origin_token)
    assert webhook.published_markup({"inline_keyboard": [[
        {"text": "✅ Publicado", "callback_data": callback},
        {"text": "📋 Copiar caption", "copy_text": {"text": "caption"}},
    ]]}) == {"inline_keyboard": [[
        {"text": "📋 Copiar caption", "copy_text": {"text": "caption"}},
    ]]}


def test_account_callback_saves_publication_even_for_new_topic(monkeypatch):
    source_hash = "a" * 64
    origin_token = organizadortg.origin_token_from_identity("forge-origin")
    callback = organizadortg._published_callback_data(source_hash, origin_token, "102")
    stored = []
    calls = []
    monkeypatch.setattr(webhook, "upsert_published_video", lambda fields: stored.append(fields) or True)
    monkeypatch.setattr(
        webhook, "post_telegram_method",
        lambda _token, method, payload: calls.append((method, payload)) or {"ok": True},
    )
    result = webhook.handle_update({"callback_query": {
        "id": "cb-new-topic",
        "data": callback,
        "message": {
            "chat": {"id": -1004436137514},
            "message_thread_id": 999999,
            "message_id": 456,
            "video": {"file_name": "forge-output.mp4"},
            "caption": "caption",
            "reply_markup": {"inline_keyboard": [[
                {"text": "✅ Publicado", "callback_data": callback},
            ]]},
        },
    }}, "token")

    assert result == {"ok": True, "handled": True}
    assert stored[0]["Publication key"] == "102:" + source_hash
    assert stored[0]["Origin token"] == origin_token
    assert calls[-1][0] == "editMessageCaption"
    assert calls[-1][1]["caption"] == "caption\n\n✅ YA PUBLICADO"


def test_clicked_topic_8585_resolves_existing_button(monkeypatch):
    monkeypatch.setattr(webhook, "TOPIC_ACCOUNT_MAP", {"-1004436137514:8585": "102"})
    assert webhook.account_id_from_topic({
        "chat": {"id": -1004436137514}, "message_thread_id": 8585,
    }) == "102"


def test_account_id_is_extracted_from_calendar_filename():
    assert webhook.account_id_from_filename("clip__ACC149__D1__S1.mp4") == "149"
    assert webhook.account_id_from_filename("clip.mp4") is None


def test_old_message_resolves_account_from_chat_topic(monkeypatch):
    captured = []
    monkeypatch.setattr(
        webhook,
        "TOPIC_ACCOUNT_MAP",
        {"-1004436137514:7524": "102"},
    )
    monkeypatch.setattr(webhook, "upsert_published_video", lambda fields: captured.append(fields) or True)
    monkeypatch.setattr(webhook, "post_telegram_method", lambda *args, **kwargs: {"ok": True})

    source_hash = "a" * 64
    result = webhook.handle_update(
        {
            "callback_query": {
                "id": "cb-old",
                "data": webhook.published_callback_data(source_hash, "b" * 16),
                "message": {
                    "chat": {"id": -1004436137514},
                    "message_thread_id": 7524,
                    "message_id": 456,
                    "video": {"file_name": "old-forge-name__c17.mp4"},
                    "caption": "caption",
                    "reply_markup": {"inline_keyboard": []},
                },
            }
        },
        "token",
    )

    assert result == {"ok": True, "handled": True}
    assert captured[0]["Account ID"] == "102"
    assert captured[0]["Publication key"] == "102:" + source_hash


def test_current_group_topic_map_resolves_clicked_evethebloom_account(monkeypatch):
    monkeypatch.setattr(webhook, "TOPIC_ACCOUNT_MAP", {"-1003749971714:39651": "349"})
    assert webhook.account_id_from_topic({
        "chat": {"id": -1003749971714},
        "message_thread_id": 39651,
    }) == "349"


def test_handle_update_upserts_origin_token(monkeypatch):
    captured = []
    monkeypatch.setenv("AIRTABLE_PAT", "pat")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    monkeypatch.setattr(webhook, "upsert_published_video", lambda fields: captured.append(fields) or True)
    monkeypatch.setattr(webhook, "post_telegram_method", lambda *args, **kwargs: {"ok": True})

    source_hash = "a" * 64
    origin_token = "b" * 16
    result = webhook.handle_update(
        {
            "callback_query": {
                "id": "cb1",
                "data": webhook.published_callback_data(source_hash, origin_token),
                "from": {"username": "operator"},
                "message": {
                    "chat": {"id": 123},
                    "message_id": 456,
                    "video": {"file_name": "variation__ACC149__D1__S1.mp4"},
                    "caption": "caption",
                    "reply_markup": {"inline_keyboard": []},
                },
            }
        },
        "token",
    )

    assert result["handled"] is True
    assert captured == [{
        "SHA-256": source_hash,
        "Origin token": origin_token,
        "Account ID": "149",
        "Publication key": "149:" + source_hash,
        "Archivo original": "variation__ACC149__D1__S1.mp4",
        "Chat ID": "123",
        "Message ID": "456",
        "Marcado por": "operator",
    }]


def test_already_published_callback_removes_stale_button(monkeypatch):
    calls = []
    monkeypatch.setattr(
        webhook,
        "post_telegram_method",
        lambda _token, method, payload: calls.append((method, payload)) or {"ok": True},
    )

    result = webhook.handle_update(
        {
            "callback_query": {
                "id": "cb-already-published",
                "data": "published",
                "message": {
                    "chat": {"id": -100123},
                    "message_id": 456,
                    "caption": "caption\n\n✅ YA PUBLICADO",
                    "reply_markup": {
                        "inline_keyboard": [[
                            {"text": "✅ Publicado", "callback_data": "published"},
                        ]]
                    },
                },
            }
        },
        "token",
    )

    assert result == {"ok": True, "handled": True}
    assert [method for method, _payload in calls] == [
        "editMessageCaption",
        "answerCallbackQuery",
    ]
    assert calls[0][1]["reply_markup"] == {"inline_keyboard": []}
    assert calls[0][1]["caption"] == "caption\n\n✅ YA PUBLICADO"
    assert calls[1][1] == {
        "callback_query_id": "cb-already-published",
        "text": "Ya estaba marcado.",
    }


def test_handle_update_without_account_does_not_write_airtable(monkeypatch):
    captured = []
    calls = []
    monkeypatch.setattr(webhook, "upsert_published_video", lambda fields: captured.append(fields) or True)
    monkeypatch.setattr(
        webhook,
        "post_telegram_method",
        lambda _token, method, payload: calls.append((method, payload)) or {"ok": True},
    )

    result = webhook.handle_update(
        {
            "callback_query": {
                "id": "cb1",
                "data": webhook.published_callback_data("a" * 64, "b" * 16),
                "message": {
                    "chat": {"id": 123},
                    "message_id": 456,
                    "video": {"file_name": "variation.mp4"},
                    "caption": "caption",
                },
            }
        },
        "token",
    )

    assert result == {"ok": True, "handled": True}
    assert captured == []
    assert calls == [("answerCallbackQuery", {
        "callback_query_id": "cb1",
        "text": "No se pudo identificar la cuenta; no se guardó.",
    })]


def test_airtable_upsert_uses_composite_publication_key(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"records":[{"id":"rec1"}]}'

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return Response()

    monkeypatch.setenv("AIRTABLE_PAT", "pat")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    monkeypatch.setattr(webhook.urllib.request, "urlopen", fake_urlopen)

    assert webhook.upsert_published_video({
        "Publication key": "149:" + "a" * 64,
        "SHA-256": "a" * 64,
    }) is True
    assert captured["payload"]["performUpsert"] == {
        "fieldsToMergeOn": ["Publication key"]
    }
