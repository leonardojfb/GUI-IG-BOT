import sqlite3

import pytest

from confirmation_ledger import build_callback, ingest_callback, parse_callback, undo_confirmation


def test_callbacks_are_versioned_and_strictly_parsed():
    callback = build_callback("confirm", "message-42")
    assert callback == "v1|confirm|message-42"
    assert parse_callback(callback) == {"version": 1, "action": "confirm", "entity_id": "message-42"}
    with pytest.raises(ValueError):
        parse_callback("v2|confirm|message-42")


def test_external_callback_inbox_deduplicates_and_supports_undo():
    connection = sqlite3.connect(":memory:")
    sent = []
    callback = build_callback("confirm", "message-42")
    first = ingest_callback(connection, callback, external_id="telegram-callback-1", user_id="u1", payload={"chat_id": "-1"})
    second = ingest_callback(connection, callback, external_id="telegram-callback-1", user_id="u1", payload={"chat_id": "-1"})

    assert first["status"] == "recorded"
    assert second["status"] == "duplicate"
    undone = undo_confirmation(connection, first["event_id"], lambda event: sent.append(event["entity_id"]))
    repeated = undo_confirmation(connection, first["event_id"], lambda _: sent.append("again"))
    assert undone["status"] == "undone"
    assert repeated["status"] == "already_undone"
    assert sent == ["message-42"]
