import csv
import sqlite3

from crm_insights import build_identity, build_infrastructure_event, export_metrics_csv, list_metric_snapshots, record_metric_snapshot, score_virality, summarize_metrics


def test_identity_is_typed_and_metrics_are_deterministic():
    identity = build_identity("alice", platform="instagram", account_id="acc-1", va="VA1")
    summary = summarize_metrics([{"account_id": "acc-1", "posts": 4, "likes": 20, "comments": 5, "shares": 2}])
    assert identity["type"] == "social_account"
    assert summary["posts"] == 4
    assert summary["engagement"] == 27
    assert summary["engagement_rate"] == 6.75
    assert score_virality(summary)["label"] == "medium"
    event = build_infrastructure_event("acc-1", device_id="device-secret", network_id="10.0.0.1", observed_at="2026-09-17T00:00:00Z")
    assert event["device_ref"].startswith("device:")
    assert "device-secret" not in str(event)


def test_metrics_csv_is_atomic_and_does_not_include_credentials(tmp_path):
    target = tmp_path / "metrics.csv"
    export_metrics_csv(target, [{"account_id": "a", "posts": 1, "likes": 2, "comments": 0, "shares": 0, "cookie": "secret"}])
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["account_id"] == "a"
    assert "cookie" not in rows[0]
    assert "secret" not in target.read_text(encoding="utf-8")


def test_metric_snapshots_are_persistent_deduplicated_and_sanitized():
    connection = sqlite3.connect(":memory:")
    row = {"posts": 2, "likes": 10, "comments": 1, "shares": 0, "token": "must-not-persist"}

    first = record_metric_snapshot(connection, "acc-1", row, observed_at="2026-09-17T10:00:00Z")
    duplicate = record_metric_snapshot(connection, "acc-1", row, observed_at="2026-09-17T10:00:00Z")
    snapshots = list_metric_snapshots(connection, "acc-1")

    assert first["status"] == "recorded"
    assert duplicate["status"] == "duplicate"
    assert snapshots == [{"account_id": "acc-1", "observed_at": "2026-09-17T10:00:00Z", "metrics": {"comments": 1, "likes": 10, "posts": 2, "shares": 0}}]
