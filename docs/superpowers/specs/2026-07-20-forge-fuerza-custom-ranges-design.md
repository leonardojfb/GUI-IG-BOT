# FORGE — Fuerza=Custom per-effect min–max ranges

**Date:** 2026-07-20
**Status:** Design approved, pending implementation plan
**Extends:** the `feature/forge-efectos-fuerza` branch / PR #3 (Efectos + Fuerza axes already merged into that branch).
**App:** `metadata_pool.py` (variant engine) + `gui_premium_v7.py` (Forge screen).

## Objetivo

Turn `Fuerza=Custom` from a single global slider into a full manual panel: a global
intensity slider **plus** an editable min–max range per effect, so the user can dial
each effect's magnitude in measurable numbers while the engine still randomizes per
copy (uniqueness preserved). Mirror stays a plain on/off.

## Constraints

- Additive, on top of the existing Efectos+Fuerza work. Only `metadata_pool.py` and
  `gui_premium_v7.py` (+ tests) change. No new dependencies.
- The two axes stay independent: **Efectos** gates which effects are on; **Fuerza**
  controls how much. Ranges only apply to effects Efectos left enabled.
- Non-Custom Fuerza (Default/Light/Medio/Alto) is UNCHANGED: preset → single `strength`
  scalar over the hardcoded default ranges.
- Every copy stays unique: the engine samples uniformly within each (possibly
  overridden, strength-scaled) range — no fixed per-copy values.
- Values are edited in engine units directly (no unit conversion): zoom is a factor
  (1.00–1.05), contrast/saturation/gamma are multipliers, rotate is degrees, etc.

## Model — Fuerza=Custom panel

When `Fuerza=Custom`, the panel shows (instead of the old lone slider):

1. **Intensidad general** — the existing 0–100% slider. It maps to a global `strength`
   scalar and scales every row's intensity (deviation from neutral) at once.
2. **10 min–max rows**, one per ranged param, pre-filled with the current engine defaults:

   | Row | Unit | default lo–hi | engine neutral |
   |---|---|---|---|
   | Recorte | px | 2 – 10 | 0 |
   | Zoom | factor | 1.00 – 1.05 | 1.0 |
   | Rotación | ° | −1.5 – 1.5 | 0 |
   | Brillo | Δ | −0.03 – 0.03 | 0 |
   | Contraste | × | 0.94 – 1.06 | 1.0 |
   | Saturación | × | 0.90 – 1.10 | 1.0 |
   | Gamma | × | 0.95 – 1.05 | 1.0 |
   | Grano | nivel | 4 – 8 | 0 |
   | Velocidad | × | 0.985 – 1.015 | 1.0 |
   | Trim | ms | 0 – 150 | 0 |

3. **Espejo** — a plain on/off toggle (no number; mirror has no magnitude).

**How the slider and rows combine:** each row is the effect's **base** `(lo, hi)`; the
global slider is the `strength` scalar that scales every base range's deviation from its
neutral (`scaled = neutral + (bound − neutral)·strength`). The Custom slider maps
`pct → pct/50` so **50% = strength 1.0 = ranges exactly as typed** (default position),
0% = off, 100% = 2×.

## Backend (`metadata_pool.py`)

`generate_variant_params(rng, enabled=None, strength=1.0, overrides=None)`:
- `overrides` (nuevo, opcional) — dict `{param: (lo, hi)}` in engine units. Valid keys:
  `crop, zoom, rotate, brightness, contrast, saturation, gamma, noise, speed, trim`.
  For a param present in `overrides`, its `(lo, hi)` REPLACES the hardcoded default base
  range before strength-scaling; params absent keep today's default range. `overrides=None`
  reproduces the current behavior exactly.
- Scaling and per-effect gating are unchanged otherwise: `enabled` still gates on/off
  (including mirror), `strength` still scales, probabilities still `min(1.0, base·strength)`,
  noise still floored at 4.

`fuerza_to_strength("Custom", slider_pct)` changes to `round(slider_pct / 50.0, 3)`
(0→0, 50→1.0, 100→2.0) so the Custom slider's neutral is the midpoint. Non-Custom levels
unchanged (Default/Medio=1.0, Light=0.5, Alto=2.4).

New pure helper `parse_custom_ranges(raw) -> dict[str, tuple[float,float]]`:
- `raw` = `{param: (min_str, max_str)}` from the UI entries. Parses to floats; if either
  side is blank/invalid, that param is omitted (engine falls back to its default). If
  `min > max`, swap. Returns only the valid overrides.

`apply_variant_and_metadata(..., strength=1.0, overrides=None)` threads `overrides` into
`generate_variant_params`.

## UI (`gui_premium_v7.py`, Forge)

`Fuerza=Custom` reveals a panel (inside the already-scrollable Forge) containing: the
existing `CTkSlider` (intensidad general), 10 rows each with two `CTkEntry` (min, max)
pre-filled from the defaults table, and a mirror on/off `ToggleRow`. Non-Custom hides the
whole panel. New state: `self.forge_range_entries` (dict param→(min_entry, max_entry)),
`self.forge_custom_mirror_var` (BooleanVar).

In `forge_process`, when `Fuerza=Custom`:
- `strength = fuerza_to_strength("Custom", slider.get())`.
- `overrides = metadata_pool.parse_custom_ranges({param: (min.get(), max.get()) ...})`.
- `enabled` = the Efectos-derived dict, but `enabled["mirror"]` is overridden by
  `self.forge_custom_mirror_var.get()` (the panel's mirror toggle is authoritative in Custom).
- Pass `enabled`, `strength`, `overrides` to `apply_variant_and_metadata`.

When Fuerza is not Custom: `overrides=None`, `strength` from the preset, `enabled` fully
from Efectos (as today).

## Tests

Backend:
- `overrides=None` reproduces current bounds at each strength (regression).
- An override widens/narrows only its param's sampled range (e.g. `crop=(0,30)` yields
  samples up to ~30 at strength 1.0; other params unchanged).
- `strength` still scales an overridden range (deviation-from-neutral rule).
- `parse_custom_ranges`: parses valid pairs; omits blank/invalid; swaps min>max.
- `fuerza_to_strength("Custom", 50) == 1.0`; `0 → 0.0`; `100 → 2.0`.

UI: py_compile + full suite (the panel behavior is covered by the backend/helper tests);
visual pass is the user's.

## Risks

- Large panel (~20 entries) — lives inside the already-scrollable Forge, only shown in
  Custom. Acceptable.
- User-entered extreme ranges can heavily degrade video — intended (they typed it);
  the even-dimension guard still protects libx264.
