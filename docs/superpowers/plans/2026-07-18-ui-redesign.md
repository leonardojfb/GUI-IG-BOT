# IG Auto Pro — UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-skin `gui_premium_v7.py` with a comfortable natural light+dark palette, reorganize the sidebar by workflow, and hide AI Advisor — without touching any business logic.

**Architecture:** Colors are centralized in `styles/colors.py` and referenced by name. Convert every color token from a hex string to a `(light, dark)` tuple; CustomTkinter consumes tuples natively and re-renders on appearance-mode change. A handful of raw Tk/ttk widgets (Treeview style, two Listboxes) cannot read tuples, so they resolve their color through a pure `resolve()` helper and are re-styled on theme switch. Navigation grouping and the theme toggle are localized edits in `gui_premium_v7.py`.

**Tech Stack:** Python 3, CustomTkinter, tkinter/ttk, pytest (optional — tests also run under plain `python`).

## Global Constraints

- **No business-logic / DB / worker changes.** Only `styles/colors.py` and `gui_premium_v7.py` are edited (plus a new `tests/test_colors.py`).
- **CustomTkinter tuple order is `(light, dark)`** — light first, dark second, everywhere.
- **All color tokens keep their existing names** (`BG_APP`, `NEON_CYAN`, `IG_PINK`, …) so no call sites break; values change to tuples. New names are added as aliases.
- **Font family** for all `FONT_*` UI fonts is `"Segoe UI"`; `FONT_MONO` stays `"Consolas"`.
- **Palette values (light / dark)** — copy verbatim:
  - `BG_APP` `#f5f4f0` / `#16181d`
  - `BG_SIDEBAR` `#edece6` / `#1b1e25`
  - `BG_CARD` `#ffffff` / `#22262e`
  - `BG_CARD2` `#f0efe9` / `#2a2f38`
  - `BG_INPUT` `#f3f2ec` / `#262b33`
  - `BORDER` `#e3e1d8` / `#333944`
  - `NEON_CYAN` (accent) `#2f8f7d` / `#4db6a2`
  - `ACCENT_WEAK` (new) `#dcefe9` / `#223a37`
  - `NEON_PURPLE` (muted secondary) `#5b7fb0` / `#7f9fcf`
  - `IG_PINK` `#c9564e` / `#e07a6f`
  - `IG_ORANGE` `#c2872f` / `#e0a94e`
  - `SUCCESS` `#3f9d6d` / `#54b184`
  - `WARNING` `#c2872f` / `#e0a94e`
  - `DANGER` `#c9564e` / `#e07a6f`
  - `INFO` `#4a7fb0` / `#6398c9`
  - `TEXT_H1` `#2a2925` / `#e9eaec`
  - `TEXT_BODY` `#55534c` / `#bdc2ca`
  - `TEXT_MUTED` `#8b887f` / `#7d838d`
- **Run commands from the project root** `Método IG VIDEOS v2.0/`. Use the working `python` on PATH (the `.venv` python is a broken stub).
- **Console-freeze fix is already applied** (`CREATE_NO_WINDOW` in `metadata_pool.py`, `videos.py`, `organizadortg.py`) — do not redo; only confirm it live in Task 5.

---

### Task 1: Palette tokens, resolver, and fonts in `styles/colors.py`

**Files:**
- Modify: `styles/colors.py` (whole token section + fonts, add `resolve()` and new aliases)
- Test: `tests/test_colors.py` (create)

**Interfaces:**
- Produces:
  - Color constants as `(light, dark)` tuples of `#rrggbb` strings: `BG_APP, BG_SIDEBAR, BG_CARD, BG_CARD2, BG_INPUT, BORDER, NEON_CYAN, NEON_PURPLE, IG_PINK, IG_ORANGE, SUCCESS, WARNING, DANGER, INFO, TEXT_H1, TEXT_BODY, TEXT_MUTED`.
  - New alias tuples: `ACCENT = NEON_CYAN`, `ACCENT_WEAK`, `SURFACE = BG_CARD`, `SURFACE2 = BG_CARD2`, `RAIL = BG_SIDEBAR`, `GROUND = BG_APP`, `LINE = BORDER`.
  - `resolve(value, mode) -> str` — pure function returning the light element for non-"dark" modes, the dark element for "dark" (case-insensitive); passes plain strings through unchanged.
  - `FONT_*` families = `"Segoe UI"` (except `FONT_MONO` = `"Consolas"`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_colors.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_colors.py -v` (or `python tests/test_colors.py`)
Expected: FAIL / AttributeError — tokens are still strings, `resolve` and `ACCENT` do not exist.

- [ ] **Step 3: Rewrite the token + font section of `styles/colors.py`**

Replace the color and font sections (the file currently defines each token as a single hex string) with:

```python
# ── Fondos ── (light, dark) ────────────────────────────────────────────────
BG_APP     = ("#f5f4f0", "#16181d")   # Fondo raíz de la ventana
BG_SIDEBAR = ("#edece6", "#1b1e25")   # Panel de navegación lateral
BG_CARD    = ("#ffffff", "#22262e")   # Cards primarias
BG_CARD2   = ("#f0efe9", "#2a2f38")   # Cards secundarias / hover
BG_INPUT   = ("#f3f2ec", "#262b33")   # Campos de entrada
BORDER     = ("#e3e1d8", "#333944")   # Bordes y separadores

# ── Acentos ── (light, dark) ────────────────────────────────────────────────
NEON_CYAN   = ("#2f8f7d", "#4db6a2")  # Acento primario (teal-sage), CTA, nav activo
ACCENT_WEAK = ("#dcefe9", "#223a37")  # Fondo del nav activo
NEON_PURPLE = ("#5b7fb0", "#7f9fcf")  # Acento secundario (slate-blue apagado)
IG_PINK     = ("#c9564e", "#e07a6f")  # Acciones destructivas (rosa apagado)
IG_ORANGE   = ("#c2872f", "#e0a94e")  # Ámbar apagado

# ── Semánticos ── (light, dark) ─────────────────────────────────────────────
SUCCESS = ("#3f9d6d", "#54b184")
WARNING = ("#c2872f", "#e0a94e")
DANGER  = ("#c9564e", "#e07a6f")
INFO    = ("#4a7fb0", "#6398c9")

# ── Tipografía ── (light, dark) ─────────────────────────────────────────────
TEXT_H1    = ("#2a2925", "#e9eaec")   # Títulos
TEXT_BODY  = ("#55534c", "#bdc2ca")   # Cuerpo
TEXT_MUTED = ("#8b887f", "#7d838d")   # Secundario / placeholder

# ── Aliases semánticos (nombres claros para código nuevo) ────────────────────
GROUND      = BG_APP
RAIL        = BG_SIDEBAR
SURFACE     = BG_CARD
SURFACE2    = BG_CARD2
LINE        = BORDER
ACCENT      = NEON_CYAN

# ── Fuentes ──────────────────────────────────────────────────────────────────
FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_H2     = ("Segoe UI", 15, "bold")
FONT_H3     = ("Segoe UI", 12, "bold")
FONT_BODY   = ("Segoe UI", 12)
FONT_SMALL  = ("Segoe UI", 10)
FONT_MONO   = ("Consolas", 10)


def resolve(value, mode):
    """Return the single color for the given CTk appearance mode.

    `value` may be a (light, dark) tuple/list or a plain color string. `mode`
    is a CTk appearance-mode string like "Light"/"Dark"/"System" (case-
    insensitive). Non-"dark" modes resolve to the light color. Plain strings
    pass through unchanged (so callers can pass either form).
    """
    if isinstance(value, (tuple, list)):
        return value[1] if str(mode).lower() == "dark" else value[0]
    return value
```

Keep the component-size constants (`SIDEBAR_W`, `STATUS_H`, `CARD_RADIUS`, `BTN_RADIUS`, `BTN_H`, `BTN_H_LG`) unchanged. Update the module docstring's "dark mode first" line to "natural light + dark".

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_colors.py -v` (or `python tests/test_colors.py`)
Expected: PASS (5 tests / `ALL PASS`).

- [ ] **Step 5: Commit**

```bash
git add styles/colors.py tests/test_colors.py
git commit -m "feat(ui): natural light+dark palette tokens, resolve(), Segoe UI"
```

---

### Task 2: Theme plumbing in `gui_premium_v7.py` (resolver, system mode, raw-Tk routing, toggle)

**Files:**
- Modify: `gui_premium_v7.py` — imports (line ~27), appearance mode (lines 36-37), add `themed()` + `_restyle_raw_tk()` methods, `_setup_treeview_style` (728-741), `list_tg` Listbox (2705-2707), `forge_lst` Listbox (3168-3172), sidebar footer toggle.

**Interfaces:**
- Consumes from Task 1: `resolve`, all token tuples, `ACCENT_WEAK`.
- Produces:
  - `self.themed(value) -> str` — instance method: `return resolve(value, ctk.get_appearance_mode())`.
  - `self._restyle_raw_tk()` — re-applies colors to the ttk Treeview style and both Listboxes for the current mode.
  - `self._apply_theme(mode)` — calls `ctk.set_appearance_mode(mode)` then `self._restyle_raw_tk()`.
  - Sidebar footer theme toggle (segmented control) wired to `self._apply_theme`.

- [ ] **Step 1: Add `resolve` and `ACCENT_WEAK` to the imports**

Modify the `from styles.colors import (...)` block (starts line 27) to include `ACCENT_WEAK` and `resolve`:

```python
from styles.colors import (
    BG_APP, BG_SIDEBAR, BG_CARD, BG_CARD2, BG_INPUT, BORDER,
    NEON_CYAN, NEON_PURPLE, IG_PINK, SUCCESS, WARNING, DANGER, INFO,
    ACCENT_WEAK, resolve,
    TEXT_H1, TEXT_BODY, TEXT_MUTED,
    FONT_TITLE, FONT_H2, FONT_H3, FONT_BODY, FONT_SMALL, FONT_MONO,
    SIDEBAR_W, STATUS_H, CARD_RADIUS, BTN_RADIUS, BTN_H, BTN_H_LG,
)
```

- [ ] **Step 2: Switch to system appearance mode**

Change lines 36-37:

```python
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("dark-blue")
```

- [ ] **Step 3: Add `themed`, `_apply_theme`, and `_restyle_raw_tk` methods**

Add these three methods to the main app class (place them next to `_setup_treeview_style`, i.e. just above line 728):

```python
    def themed(self, value):
        """Resolve a (light, dark) color token to a single color for the
        current appearance mode. Use for raw Tk/ttk widgets that cannot
        consume CustomTkinter tuples."""
        return resolve(value, ctk.get_appearance_mode())

    def _apply_theme(self, mode: str):
        """Switch appearance mode and re-color the raw Tk/ttk widgets that
        do not auto-update. `mode` is 'Light', 'Dark', or 'System'."""
        ctk.set_appearance_mode(mode)
        self._restyle_raw_tk()

    def _restyle_raw_tk(self):
        """Re-apply mode-correct colors to the ttk Treeview style and the
        raw Tk Listboxes (CustomTkinter widgets recolor themselves)."""
        self._setup_treeview_style()
        for lb in (getattr(self, "list_tg", None), getattr(self, "forge_lst", None)):
            if lb is not None:
                lb.configure(
                    bg=self.themed(BG_INPUT), fg=self.themed(TEXT_BODY),
                    selectbackground=self.themed(NEON_PURPLE),
                    highlightbackground=self.themed(BORDER),
                )
```

- [ ] **Step 4: Route `_setup_treeview_style` colors through `themed`**

Replace the body of `_setup_treeview_style` (lines 730-741) with:

```python
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Premium.Treeview",
                        background=self.themed(BG_CARD2), foreground=self.themed(TEXT_BODY),
                        fieldbackground=self.themed(BG_CARD2), rowheight=28,
                        font=FONT_BODY, borderwidth=0)
        style.configure("Premium.Treeview.Heading",
                        background=self.themed(BG_CARD), foreground=self.themed(NEON_CYAN),
                        font=FONT_H3, borderwidth=0, relief="flat")
        style.map("Premium.Treeview",
                  background=[("selected", self.themed(NEON_PURPLE))],
                  foreground=[("selected", self.themed(TEXT_H1))])
```

- [ ] **Step 5: Route the two Listboxes through `themed`**

Replace `list_tg` construction (lines 2705-2707):

```python
        self.list_tg = tk.Listbox(ctrl_card, bg=self.themed(BG_INPUT), fg=self.themed(TEXT_BODY),
                                  selectbackground=self.themed(NEON_PURPLE),
                                  selectmode=tk.EXTENDED,
                                  borderwidth=0, highlightthickness=1,
                                  highlightbackground=self.themed(BORDER), font=FONT_BODY)
```

Replace `forge_lst` construction (lines 3168-3173):

```python
        self.forge_lst = tk.Listbox(
            card_vids, bg=self.themed(BG_INPUT), fg=self.themed(TEXT_BODY),
            selectbackground=self.themed(NEON_PURPLE), selectmode=tk.EXTENDED,
            borderwidth=0, highlightthickness=1, highlightbackground=self.themed(BORDER),
            font=FONT_BODY, height=9
        )
```

- [ ] **Step 6: Add the theme toggle to the sidebar footer (on fixed high rows)**

The grouped nav in Task 3 will occupy more rows than today, so move the footer to fixed high row numbers that the nav can never reach. tkinter grid rows need not be contiguous; a weighted empty row absorbs the slack and pins the footer to the bottom regardless of nav length. Make three edits in `_build_sidebar`:

1. Change the spacer weight (line 750) from `self.sidebar.grid_rowconfigure(11, weight=1)` to:

```python
        self.sidebar.grid_rowconfigure(90, weight=1)
```

2. Re-grid the existing bottom separator (lines 793-794) and bot-status label (line 798) to high rows — change only their `row=` values: the separator to `row=92`, `self.lbl_bot_status` to `row=93`.

3. Insert the theme toggle at `row=91`, just above that separator block:

```python
        # — Selector de tema —
        self.theme_seg = ctk.CTkSegmentedButton(
            self.sidebar, values=["Claro", "Oscuro", "Sistema"],
            command=self._on_theme_change,
            font=ctk.CTkFont(family="Segoe UI", size=11), height=28,
        )
        self.theme_seg.set("Sistema")
        self.theme_seg.grid(row=91, column=0, padx=14, pady=(8, 4), sticky="ew")
```

And add the handler method to the class (next to `_apply_theme`):

```python
    def _on_theme_change(self, choice: str):
        self._apply_theme({"Claro": "Light", "Oscuro": "Dark", "Sistema": "System"}[choice])
```

- [ ] **Step 7: Verify the app launches and toggles in both themes**

Run: `python gui_premium_v7.py`
Expected (manual):
1. App opens following the OS theme (light on a light-themed Windows).
2. Click **Oscuro** → whole UI including the Forge video Listbox, the Telegram Listbox, and any Treeview table recolor to dark with legible text.
3. Click **Claro** → everything returns to the light palette; no leftover neon cyan/purple; no white-on-white or black-on-black anywhere.
4. Click **Sistema** → matches OS.
Close the window to end.

- [ ] **Step 8: Commit**

```bash
git add gui_premium_v7.py
git commit -m "feat(ui): light+dark theme plumbing, resolver for raw-Tk widgets, theme toggle"
```

---

### Task 3: Reorganize the sidebar navigation and hide AI Advisor

**Files:**
- Modify: `gui_premium_v7.py` — `_build_sidebar` nav section (lines 767-790).

**Interfaces:**
- Consumes from Task 2: `ACCENT_WEAK` import, `self._nav_btns`, `show_frame`.
- Produces: grouped nav with non-clickable headers; AI Advisor button absent; active-item styling via `ACCENT_WEAK` + `NEON_CYAN`.

- [ ] **Step 1: Replace the flat nav loop with grouped rendering**

Replace the nav block (lines 767-790, from `# — Botones de navegación —` through the `self._nav_btns[key] = btn` loop) with:

```python
        # — Navegación agrupada por flujo de trabajo —
        nav_groups = [
            ("Contenido",    [("🔮   Forge", "Forge"), ("🎬   Tandas", "Tandas")]),
            ("Distribución", [("🚀   Logística", "Logistica"), ("📡   Cuentas", "Cuentas"),
                              ("📲   Telegram", "Telegram")]),
            ("Control",      [("📊   Dashboard", "Dashboard")]),
            ("Sistema",      [("⚙️   Admin", "Equipo"), ("⬇   Actualizaciones", "Actualizaciones")]),
        ]
        self._nav_btns = {}
        row = 2
        for group_name, items in nav_groups:
            ctk.CTkLabel(self.sidebar, text=group_name.upper(), anchor="w",
                         font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                         text_color=TEXT_MUTED).grid(row=row, column=0, padx=18,
                                                     pady=(10, 2), sticky="w")
            row += 1
            for label, key in items:
                btn = ctk.CTkButton(
                    self.sidebar, text=label, anchor="w",
                    height=40, corner_radius=BTN_RADIUS,
                    font=ctk.CTkFont(family="Segoe UI", size=13),
                    fg_color="transparent", text_color=TEXT_BODY,
                    hover_color=BG_CARD2, border_width=0,
                    command=lambda k=key: self.show_frame(k)
                )
                btn.grid(row=row, column=0, padx=10, pady=2, sticky="ew")
                self._nav_btns[key] = btn
                row += 1
```

The grouped nav occupies rows 2..~15 — safely below the footer rows (90-93) fixed in Task 2. No footer changes are needed here.

- [ ] **Step 2: Update the active-item highlight color in `show_frame`**

`show_frame` (line 849) already highlights the active nav button. It currently sets the active button to `fg_color=BG_CARD2`. Change only that color to `ACCENT_WEAK`. Replace lines 853-855:

```python
        if name in self._nav_btns:
            self._nav_btns[name].configure(
                fg_color=ACCENT_WEAK, text_color=NEON_CYAN)
```

The reset-of-previous branch (lines 850-852, sets `fg_color="transparent"`) stays as-is. AI Advisor's key `"AIAdvisor"` is not in `self._nav_btns`, so the `if name in self._nav_btns` guard already makes it a no-op if ever called — nothing breaks; `_build_content_area` still builds its (dormant) frame.

- [ ] **Step 4: Verify navigation**

Run: `python gui_premium_v7.py`
Expected (manual):
1. Sidebar shows four uppercase group labels: CONTENIDO, DISTRIBUCIÓN, CONTROL, SISTEMA.
2. Items appear under the right groups; **AI Advisor is absent**.
3. Clicking each item opens its screen; the active item shows the teal `ACCENT_WEAK` highlight.
4. Theme toggle + bot status sit pinned at the bottom.
5. No traceback on launch or navigation.

- [ ] **Step 5: Commit**

```bash
git add gui_premium_v7.py
git commit -m "feat(ui): group sidebar by workflow, hide AI Advisor, active-item highlight"
```

---

### Task 4: Consistency polish pass

**Files:**
- Modify: `gui_premium_v7.py` — destructive buttons and any lingering neon accent usages.

**Interfaces:**
- Consumes: existing tokens. No new interfaces.

- [ ] **Step 1: Find destructive / delete actions still using a bright accent**

Run: `git grep -n "IG_PINK\|NEON_PURPLE" gui_premium_v7.py`
Review each hit. For **destructive** buttons/labels (delete, eliminar, suicide, ban) the color should be `DANGER`. `NEON_PURPLE` used purely as a decorative secondary can stay (now a muted slate-blue). Do not change Listbox `selectbackground` (already routed through `themed` in Task 2).

- [ ] **Step 2: Apply DANGER to destructive controls**

For each destructive control found, set its `fg_color=DANGER` (buttons) or `text_color=DANGER` (labels). Example pattern (apply only where the action is destructive):

```python
# before: fg_color=IG_PINK
# after:
fg_color=DANGER
```

Leave non-destructive uses unchanged.

- [ ] **Step 3: Verify visually**

Run: `python gui_premium_v7.py`
Expected (manual): destructive buttons read as muted rose (`DANGER`) in both themes; no harsh neon remains; primary CTAs are teal (`NEON_CYAN`). Toggle both themes and confirm contrast is comfortable.

- [ ] **Step 4: Commit**

```bash
git add gui_premium_v7.py
git commit -m "style(ui): unify destructive controls on DANGER, drop leftover neon"
```

---

### Task 5: Full verification + live console-fix confirmation

**Files:** none (verification only).

- [ ] **Step 1: Run the color unit tests**

Run: `python -m pytest tests/test_colors.py -v` (or `python tests/test_colors.py`)
Expected: all pass.

- [ ] **Step 2: Regression sweep of every screen**

Run: `python gui_premium_v7.py`
Expected (manual): open each nav screen (Forge, Tandas, Logística, Cuentas, Telegram, Dashboard, Admin, Actualizaciones). No traceback; every screen legible in both Claro and Oscuro; tables and listboxes correctly colored.

- [ ] **Step 3: Live console-fix confirmation (requires FFmpeg on PATH)**

In Forge: add a couple of short videos, set **Copias por vídeo = 5**, generate preview, then Procesar.
Expected: processing completes and **no console windows flash open/closed** during FFmpeg work. The PC stays usable throughout.

- [ ] **Step 4: Final commit if any fixups were needed**

```bash
git add -A
git commit -m "test(ui): verify redesign across screens and live Forge run"
```

---

## Notes for the implementer

- The `.venv` python is a broken stub (points at a missing `C:\Python314`). Use the `python` already on PATH.
- If `pytest` is not installed, run the test file directly: `python tests/test_colors.py` (it has a `__main__` runner).
- CustomTkinter `(light, dark)` tuples auto-switch on `set_appearance_mode`; only the ttk Treeview style and the two `tk.Listbox` widgets need the manual `_restyle_raw_tk()` re-color — that is the whole reason the resolver exists.
- Do not delete the AI Advisor frame or its builder; it stays dormant so it can be re-enabled by adding one nav entry back.
