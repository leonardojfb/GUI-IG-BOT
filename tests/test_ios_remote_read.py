import json

import pytest

from ios_remote_read import sanitize_snapshot, write_sanitized_snapshot


def test_sanitize_snapshot_removes_sessions_but_keeps_read_metadata():
    snapshot = {"account": {"username": "alice", "cookies": "sid=secret", "status": "ok"}, "headers": {"Authorization": "Bearer secret"}, "posts": [{"id": "p1", "caption": "hello"}]}

    result = sanitize_snapshot(snapshot)

    assert result["account"] == {"username": "alice", "status": "ok"}
    assert result["posts"] == [{"id": "p1", "caption": "hello"}]
    assert "headers" not in result
    assert "secret" not in json.dumps(result)


def test_write_sanitized_snapshot_is_atomic_and_does_not_store_cookie(tmp_path):
    source = tmp_path / "remote.json"
    target = tmp_path / "export.json"
    source.write_text(json.dumps({"username": "alice", "sessionid": "secret", "media": [{"id": 1}]}), encoding="utf-8")

    result = write_sanitized_snapshot(source, target)

    assert result["schema_version"] == 1
    assert target.is_file()
    assert "secret" not in target.read_text(encoding="utf-8")
    assert list(tmp_path.glob(".*.tmp")) == []


def test_sanitize_snapshot_rejects_non_object_root():
    with pytest.raises(ValueError, match="objeto"):
        sanitize_snapshot([{"cookie": "secret"}])
