# OOPSIE Skin Reskin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin the CustomTkinter GUI (`gui_premium_v7.py`) to match the OOPSIE app's visual language — near-black warm background, single peach accent, big radii, shared component kit — with zero business-logic changes.

**Architecture:** Central design tokens in `styles/colors.py` (already `(light,dark)` tuples consumed by CTk natively + a `themed()` resolver for raw tk/ttk widgets). A new `styles/components.py` provides reusable OOPSIE-shaped widgets. Screen builders in `gui_premium_v7.py` are refactored to consume the kit. This is redesign **v2** on top of the already-shipped `2026-07-18-ui-redesign` (teal→peach swap on the same architecture).

**Tech Stack:** Python 3, CustomTkinter, Tkinter/ttk, pytest.

## Global Constraints

- **Pure reskin. Zero logic changes.** No edits to `metadata_pool.py`, `database.py`, `videos.py`, `telegram_core.py`, `updater.py`, `Organizador.py`, scheduler, anti-collision, DB schema, command handlers, instance-variable names, or threading.
- **No new runtime dependencies. No web stack.** Kit = CustomTkinter built-ins + small composites.
- All colors come from `styles/colors.py` tokens — never hardcode a hex outside that module.
- Dark palette values are authoritative (from OOPSIE screenshots); light values are derived and get one polish pass.
- Peach accent dark = `#e9c7a3`; text-on-peach = `#1c1710`; near-black bg dark = `#0c0c0e`.
- Repo root is `Método IG VIDEOS v2.0/` (the parent folder's `.git` is stray — ignore it). Active branch: `ui-redesign`.
- Every task ends green: existing `tests/` suite must still pass (proves no logic regression).

---

### Task 1: Rewrite design tokens (`styles/colors.py`)

**Files:**
- Modify: `styles/colors.py` (full token rewrite, keep `resolve()`/`darken()` verbatim)
- Test: `tests/test_colors.py`

**Interfaces:**
- Produces: token names `BG_APP, BG_SIDEBAR, BG_CARD, BG_CARD2, BG_INPUT, BORDER, NEON_CYAN, ACCENT_WEAK, NEON_PURPLE, IG_PINK, IG_ORANGE, SUCCESS, WARNING, DANGER, INFO, TELEGRAM, BRAND_REDDIT, BRAND_X, BRAND_IG, TEXT_H1, TEXT_BODY, TEXT_MUTED, ACCENT_TEXT, ACCENT_HOVER` (each a `(light,dark)` tuple); aliases `GROUND, RAIL, SURFACE, SURFACE2, LINE, ACCENT, ACCENT_2`; fonts `FONT_TITLE, FONT_KICKER, FONT_DESC, FONT_H2, FONT_H3, FONT_BODY, FONT_SMALL, FONT_MONO`; sizes `SIDEBAR_W=240, STATUS_H, CARD_RADIUS=16, BTN_RADIUS=10, INPUT_RADIUS=10, BTN_H=40, BTN_H_LG=46`; functions `resolve(value, mode)`, `darken(value, factor=0.75)`.
- Note: legacy names `NEON_CYAN`/`NEON_PURPLE`/`IG_PINK` are kept but remapped to the new palette, so existing `fg_color=NEON_CYAN` call sites recolor automatically with no edits.

- [ ] **Step 1: Read the existing test file**

Run: read `tests/test_colors.py` to see what it currently asserts (token shapes, `resolve()`, `darken()`).

- [ ] **Step 2: Write/adjust the failing test**

Add or update these assertions in `tests/test_colors.py` (reconcile with existing ones; keep any `resolve()`/`darken()` behavior tests):

```python
from styles import colors as C

def test_accent_is_peach_in_dark():
    assert C.resolve(C.ACCENT, "Dark") == "#e9c7a3"
    assert C.resolve(C.BG_APP, "Dark") == "#0c0c0e"

def test_accent_text_and_hover_exist():
    assert C.resolve(C.ACCENT_TEXT, "Dark") == "#1c1710"
    assert isinstance(C.ACCENT_HOVER, tuple)

def test_new_sizes_and_fonts():
    assert C.SIDEBAR_W == 240
    assert C.CARD_RADIUS == 16
    assert C.BTN_RADIUS == 10
    assert C.FONT_TITLE[1] == 28
    assert C.FONT_KICKER[2] == "bold"

def test_platform_brand_tokens_present():
    for t in (C.BRAND_REDDIT, C.BRAND_X, C.BRAND_IG):
        assert isinstance(t, tuple) and len(t) == 2

def test_all_color_tokens_are_light_dark_tuples():
    for name in ("BG_APP","BG_CARD","ACCENT","TEXT_H1","DANGER","SUCCESS"):
        val = getattr(C, name)
        assert isinstance(val, tuple) and len(val) == 2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_colors.py -v`
Expected: FAIL (ACCENT still teal `#4db6a2`, `ACCENT_TEXT` undefined, `SIDEBAR_W` is 210).

- [ ] **Step 4: Rewrite `styles/colors.py`**

Replace the file's token section with the following (keep the module docstring intent; keep `resolve()` and `darken()` exactly as they already are):

```python
# ── Fondos ── (light, dark) ─────────────────────────────────────────────
BG_APP     = ("#faf9f6", "#0c0c0e")   # Fondo raíz (near-black cálido en dark)
BG_SIDEBAR = ("#f3f1ea", "#0e0e10")   # Panel lateral
BG_CARD    = ("#ffffff", "#141416")   # Cards primarias
BG_CARD2   = ("#f0eee7", "#1a1a1d")   # Cards secundarias / hover
BG_INPUT   = ("#f3f1ea", "#141416")   # Campos de entrada
BORDER     = ("#e7e3d9", "#242428")   # Bordes y separadores

# ── Acentos ── (light, dark) — peach/almond, acento único OOPSIE ─────────
NEON_CYAN   = ("#c98a3f", "#e9c7a3")  # ACENTO PRIMARIO (peach). Nombre legacy.
ACCENT_WEAK = ("#f3e6d3", "#2a2118")  # Fondo del nav activo (peach tenue)
NEON_PURPLE = ("#7a6a52", "#c9b48f")  # Acento secundario apagado (legacy)
IG_PINK     = ("#c9564e", "#e5675f")  # Destructivas
IG_ORANGE   = ("#c2872f", "#e0a94e")  # Ámbar

# ── Semánticos ──
SUCCESS  = ("#3f9d6d", "#3fb768")
WARNING  = ("#c2872f", "#e0a94e")
DANGER   = ("#c9564e", "#e5675f")
INFO     = ("#2f88c2", "#29a9ea")
TELEGRAM = ("#2f88c2", "#29a9ea")     # Botón de soporte Telegram

# ── Marcas de plataforma (el icono conserva color de marca) ──
BRAND_REDDIT = ("#ff4500", "#ff4500")
BRAND_X      = ("#1d1d1f", "#e7e9ea")
BRAND_IG     = ("#e1306c", "#e1306c")

# ── Tipografía ── (light, dark) ──
TEXT_H1    = ("#1b1a17", "#f5f5f5")
TEXT_BODY  = ("#55534c", "#a0a0a6")
TEXT_MUTED = ("#8b887f", "#6c6c72")

# ── Texto/hover sobre acento peach ──
ACCENT_TEXT  = ("#1c1710", "#1c1710")
ACCENT_HOVER = ("#b87d38", "#dcb489")

# ── Aliases semánticos ──
GROUND   = BG_APP
RAIL     = BG_SIDEBAR
SURFACE  = BG_CARD
SURFACE2 = BG_CARD2
LINE     = BORDER
ACCENT   = NEON_CYAN
ACCENT_2 = NEON_PURPLE

# ── Fuentes ──
FONT_TITLE  = ("Segoe UI", 28, "bold")   # Título de página grande
FONT_KICKER = ("Segoe UI", 11, "bold")   # Eyebrow uppercase
FONT_DESC   = ("Segoe UI", 14)           # Descripción bajo el título
FONT_H2     = ("Segoe UI", 15, "bold")
FONT_H3     = ("Segoe UI", 12, "bold")
FONT_BODY   = ("Segoe UI", 12)
FONT_SMALL  = ("Segoe UI", 10)
FONT_MONO   = ("Consolas", 10)

# ── Tamaños de componentes ──
SIDEBAR_W    = 240
STATUS_H     = 28
CARD_RADIUS  = 16
BTN_RADIUS   = 10
INPUT_RADIUS = 10
BTN_H        = 40
BTN_H_LG     = 46
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_colors.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite (regression guard)**

Run: `python -m pytest -q`
Expected: PASS (no logic touched).

- [ ] **Step 7: Commit**

```bash
git add styles/colors.py tests/test_colors.py
git commit -m "feat(ui): swap design tokens to OOPSIE peach-on-near-black (v2)"
```

---

### Task 2: Refresh raw tk/ttk styles to the new tokens

**Files:**
- Modify: `gui_premium_v7.py` — the ttk style setup (`Premium.Treeview`, scrollbars, combobox) and the existing `_restyle_raw_tk()` / raw-tk color sites (Forge `tk.Listbox`, trees).

**Interfaces:**
- Consumes: `themed()` (already on the app class), tokens from Task 1.
- Produces: no new API; ensures every `tk.`/`ttk.` widget reads current tokens so peach/near-black applies and survives theme toggle.

- [ ] **Step 1: Inventory raw-tk/ttk color sites**

Run: `grep -nE "style\.configure|ttk\.|tk\.Listbox|configure\(bg=|fg=|selectbackground|highlightbackground|fieldbackground" gui_premium_v7.py`
Record each Treeview/Listbox/Scrollbar/Combobox style line.

- [ ] **Step 2: Route each site through `themed()` with new tokens**

For the `Premium.Treeview` style, ensure it reads: `background=self.themed(BG_CARD)`, `fieldbackground=self.themed(BG_CARD)`, `foreground=self.themed(TEXT_BODY)`, `bordercolor=self.themed(BORDER)`, selection `background=self.themed(ACCENT)`, selection `foreground=self.themed(ACCENT_TEXT)`, and set `rowheight=30`. Example:

```python
style.configure("Premium.Treeview",
                background=self.themed(BG_CARD),
                fieldbackground=self.themed(BG_CARD),
                foreground=self.themed(TEXT_BODY),
                bordercolor=self.themed(BORDER),
                borderwidth=0, rowheight=30)
style.map("Premium.Treeview",
          background=[("selected", self.themed(ACCENT))],
          foreground=[("selected", self.themed(ACCENT_TEXT))])
style.configure("Premium.Treeview.Heading",
                background=self.themed(BG_CARD2),
                foreground=self.themed(TEXT_MUTED),
                borderwidth=0)
```

Confirm the Forge `tk.Listbox` uses `bg=self.themed(BG_INPUT)`, `fg=self.themed(TEXT_BODY)`, `selectbackground=self.themed(ACCENT)`, `selectforeground=self.themed(ACCENT_TEXT)`, `highlightbackground=self.themed(BORDER)`.

- [ ] **Step 3: Verify launch + theme toggle**

Run: `python gui_premium_v7.py` (or `pythonw`), open Forge, toggle Claro/Oscuro/Sistema.
Expected: Treeview + Listbox recolor to peach selection on near-black, legible in both modes; no traceback.

- [ ] **Step 4: Run suite + commit**

```bash
python -m pytest -q
git add gui_premium_v7.py
git commit -m "style(ui): route ttk/tk widgets to new peach tokens"
```

---

### Task 3: Component kit — header, card, buttons (`styles/components.py`)

**Files:**
- Create: `styles/components.py`
- Test: `tests/test_components.py`

**Interfaces:**
- Consumes: `styles.colors` tokens.
- Produces: `_font(spec) -> dict`; classes `PageHeader(master, kicker, title, description="", action=None)`, `Card(master, title=None)` (exposes `.body` frame), `PrimaryButton(master, **kw)`, `GhostButton(master, **kw)`, `DangerButton(master, **kw)`.

- [ ] **Step 1: Write the failing smoke test**

Create `tests/test_components.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_components.py -v`
Expected: FAIL with `ModuleNotFoundError: styles.components`.

- [ ] **Step 3: Create `styles/components.py`**

```python
"""OOPSIE-style reusable widget kit. All colors from styles.colors tokens."""
import customtkinter as ctk
from styles import colors as C


def _font(spec):
    weight = spec[2] if len(spec) > 2 else "normal"
    return {"family": spec[0], "size": spec[1], "weight": weight}


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", C.ACCENT)
        kw.setdefault("hover_color", C.ACCENT_HOVER)
        kw.setdefault("text_color", C.ACCENT_TEXT)
        kw.setdefault("corner_radius", C.BTN_RADIUS)
        kw.setdefault("height", C.BTN_H)
        kw.setdefault("font", ctk.CTkFont(**_font(C.FONT_H3)))
        super().__init__(master, **kw)


class GhostButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("hover_color", C.SURFACE2)
        kw.setdefault("text_color", C.TEXT_BODY)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", C.LINE)
        kw.setdefault("corner_radius", C.BTN_RADIUS)
        kw.setdefault("height", C.BTN_H)
        kw.setdefault("font", ctk.CTkFont(**_font(C.FONT_H3)))
        super().__init__(master, **kw)


class DangerButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", C.DANGER)
        kw.setdefault("hover_color", C.darken(C.DANGER))
        kw.setdefault("text_color", ("#ffffff", "#ffffff"))
        kw.setdefault("corner_radius", C.BTN_RADIUS)
        kw.setdefault("height", C.BTN_H)
        kw.setdefault("font", ctk.CTkFont(**_font(C.FONT_H3)))
        super().__init__(master, **kw)


class PageHeader(ctk.CTkFrame):
    def __init__(self, master, kicker, title, description="", action=None, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(master, **kw)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=kicker.upper(), anchor="w",
                     font=ctk.CTkFont(**_font(C.FONT_KICKER)),
                     text_color=C.TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(self, text=title, anchor="w",
                     font=ctk.CTkFont(**_font(C.FONT_TITLE)),
                     text_color=C.TEXT_H1).grid(row=1, column=0, sticky="w", pady=(2, 0))
        if description:
            ctk.CTkLabel(self, text=description, anchor="w", justify="left",
                         font=ctk.CTkFont(**_font(C.FONT_DESC)),
                         text_color=C.TEXT_BODY).grid(row=2, column=0, sticky="w", pady=(6, 0))
        if action:
            GhostButton(self, text=action[0], command=action[1], height=34
                        ).grid(row=0, column=1, rowspan=2, sticky="e")


class Card(ctk.CTkFrame):
    def __init__(self, master, title=None, **kw):
        kw.setdefault("fg_color", C.SURFACE)
        kw.setdefault("corner_radius", C.CARD_RADIUS)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", C.LINE)
        super().__init__(master, **kw)
        self.grid_columnconfigure(0, weight=1)
        r = 0
        if title:
            ctk.CTkLabel(self, text=title, anchor="w",
                         font=ctk.CTkFont(**_font(C.FONT_H2)),
                         text_color=C.TEXT_H1).grid(row=0, column=0, sticky="ew",
                                                    padx=20, pady=(18, 0))
            r = 1
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=r, column=0, sticky="nsew", padx=20, pady=18)
        self.body.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(r, weight=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_components.py -v`
Expected: PASS (or SKIP if run headless — acceptable; must PASS on the Windows dev machine).

- [ ] **Step 5: Commit**

```bash
git add styles/components.py tests/test_components.py
git commit -m "feat(ui): add component kit — header, card, buttons"
```

---

### Task 4: Component kit — segmented control, stepper, toggle row

**Files:**
- Modify: `styles/components.py`
- Modify: `tests/test_components.py`

**Interfaces:**
- Produces: `SegmentedControl(master, values, default=None, command=None)` (exposes `.get()`/`.set()` from CTk); `Stepper(master, value=0, min=0, max=999, step=1, command=None)` with `.get() -> int`, `.set(int)`; `ToggleRow(master, label, variable=None)` exposing `.var` (BooleanVar) and `.switch`.

- [ ] **Step 1: Add failing test**

Append to `tests/test_components.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_components.py::test_inputs_construct -v`
Expected: FAIL with `AttributeError: module 'styles.components' has no attribute 'SegmentedControl'`.

- [ ] **Step 3: Append implementations to `styles/components.py`**

```python
class SegmentedControl(ctk.CTkSegmentedButton):
    def __init__(self, master, values, default=None, command=None, **kw):
        kw.setdefault("fg_color", C.SURFACE2)
        kw.setdefault("selected_color", C.ACCENT)
        kw.setdefault("selected_hover_color", C.ACCENT_HOVER)
        kw.setdefault("unselected_color", C.SURFACE2)
        kw.setdefault("unselected_hover_color", C.SURFACE2)
        kw.setdefault("text_color", C.TEXT_BODY)
        kw.setdefault("corner_radius", C.BTN_RADIUS)
        kw.setdefault("font", ctk.CTkFont(**_font(C.FONT_H3)))
        super().__init__(master, values=values, command=command, **kw)
        if default is not None:
            self.set(default)


class Stepper(ctk.CTkFrame):
    def __init__(self, master, value=0, min=0, max=999, step=1, command=None, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(master, **kw)
        self._min, self._max, self._step, self._cmd = min, max, step, command
        self.var = ctk.StringVar(value=str(value))
        GhostButton(self, text="−", width=38, command=self._dec).grid(row=0, column=0)
        self.entry = ctk.CTkEntry(self, textvariable=self.var, width=64, justify="center",
                                  fg_color=C.BG_INPUT, border_color=C.LINE,
                                  corner_radius=C.INPUT_RADIUS)
        self.entry.grid(row=0, column=1, padx=6)
        GhostButton(self, text="+", width=38, command=self._inc).grid(row=0, column=2)

    def get(self):
        try:
            return int(self.var.get())
        except (ValueError, TypeError):
            return self._min

    def set(self, v):
        v = max(self._min, min(self._max, int(v)))
        self.var.set(str(v))
        if self._cmd:
            self._cmd(v)

    def _inc(self):
        self.set(self.get() + self._step)

    def _dec(self):
        self.set(self.get() - self._step)


class ToggleRow(ctk.CTkFrame):
    def __init__(self, master, label, variable=None, **kw):
        kw.setdefault("fg_color", C.SURFACE)
        kw.setdefault("corner_radius", C.BTN_RADIUS)
        super().__init__(master, **kw)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label, anchor="w",
                     font=ctk.CTkFont(**_font(C.FONT_BODY)),
                     text_color=C.TEXT_BODY).grid(row=0, column=0, sticky="w",
                                                  padx=16, pady=12)
        self.var = variable if variable is not None else ctk.BooleanVar(value=False)
        self.switch = ctk.CTkSwitch(self, text="", variable=self.var,
                                    progress_color=C.ACCENT,
                                    button_color=("#ffffff", "#ffffff"))
        self.switch.grid(row=0, column=1, sticky="e", padx=16)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_components.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add styles/components.py tests/test_components.py
git commit -m "feat(ui): add segmented control, stepper, toggle row"
```

---

### Task 5: Component kit — key-value row, dropzone, phone preview, nav item

**Files:**
- Modify: `styles/components.py`
- Modify: `tests/test_components.py`

**Interfaces:**
- Produces: `KeyValueRow(master, key, value, divider=True)` with `.value_lbl`; `Dropzone(master, title, subtitle="", on_browse=None, browse_text="Browse files")`; `PhonePreview(master)` (fixed 9:16 frame); `NavItem(master, text, command=None)` with `.set_active(bool)`.

- [ ] **Step 1: Add failing test**

Append to `tests/test_components.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_components.py::test_rows_zones_construct -v`
Expected: FAIL (`AttributeError: ... 'KeyValueRow'`).

- [ ] **Step 3: Append implementations to `styles/components.py`**

```python
class KeyValueRow(ctk.CTkFrame):
    def __init__(self, master, key, value, divider=True, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(master, **kw)
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=key, anchor="w",
                     font=ctk.CTkFont(**_font(C.FONT_BODY)),
                     text_color=C.TEXT_MUTED).grid(row=0, column=0, sticky="w", pady=10)
        self.value_lbl = ctk.CTkLabel(self, text=value, anchor="e",
                                      font=ctk.CTkFont(**_font(C.FONT_BODY)),
                                      text_color=C.TEXT_H1)
        self.value_lbl.grid(row=0, column=1, sticky="e", pady=10)
        if divider:
            ctk.CTkFrame(self, height=1, fg_color=C.LINE).grid(
                row=1, column=0, columnspan=2, sticky="ew")


class Dropzone(ctk.CTkFrame):
    def __init__(self, master, title, subtitle="", on_browse=None,
                 browse_text="Browse files", **kw):
        kw.setdefault("fg_color", C.SURFACE)
        kw.setdefault("corner_radius", C.CARD_RADIUS)
        kw.setdefault("border_width", 2)
        kw.setdefault("border_color", C.LINE)
        super().__init__(master, **kw)
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(expand=True, pady=40)
        ctk.CTkLabel(inner, text=title, font=ctk.CTkFont(**_font(C.FONT_H2)),
                     text_color=C.TEXT_H1).pack()
        if subtitle:
            ctk.CTkLabel(inner, text=subtitle, font=ctk.CTkFont(**_font(C.FONT_BODY)),
                         text_color=C.TEXT_MUTED).pack(pady=(4, 0))
        ctk.CTkLabel(inner, text="or", font=ctk.CTkFont(**_font(C.FONT_BODY)),
                     text_color=C.TEXT_MUTED).pack(pady=8)
        if on_browse:
            PrimaryButton(inner, text=browse_text, command=on_browse).pack()


class PhonePreview(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", C.BG_CARD2)
        kw.setdefault("corner_radius", 18)
        kw.setdefault("width", 260)
        kw.setdefault("height", 462)   # ~9:16
        super().__init__(master, **kw)
        self.grid_propagate(False)
        self.pack_propagate(False)


class NavItem(ctk.CTkButton):
    def __init__(self, master, text, command=None, **kw):
        kw.setdefault("anchor", "w")
        kw.setdefault("height", 40)
        kw.setdefault("corner_radius", C.BTN_RADIUS)
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("text_color", C.TEXT_BODY)
        kw.setdefault("hover_color", C.SURFACE2)
        kw.setdefault("border_width", 0)
        kw.setdefault("font", ctk.CTkFont(**_font(C.FONT_BODY)))
        super().__init__(master, text=text, command=command, **kw)

    def set_active(self, active):
        if active:
            self.configure(fg_color=C.ACCENT_WEAK, text_color=C.ACCENT)
        else:
            self.configure(fg_color="transparent", text_color=C.TEXT_BODY)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_components.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add styles/components.py tests/test_components.py
git commit -m "feat(ui): add key-value row, dropzone, phone preview, nav item"
```

---

### Task 6: Sidebar redesign (brand tile, groups, active pill, theme toggle)

**Files:**
- Modify: `gui_premium_v7.py` — `_build_sidebar` (~lines 855-917) and the active-item styling in `show_frame` (~lines 968-974).

**Interfaces:**
- Consumes: `NavItem`, tokens. Import at top: `from styles.components import NavItem, GhostButton, PrimaryButton, Card, PageHeader, SegmentedControl, Stepper, ToggleRow, KeyValueRow, Dropzone, PhonePreview` (add the whole kit import once; unused-now names are used by later tasks).
- Produces: `self._nav_btns[key]` now holds `NavItem` instances; `show_frame` toggles active via `NavItem.set_active`.

- [ ] **Step 1: Add the kit import**

At the top of `gui_premium_v7.py`, after the existing `from styles ... import` lines, add:

```python
from styles.components import (
    NavItem, GhostButton, PrimaryButton, DangerButton, Card, PageHeader,
    SegmentedControl, Stepper, ToggleRow, KeyValueRow, Dropzone, PhonePreview,
)
```

- [ ] **Step 2: Replace the brand block**

Replace the current `logo_wrap` block (the `⚡ IG AUTO` / `PRO · v7.0` labels) with a peach monogram tile + name + kicker:

```python
brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
brand.grid(row=0, column=0, padx=16, pady=(20, 10), sticky="ew")
tile = ctk.CTkLabel(brand, text="IA", width=40, height=40,
                    corner_radius=12, fg_color=ACCENT, text_color=ACCENT_TEXT,
                    font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"))
tile.grid(row=0, column=0, rowspan=2, padx=(0, 10))
ctk.CTkLabel(brand, text="IG AUTO PRO", anchor="w",
             font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
             text_color=TEXT_H1).grid(row=0, column=1, sticky="sw")
ctk.CTkLabel(brand, text="AUTOMATION SUITE", anchor="w",
             font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
             text_color=TEXT_MUTED).grid(row=1, column=1, sticky="nw")
```

- [ ] **Step 3: Convert nav items to `NavItem`**

In the nav-group loop, replace the `ctk.CTkButton(...)` construction with:

```python
btn = NavItem(self.sidebar, text=label, command=lambda k=key: self.show_frame(k))
btn.grid(row=row, column=0, padx=10, pady=2, sticky="ew")
self._nav_btns[key] = btn
```

Keep the existing `nav_groups` list and group-header labels unchanged (AI Advisor already absent — do not add it).

- [ ] **Step 4: Update `show_frame` active styling**

Replace the two `.configure(fg_color=..., text_color=...)` calls in `show_frame` with:

```python
if self._active_nav and self._active_nav in self._nav_btns:
    self._nav_btns[self._active_nav].set_active(False)
if name in self._nav_btns:
    self._nav_btns[name].set_active(True)
```

- [ ] **Step 5: Restyle the theme toggle**

Leave `self.theme_seg` (CTkSegmentedButton) but restyle it peach-active:

```python
self.theme_seg = ctk.CTkSegmentedButton(
    self.sidebar, values=["Claro", "Oscuro", "Sistema"],
    command=self._on_theme_change,
    fg_color=SURFACE2, selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
    unselected_color=SURFACE2, text_color=TEXT_BODY,
    font=ctk.CTkFont(family="Segoe UI", size=11), height=30, corner_radius=BTN_RADIUS,
)
```

- [ ] **Step 6: Verify launch**

Run: `python gui_premium_v7.py`
Expected: sidebar shows peach monogram tile + IG AUTO PRO / AUTOMATION SUITE; nav groups render; clicking each item shows its frame and highlights it with a peach pill; theme toggle recolors app; no traceback.

- [ ] **Step 7: Run suite + commit**

```bash
python -m pytest -q
git add gui_premium_v7.py
git commit -m "feat(ui): OOPSIE-style sidebar — brand tile, nav pills, theme toggle"
```

---

### Task 7: Forge screen reskin (PROOF SCREEN — approval gate)

**Files:**
- Modify: `gui_premium_v7.py` — `_build_forge_frame` (lines 3254-3453).

**Interfaces:**
- Consumes: kit from Tasks 3-5. Reuses ALL existing handlers/vars unchanged: `forge_add_videos`, `forge_remove_video`, `forge_preview_metadata`, `forge_reshuffle`, `forge_process`, `self.forge_video_paths`, `self.forge_meta_assignments`, `self.forge_fx_vars`, `self.forge_dist_var`, `self.e_forge_tanda`, `self.c_forge_cat`, `self.e_forge_copies`, `self.e_forge_days`, `self.forge_lbl_count`, `self.forge_lst`, `self.forge_tree`, `self.btn_forge_reshuffle`, `self.btn_forge_process`.

- [ ] **Step 1: Replace the header block**

Replace lines ~3263-3271 (the `header` frame + two labels) with:

```python
PageHeader(f, kicker="CONTENIDO", title="Forge de Metadata",
           description="Inyecta fingerprints iPhone únicos · 276,000 combinaciones disponibles",
           action=("Tanda", self.forge_preview_metadata)
           ).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
```

- [ ] **Step 2: Convert the Videos card buttons**

In `card_vids`, replace the two `ctk.CTkButton(...)` (Agregar / Quitar) with:

```python
PrimaryButton(btn_v, text="＋  Agregar Videos",
              command=self.forge_add_videos).pack(side="left", padx=(0, 8))
GhostButton(btn_v, text="−  Quitar",
            command=self.forge_remove_video).pack(side="left")
```

Keep `card_vids` itself but change its construction to `Card`:  replace `card_vids = ctk.CTkFrame(top, fg_color=BG_CARD, corner_radius=CARD_RADIUS)` — leave as-is (already a card look); only the buttons change. (Do NOT touch `self.forge_lst` / `self.forge_lbl_count`.)

- [ ] **Step 3: Convert Copias / Días to Steppers**

Where `cfg_rows` builds `e_forge_copies` and `e_forge_days` as `CTkEntry`, replace those two rows with `Stepper`s that expose the same read API the handlers expect. Because the handlers read via `self.e_forge_copies.get()`, keep attributes named `e_forge_copies` / `e_forge_days` pointing at the Stepper (its `.get()` returns int; if a handler does `int(self.e_forge_copies.get())`, an int is fine):

```python
# In the current cfg_rows order (tanda=1, cat=2, copies=3, days=4):
self.e_forge_copies = Stepper(card_cfg, value=4, min=1, max=50)
self.e_forge_copies.grid(row=3, column=1, padx=(0, 18), pady=7, sticky="w")
self.e_forge_days = Stepper(card_cfg, value=7, min=1, max=60)
self.e_forge_days.grid(row=4, column=1, padx=(0, 18), pady=7, sticky="w")
```

**Note:** the current default for days is the string `"MAX"`. Preserve that behavior — if the handler special-cases `"MAX"`, keep a `CTkEntry` for `e_forge_days` instead and only convert `e_forge_copies`. Verify by reading `forge_process`/`forge_preview_metadata` before converting; convert only the fields whose handlers do integer parsing.

- [ ] **Step 4: Convert the 8 micro-edit checkboxes + auto-distribute to switches**

Replace the `CTkCheckBox` for `forge_dist_var` and the 8 `CTkCheckBox` effect toggles with `ToggleRow`s, reusing the same `self.forge_dist_var` and `self.forge_fx_vars[key]` BooleanVars (pass them in as `variable=`):

```python
ToggleRow(card_cfg, "Distribuir automáticamente al procesar",
          variable=self.forge_dist_var).grid(row=5, column=0, columnspan=2,
                                             sticky="ew", padx=18, pady=(6, 4))
# effects:
for i, (key, lbl) in enumerate(self.FORGE_FX_DEFS):
    var = tk.BooleanVar(value=True)
    self.forge_fx_vars[key] = var
    ToggleRow(fx_frame, lbl, variable=var).grid(
        row=1 + i, column=0, sticky="ew", pady=3)
```

The 8 effects stay individual switches (do NOT collapse into a Strength preset — that is Phase 2).

- [ ] **Step 5: Convert the bottom action buttons**

Replace the three bottom `ctk.CTkButton(...)` with kit buttons, same commands:

```python
GhostButton(bot, text="👁  Preview Metadata", height=BTN_H_LG,
            command=self.forge_preview_metadata).grid(row=0, column=0, padx=(0, 8))
self.btn_forge_reshuffle = GhostButton(bot, text="🔀  Regenerar Shuffle",
            height=BTN_H_LG, state="disabled", command=self.forge_reshuffle)
self.btn_forge_reshuffle.grid(row=0, column=1, padx=(0, 8))
self.btn_forge_process = PrimaryButton(bot, text="⚡  Procesar Ahora",
            height=BTN_H_LG, state="disabled", command=self.forge_process)
self.btn_forge_process.grid(row=0, column=2, padx=(0, 20))
```

- [ ] **Step 6: Verify launch + Forge flow**

Run: `python gui_premium_v7.py`, open Forge.
Expected: OOPSIE header (kicker/title/desc + Tanda pill); Videos card with peach Agregar; Copias stepper; effects + auto-distribute as switches; Treeview dark with peach selection; Procesar Ahora = peach. Add a video → count updates; Preview Metadata → tree fills; buttons enable. No traceback.

- [ ] **Step 7: Run suite + commit, then STOP for user approval**

```bash
python -m pytest -q
git add gui_premium_v7.py
git commit -m "feat(ui): reskin Forge screen to OOPSIE look (proof screen)"
```

**Gate:** show the reskinned Forge to the user and get approval before rolling the pattern to the remaining screens.

---

### Tasks 8–14: Roll the pattern across the remaining screens

Each screen task follows the **same three moves** proven in Task 7 (its content differs, shown per task):
1. Replace the screen's ad-hoc title/subtitle with a `PageHeader(...)` call (exact call given below).
2. Route primary buttons → `PrimaryButton`, secondary → `GhostButton`, destructive → `DangerButton`.
3. Wrap grouped content in `Card(title=...)`; convert numeric fields → `Stepper`, on/off → `ToggleRow`, label/value readouts → `KeyValueRow`.

Each task ends: `python -m pytest -q` green, launch the screen, verify no traceback, commit `feat(ui): reskin <screen> screen`. Do NOT alter any command handler or variable.

- [ ] **Task 8 — Dashboard** (`_build_dashboard_frame`, ~1160). Header:
  `PageHeader(f, "CONTROL", "Dashboard", "Estado del sistema y actividad reciente.")`
  Wrap stat blocks in `Card`; recolor buttons.

- [ ] **Task 9 — Tandas** (`_build_mix_frame`, ~1976). Header:
  `PageHeader(f, "CONTENIDO", "Tandas", "Lotes de videos forjados listos para distribuir.")`
  Convert list actions to `PrimaryButton`/`GhostButton`; wrap in `Card`.

- [ ] **Task 10 — Logística** (`_build_dist_frame` + `_build_dist_tandas_tab` + `_build_dist_cuentas_tab`, ~2142). Header:
  `PageHeader(f, "DISTRIBUCIÓN", "Logística", "Reparto anti-colisión de tandas entre cuentas y días.")`
  Restyle the distribution `Treeview`s (inherit `Premium.Treeview` from Task 2); buttons to kit. **Anti-collision logic untouched** — only the tables/buttons are restyled.

- [ ] **Task 11 — Cuentas** (`_build_cuentas_frame`, ~3149). Header:
  `PageHeader(f, "DISTRIBUCIÓN", "Cuentas", "Cuentas de Instagram y su estado.")`
  Wrap account panel in `Card`; buttons to kit; call `self._cuentas_panel.refresh()` path unchanged.

- [ ] **Task 12 — Telegram** (`_build_tg_frame`, ~2765). Header:
  `PageHeader(f, "DISTRIBUCIÓN", "Telegram", "Envío programado vía Telegram.")`
  Buttons to kit; wrap config in `Card`; the bright Telegram-blue send button uses `fg_color=TELEGRAM, text_color=("#ffffff","#ffffff")`.

- [ ] **Task 13 — Admin/Equipo** (`_build_team_frame`, ~1398). Header:
  `PageHeader(f, "SISTEMA", "Admin", "Gestión de equipo y configuración.")`
  Wrap in `Card`; buttons to kit.

- [ ] **Task 14 — Actualizaciones/Settings** (`_build_updates_frame`, ~991). Header:
  `PageHeader(f, "APP", "Actualizaciones", "Mantén la app al día.")`
  Adopt OOPSIE Settings layout: a `Card(title="Estado")` with `KeyValueRow`s (versión actual, canal, última comprobación), `PrimaryButton` "Buscar actualizaciones" (command unchanged), and a `KeyValueRow`-style Advanced/paths block if present.

---

### Task 15: Final verification pass

**Files:** none (verification only).

- [ ] **Step 1: Full regression suite**

Run: `python -m pytest -q`
Expected: PASS (including `test_colors.py`, `test_components.py`, and all pre-existing logic/DB tests).

- [ ] **Step 2: Launch checklist**

Run: `python gui_premium_v7.py`. Verify:
- All 8 visible nav items (Forge, Tandas, Logística, Cuentas, Telegram, Dashboard, Admin, Actualizaciones) open without traceback; each shows a `PageHeader`.
- Active nav shows the peach pill.
- Toggle Claro / Oscuro / Sistema — every screen (incl. Forge Listbox + all Treeviews) recolors legibly in both themes.
- Forge: add a video, Preview Metadata fills the tree, buttons enable, Procesar Ahora is peach.

- [ ] **Step 3: Confirm no logic files changed**

Run: `git diff --name-only 0ce16ec..HEAD`
Expected: only `styles/colors.py`, `styles/components.py`, `gui_premium_v7.py`, `tests/test_colors.py`, `tests/test_components.py`, and the two `docs/superpowers/*` files. If `metadata_pool.py`, `database.py`, `videos.py`, `Organizador.py`, `telegram_core.py`, or `updater.py` appear, a logic file was touched — revert those hunks.

- [ ] **Step 4: Final commit (if any verification tweaks were made)**

```bash
git add -A
git commit -m "chore(ui): final OOPSIE reskin verification pass"
```

---

## Self-Review notes

- **Spec coverage:** tokens (Task 1), component kit (Tasks 3-5), sidebar (Task 6), header pattern (all screen tasks), Forge proof (Task 7), remaining screens (8-14), untouched-logic guard (Task 15 Step 3), verification (Task 15). AI Advisor correctly excluded.
- **Light mode:** derived values ship in Task 1; a dedicated polish pass is optional and can be added after Task 15 if contrast needs work (flagged in spec §9).
- **Risk — `e_forge_days == "MAX"`:** Task 7 Step 3 explicitly instructs reading the handler before converting, converting only integer-parsed fields — prevents breaking the "MAX days" behavior.
