# Handoff — OOPSIE reskin continuation (Tasks 8–14)

Continuation brief for any agent (Codex/Claude) picking up the CustomTkinter → "OOPSIE" peach reskin. Read fully, continue from **Task 8**.

## Repo & branch
- Work ONLY in: `Método IG VIDEOS v2.0/` — that folder IS the git repo. Run all git from there.
- Branch: `ui-redesign`. Foundation HEAD after Task 7 = `cb1d77d`.
- GOTCHA: the PARENT folder has a stray/broken `.git` — never run git from the parent.
- Working tree clean except two untracked planning docs (leave untracked).

## What this is
Pure visual reskin of `gui_premium_v7.py` (~3600-line CustomTkinter app) to the "OOPSIE" look: near-black warm background, single peach accent, big radii, shared component kit, `KICKER → Title → description` headers. **Zero business-logic changes.**

## Read these first
- Spec:  `docs/superpowers/specs/2026-07-20-oopsie-skin-reskin-design.md`
- Plan:  `docs/superpowers/plans/2026-07-20-oopsie-skin-reskin.md` (15 tasks)
- Ledger: `.superpowers/sdd/progress.md`

## Done (Tasks 1–7, committed & user-approved)
1. `styles/colors.py` — peach tokens (`ACCENT=#e9c7a3`, bg `#0c0c0e`). Legacy names (`NEON_CYAN`, `NEON_PURPLE`, `IG_PINK`) kept but remapped. White tokens: `TEXT_ON_DANGER`, `SWITCH_KNOB`. Sizes `SIDEBAR_W=240, CARD_RADIUS=16, BTN_RADIUS=10`.
2. ttk/tk styles routed to tokens (Treeview peach selection, rowheight 30).
3–5. `styles/components.py` kit (already imported in `gui_premium_v7.py`):
   `PageHeader(master, kicker, title, description="", action=(text,cmd)|None)`, `Card(master, title=None)` (`.body`), `PrimaryButton`, `GhostButton`, `DangerButton`, `SegmentedControl(master, values, default=None, command=None)`, `Stepper(master, value, min, max)` (`.get()->int`), `ToggleRow(master, label, variable=None)` (`.var`), `KeyValueRow(master, key, value, divider=True)`, `Dropzone`, `PhonePreview`, `NavItem`.
6. Sidebar redesigned (peach monogram tile, `NavItem` pills, peach theme toggle).
7. Forge reskinned + made scrollable (commit `cb1d77d` = the scroll-wrapper pattern).

## Remaining — Tasks 8–14 (one screen per commit)
Each screen, 3 moves:
1. Replace ad-hoc title/subtitle with `PageHeader(...)` (exact calls below).
2. Buttons: primary → `PrimaryButton`, secondary → `GhostButton`, destructive → `DangerButton`.
3. Group content in `Card(title=...)`; numeric → `Stepper`; on/off → `ToggleRow`; label/value → `KeyValueRow`.

| Task | Screen | Builder (approx line) | PageHeader call |
|---|---|---|---|
| 8 | Dashboard | `_build_dashboard_frame` (~1160) | `PageHeader(f, "CONTROL", "Dashboard", "Estado del sistema y actividad reciente.")` |
| 9 | Tandas | `_build_mix_frame` (~1976) | `PageHeader(f, "CONTENIDO", "Tandas", "Lotes de videos forjados listos para distribuir.")` |
| 10 | Logística | `_build_dist_frame` + `_build_dist_tandas_tab` + `_build_dist_cuentas_tab` (~2142) | `PageHeader(f, "DISTRIBUCIÓN", "Logística", "Reparto anti-colisión de tandas entre cuentas y días.")` |
| 11 | Cuentas | `_build_cuentas_frame` (~3149) | `PageHeader(f, "DISTRIBUCIÓN", "Cuentas", "Cuentas de Instagram y su estado.")` |
| 12 | Telegram | `_build_tg_frame` (~2765) | `PageHeader(f, "DISTRIBUCIÓN", "Telegram", "Envío programado vía Telegram.")` |
| 13 | Admin/Equipo | `_build_team_frame` (~1398) | `PageHeader(f, "SISTEMA", "Admin", "Gestión de equipo y configuración.")` |
| 14 | Actualizaciones/Settings | `_build_updates_frame` (~991) | `PageHeader(f, "APP", "Actualizaciones", "Mantén la app al día.")` |

Task-specific notes:
- **Task 10 Logística:** anti-collision distribution logic MUST stay untouched — restyle only tables/buttons.
- **Task 12 Telegram:** the blue "send" button = `fg_color=TELEGRAM, text_color=TEXT_ON_DANGER` (white token).
- **Task 14 Settings:** OOPSIE Settings layout = `Card` + `KeyValueRow`s (versión, canal, última comprobación) + `PrimaryButton` "Buscar actualizaciones". Form-style screen → **wrap content in `ctk.CTkScrollableFrame`** like Forge `cb1d77d`.

## Hard rules (every task)
- Pure reskin. NO changes to command handlers, instance-variable names, threading, DB, or logic files (`metadata_pool.py`, `database.py`, `videos.py`, `telegram_core.py`, `updater.py`, `Organizador.py`). Reuse existing `self.*` vars/commands exactly.
- Do NOT add "AI Advisor" to the nav — stays hidden/dormant.
- NO hardcoded hex — tokens only (white = `TEXT_ON_DANGER` / `SWITCH_KNOB`).
- Each screen task touches ONLY `gui_premium_v7.py`. `git add gui_premium_v7.py` — **never `git add -A`**.
- If a screen overflows the window, wrap in `ctk.CTkScrollableFrame` (pattern = `cb1d77d`); inside scroll frames drop `weight=1` row-fill and give tables a fixed `height=`.

## Verification (per task) — GUI is non-interactive, do NOT launch it
1. `python -m py_compile gui_premium_v7.py` → must succeed.
2. `python -m pytest -q` → all pass (was 48 after Task 7).
Commit: `git commit -m "feat(ui): reskin <screen> screen"`.

## Task 15 — final verification
- `python -m pytest -q` green.
- Reskin commits (after `cb1d77d`) touch ONLY `gui_premium_v7.py` (+ `styles/*` if any). NOTE: commit `d5f7191` in history = user's unrelated `list_and_sync_tandas` feature; ignore it in the scope guard.
- Produce a launch checklist for the user to eyeball all 8 visible screens + theme toggle.

Update `.superpowers/sdd/progress.md` with one line after each task.
