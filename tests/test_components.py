import pytest
ctk = pytest.importorskip("customtkinter")

def _root():
    try:
        r = ctk.CTk(); r.withdraw(); return r
    except Exception:
        pytest.skip("no display available")

def test_header_card_buttons_construct():
    from styles import components as K
    r = _root()
    try:
        K.PageHeader(r, "KICKER", "Title", "desc", action=("Do", lambda: None))
        c = K.Card(r, title="Card")
        assert hasattr(c, "body")
        K.PrimaryButton(r, text="P")
        K.GhostButton(r, text="G")
        K.DangerButton(r, text="D")
    finally:
        r.destroy()
