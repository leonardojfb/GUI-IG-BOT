import random
from metadata_pool import generate_variant_params


def _samples(strength, n=400, enabled=None):
    r = random.Random(1234)
    return [generate_variant_params(r, enabled=enabled, strength=strength) for _ in range(n)]


def test_strength_1_matches_historical_bounds():
    ps = _samples(1.0)
    assert all(2 <= p["crop_px"] <= 10 for p in ps)
    assert all(1.0 <= p["zoom_pct"] <= 1.05 for p in ps)
    assert all(-1.5 <= p["rotate_deg"] <= 1.5 for p in ps)
    assert all(0.94 <= p["contrast"] <= 1.06 for p in ps)
    assert all(0.90 <= p["saturation"] <= 1.10 for p in ps)
    assert all(p["noise"] == 0 or 4 <= p["noise"] <= 8 for p in ps)
    assert all(0 <= p["trim_start_ms"] <= 150 for p in ps)
    assert all(0.985 <= p["speed"] <= 1.015 for p in ps)


def test_low_strength_shrinks_bounds():
    ps = _samples(0.5)
    assert all(0 <= p["crop_px"] <= 5 for p in ps)          # round(10*0.5)=5
    assert all(1.0 <= p["zoom_pct"] <= 1.025 for p in ps)   # 1+0.05*0.5
    assert all(-0.75 <= p["rotate_deg"] <= 0.75 for p in ps)


def test_high_strength_grows_bounds():
    ps = _samples(2.4)
    assert all(0 <= p["crop_px"] <= 24 for p in ps)         # round(10*2.4)=24
    assert all(1.0 <= p["zoom_pct"] <= 1.12 for p in ps)    # 1+0.05*2.4
    assert any(abs(p["rotate_deg"]) > 1.5 for p in ps)      # exceeds historical


def test_magnitude_is_monotonic_in_strength():
    def max_rot(s):
        return max(abs(p["rotate_deg"]) for p in _samples(s))
    assert max_rot(0.5) < max_rot(1.0) < max_rot(2.4)


def test_noise_floored_at_4_when_firing():
    for s in (0.5, 1.0, 2.4):
        ps = _samples(s)
        assert all(p["noise"] == 0 or p["noise"] >= 4 for p in ps)


def test_disabled_effects_never_apply_at_any_strength():
    off = {"mirror": False, "crop": False, "noise": False, "zoom": False}
    for s in (0.5, 1.0, 2.4):
        ps = _samples(s, enabled=off)
        assert all(p["mirror"] is False for p in ps)
        assert all(p["crop_px"] == 0 for p in ps)
        assert all(p["noise"] == 0 for p in ps)
        assert all(p["zoom_pct"] == 1.0 for p in ps)
