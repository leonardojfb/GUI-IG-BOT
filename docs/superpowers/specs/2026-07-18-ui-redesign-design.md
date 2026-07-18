# IG Auto Pro — UI Redesign (comfortable theme + reorganization)

**Date:** 2026-07-18
**Status:** Approved design, pending implementation plan
**Scope:** Visual re-skin + navigation reorganization of `gui_premium_v7.py`. No business-logic changes.

---

## 1. Problem & goals

The app (`gui_premium_v7.py`, ~182KB, CustomTkinter) works but is uncomfortable to use:

- Harsh **neon-dark** theme (cyan `#00f5d4` / purple `#7c3aed` / pink `#e1306c`) that strains the eyes.
- **Flat 9-item sidebar** with no grouping — hard to orient.
- Forging large batches froze the whole PC (**already fixed**, see §2).

**Goals**

1. Replace the neon theme with a **natural, restful palette** that is comfortable for long sessions.
2. Support **light + dark automatically** (follows OS, with a manual toggle).
3. **Reorganize navigation** into logical groups that follow the real workflow.
4. Keep the change **low-risk**: business logic, data flow, and DB untouched.

**Non-goals**

- No framework migration (stays CustomTkinter).
- No new features. No changes to the Forge/distribution/Telegram logic.
- No redesign of individual screen internals beyond applying the new tokens and consistent spacing.

---

## 2. Console-freeze fix (DONE — documented for completeness)

**Root cause:** the GUI launches windowless (`pythonw.exe`). Every FFmpeg/FFprobe call used `subprocess.run(cmd, capture_output=True)` **without** `creationflags`. On Windows a windowless parent spawning a console child forces a **new console window per call**; a 200-copy batch = ~400+ windows flashing and stealing focus → PC unusable.

**Fix applied:** module-level `_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)` (0 on non-Windows) passed as `creationflags=_NO_WINDOW` to every FFmpeg/FFprobe call:

- `metadata_pool.py` — 3 calls (lines ~226, ~247, ~425)
- `videos.py` — 2 calls (`get_audio`, render)
- `organizadortg.py` — 2 calls (probe + compress)

Verified: all three files compile; flag resolves to `134217728` on Windows. **Remaining verification:** one live Forge run with FFmpeg installed to confirm zero console windows appear.

---

## 3. Palette (design tokens)

Warm-biased neutrals (not pure grey), a single restful **teal-sage accent**, desaturated semantics. Every token is a `(light, dark)` pair.

| Token (proposed name) | Current name in `colors.py` | Light | Dark | Use |
|---|---|---|---|---|
| `GROUND`      | `BG_APP`     | `#f5f4f0` | `#16181d` | Window background |
| `RAIL`        | `BG_SIDEBAR` | `#edece6` | `#1b1e25` | Sidebar |
| `SURFACE`     | `BG_CARD`    | `#ffffff` | `#22262e` | Primary cards |
| `SURFACE2`    | `BG_CARD2`   | `#f0efe9` | `#2a2f38` | Secondary / hover |
| `INPUT`       | `BG_INPUT`   | `#f3f2ec` | `#262b33` | Input fields |
| `LINE`        | `BORDER`     | `#e3e1d8` | `#333944` | Borders / separators |
| `ACCENT`      | `NEON_CYAN`  | `#2f8f7d` | `#4db6a2` | Primary CTA, active nav |
| `ACCENT_WEAK` | *(new)*      | `#dcefe9` | `#223a37` | Active-nav background |
| `ACCENT_2`    | `NEON_PURPLE`| `#5b7fb0` | `#7f9fcf` | Secondary highlight (muted slate-blue) |
| `SUCCESS`     | `SUCCESS`    | `#3f9d6d` | `#54b184` | OK states |
| `WARNING`     | `WARNING`    | `#c2872f` | `#e0a94e` | Warnings |
| `DANGER`      | `DANGER` / `IG_PINK` | `#c9564e` | `#e07a6f` | Errors / destructive |
| `INFO`        | `INFO`       | `#4a7fb0` | `#6398c9` | Neutral info |
| `TEXT_H1`     | `TEXT_H1`    | `#2a2925` | `#e9eaec` | Headings |
| `TEXT_BODY`   | `TEXT_BODY`  | `#55534c` | `#bdc2ca` | Body text |
| `TEXT_MUTED`  | `TEXT_MUTED` | `#8b887f` | `#7d838d` | Muted / placeholder |

`IG_PINK` / `IG_ORANGE` (neon brand accents) are retired from general use; a subtle Instagram gradient may remain only on the logo mark. `DANGER` becomes a muted rose.

**Token strategy:** keep the **existing token names** in `styles/colors.py` and change each value from a hex string to a `(light, dark)` tuple. This propagates to every `fg_color=TOKEN` / `text_color=TOKEN` CustomTkinter usage with **zero call-site edits**. Add the new alias names (`ACCENT`, `SURFACE`, …) pointing at the same tuples for future clarity.

---

## 4. Theming mechanism

- Set `ctk.set_appearance_mode("system")` (was `"dark"`) so the app follows the OS; add a **manual toggle** (Claro / Oscuro / Sistema) in the sidebar footer that calls `ctk.set_appearance_mode(...)`.
- CustomTkinter reads `(light, dark)` tuples natively and re-renders CTk widgets on mode change — **no manual refresh needed for CTk widgets.**
- **The one catch — raw Tk / ttk widgets** don't understand tuples and must get a single resolved color:
  - Known sites: Forge `tk.Listbox` ([:3168](../../../gui_premium_v7.py)), `ttk.Treeview` "Premium.Treeview" ([:3283](../../../gui_premium_v7.py)), `ttk.Scrollbar`, any account-panel tree, and ttk style definitions.
  - Add a resolver `themed(token) -> str` returning the correct tuple element for `ctk.get_appearance_mode()`.
  - Register these widgets/styles and **re-apply their colors on theme switch** via a `_restyle_raw_tk()` callback bound to the toggle.
  - **Implementation task must first inventory every `tk.`/`ttk.` color argument** (grep `tk.Listbox`, `ttk.`, `style.configure`, `configure(bg=`, `fg=`) and route each through `themed()`.
- Optionally ship a small custom CTk theme JSON for default widget colors; not required since most widgets set `fg_color` explicitly.

---

## 5. Typography

- Change `FONT_*` family from `Arial` → **`Segoe UI`** (present on all Windows; much more comfortable). Keep `Consolas` for `FONT_MONO` (logs).
- Keep the existing size scale; only the family changes. Single edit in `styles/colors.py`.

---

## 6. Navigation reorganization

Flat 9-item list → **4 labeled groups** following the real pipeline. Non-clickable group headers (small uppercase muted labels) separate the sections.

| Group | Items |
|---|---|
| **Contenido** | 🔮 Forge · 🎬 Tandas |
| **Distribución** | 🚀 Logística · 📡 Cuentas · 📲 Telegram |
| **Control** | 📊 Dashboard |
| **Sistema** | ⚙️ Admin (Equipo) · ⬇ Actualizaciones |

- **AI Advisor is hidden**: its nav button is removed. Its frame **is still built** (kept dormant) so no code path breaks and it can be re-enabled by restoring one nav entry. Not deleted.
- Sidebar footer keeps the **bot status** indicator and gains the **theme toggle**.
- `SIDEBAR_W` may widen slightly (210 → 220) to fit group labels comfortably.
- Nav rebuild is localized to `_build_sidebar` (nav list + group-header rendering). `_build_content_area` still builds all frames (incl. AIAdvisor); only the nav button list drives visibility.

---

## 7. Component consistency (light touch)

Apply the tokens uniformly and normalize obvious inconsistencies while re-skinning (no structural rework):

- Active nav item uses `ACCENT_WEAK` background + `ACCENT` text (see mockup).
- Cards: `SURFACE` on `GROUND`, `LINE` border, consistent `CARD_RADIUS`, soft elevation.
- Buttons: primary = `ACCENT` fill; secondary = ghost (`LINE` border, `TEXT_BODY`); destructive = `DANGER`.
- Inputs: `INPUT` bg + `LINE` border; focus ring in `ACCENT`.
- Fix the naming drift where harmless (nav label "Admin" ↔ internal key "Equipo" stays; no key renames to avoid touching logic).

---

## 8. Data flow / risk

- **Untouched:** DB (`database.py`, `organizador.db`), Forge/variant engine, distribution (`Organizador.py`), Telegram, updater, all worker threads.
- **Changed files:** `styles/colors.py` (tokens + fonts), `gui_premium_v7.py` (sidebar build, theme toggle, raw-tk restyle helper, `set_appearance_mode`).
- Because tokens are centralized and CTk consumes tuples natively, the blast radius is small and mostly mechanical. The main real work is the **raw-tk widget inventory + resolver**.

---

## 9. Verification

1. **Console fix:** run a small Forge batch (e.g. 5 copies) with FFmpeg installed → confirm zero console windows.
2. **Theme:** launch app; confirm it follows OS theme; toggle Claro/Oscuro/Sistema → all screens (including Forge Listbox + Treeview tables) recolor correctly with legible contrast in both.
3. **Navigation:** all groups render; every button opens its frame; hidden AI Advisor is absent but app is stable.
4. **Regression:** open each screen, run a preview + a small Forge, confirm nothing broke.
5. Contrast check: body text on ground/surface passes comfortable legibility in both themes.

---

## 10. Rollout order

1. Console fix — **done**, needs live confirmation.
2. `styles/colors.py`: tokens → tuples, fonts → Segoe UI, add aliases + `themed()` resolver.
3. Raw-tk widget inventory + route through resolver; add `_restyle_raw_tk()`.
4. Sidebar: group headers, reorganized nav, hide AI Advisor, theme toggle, `set_appearance_mode("system")`.
5. Consistency polish pass on cards/buttons/inputs.
6. Verify per §9.
