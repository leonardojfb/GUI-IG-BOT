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


def test_fuerza_custom_slider_maps_around_neutral():
    from metadata_pool import fuerza_to_strength
    assert fuerza_to_strength("Custom", 0) == 0.0
    assert fuerza_to_strength("Custom", 50) == 1.0
    assert fuerza_to_strength("Custom", 100) == 2.0


def test_parse_custom_ranges_valid():
    from metadata_pool import parse_custom_ranges
    r = parse_custom_ranges({"crop": ("2", "10"), "zoom": ("1.0", "1.05")})
    assert r["crop"] == (2.0, 10.0)
    assert r["zoom"] == (1.0, 1.05)


def test_parse_custom_ranges_swaps_min_max():
    from metadata_pool import parse_custom_ranges
    assert parse_custom_ranges({"rotate": ("1.5", "-1.5")})["rotate"] == (-1.5, 1.5)


def test_parse_custom_ranges_omits_blank_or_invalid():
    from metadata_pool import parse_custom_ranges
    r = parse_custom_ranges({"crop": ("", "10"), "noise": ("x", "8"), "trim": ("0", "150")})
    assert "crop" not in r and "noise" not in r
    assert r["trim"] == (0.0, 150.0)


def test_parse_custom_ranges_empty():
    from metadata_pool import parse_custom_ranges
    assert parse_custom_ranges({}) == {}
    assert parse_custom_ranges(None) == {}


def test_unknown_levels_fall_back():
    assert sum(efectos_to_enabled("???").values()) == 7   # falls back to Default
    assert fuerza_to_strength("???") == 1.0
