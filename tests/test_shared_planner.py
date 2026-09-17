import pytest

from shared_planner import (
    assess_candidate_eligibility,
    filter_candidates_for_account,
    preview_shared_schedule_by_account,
    preview_shared_schedule,
)


def _candidates(count, tanda="T1"):
    return [
        {
            "source_id": f"{tanda}:{index}",
            "source_path": f"/vault/{tanda}/{index}.mp4",
            "tanda": tanda,
        }
        for index in range(count)
    ]


def test_preview_shared_schedule_is_deterministic_and_preserves_sources():
    preview = preview_shared_schedule(
        accounts=[{"username": "alice"}, {"username": "bob"}],
        candidates=_candidates(6) + _candidates(2, "T2"),
        daily_quota=2,
        days=2,
        lane="reel",
        placement="feed",
        method="telegram",
        seed=17,
    )

    same_preview = preview_shared_schedule(
        accounts=[{"username": "alice"}, {"username": "bob"}],
        candidates=_candidates(6) + _candidates(2, "T2"),
        daily_quota=2,
        days=2,
        lane="reel",
        placement="feed",
        method="telegram",
        seed=17,
    )

    assert preview == same_preview
    assert preview["status"] == "ready"
    assert preview["summary"] == {
        "requested": 8,
        "assignable": 8,
        "omitted": 0,
        "accounts": 2,
        "days": 2,
        "daily_quota": 2,
    }
    assert {row["tanda"] for row in preview["assignments"]} == {"T1", "T2"}
    assert all(row["lane"] == "reel" for row in preview["assignments"])
    assert all(row["placement"] == "feed" for row in preview["assignments"])
    assert all(row["method"] == "telegram" for row in preview["assignments"])


def test_preview_shared_schedule_reports_partial_inventory_by_account_and_source():
    preview = preview_shared_schedule(
        accounts=[{"username": "alice"}, {"username": "bob"}],
        candidates=_candidates(3),
        daily_quota=2,
        days=2,
        mode="partial",
        seed=1,
    )

    assert preview["status"] == "partial"
    assert preview["summary"]["requested"] == 8
    assert preview["summary"]["assignable"] == 3
    assert preview["summary"]["omitted"] == 5
    assert len(preview["assignments"]) == 3
    assert preview["omitted"]
    assert {row["reason"] for row in preview["omitted"]} == {"insufficient_inventory"}
    assert {row["username"] for row in preview["omitted"]} == {"alice", "bob"}


def test_preview_shared_schedule_strict_mode_blocks_partial_plan_without_side_effects():
    preview = preview_shared_schedule(
        accounts=[{"username": "alice"}, {"username": "bob"}],
        candidates=_candidates(3),
        daily_quota=2,
        days=2,
        mode="strict",
        seed=1,
    )

    assert preview["status"] == "blocked"
    assert preview["assignments"] == []
    assert preview["summary"]["assignable"] == 3
    assert preview["summary"]["omitted"] == 5


def test_candidate_eligibility_blocks_only_same_account_and_lane_usage():
    candidate = {
        "source_id": "T1:clip.mp4",
        "delivery_kind": "normal",
        "used_in": [
            {"username": "alice", "lane": "reel"},
            {"username": "alice", "lane": "story"},
        ],
    }

    blocked = assess_candidate_eligibility(candidate, username="alice", lane="reel")
    other_lane = assess_candidate_eligibility(candidate, username="alice", lane="story")
    other_account = assess_candidate_eligibility(candidate, username="bob", lane="reel")

    assert blocked == {
        "eligible": False,
        "reason": "already_used_in_lane",
        "context_usage_count": 1,
    }
    assert other_lane["eligible"] is False
    assert other_lane["context_usage_count"] == 1
    assert other_account == {"eligible": True, "reason": "", "context_usage_count": 0}


def test_candidate_eligibility_enforces_trial_lane_and_filter_reports_exclusions():
    candidates = [
        {"source_id": "normal", "delivery_kind": "normal"},
        {"source_id": "trial", "delivery_kind": "trial"},
    ]

    result = filter_candidates_for_account(candidates, username="alice", lane="reel")

    assert [item["source_id"] for item in result["candidates"]] == ["normal"]
    assert result["excluded"] == [
        {
            "source_id": "trial",
            "username": "alice",
            "lane": "reel",
            "reason": "trial_lane_mismatch",
        }
    ]


def test_preview_shared_schedule_by_account_applies_usage_per_account():
    candidates = [
        {"source_id": "shared", "tanda": "T1", "used_in": [{"username": "alice", "lane": "reel"}]},
        {"source_id": "fresh", "tanda": "T1", "used_in": []},
    ]

    preview = preview_shared_schedule_by_account(
        accounts=[{"username": "alice"}, {"username": "bob"}],
        candidates_by_account={"alice": candidates, "bob": candidates},
        daily_quota=1,
        days=1,
        lane="reel",
        seed=4,
    )

    alice = [row for row in preview["assignments"] if row["username"] == "alice"]
    bob = [row for row in preview["assignments"] if row["username"] == "bob"]
    assert preview["status"] == "ready"
    assert alice[0]["source_id"] == "fresh"
    assert bob[0]["source_id"] in {"shared", "fresh"}
    assert preview["account_summary"]["alice"]["excluded"] == 1
    assert preview["account_summary"]["bob"]["excluded"] == 0


def test_preview_shared_schedule_by_account_reports_fixed_period_shortage():
    preview = preview_shared_schedule_by_account(
        accounts=[{"username": "alice"}, {"username": "bob"}],
        candidates_by_account={"alice": _candidates(1), "bob": _candidates(3, "T2")},
        daily_quota=2,
        days=2,
        mode="partial",
        seed=2,
    )

    assert preview["status"] == "partial"
    assert preview["summary"]["requested"] == 8
    assert preview["summary"]["assignable"] == 4
    assert preview["summary"]["omitted"] == 4
    assert preview["account_summary"]["alice"]["omitted"] == 3
    assert preview["account_summary"]["bob"]["omitted"] == 1


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"accounts": [], "candidates": _candidates(1), "daily_quota": 1, "days": 1}, "accounts"),
        ({"accounts": [{"username": "alice"}], "candidates": _candidates(1), "daily_quota": 0, "days": 1}, "daily_quota"),
        ({"accounts": [{"username": "alice"}], "candidates": _candidates(1), "daily_quota": 1, "days": 0}, "days"),
        ({"accounts": [{"username": "alice"}, {"username": "alice"}], "candidates": _candidates(1), "daily_quota": 1, "days": 1}, "username"),
    ],
)
def test_preview_shared_schedule_rejects_invalid_scope(kwargs, message):
    with pytest.raises(ValueError, match=message):
        preview_shared_schedule(**kwargs)
