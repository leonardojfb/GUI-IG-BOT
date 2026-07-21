from metadata_pool import efectos_to_enabled, fuerza_to_strength


def test_efectos_default_is_seven_without_mirror():
    en = efectos_to_enabled("Default")
    assert en["mirror"] is False
    assert sum(en.values()) == 7
    assert all(en[k] for k in ("crop", "zoom", "rotate", "color", "noise", "speed", "trim"))


def test_efectos_level_counts():
    assert sum(efectos_to_enabled("Light").values()) == 2
    assert sum(efectos_to_enabled("Medio").values()) == 5
    assert sum(efectos_to_enabled("Alto").values()) == 8


def test_efectos_custom_reads_fx_vars():
    fx = {"crop": True, "mirror": True, "zoom": False, "rotate": False,
          "color": False, "noise": False, "speed": False, "trim": False}
    en = efectos_to_enabled("Custom", fx)
    assert en["crop"] is True and en["mirror"] is True and en["zoom"] is False
    assert sum(en.values()) == 2


def test_efectos_returns_all_eight_keys():
    en = efectos_to_enabled("Light")
    assert set(en.keys()) == {"crop", "mirror", "zoom", "rotate", "color", "noise", "speed", "trim"}


def test_fuerza_levels():
    assert fuerza_to_strength("Default") == 1.0
    assert fuerza_to_strength("Medio") == 1.0
    assert fuerza_to_strength("Light") == 0.5
    assert fuerza_to_strength("Alto") == 2.4


def test_fuerza_custom_slider_maps_0_to_100():
    assert fuerza_to_strength("Custom", 0) == 0.3
    assert fuerza_to_strength("Custom", 100) == 2.5
    mid = fuerza_to_strength("Custom", 50)
    assert 0.3 < mid < 2.5


def test_unknown_levels_fall_back():
    assert sum(efectos_to_enabled("???").values()) == 7   # falls back to Default
    assert fuerza_to_strength("???") == 1.0
