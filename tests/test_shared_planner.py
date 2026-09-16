import pytest

from shared_planner import preview_shared_schedule


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

