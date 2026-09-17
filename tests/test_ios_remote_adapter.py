import json

from ios_remote_adapter import load_ios_remote_snapshot


def test_ios_remote_snapshot_is_allowlisted_and_hashed(tmp_path):
    source = tmp_path / "ios-export.json"
    source.write_text(json.dumps({
        "containers": [{
            "container_id": "c-1",
            "name": "Alice device",
            "status": "active",
            "accounts": [{"account_id": "acc-1", "username": "alice", "cookie": "secret"}],
            "device_profile": {
                "profile_id": "p-1", "version": 3, "model": "iPhone 15",
                "os": "18.1", "carrier": "Carrier", "locale": "es-AR",
                "timezone": "America/Argentina/Buenos_Aires", "location": "Buenos Aires",
                "updated_at": "2026-09-17T10:00:00Z", "token": "secret",
            },
            "password": "secret",
        }],
        "ignored": "drop-me",
    }), encoding="utf-8")

    result = load_ios_remote_snapshot(source)

    assert result["schema_version"] == 1
    assert result["snapshot_hash"].startswith("sha256:")
    assert result["containers"][0]["accounts"] == [{"account_id": "acc-1", "username": "alice"}]
    assert result["containers"][0]["device_profile"]["model"] == "iPhone 15"
    assert "password" not in result["containers"][0]
    assert "ignored" not in result


def test_ios_remote_snapshot_rejects_missing_identity_or_profile(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text(json.dumps({"containers": [{"container_id": "c-1"}]}), encoding="utf-8")
    try:
        load_ios_remote_snapshot(source)
    except ValueError as exc:
        assert "device_profile" in str(exc)
    else:
        raise AssertionError("incomplete ios-remote snapshot must be rejected")
