# FORGE "Efectos" + "Fuerza" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give FORGE two independent controls — **Efectos** (which micro-effects apply) and **Fuerza** (how intense/random they are) — over the existing video variant engine.

**Architecture:** The variant engine `generate_variant_params` gains a `strength` float that scales every effect's magnitude and firing probability; two pure preset-mapping helpers translate the UI axis levels into the `enabled` dict and the `strength` float. The Forge screen gets two `SegmentedControl`s (`Default/Light/Medio/Alto/Custom`); `Efectos=Custom` reveals the existing 8 on/off toggles, `Fuerza=Custom` reveals a 0–100% slider.

**Tech Stack:** Python 3, CustomTkinter, pytest. No new dependencies.

## Global Constraints

- Changes limited to `metadata_pool.py` (variant engine + preset maps) and `gui_premium_v7.py` (Forge UI). No new dependencies.
- Reuse the existing `generate_variant_params` / `apply_variant_and_metadata` / `forge_fx_vars` / kit `SegmentedControl`. Do not touch the ffmpeg filter builder, the `-c copy` fast path, or the even-dimension guard.
- `strength=1.0` MUST reproduce the historical behavior (same value bounds and same RNG call order), so a seeded run at `strength=1.0` is byte-identical to today.
- The two axes are **independent**: `enabled` (from Efectos) and `strength` (from Fuerza) never derive from each other.
- Effect presets (exact sets): **Default** = `{crop, zoom, rotate, color, noise, speed, trim}` (7, no mirror); **Light** = `{color, trim}`; **Medio** = `{crop, color, noise, speed, trim}` (5); **Alto** = all 8; **Custom** = the 8 manual toggles.
- Fuerza presets: **Default**=1.0, **Light**=0.5, **Medio**=1.0, **Alto**=2.4, **Custom**=`0.3 + 0.022*pct` for slider pct∈[0,100].
- Probability scaling is `min(1.0, base_prob * strength)`; magnitude scaling is `neutral + (bound − neutral) * strength`; `noise` is floored at 4 when it fires.
- The only intentional default-behavior change: **Efectos=Default excludes `mirror`** (was on at 50%). Everything else at default (`Fuerza=Default`=1.0) is unchanged.
- Branch off `main` (currently v1.0.8) before starting: `git checkout -b feature/forge-efectos-fuerza main`. Repo root is `Método IG VIDEOS v2.0/`.

---

### Task 1: `strength` parameter in the variant engine

**Files:**
- Modify: `metadata_pool.py` — `generate_variant_params` and `apply_variant_and_metadata`
- Test: `tests/test_variant_strength.py` (create)

**Interfaces:**
- Consumes: existing `DEFAULT_VARIANT_EFFECTS` (dict of 8 keys→bool) and `generate_variant_params(rng=None, enabled=None)`.
- Produces: `generate_variant_params(rng=None, enabled=None, strength=1.0) -> dict` (same 12 keys as today); `apply_variant_and_metadata(input_path, output_path, meta, rng=None, enabled=None, strength=1.0) -> dict`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_variant_strength.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_variant_strength.py -v`
Expected: FAIL — `generate_variant_params()` got an unexpected keyword argument `strength`.

- [ ] **Step 3: Add `strength` to `generate_variant_params`**

Replace the body of `generate_variant_params` in `metadata_pool.py` with this (keep the existing docstring, extend it to mention `strength`; keep the same key order so the RNG call sequence at `strength=1.0` is unchanged):

```python
def generate_variant_params(
    rng: "random.Random | None" = None,
    enabled: "dict | None" = None,
    strength: float = 1.0,
) -> dict:
    """
    Sortea una combinación de micro-ediciones. `enabled` (claves de
    DEFAULT_VARIANT_EFFECTS) prende/apaga cada efecto. `strength` (float, default
    1.0) escala la magnitud de cada rango desde su valor neutro y la probabilidad
    de disparo de los efectos probabilísticos; strength=1.0 reproduce el
    comportamiento histórico exacto.
    """
    r = rng or random
    en = {**DEFAULT_VARIANT_EFFECTS, **(enabled or {})}
    s = max(0.0, float(strength))

    def fires(p: float) -> bool:
        return r.random() < min(1.0, p * s)

    return {
        "crop_px":       r.randint(round(2 * s), round(10 * s)) if en["crop"] else 0,
        "mirror":        bool(en["mirror"] and fires(0.5)),
        "zoom_pct":      r.uniform(1.0, 1.0 + 0.05 * s) if (en["zoom"] and fires(0.7)) else 1.0,
        "rotate_deg":    r.uniform(-1.5 * s, 1.5 * s) if (en["rotate"] and fires(0.6)) else 0.0,
        "brightness":    r.uniform(-0.03 * s, 0.03 * s) if en["color"] else 0.0,
        "contrast":      r.uniform(1.0 - 0.06 * s, 1.0 + 0.06 * s) if en["color"] else 1.0,
        "saturation":    r.uniform(1.0 - 0.10 * s, 1.0 + 0.10 * s) if en["color"] else 1.0,
        "gamma":         r.uniform(1.0 - 0.05 * s, 1.0 + 0.05 * s) if en["color"] else 1.0,
        # Piso 4: niveles 2-3 quedan casi borrados por la compresión CRF 20.
        "noise":         max(4, r.randint(round(4 * s), round(8 * s))) if (en["noise"] and fires(0.4)) else 0,
        "speed":         r.uniform(1.0 - 0.015 * s, 1.0 + 0.015 * s) if (en["speed"] and fires(0.5)) else 1.0,
        "trim_start_ms": r.randint(0, round(150 * s)) if en["trim"] else 0,
        "trim_end_ms":   r.randint(0, round(150 * s)) if en["trim"] else 0,
    }
```

- [ ] **Step 4: Thread `strength` through `apply_variant_and_metadata`**

In `apply_variant_and_metadata`, add the parameter and pass it through. Change the signature line from:

```python
def apply_variant_and_metadata(
    input_path: str,
    output_path: str,
    meta: dict,
    rng: "random.Random | None" = None,
    enabled: "dict | None" = None,
) -> dict:
```

to add `strength: float = 1.0,` as the last parameter, and change the call `params = generate_variant_params(rng, enabled)` to:

```python
    params = generate_variant_params(rng, enabled, strength)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_variant_strength.py -v`
Expected: PASS (all 6).

- [ ] **Step 6: Run the full suite + compile**

Run: `python -m pytest -q` (expect all pass) and `python -m py_compile metadata_pool.py` (expect no output).

- [ ] **Step 7: Commit**

```bash
git add metadata_pool.py tests/test_variant_strength.py
git commit -m "feat(forge): add strength scaling to variant engine"
```

---

### Task 2: Preset-mapping helpers for the two axes

**Files:**
- Modify: `metadata_pool.py` (add presets + two pure functions)
- Test: `tests/test_forge_presets.py` (create)

**Interfaces:**
- Consumes: `DEFAULT_VARIANT_EFFECTS` (8 keys→bool).
- Produces:
  - `EFECTOS_PRESETS: dict[str, set[str]]`, `FUERZA_PRESETS: dict[str, float]`.
  - `efectos_to_enabled(level: str, fx_vars: dict | None = None) -> dict[str, bool]` — full 8-key dict.
  - `fuerza_to_strength(level: str, slider_pct: float = 50.0) -> float`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_forge_presets.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_forge_presets.py -v`
Expected: FAIL — `ImportError: cannot import name 'efectos_to_enabled'`.

- [ ] **Step 3: Add the presets + helpers to `metadata_pool.py`**

Add near `DEFAULT_VARIANT_EFFECTS` (after it):

```python
# ── Presets de los dos ejes de Forge ─────────────────────────────────────────
EFECTOS_PRESETS = {
    "Default": {"crop", "zoom", "rotate", "color", "noise", "speed", "trim"},   # 7, sin mirror
    "Light":   {"color", "trim"},
    "Medio":   {"crop", "color", "noise", "speed", "trim"},
    "Alto":    {"crop", "mirror", "zoom", "rotate", "color", "noise", "speed", "trim"},
}
FUERZA_PRESETS = {"Default": 1.0, "Light": 0.5, "Medio": 1.0, "Alto": 2.4}


def efectos_to_enabled(level: str, fx_vars: "dict | None" = None) -> dict:
    """Traduce un nivel del eje 'Efectos' (o 'Custom') al dict `enabled` de 8 claves.
    'Custom' lee los 8 on/off de `fx_vars` (clave->bool). Nivel desconocido -> Default."""
    if level == "Custom":
        vals = fx_vars or {}
        return {k: bool(vals.get(k, DEFAULT_VARIANT_EFFECTS[k])) for k in DEFAULT_VARIANT_EFFECTS}
    on = EFECTOS_PRESETS.get(level, EFECTOS_PRESETS["Default"])
    return {k: (k in on) for k in DEFAULT_VARIANT_EFFECTS}


def fuerza_to_strength(level: str, slider_pct: float = 50.0) -> float:
    """Traduce un nivel del eje 'Fuerza' (o 'Custom') a un float strength.
    'Custom' mapea slider_pct∈[0,100] a [0.3, 2.5] lineal. Nivel desconocido -> 1.0."""
    if level == "Custom":
        pct = max(0.0, min(100.0, float(slider_pct)))
        return round(0.3 + 0.022 * pct, 3)
    return FUERZA_PRESETS.get(level, 1.0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_forge_presets.py -v`
Expected: PASS (all 7).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add metadata_pool.py tests/test_forge_presets.py
git commit -m "feat(forge): add Efectos/Fuerza preset mapping helpers"
```

---

### Task 3: Forge UI — two axis controls wired into processing

**Files:**
- Modify: `gui_premium_v7.py` — `_build_forge_frame` (the Config card) and the effect/strength read in `forge_process` and `forge_preview_metadata`.

**Interfaces:**
- Consumes: `efectos_to_enabled(level, fx_vars)`, `fuerza_to_strength(level, slider_pct)`, `apply_variant_and_metadata(..., enabled=..., strength=...)` from Tasks 1-2; kit `SegmentedControl` (already imported).
- Produces: instance state `self.forge_efectos_var` (StringVar "Default"), `self.forge_fuerza_var` (StringVar "Default"), `self.forge_strength_slider` (CTkSlider), reuse of `self.forge_fx_vars` and `self.fx_frame`.

- [ ] **Step 1: Locate the current controls**

Run: `grep -nE "fx_frame|forge_fx_vars|forge_dist_var|def forge_process|def forge_preview_metadata|apply_variant_and_metadata|import metadata_pool|from metadata_pool" gui_premium_v7.py`
Note: the line where `fx_frame` (the 2-column grid of the 8 effect `ToggleRow`s) is created, the effect-var read inside `forge_process` (currently `fx_enabled = {key: var.get() for key, var in self.forge_fx_vars.items()}`), and the `apply_variant_and_metadata(...)` call. Keep a reference to the `fx_frame` widget variable name; store it as `self.fx_frame` if it is a local so the show/hide callback can reach it.

- [ ] **Step 2: Add the two SegmentedControls above the effect toggles**

In `_build_forge_frame`, immediately before the `fx_frame` (the effect toggles block) inside `card_cfg`, add the two axis controls and the slider. Assign `fx_frame` to `self.fx_frame` at its creation. Insert:

```python
# ── Eje Efectos (qué efectos) ────────────────────────────────────────────
ctk.CTkLabel(card_cfg, text="Efectos", text_color=TEXT_MUTED,
             font=ctk.CTkFont(size=11, weight="bold")).grid(
                 row=<R>, column=0, columnspan=2, sticky="w", padx=18, pady=(8, 2))
self.forge_efectos_var = tk.StringVar(value="Default")
SegmentedControl(card_cfg, values=["Default", "Light", "Medio", "Alto", "Custom"],
                 default="Default", command=self._forge_on_efectos_change,
                 variable=self.forge_efectos_var).grid(
                     row=<R+1>, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 6))

# ── Eje Fuerza (cuánta intensidad) ───────────────────────────────────────
ctk.CTkLabel(card_cfg, text="Fuerza", text_color=TEXT_MUTED,
             font=ctk.CTkFont(size=11, weight="bold")).grid(
                 row=<R+2>, column=0, columnspan=2, sticky="w", padx=18, pady=(4, 2))
self.forge_fuerza_var = tk.StringVar(value="Default")
SegmentedControl(card_cfg, values=["Default", "Light", "Medio", "Alto", "Custom"],
                 default="Default", command=self._forge_on_fuerza_change,
                 variable=self.forge_fuerza_var).grid(
                     row=<R+3>, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 6))

# Slider de Fuerza (solo visible en Custom)
self.forge_strength_slider = ctk.CTkSlider(card_cfg, from_=0, to=100, number_of_steps=100)
self.forge_strength_slider.set(50)
self._forge_strength_row = <R+4>   # remembered so the callback can grid/ungrid it
```

`SegmentedControl` (kit) already accepts `values`, `default`, `command`. If it does not forward a `variable=` kwarg, drop `variable=` and instead set `self.forge_efectos_var`/`self.forge_fuerza_var` from inside the `command` callbacks (the callbacks receive the selected value string). Pick real row numbers for `<R>..<R+4>` from the current `card_cfg` grid (place this block just above `self.fx_frame`; shift the following rows if needed). Ensure `self.fx_frame = fx_frame` is set where `fx_frame` is created.

- [ ] **Step 3: Add the show/hide callbacks**

Add two methods on the app class (near the other `forge_*` methods):

```python
def _forge_on_efectos_change(self, level: str) -> None:
    self.forge_efectos_var.set(level)
    # Los 8 toggles manuales solo se muestran en Custom.
    if level == "Custom":
        self.fx_frame.grid()
    elif self.fx_frame.winfo_manager():
        self.fx_frame.grid_remove()

def _forge_on_fuerza_change(self, level: str) -> None:
    self.forge_fuerza_var.set(level)
    if level == "Custom":
        self.forge_strength_slider.grid(row=self._forge_strength_row, column=0, columnspan=2,
                                        sticky="ew", padx=18, pady=(0, 6))
    elif self.forge_strength_slider.winfo_manager():
        self.forge_strength_slider.grid_remove()
```

At the end of `_build_forge_frame`, call both once so the initial "Default" state hides the toggles and the slider:

```python
self._forge_on_efectos_change("Default")
self._forge_on_fuerza_change("Default")
```

- [ ] **Step 4: Use the axes when processing**

In `forge_process` (and the same spot in `forge_preview_metadata` if it computes `enabled`), replace the current effect read with the mapped values, and pass `strength` to the variant call. Replace:

```python
fx_enabled = {key: var.get() for key, var in self.forge_fx_vars.items()}
```

with:

```python
fx_vals = {key: var.get() for key, var in self.forge_fx_vars.items()}
fx_enabled = metadata_pool.efectos_to_enabled(self.forge_efectos_var.get(), fx_vals)
forge_strength = metadata_pool.fuerza_to_strength(
    self.forge_fuerza_var.get(), self.forge_strength_slider.get())
```

and change the `apply_variant_and_metadata(...)` call to pass `strength=forge_strength`:

```python
metadata_pool.apply_variant_and_metadata(vid_path, out_path, meta,
                                         enabled=fx_enabled, strength=forge_strength)
```

If `forge_preview_metadata` does not run the variant engine (only assigns iPhone metadata), leave it unchanged — only `forge_process` needs the `strength`.

- [ ] **Step 5: Verify (headless — do NOT launch the GUI, it blocks)**

Run: `python -m py_compile gui_premium_v7.py` (expect no output) and `python -m pytest -q` (expect all pass — the mapping/engine behavior is covered by Tasks 1-2). Visual verification (the two segmented controls, Custom reveals toggles / slider) is the user's manual pass.

- [ ] **Step 6: Commit**

```bash
git add gui_premium_v7.py
git commit -m "feat(forge): Efectos + Fuerza axis controls in the UI"
```

---

### Task 4: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Full suite + compile**

Run: `python -m pytest -q` (all pass, including `test_variant_strength.py` + `test_forge_presets.py`) and `python -m py_compile gui_premium_v7.py metadata_pool.py`.

- [ ] **Step 2: Scope guard**

Run: `git diff --name-only main..HEAD`
Expected: only `metadata_pool.py`, `gui_premium_v7.py`, `tests/test_variant_strength.py`, `tests/test_forge_presets.py` (+ the two `docs/superpowers/*` files if committed). No other file.

- [ ] **Step 3: Manual visual checklist for the user**

Launch the app, open Forge. Confirm: two controls "Efectos" and "Fuerza" (Default selected); switching **Efectos → Custom** reveals the 8 effect toggles; switching **Fuerza → Custom** reveals the 0–100% slider; a small Forge run at Efectos=Alto + Fuerza=Alto produces visibly stronger variation than Default; default run no longer horizontally mirrors any copy.

---

## Self-Review notes

- **Spec coverage:** strength scaling + probability + noise floor (Task 1); Efectos/Fuerza presets incl. Default=7-no-mirror and Custom slider mapping (Task 2); two independent SegmentedControls + Custom reveals toggles/slider + wiring into processing (Task 3); regression that strength=1.0 matches historical bounds (Task 1); scope guard (Task 4).
- **RNG order:** Task 1's replacement preserves the original dict key order and one `r.random()` per gated effect, so `strength=1.0` keeps the historical RNG sequence — the regression tests assert bounds rather than precomputed values, which is robust to platform float formatting.
- **Placeholder note:** `<R>..<R+4>` in Task 3 Step 2 are grid row numbers to read from the current `card_cfg` layout (the post-reskin Forge shifted line numbers); they are positions to fill from the actual file, not code placeholders. The `variable=` kwarg on `SegmentedControl` has an explicit fallback in the same step if the kit does not support it.
