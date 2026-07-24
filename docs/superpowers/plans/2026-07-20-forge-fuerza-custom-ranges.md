# FORGE Fuerza=Custom Per-Effect Ranges — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn FORGE's `Fuerza=Custom` into a full manual panel — a global intensity slider plus an editable min–max range per effect — so each effect's magnitude is set in measurable numbers while the engine still randomizes per copy.

**Architecture:** `generate_variant_params` gains an `overrides` dict of per-effect base ranges that replace the hardcoded defaults before strength-scaling; a pure `parse_custom_ranges` helper validates the UI entries; the Forge `Fuerza=Custom` reveal becomes a panel (slider + 10 min–max entry pairs + mirror on/off).

**Tech Stack:** Python 3, CustomTkinter, pytest. No new dependencies.

## Global Constraints

- Work on the existing branch `feature/forge-efectos-fuerza` (extends PR #3). Repo root: `Método IG VIDEOS v2.0/`.
- Only `metadata_pool.py` and `gui_premium_v7.py` (+ the two existing test files) change. No new deps.
- `overrides=None` MUST reproduce the current behavior exactly (same value bounds AND same RNG call order). Range computation must stay pure (no `rng` calls), so the dict-evaluation RNG order is unchanged.
- Axes stay independent: `enabled` (Efectos) gates on/off; `strength` (Fuerza) + `overrides` (Fuerza=Custom rows) control magnitude. Ranges apply only to enabled effects.
- Override base range `(lo,hi)` replaces the default; strength then scales deviation from neutral: `scaled = neutral + (bound − neutral) * strength`. Neutrals: crop 0, zoom 1.0, rotate 0, brightness 0, contrast 1.0, saturation 1.0, gamma 1.0, noise 0, speed 1.0, trim 0.
- Override param keys: `crop, zoom, rotate, brightness, contrast, saturation, gamma, noise, speed, trim` (10). Mirror has NO range — it is on/off via `enabled["mirror"]`.
- `fuerza_to_strength("Custom", pct)` changes to `round(pct/50.0, 3)` (0→0.0, 50→1.0, 100→2.0). Non-Custom levels unchanged (Default/Medio=1.0, Light=0.5, Alto=2.4).
- Values are edited in engine units directly (zoom is a factor like 1.05, not a %). No unit conversion.
- When `Fuerza=Custom`, the panel's mirror on/off is authoritative: `enabled["mirror"]` = panel toggle. Noise still floored at 4; probability still `min(1.0, base·strength)`.

---

### Task 1: `overrides` in the variant engine

**Files:**
- Modify: `metadata_pool.py` — `generate_variant_params`, `apply_variant_and_metadata`
- Test: `tests/test_variant_strength.py` (add cases)

**Interfaces:**
- Consumes: existing `generate_variant_params(rng, enabled, strength)`.
- Produces: `generate_variant_params(rng=None, enabled=None, strength=1.0, overrides=None) -> dict`; `apply_variant_and_metadata(..., strength=1.0, overrides=None)`.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_variant_strength.py`:

```python
def test_overrides_none_matches_default_bounds():
    ps = _samples(1.0)  # overrides defaults to None
    assert all(2 <= p["crop_px"] <= 10 for p in ps)
    assert all(0.94 <= p["contrast"] <= 1.06 for p in ps)


def test_override_widens_only_its_param():
    r = random.Random(7)
    ps = [generate_variant_params(r, strength=1.0, overrides={"crop": (0, 30)}) for _ in range(400)]
    assert any(p["crop_px"] > 10 for p in ps)          # crop range widened
    assert all(p["crop_px"] <= 30 for p in ps)
    assert all(0.94 <= p["contrast"] <= 1.06 for p in ps)  # untouched param unchanged


def test_override_narrows_range():
    r = random.Random(7)
    ps = [generate_variant_params(r, strength=1.0, overrides={"rotate": (-0.2, 0.2)}) for _ in range(400)]
    assert all(-0.2 <= p["rotate_deg"] <= 0.2 for p in ps)


def test_strength_still_scales_an_override():
    r = random.Random(7)
    ps = [generate_variant_params(r, strength=2.0, overrides={"crop": (0, 10)}) for _ in range(400)]
    assert any(p["crop_px"] > 10 for p in ps)          # 0..10 base scaled by 2.0 -> up to ~20


def test_override_trim_respects_min():
    r = random.Random(7)
    ps = [generate_variant_params(r, strength=1.0, overrides={"trim": (100, 150)}) for _ in range(400)]
    assert all(100 <= p["trim_start_ms"] <= 150 for p in ps)
    assert all(100 <= p["trim_end_ms"] <= 150 for p in ps)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_variant_strength.py -k override -v`
Expected: FAIL — `generate_variant_params()` got an unexpected keyword argument `overrides`.

- [ ] **Step 3: Replace `generate_variant_params` with override-aware version**

Replace the whole function body in `metadata_pool.py` (extend the docstring to mention `overrides`; keep dict key order):

```python
def generate_variant_params(
    rng: "random.Random | None" = None,
    enabled: "dict | None" = None,
    strength: float = 1.0,
    overrides: "dict | None" = None,
) -> dict:
    """
    Sortea micro-ediciones. `enabled` prende/apaga cada efecto; `strength` escala
    la magnitud (desde el neutro) y la probabilidad de disparo; `overrides`
    (dict param->(lo,hi) en unidades del motor) reemplaza el rango base de ese
    param antes de escalar por strength. strength=1.0 y overrides=None reproducen
    el comportamiento histórico exacto.
    """
    r = rng or random
    en = {**DEFAULT_VARIANT_EFFECTS, **(enabled or {})}
    s = max(0.0, float(strength))
    ov = overrides or {}

    def fires(p: float) -> bool:
        return r.random() < min(1.0, p * s)

    def base(param: str, lo: float, hi: float, neutral: float):
        # override reemplaza el rango base; strength escala la desviación del neutro.
        if param in ov:
            lo, hi = ov[param]
        return neutral + (lo - neutral) * s, neutral + (hi - neutral) * s

    crop_lo, crop_hi = base("crop", 2, 10, 0)
    zoom_lo, zoom_hi = base("zoom", 1.0, 1.05, 1.0)
    rot_lo, rot_hi   = base("rotate", -1.5, 1.5, 0)
    br_lo, br_hi     = base("brightness", -0.03, 0.03, 0)
    co_lo, co_hi     = base("contrast", 0.94, 1.06, 1.0)
    sa_lo, sa_hi     = base("saturation", 0.90, 1.10, 1.0)
    ga_lo, ga_hi     = base("gamma", 0.95, 1.05, 1.0)
    no_lo, no_hi     = base("noise", 4, 8, 0)
    sp_lo, sp_hi     = base("speed", 0.985, 1.015, 1.0)
    tr_lo, tr_hi     = base("trim", 0, 150, 0)

    return {
        "crop_px":       r.randint(round(crop_lo), round(crop_hi)) if en["crop"] else 0,
        "mirror":        bool(en["mirror"] and fires(0.5)),
        "zoom_pct":      r.uniform(zoom_lo, zoom_hi) if (en["zoom"] and fires(0.7)) else 1.0,
        "rotate_deg":    r.uniform(rot_lo, rot_hi) if (en["rotate"] and fires(0.6)) else 0.0,
        "brightness":    r.uniform(br_lo, br_hi) if en["color"] else 0.0,
        "contrast":      r.uniform(co_lo, co_hi) if en["color"] else 1.0,
        "saturation":    r.uniform(sa_lo, sa_hi) if en["color"] else 1.0,
        "gamma":         r.uniform(ga_lo, ga_hi) if en["color"] else 1.0,
        "noise":         max(4, r.randint(round(no_lo), round(no_hi))) if (en["noise"] and fires(0.4)) else 0,
        "speed":         r.uniform(sp_lo, sp_hi) if (en["speed"] and fires(0.5)) else 1.0,
        "trim_start_ms": r.randint(round(tr_lo), round(tr_hi)) if en["trim"] else 0,
        "trim_end_ms":   r.randint(round(tr_lo), round(tr_hi)) if en["trim"] else 0,
    }
```

Note: `base()` performs no `rng` calls, so the RNG sequence at `overrides=None` is unchanged; at `strength=1.0, overrides=None`, `base(...)` returns the literal defaults, reproducing the historical bounds. (`trim` now honors its lower bound — at the default `(0,150)` that is `randint(0, 150)`, identical to before.)

- [ ] **Step 4: Thread `overrides` through `apply_variant_and_metadata`**

Add `overrides: "dict | None" = None` as the last parameter of `apply_variant_and_metadata`, and change its `params = generate_variant_params(rng, enabled, strength)` call to:

```python
    params = generate_variant_params(rng, enabled, strength, overrides)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_variant_strength.py -v` (all pass, incl. the pre-existing regression tests) and `python -m py_compile metadata_pool.py`.

- [ ] **Step 6: Commit**

```bash
git add metadata_pool.py tests/test_variant_strength.py
git commit -m "feat(forge): per-effect range overrides in variant engine"
```

---

### Task 2: `parse_custom_ranges` helper + Custom slider remap

**Files:**
- Modify: `metadata_pool.py` (add `parse_custom_ranges`; change `fuerza_to_strength` Custom branch)
- Modify: `tests/test_forge_presets.py` (add parse tests; update the Custom-slider test)

**Interfaces:**
- Produces: `parse_custom_ranges(raw: dict) -> dict[str, tuple[float,float]]`; `fuerza_to_strength("Custom", pct)` now returns `round(pct/50.0, 3)`.

- [ ] **Step 1: Update/add failing tests**

In `tests/test_forge_presets.py`, REPLACE the existing `test_fuerza_custom_slider_maps_0_to_100` with:

```python
def test_fuerza_custom_slider_maps_around_neutral():
    from metadata_pool import fuerza_to_strength
    assert fuerza_to_strength("Custom", 0) == 0.0
    assert fuerza_to_strength("Custom", 50) == 1.0
    assert fuerza_to_strength("Custom", 100) == 2.0
```

and add:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_forge_presets.py -k "parse_custom or custom_slider" -v`
Expected: FAIL — `cannot import name 'parse_custom_ranges'` and the slider assertions differ.

- [ ] **Step 3: Change `fuerza_to_strength` Custom branch + add `parse_custom_ranges`**

In `metadata_pool.py`, in `fuerza_to_strength`, replace the `Custom` branch body:

```python
    if level == "Custom":
        pct = max(0.0, min(100.0, float(slider_pct)))
        return round(pct / 50.0, 3)
```

Add near the other helpers:

```python
def parse_custom_ranges(raw: "dict | None") -> dict:
    """Valida las entradas min/max del panel Fuerza=Custom.
    `raw` = {param: (min_str, max_str)}. Devuelve {param: (lo, hi)} float.
    Omite un param si algún lado es vacío/inválido; ordena lo<=hi."""
    out = {}
    for param, pair in (raw or {}).items():
        try:
            lo = float(str(pair[0]).strip())
            hi = float(str(pair[1]).strip())
        except (TypeError, ValueError, IndexError):
            continue
        if lo > hi:
            lo, hi = hi, lo
        out[param] = (lo, hi)
    return out
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_forge_presets.py -v` (all pass) and `python -m pytest -q` (full suite pass).

- [ ] **Step 5: Commit**

```bash
git add metadata_pool.py tests/test_forge_presets.py
git commit -m "feat(forge): parse_custom_ranges + neutral-centered Custom slider"
```

---

### Task 3: Forge UI — Fuerza=Custom panel

**Files:**
- Modify: `gui_premium_v7.py` — `_build_forge_frame` (the Fuerza=Custom reveal), `_forge_on_fuerza_change`, `forge_process`.

**Interfaces:**
- Consumes: `parse_custom_ranges`, `fuerza_to_strength`, `efectos_to_enabled`, `generate_variant_params`/`apply_variant_and_metadata(..., overrides=)` from Tasks 1-2.
- Produces: `self.forge_custom_panel` (the reveal container), `self.forge_range_entries` (dict `param -> (min_entry, max_entry)`), `self.forge_custom_mirror_var` (BooleanVar). `self.forge_strength_slider` moves inside the panel.

- [ ] **Step 1: Locate the current Fuerza reveal**

Run: `grep -nE "forge_strength_slider|_forge_on_fuerza_change|_forge_strength_row|def forge_process|efectos_to_enabled|fuerza_to_strength|apply_variant_and_metadata" gui_premium_v7.py`
Read `_forge_on_fuerza_change` (currently grids/ungrids just `self.forge_strength_slider`) and the `forge_process` block that computes `fx_enabled`/`forge_strength`.

- [ ] **Step 2: Build the Custom panel in `_build_forge_frame`**

Where `self.forge_strength_slider` is currently created, replace that single-slider creation with a panel frame that holds the slider, the 10 min–max rows, and the mirror toggle. Add this near the top of `_build_forge_frame` (module-level constant above the class is fine too):

```python
        FORGE_RANGE_ROWS = [
            ("crop",       "Recorte (px)",   "2",     "10"),
            ("zoom",       "Zoom (factor)",  "1.00",  "1.05"),
            ("rotate",     "Rotación (°)",   "-1.5",  "1.5"),
            ("brightness", "Brillo (Δ)",     "-0.03", "0.03"),
            ("contrast",   "Contraste (×)",  "0.94",  "1.06"),
            ("saturation", "Saturación (×)", "0.90",  "1.10"),
            ("gamma",      "Gamma (×)",      "0.95",  "1.05"),
            ("noise",      "Grano",          "4",     "8"),
            ("speed",      "Velocidad (×)",  "0.985", "1.015"),
            ("trim",       "Trim (ms)",      "0",     "150"),
        ]
        self.forge_custom_panel = ctk.CTkFrame(card_cfg, fg_color="transparent")
        self.forge_custom_panel.grid_columnconfigure(2, weight=1)
        self._forge_custom_row = <PANEL_ROW>   # grid row inside card_cfg (reuse the old slider row)

        ctk.CTkLabel(self.forge_custom_panel, text="Intensidad general", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))
        self.forge_strength_slider = ctk.CTkSlider(self.forge_custom_panel, from_=0, to=100, number_of_steps=100)
        self.forge_strength_slider.set(50)
        self.forge_strength_slider.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        self.forge_range_entries = {}
        for i, (param, label, dmin, dmax) in enumerate(FORGE_RANGE_ROWS):
            rr = 2 + i
            ctk.CTkLabel(self.forge_custom_panel, text=label, text_color=TEXT_BODY,
                         font=ctk.CTkFont(size=11)).grid(row=rr, column=0, sticky="w", pady=2)
            e_min = ctk.CTkEntry(self.forge_custom_panel, width=64, fg_color=BG_INPUT, border_color=BORDER)
            e_min.insert(0, dmin)
            e_min.grid(row=rr, column=1, padx=(8, 4), pady=2)
            e_max = ctk.CTkEntry(self.forge_custom_panel, width=64, fg_color=BG_INPUT, border_color=BORDER)
            e_max.insert(0, dmax)
            e_max.grid(row=rr, column=2, sticky="w", padx=(4, 0), pady=2)
            self.forge_range_entries[param] = (e_min, e_max)

        self.forge_custom_mirror_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.forge_custom_panel, text="Espejo horizontal",
                        variable=self.forge_custom_mirror_var,
                        font=ctk.CTkFont(size=11), text_color=TEXT_BODY).grid(
                            row=2 + len(FORGE_RANGE_ROWS), column=0, columnspan=3, sticky="w", pady=(6, 0))
```

Replace `<PANEL_ROW>` with the grid row the old slider used (`self._forge_strength_row`). Remove the old standalone `self.forge_strength_slider = ctk.CTkSlider(card_cfg, ...)` / `self._forge_strength_row = ...` lines that Task 3 of the prior feature added — the slider now lives inside `self.forge_custom_panel`.

- [ ] **Step 3: Update `_forge_on_fuerza_change` to reveal the panel**

Replace its body so Custom grids/ungrids the whole panel:

```python
def _forge_on_fuerza_change(self, level: str) -> None:
    self.forge_fuerza_var.set(level)
    if level == "Custom":
        self.forge_custom_panel.grid(row=self._forge_custom_row, column=0, columnspan=2,
                                     sticky="ew", padx=18, pady=(0, 6))
    elif self.forge_custom_panel.winfo_manager():
        self.forge_custom_panel.grid_remove()
```

The existing trailing `self._forge_on_fuerza_change("Default")` call in `_build_forge_frame` now hides the whole panel at startup — keep it.

- [ ] **Step 4: Wire `forge_process`**

Replace the strength/enabled computation added by the prior feature with the Custom-aware version:

```python
fx_vals = {key: var.get() for key, var in self.forge_fx_vars.items()}
fx_enabled = metadata_pool.efectos_to_enabled(self.forge_efectos_var.get(), fx_vals)
fuerza_level = self.forge_fuerza_var.get()
if fuerza_level == "Custom":
    forge_strength = metadata_pool.fuerza_to_strength("Custom", self.forge_strength_slider.get())
    forge_overrides = metadata_pool.parse_custom_ranges(
        {p: (mn.get(), mx.get()) for p, (mn, mx) in self.forge_range_entries.items()})
    fx_enabled["mirror"] = bool(self.forge_custom_mirror_var.get())
else:
    forge_strength = metadata_pool.fuerza_to_strength(fuerza_level)
    forge_overrides = None
```

and change the `apply_variant_and_metadata(...)` call to pass both:

```python
metadata_pool.apply_variant_and_metadata(vid_path, out_path, meta,
                                         enabled=fx_enabled, strength=forge_strength,
                                         overrides=forge_overrides)
```

- [ ] **Step 5: Verify (headless — do NOT launch the GUI)**

Run: `python -m py_compile gui_premium_v7.py` (no output) and `python -m pytest -q` (all pass). Visual verification (Fuerza=Custom reveals slider + 10 rows + mirror toggle) is the user's manual pass.

- [ ] **Step 6: Commit**

```bash
git add gui_premium_v7.py
git commit -m "feat(forge): Fuerza=Custom panel with per-effect min-max ranges"
```

---

### Task 4: Final verification

**Files:** none.

- [ ] **Step 1: Full suite + compile**

Run: `python -m pytest -q` (all pass) and `python -m py_compile gui_premium_v7.py metadata_pool.py`.

- [ ] **Step 2: Scope guard**

Run: `git diff --name-only 177ec2e..HEAD`
Expected: only `metadata_pool.py`, `gui_premium_v7.py`, `tests/test_variant_strength.py`, `tests/test_forge_presets.py` (+ `docs/superpowers/*` if committed). No other file.

- [ ] **Step 3: Manual visual checklist (user)**

Launch, open Forge, set Fuerza=Custom: confirm the panel shows the intensity slider + 10 min–max rows (pre-filled) + an "Espejo horizontal" checkbox. Edit e.g. Recorte to `0`–`30`, run a small batch → visibly stronger crop variation; set Recorte to `0`–`0` → no crop. Set Fuerza back to Medio → panel hides, default behavior returns.

---

## Self-Review notes

- **Spec coverage:** overrides in engine (Task 1) with `overrides=None` regression; `parse_custom_ranges` + neutral-centered Custom slider (Task 2); the panel (slider + 10 rows + mirror on/off) and forge_process wiring incl. mirror-authoritative-in-Custom (Task 3); scope guard (Task 4).
- **RNG order:** `base()` is pure (no rng), inserted before the dict; the dict keeps its key order and one rng call per field, so `overrides=None, strength=1.0` stays byte-identical — asserted by the pre-existing regression tests plus `test_overrides_none_matches_default_bounds`.
- **Byte-identity scope (post-review clarification):** the byte-for-byte guarantee is exact only at `strength=1.0`. At other strengths the neutral=1.0 params (zoom, contrast, saturation, gamma, speed) can differ from the pre-refactor values by ≤1 ULP (~1e-16), because `base()` reassociates the float arithmetic (`neutral + (bound − neutral)·s` vs the old `1.0 ± c·s`). This drift is erased by FFmpeg filter formatting (`.4f` / integer pixel rounding), so the RNG call order AND the rendered output stay identical at every strength, and the raw param dict is never persisted. Do NOT add a byte-identity regression test at `strength ≠ 1.0` — it would fail on this immaterial drift, not a real behavior change.
- **Placeholder note:** `<PANEL_ROW>` in Task 3 Step 2 is the grid row to reuse from the prior feature's slider (`self._forge_strength_row`) — a value to read from the current file, not a code placeholder.
- **Type consistency:** `overrides` is `dict[str,(float,float)]` everywhere; `parse_custom_ranges` returns exactly that; `forge_process` builds it from the entry pairs and passes `overrides=` through `apply_variant_and_metadata` to `generate_variant_params`.
