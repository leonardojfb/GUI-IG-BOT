import csv

from crm_insights import build_identity, export_metrics_csv, summarize_metrics


def test_identity_is_typed_and_metrics_are_deterministic():
    identity = build_identity("alice", platform="instagram", account_id="acc-1", va="VA1")
    summary = summarize_metrics([{"account_id": "acc-1", "posts": 4, "likes": 20, "comments": 5, "shares": 2}])
    assert identity["type"] == "social_account"
    assert summary["posts"] == 4
    assert summary["engagement"] == 27
    assert summary["engagement_rate"] == 6.75


def test_metrics_csv_is_atomic_and_does_not_include_credentials(tmp_path):
    target = tmp_path / "metrics.csv"
    export_metrics_csv(target, [{"account_id": "a", "posts": 1, "likes": 2, "comments": 0, "shares": 0, "cookie": "secret"}])
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["account_id"] == "a"
    assert "cookie" not in rows[0]
    assert "secret" not in target.read_text(encoding="utf-8")
