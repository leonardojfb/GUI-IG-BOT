import re
from styles import colors

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

PAIR_TOKENS = [
    "BG_APP", "BG_SIDEBAR", "BG_CARD", "BG_CARD2", "BG_INPUT", "BORDER",
    "NEON_CYAN", "NEON_PURPLE", "IG_PINK", "IG_ORANGE",
    "SUCCESS", "WARNING", "DANGER", "INFO",
    "TEXT_H1", "TEXT_BODY", "TEXT_MUTED",
    "ACCENT", "ACCENT_WEAK", "SURFACE", "SURFACE2", "RAIL", "GROUND", "LINE",
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

if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print(f"PASS {_name}")
    print("ALL PASS")
