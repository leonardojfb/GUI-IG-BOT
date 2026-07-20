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

def test_inputs_construct():
    from styles import components as K
    r = _root()
    try:
        seg = K.SegmentedControl(r, ["A", "B", "C"], default="B")
        assert seg.get() == "B"
        st = K.Stepper(r, value=5, min=1, max=10)
        st.set(20)
        assert st.get() == 10          # clamped to max
        st.set(0)
        assert st.get() == 1           # clamped to min
        tr = K.ToggleRow(r, "Enable", None)
        assert tr.var.get() is False
    finally:
        r.destroy()

def test_rows_zones_construct():
    from styles import components as K
    r = _root()
    try:
        K.KeyValueRow(r, "Status", "Active")
        K.Dropzone(r, "Drop files", "Image or video", on_browse=lambda: None)
        K.PhonePreview(r)
        nav = K.NavItem(r, "Forge", command=lambda: None)
        nav.set_active(True)
        nav.set_active(False)
    finally:
        r.destroy()
