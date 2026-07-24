# OOPSIE-style Reskin — Instagram Automation Pro v7

**Date:** 2026-07-20
**Status:** Approved (Phase 1 skin). Phase 2 feature backlog recorded as appendix.
**App:** `Método IG VIDEOS v2.0/gui_premium_v7.py` (CustomTkinter, 3643 lines, 9 screens)

## Goal

Reskin the existing CustomTkinter GUI to match the visual language of the "OOPSIE"
Tauri app (near-black warm background, single peach/almond accent, generous spacing,
large radii, kicker→title→description headers, sidebar with brand tile + collapsible
icon groups, and a shared component kit). Keep all existing functionality.

## Hard constraints

- **Pure reskin. Zero logic changes.** FORGE (`metadata_pool.py`), scheduler,
  accounts, anti-collision distribution (`database.py`, `videos.py`), Telegram
  (`telegram_core.py`), and the DB behave byte-identically. Only the *view* layer
  (colors, layout, widget composition) changes.
- **No new features in Phase 1.** OOPSIE features the user may add later are listed in
  the Phase 2 appendix and are explicitly out of scope for this work.
- **No new runtime dependencies, no web stack.** The component kit is built from
  CustomTkinter built-ins plus small composites.
- All command handlers, instance variables (`forge_*`, etc.), threading model, and DB
  access remain unchanged; only the widgets that call them are restyled.

## Chosen direction (from brainstorming)

- Architecture: **restyle CustomTkinter** (not a web rewrite).
- Palette: **adopt OOPSIE peach on near-black** exactly.
- Rollout: **phased** — build tokens + kit, reskin Forge as the proof screen, then roll
  the same kit across the other screens.

## Relationship to the prior 2026-07-18 redesign (already implemented)

This is **redesign v2**, built on top of the already-shipped `2026-07-18-ui-redesign`
work on the `ui-redesign` branch. That prior pass already delivered the architecture this
spec depends on, so this spec **leverages** rather than rebuilds it:

- `(light, dark)` tuple tokens in `styles/colors.py`, consumed by CTk natively.
- The `resolve()` / `themed()` resolver that routes single colors to raw `tk`/`ttk`
  widgets (Forge `Listbox`, `Premium.Treeview`, scrollbars) plus a raw-tk restyle-on-
  theme-switch path. **The OOPSIE reskin reuses this; no new resolver needed.**
- Segoe UI fonts and the manual Claro/Oscuro/Sistema theme toggle.
- Grouped sidebar nav (Contenido / Distribución / Control / Sistema) and the
  **already-hidden AI Advisor** (nav button removed; frame kept dormant).
- The FFmpeg/FFprobe console-freeze fix (`_NO_WINDOW`) — done, unrelated to skin.

What v2 changes vs v1: swaps the **teal-sage `ACCENT` → peach `#e9c7a3`**, darkens the
background to near-black, adds the **`styles/components.py` component kit**, the **brand
tile**, the **kicker→title→description header pattern**, and OOPSIE-shaped widgets
(segmented control, stepper, toggle switch, key-value rows, dropzone).

## 1. Design tokens — rewrite `styles/colors.py`

Dark values read from the OOPSIE screenshots. Light values are derived (only dark
screenshots exist; light mode gets a dedicated polish pass). Values are `(light, dark)`
tuples consumed through the existing `resolve()` / `themed()` helpers, so every screen
inherits the new look automatically.

| Token | Dark | Purpose |
|---|---|---|
| `BG_APP` / `GROUND` | `#0c0c0e` | app + content background |
| `BG_SIDEBAR` / `RAIL` | `#0e0e10` | sidebar |
| `BG_CARD` / `SURFACE` | `#141416` | cards (with 1px `#242428` border) |
| `BG_CARD2` / `SURFACE2` | `#1a1a1d` | hover / secondary surface |
| `BG_INPUT` | `#141416` | inputs (border `#2a2a2e`) |
| `BORDER` / `LINE` | `#242428` | borders, dividers |
| `ACCENT` (peach) | `#e9c7a3` | primary CTA, active nav, selection |
| `ACCENT_TEXT` | `#1c1710` | dark text drawn on peach |
| `ACCENT_HOVER` | `#dcb489` | peach hover |
| `TEXT_H1` | `#f5f5f5` | headings |
| `TEXT_BODY` | `#a0a0a6` | body |
| `TEXT_MUTED` | `#6c6c72` | kicker, placeholder, secondary |
| `SUCCESS` | `#3fb768` | status dots |
| `DANGER` | `#e5675f` | destructive |
| `WARNING` | `#e0a94e` | warnings |
| `TELEGRAM` / `INFO` | `#29a9ea` | support button, info |
| `BRAND_REDDIT` / `BRAND_X` / `BRAND_IG` | `#ff4500` / `#e7e9ea` / `#e1306c` | platform icons keep brand color |

Light palette (derived): `BG_APP #faf9f6`, `BG_CARD #ffffff`, `BORDER #e7e3d9`, peach
accent kept, `TEXT_H1 #1b1a17` / `TEXT_BODY #55534c` / `TEXT_MUTED #8b887f`.

Sizing bumped to match OOPSIE: `CARD_RADIUS 16`, `BTN_RADIUS 10`, `SIDEBAR_W 240`,
`BTN_H 40`, `BTN_H_LG 46`. New font roles: `FONT_KICKER` (~11, uppercase, letterspaced),
`FONT_TITLE` (~28 bold), `FONT_DESC` (~14). Existing aliases (`NEON_CYAN`, etc.) are
remapped to the new palette so current call sites keep working during the transition.

## 2. New `styles/components.py` — shared component kit

Reusable factories/classes so all 9 screens render identically. Each reads tokens and is
theme-aware via `themed()`:

- `PageHeader(parent, kicker, title, description, action=None)` — uppercase muted kicker,
  large title, muted one-line description, optional top-right context pill button.
- `Card(parent, title=None)` — `SURFACE` background, radius 16, 1px `LINE` border,
  optional title; content added to `.body`.
- `PrimaryButton` (peach fill, `ACCENT_TEXT`), `GhostButton` (transparent + 1px border),
  `DangerButton`.
- `SegmentedControl(parent, options, default)` — themes `CTkSegmentedButton` to
  peach-active / transparent-inactive (OOPSIE Strength / EXIF-camera pattern).
- `Stepper(parent, label, value, min, max)` — `[ − ] value [ + ]` block.
- `ToggleRow(parent, label, var)` — label + `CTkSwitch` (OOPSIE toggle pill).
- `KeyValueRow(parent, key, value)` — muted label left, value right, hairline divider
  (OOPSIE License rows).
- `Dropzone(parent, title, subtitle, on_browse)` — dashed rounded rect, title + "or" +
  peach Browse button.
- `PhonePreview(parent)` — 9:16 dark rounded panel (used later by Phase 2 preview; in
  Phase 1 only where a preview area already exists).
- `NavItem` — sidebar pill: icon + label + active state (peach text + faint peach fill).

## 3. Sidebar redesign

- Brand block: peach rounded-square monogram tile + **IG AUTO PRO** (bold) + `AUTOMATION
  SUITE` (kicker), mirroring OOPSIE's `OOPSIE / CREATOR SUITE`.
- Collapsible section groups with a section icon and chevron. Existing groups kept:
  Contenido (Forge, Tandas), Distribución (Logística, Cuentas, Telegram), Control
  (Dashboard), Sistema (Admin/Equipo, Actualizaciones). **AI Advisor stays hidden**
  (nav button already removed in v1); its frame remains dormant, not restyled.
- Active nav item: peach text + faint peach-tint fill pill + colored icon (replaces the
  current `ACCENT_WEAK` treatment in `show_frame`).
- Bottom: Light/Dark/System theme toggle styled as an OOPSIE pill, a Telegram/Support
  link, and the existing bot-status dot.
- Width 240 (from 210).

## 4. Header pattern (all screens)

Every screen's top region uses `PageHeader`: `KICKER → Big Title → description → optional
top-right pill`, replacing the current ad-hoc title+subtitle labels.

## 5. Forge screen — proof screen (built and approved first)

Restyle only; same widgets, same command bindings (`forge_add_videos`,
`forge_remove_video`, `forge_preview_metadata`, `forge_reshuffle`, `forge_process`) and
same variables (`forge_video_paths`, `forge_meta_assignments`, `forge_fx_vars`,
`forge_dist_var`, `e_forge_*`, `c_forge_cat`, `forge_tree`).

- Header → `PageHeader("CONTENIDO", "Forge de Metadata", "276,000 fingerprints…",
  action=pill "Tanda")`.
- Videos card: styled list + peach **＋ Agregar Videos** / ghost **Quitar**.
- Config card: "Copias por vídeo" and "Días a distribuir" → `Stepper`; "Distribuir
  automáticamente" → `ToggleRow` switch; the 8 micro-edit checkboxes (crop, mirror,
  zoom, rotate, color, noise, speed, trim) → 8 `ToggleRow` switches. **The 8 effects stay
  individual** — they are NOT collapsed into an OOPSIE-style Strength preset, because that
  would change the variant-engine behavior. Strength presets are a Phase 2 item.
- Preview `Treeview` ("Premium.Treeview" style) restyled to OOPSIE dark: peach selection,
  borderless, taller rows.
- Bottom bar: Preview + Regenerar Shuffle = `GhostButton`; **Procesar Ahora** =
  `PrimaryButton` (peach).

## 6. Remaining 7 visible screens (after Forge approved)

Same kit applied uniformly: Dashboard, Tandas, Logística (anti-collision distribution
tables restyled, logic untouched), Cuentas, Telegram, Admin/Equipo, Actualizaciones.
Actualizaciones/Settings adopts OOPSIE's License + Advanced `KeyValueRow` card layout.
AI Advisor stays hidden/dormant (see §3) and is skipped until re-enabled.

## 7. Explicitly untouched

`metadata_pool.py`, `database.py`, `videos.py`, `telegram_core.py`, `updater.py`,
scheduler logic, anti-collision distribution, all command handlers, instance variables,
threading, and DB schema/access.

## 8. Verification

- **Logic regression guard:** the existing `tests/` suite (colors, database schedule,
  message format, schedule fallback, tanda sync, timezone, updater) must still pass after
  the refactor — they cover logic/DB, not UI, so a green run proves no behavior changed.
- **`tests/test_colors.py`** will need updating to the new token values (it tests the
  design tokens directly); that is an expected, intended change, not a regression.
- **Launch check:** app starts under `pythonw`, all 9 nav items switch without error, and
  Forge preview + process still fire.

## 9. Risks

- `ttk.Treeview` styling in Tk is limited (row height and selection color are
  controllable; rounded rows are not). Accepted.
- `Stepper` and `ToggleRow` are composites needing careful layout, but use standard
  widgets.
- Light mode is derived, not screenshot-verified; it may need a follow-up polish pass.

---

## Appendix — Phase 2 feature backlog (build after skin, user selects)

Recorded for later; NOT part of this spec's implementation. Tags: **NEW** = not present,
**HAVE** = equivalent already exists, **SKIP** = not useful for this user.

Video editing: (1) Auto subtitles via Whisper + style presets [NEW], (2) Snapchat static
text bar [NEW], (3) Image converter [NEW], (4) Video converter [NEW].

Spoofer: (5) generic multi-platform spoof engine [HAVE = FORGE], (6) Strength presets
over the 8 effects [NEW UX], (7) Parallel spoofs [NEW], (8) EXIF iOS/Android camera
[NEW/partial], (9) Reddit post generator [NEW], (10) Twitter/X + IG/Threads post
generators [NEW], (11) per-platform tabs [NEW].

Workflow: (12) live job queue + history [NEW], (13) output naming + batch folder UI
[NEW], (14) quick vs batch mode [NEW], (15) live 9:16 phone preview [NEW, heaviest].

App: (16) export-folders panel [NEW], (17) check for updates [HAVE], (18) light/dark
toggle [HAVE], (19) license/DRM [SKIP — vendor feature, only if reselling].
