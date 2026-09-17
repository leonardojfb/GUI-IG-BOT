import pytest

from platform_adapters import PlatformAdapter, execute_platform_action


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
