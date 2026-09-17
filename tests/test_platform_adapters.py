import pytest

from platform_adapters import PlatformAdapter, build_platform_policy, detect_downstream_duplicates, execute_platform_action, execute_publication_group


def test_adapter_requires_declared_capability_and_tracks_phases():
    calls = []
    adapter = PlatformAdapter("meta", {"prepare", "verify"}, handlers={"prepare": lambda request: calls.append(request) or {"status": "prepared"}, "verify": lambda request: {"status": "verified"}})

    assert execute_platform_action(adapter, "prepare", {"asset": "a"})["status"] == "prepared"
    assert calls == [{"asset": "a"}]
    with pytest.raises(ValueError, match="no soporta"):
        execute_platform_action(adapter, "publish", {})


def test_adapter_never_claims_success_without_explicit_result():
    adapter = PlatformAdapter("instagram", {"publish"}, handlers={"publish": lambda _: None})
    with pytest.raises(RuntimeError, match="resultado"):
        execute_platform_action(adapter, "publish", {"asset": "a"})


def test_publication_group_keeps_destination_results_independent():
    adapters = {
        "ig": PlatformAdapter("instagram", {"publish"}, handlers={"publish": lambda request: {"status": "confirmed", "remote_id": "ig-1"}}),
        "fb": PlatformAdapter("facebook", {"publish"}, handlers={"publish": lambda request: {"status": "failed", "error": "permission"}}),
    }
    group = [
        {"destination_id": "ig-1", "adapter": "ig", "request": {"asset": "a"}},
        {"destination_id": "fb-1", "adapter": "fb", "request": {"asset": "a"}},
    ]

    result = execute_publication_group(group, adapters, "publish")

    assert result["status"] == "partial"
    assert result["results"] == [
        {"destination_id": "ig-1", "status": "confirmed", "platform": "instagram", "remote_id": "ig-1"},
        {"destination_id": "fb-1", "status": "failed", "platform": "facebook", "error": "permission"},
    ]


def test_downstream_duplicate_is_blocked_only_for_same_lane_and_destination():
    rows = [
        {"root_id": "root-1", "destination_id": "page-1", "lane": "reel", "method": "crosspost"},
        {"root_id": "root-1", "destination_id": "page-1", "lane": "reel", "method": "manual"},
        {"root_id": "root-1", "destination_id": "page-1", "lane": "story", "method": "manual"},
    ]
    duplicates = detect_downstream_duplicates(rows)
    assert duplicates == [{"indexes": [0, 1], "root_id": "root-1", "destination_id": "page-1", "lane": "reel"}]


def test_strict_adapter_validates_platform_policy_before_handler():
    calls = []
    policy = build_platform_policy(
        targets={"instagram_reel"}, media_classes={"image", "video"}, max_upload_bytes=1000, rate_limit_per_minute=10,
    )
    adapter = PlatformAdapter("meta", {"publish"}, policy=policy, handlers={"publish": lambda request: calls.append(request) or {"status": "confirmed"}})
    request = {"destination_id": "ig-1", "publication_target": "instagram_reel", "media_class": "image", "media_size": 50, "account_context": {"account_id": "a1", "org_id": "o1"}}
    assert execute_platform_action(adapter, "publish", request)["status"] == "confirmed"
    assert calls == [request]
    with pytest.raises(ValueError, match="account_context"):
        execute_platform_action(adapter, "publish", {**request, "account_context": {}})
    with pytest.raises(ValueError, match="media_class"):
        execute_platform_action(adapter, "publish", {**request, "media_class": "pdf"})
