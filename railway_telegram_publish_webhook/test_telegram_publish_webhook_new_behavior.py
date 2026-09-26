import sys
import base64
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import telegram_publish_webhook as webhook
import organizadortg


def _hash_callback(raw):
    return "pub:" + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _callback(data):
    return {
        "callback_query": {
            "id": "cb-1",
            "data": data,
            "from": {"username": "operator"},
            "message": {
                "message_id": 77,
                "chat": {"id": -100123},
                "caption": "caption",
                "video": {"file_name": "video.mp4"},
                "reply_markup": {
                    "inline_keyboard": [[
                        {"text": "✅ Publicado", "callback_data": data},
                        {"text": "📋 Copiar caption", "copy_text": {"text": "caption"}},
                    ]]
                },
            },
        }
    }


def test_webhook_registration_payload_includes_callback_queries():
    assert webhook.webhook_registration_payload(
        "https://telegram-publish-webhook-production.up.railway.app",
        "secret-value",
    ) == {
        "url": "https://telegram-publish-webhook-production.up.railway.app/telegram/callback",
        "secret_token": "secret-value",
        "allowed_updates": [
            "message",
            "edited_message",
            "channel_post",
            "edited_channel_post",
            "callback_query",
        ],
    }


def test_reconcile_webhook_replaces_foreign_registration(monkeypatch):
    calls = []
    responses = [
        {
            "ok": True,
            "result": {
                "url": "https://tele.goldenherd.com/tg/webhook/other",
                "allowed_updates": ["message"],
            },
        },
        {"ok": True, "result": True},
    ]

    def fake_post(token, method, payload):
        calls.append((token, method, payload))
        return responses.pop(0)

    monkeypatch.setattr(webhook, "post_telegram_method", fake_post)

    result = webhook.reconcile_webhook(
        "token-123",
        "https://telegram-publish-webhook-production.up.railway.app",
        "secret-value",
    )

    assert result == {"ok": True, "result": True}
    assert calls == [
        ("token-123", "getWebhookInfo", {}),
        (
            "token-123",
            "setWebhook",
            {
                "url": "https://telegram-publish-webhook-production.up.railway.app/telegram/callback",
                "secret_token": "secret-value",
                "allowed_updates": [
                    "message",
                    "edited_message",
                    "channel_post",
                    "edited_channel_post",
                    "callback_query",
                ],
            },
        ),
    ]


def test_new_publish_button_is_explicit_action():
    assert organizadortg._publish_button_markup("caption")["inline_keyboard"] == [[
        {"text": "✅ Publicado", "callback_data": "pub"},
        {"text": "📋 Copiar caption", "copy_text": {"text": "caption"}},
    ]]


def test_published_markup_removes_publish_button_and_preserves_copy_button():
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ Publicado", "callback_data": "pub"},
            {"text": "📋 Copiar caption", "copy_text": {"text": "caption"}},
        ]]
    }

    updated = webhook.published_markup(reply_markup)

    assert updated == {
        "inline_keyboard": [[
            {"text": "📋 Copiar caption", "copy_text": {"text": "caption"}},
        ]]
    }


def test_publish_callback_marks_caption_and_removes_publish_button(monkeypatch):
    calls = []
    monkeypatch.setattr(
        webhook,
        "post_telegram_method",
        lambda token, method, payload: calls.append((method, payload)) or {"ok": True},
    )

    result = webhook.handle_update(
        {
            "callback_query": {
                "id": "cb-1",
                "data": "pub",
                "message": {
                    "message_id": 77,
                    "chat": {"id": -100123},
                    "caption": "caption",
                    "reply_markup": {
                        "inline_keyboard": [[
                            {"text": "✅ Publicado", "callback_data": "pub"},
                            {"text": "📋 Copiar caption", "copy_text": {"text": "caption"}},
                        ]]
                    },
                },
            }
        },
        "token-123",
    )

    assert result == {"ok": True, "handled": True}
    assert calls == [
        ("answerCallbackQuery", {"callback_query_id": "cb-1"}),
        (
            "editMessageCaption",
            {
                "chat_id": -100123,
                "message_id": 77,
                "caption": "caption\n\n✅ YA PUBLICADO",
                "reply_markup": {
                    "inline_keyboard": [[
                        {"text": "📋 Copiar caption", "copy_text": {"text": "caption"}},
                    ]]
                },
            },
        ),
    ]


def test_hash_callback_upserts_before_caption_edit(monkeypatch):
    calls = []
    stored = []
    monkeypatch.setattr(
        webhook, "upsert_published_video", lambda fields: stored.append(fields) or True,
        raising=False,
    )
    monkeypatch.setattr(
        webhook,
        "post_telegram_method",
        lambda _token, method, payload: calls.append((method, payload)) or {"ok": True},
    )

    result = webhook.handle_update(_callback(_hash_callback(b"a" * 32)), "token-123")

    assert result == {"ok": True, "handled": True}
    assert stored[0]["SHA-256"] == (b"a" * 32).hex()
    assert calls[-1][0] == "editMessageCaption"


def test_hash_callback_keeps_button_when_airtable_write_fails(monkeypatch):
    calls = []
    monkeypatch.setattr(webhook, "upsert_published_video", lambda _fields: False, raising=False)
    monkeypatch.setattr(
        webhook,
        "post_telegram_method",
        lambda _token, method, payload: calls.append((method, payload)) or {"ok": True},
    )

    result = webhook.handle_update(_callback(_hash_callback(b"a" * 32)), "token-123")

    assert result == {"ok": True, "handled": True}
    assert not any(method.startswith("editMessage") for method, _payload in calls)


def test_legacy_pub_callback_remains_visual_only(monkeypatch):
    monkeypatch.setattr(
        webhook,
        "upsert_published_video",
        lambda _fields: (_ for _ in ()).throw(AssertionError("legacy must not write")),
        raising=False,
    )
    monkeypatch.setattr(webhook, "post_telegram_method", lambda *_args: {"ok": True})

    assert webhook.handle_update(_callback("pub"), "token-123") == {"ok": True, "handled": True}


def test_readme_requires_publication_store_variables():
    text = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

    for value in (
        "AIRTABLE_PAT",
        "AIRTABLE_BASE_ID",
        "AIRTABLE_PUBLISHED_TABLE",
        "SHA-256",
    ):
        assert value in text
