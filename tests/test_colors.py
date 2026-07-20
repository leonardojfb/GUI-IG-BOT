import re
from styles import colors

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

PAIR_TOKENS = [
    "BG_APP", "BG_SIDEBAR", "BG_CARD", "BG_CARD2", "BG_INPUT", "BORDER",
    "NEON_CYAN", "NEON_PURPLE", "IG_PINK", "IG_ORANGE",
    "SUCCESS", "WARNING", "DANGER", "INFO", "TELEGRAM",
    "TEXT_H1", "TEXT_BODY", "TEXT_MUTED",
    "ACCENT_TEXT", "ACCENT_HOVER",
    "ACCENT", "ACCENT_WEAK", "SURFACE", "SURFACE2", "RAIL", "GROUND", "LINE",
    "BRAND_REDDIT", "BRAND_X", "BRAND_IG",
]

def test_tokens_are_light_dark_hex_pairs():
    for name in PAIR_TOKENS:
        val = getattr(colors, name)
        assert isinstance(val, tuple) and len(val) == 2, f"{name} is not a 2-tuple"
        assert HEX.match(val[0]), f"{name} light not hex: {val[0]}"
        assert HEX.match(val[1]), f"{name} dark not hex: {val[1]}"

def test_accent_alias_matches_neon_cyan():
    assert colors.ACCENT == colors.NEON_CYAN

def test_resolve_picks_correct_mode():
    pair = ("#ffffff", "#000000")
    assert colors.resolve(pair, "Light") == "#ffffff"
    assert colors.resolve(pair, "Dark") == "#000000"
    assert colors.resolve(pair, "dark") == "#000000"
    assert colors.resolve(pair, "System") == "#ffffff"

def test_resolve_passes_plain_string_through():
    assert colors.resolve("#abcdef", "Dark") == "#abcdef"

def test_ui_fonts_use_segoe_and_mono_stays_consolas():
    assert colors.FONT_BODY[0] == "Segoe UI"
    assert colors.FONT_TITLE[0] == "Segoe UI"
    assert colors.FONT_MONO[0] == "Consolas"

def test_darken_string():
    assert colors.darken("#ffffff") == "#bfbfbf"   # 255*0.75 = 191 = 0xbf
    assert colors.darken("#000000") == "#000000"

def test_darken_tuple_returns_tuple():
    out = colors.darken(("#ffffff", "#000000"))
    assert out == ("#bfbfbf", "#000000")

def test_accent_is_peach_in_dark():
    assert colors.resolve(colors.ACCENT, "Dark") == "#e9c7a3"
    assert colors.resolve(colors.BG_APP, "Dark") == "#0c0c0e"

def test_accent_text_and_hover_exist():
    assert colors.resolve(colors.ACCENT_TEXT, "Dark") == "#1c1710"
    assert isinstance(colors.ACCENT_HOVER, tuple)

def test_new_sizes_and_fonts():
    assert colors.SIDEBAR_W == 240
    assert colors.CARD_RADIUS == 16
    assert colors.BTN_RADIUS == 10
    assert colors.FONT_TITLE[1] == 28
    assert colors.FONT_KICKER[2] == "bold"

def test_platform_brand_tokens_present():
    for t in (colors.BRAND_REDDIT, colors.BRAND_X, colors.BRAND_IG):
        assert isinstance(t, tuple) and len(t) == 2

def test_all_color_tokens_are_light_dark_tuples():
    for name in ("BG_APP","BG_CARD","ACCENT","TEXT_H1","DANGER","SUCCESS"):
        val = getattr(colors, name)
        assert isinstance(val, tuple) and len(val) == 2

if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print(f"PASS {_name}")
    print("ALL PASS")
