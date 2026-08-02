# E2E multimedia Logistica Telegram — full report (2026-07-27)

Branch: `test/e2e-multimedia-logistica-telegram-20260727` (cut fresh off `main`;
the plan's original `fix/forge-sin-distribucion` branch had already been merged
and `main` had moved on to v1.0.13, so it was stale). The first verification
pass touched only `tests/` and `docs`; the follow-up fixes listed below are
being packaged for release as v1.0.14.

The harness described in the plan (`tests/support/e2e_pipeline.py`,
`e2e_audit.py`, `fake_telegram.py`, `tests/fixtures/e2e_pipeline_matrix.json`,
`tests/smoke_e2e_pipeline.py`) already existed on `main`, built and merged in a
prior session (commit `d5e1b04`) together with the production fix that routes
captions per-tanda instead of through one global file. This pass: re-verified
that harness still passes against current `main` (v1.0.13), analyzed every
distribution mode Logística actually has, added test coverage for the modes
the mandatory 27-file matrix doesn't exercise, added negative-case coverage,
fixed a bug in the harness itself, and found two real bugs in production
code.

**Update (same session, follow-up request):** both production bugs found
below — `LOGISTICA_NO_CROSS_RUN_ANTICOLLISION` and `EMOJI_PRINT_CRASH` — were
then fixed with TDD (failing test first, watched it fail, minimal fix,
watched it pass), and the full closing suite was rerun clean afterward. The
first fix attempt for the anti-collision bug was itself too broad (see the
bug table) and got caught by rerunning the mandatory 27-file smoke, which
regressed to 24/27 — narrowed the fix and confirmed 27/27 again before
calling it done.

## 1. Files created / modified

Created:
- `console_encoding.py` — shared `ensure_stdout_utf8()` guard; the fix for `EMOJI_PRINT_CRASH`.
- `tests/test_logistica_por_cuentas_e2e.py` — functional coverage for the "Por Cuentas" distribution mode (previously only had a source-string-match test).
- `tests/test_logistica_fillup_e2e.py` — functional coverage for `distribute_tanda(..., fill_up=True)` and multi-day runs (previously never exercised — the matrix always calls it with `fill_up=False, days="1"`).
- `tests/test_logistica_negative_cases.py` — missing tanda folder, category with zero accounts, rerun-into-existing-day collision handling, and two regression tests for the anti-collision fix (same-tanda rerun blocked; cross-tanda false positive not blocked).
- `tests/test_telegram_single_account_selection.py` — selecting one account must not leak other accounts' files or pre-create their topics.
- `tests/test_console_encoding.py` — regression tests for `EMOJI_PRINT_CRASH` / `console_encoding.ensure_stdout_utf8()`.
- `docs/test-reports/2026-07-27-e2e-multimedia-logistica-telegram-full.md` — this report.

Modified (production code — only after the user explicitly asked for the two bugs to be fixed):
- `Organizador.py` — `distribute_tanda` now seeds `account_lifetime_combos` from `fingerprint_history`, scoped to the tanda(s) being distributed (new `get_account_used_combinations_for_tandas()`). Fixes `LOGISTICA_NO_CROSS_RUN_ANTICOLLISION`.
- `videos.py`, `organizadortg.py`, `gui_premium_v7.py` — each now calls `console_encoding.ensure_stdout_utf8()` at import time. Fixes `EMOJI_PRINT_CRASH`.

Modified (test harness / docs):
- `tests/smoke_e2e_pipeline.py` — briefly added a stdout-encoding workaround, then removed it once the production fix (above) made it redundant — the smoke now passes with zero env-var or test-side workarounds.
- `tests/support/e2e_pipeline.py` — fixed `patched_modules()` restoring an already-closed `organizadortg.db` connection on exit (harness bug, not production; see bug table).
- `docs/superpowers/plans/2026-07-26-e2e-multimedia-logistica-telegram.md` — checked off Tasks 1–6 (already implemented and reverified), Task 7 Steps 1 and 5, Task 8 Step 3. Left unchecked: Task 7 Steps 2/3/4/6 (Edición/Tandas/Forge/Telegram edge cases beyond what's listed here), Task 8 Steps 1/2/4 (manual GUI screenshot walkthrough and the real-Telegram gate — both require a human, not automatable here).

Untouched, as instructed: `organizador.db`, `videos_finales/`, `CALENDARIO_POSTEO/`, any real Telegram group, `organizador.db.bak_20260724`.

## 2. Análisis de los modos de distribución de Logística

Read `Organizador.py` in full and `gui_premium_v7.py:2234-2934` (the whole
Logística frame). There are **four** distribution code paths, not one:

### A. "Por Tandas" tab — `Organizador.distribute_tanda(tanda, category, quota, fill_up, days, tanda_name_2=None)`
The main, category-scoped engine. Filters accounts by `account_type == category`.
Builds a pool of every video in `videos_finales/<tanda>/` (and a second tanda's
folder too, if `tanda_name_2` is set — the "dos tandas" option in the GUI).
Anti-collision has two tiers per account/day/slot: a **hard rule** (never
repeat a P1+P2 combo for the same account, tracked in an in-memory
`account_lifetime_combos` dict built fresh every call) and a **soft rule**
(penalize a P1 already used today by this account or in this time slot).
`fill_up=True` only changes one thing: when the per-run pool (`video_items`,
which shrinks as videos get consumed) has nothing left for a slot, it retries
against `full_tanda_pool` — the *original*, unshrunk list — still respecting
the hard per-account rule. In practice this lets account B reuse a video
account A already posted, once fresh inventory runs out; it does **not**
manufacture new content (that's `generate_fill_up_combinations`, see D).
This is what `preview_distribution_tanda` + `distribute_tanda` in
`tests/smoke_e2e_pipeline.py` exercise for all 9 tandas — but always with
`fill_up=False` and `days="1"`, so the fill-up branch and multi-day runs were
never actually exercised until this pass (`test_logistica_fillup_e2e.py`).

### B. "Por Cuentas" tab — `gui_premium_v7.py::_acct_dist_run`
A **second, fully independent implementation**, not a wrapper around
`distribute_tanda`. Differences that matter:
- Account selection is **manual** (a free-text list the user builds via
  "+ Cargar categoría" / "+ Cargar promo/suicide" / typing `@cuenta`), so it
  can freely **cross categories** — that's the point of the tab, not a bug.
- Sizing is "videos/día × período" (`Stepper` + `1 semana`/`2 semanas`/
  `3 semanas`/`1 mes` → 7/14/21/30 days), not "daily quota × días a organizar".
- Anti-collision keys on a Forge-style `vid_id` (`source__cNN` with the
  `__cNN` stripped) rather than P1/P2 — appropriate since this tab is what's
  left to distribute Forge output now that Forge's own auto-distribution was
  removed (commit `8214eb3`, "fix(forge): remove automatic distribution
  controls").
- It still writes through the same `build_calendar_video_filename()`, so the
  `__TANDA_<name>__` tag Telegram relies on for caption routing is identical.
Before this pass, the *only* test touching this code was
`test_logistica_caption_ui.py::test_por_cuentas_distribution_calendarizes_filenames_for_telegram_captions`
— which just `grep`s the method's source text for the string
`"build_calendar_video_filename"`. It never ran the algorithm. I added
`test_logistica_por_cuentas_e2e.py`, which instantiates the real
`gui_premium_v7.InstagramAutoPro()` (same pattern as the existing
`test_dashboard_refresh.py`), drives the real bound `_acct_dist_run`, and
checks the actual files produced: 2 accounts from **two different
categories**, 14 files (2 accounts × 7 days × 1/day), every filename carries
`__TANDA_PC_SRC__`, no file lands outside the two selected accounts, and the
tanda's own caption resolves correctly for every one of the 14 files via the
real `organizadortg.caption_for_calendar_video`.

### C. Legacy `Organizador.distribute(daily_goal, fill_up)` — dead code
Only ever called from `Organizador.py`'s own `if __name__ == "__main__":`
block. `grep` across `gui_premium_v7.py` found zero call sites. It expects a
totally different on-disk layout (`videos_finales/<category>/`, flat, no
tanda subfolders) and module-level globals (`DAILY_GOAL`, `FILL_UP_ENABLED`)
that nothing in the current schema populates the way it expects. It is the
only caller of `generate_fill_up_combinations` / `generate_fill_up_from_history`
(which manufacture *new* P1×P2 combinations from the tanda's raw `inputs/`
folders — different from mode A's fill-up, which only *reuses* existing
processed outputs) and of `get_all_used_combinations()` /
`pick_balanced_with_anti_collision()`, which read `fingerprint_history` —
these are the *only* functions in the file that check history across runs
(see bug `LOGISTICA_NO_CROSS_RUN_ANTICOLLISION` below). Not reachable from the
GUI today, so not in scope for functional E2E coverage; flagged here in case
anyone reactivates it — it would need real testing since it's unexercised in
years.

### D. Fill-up combination generators — `generate_fill_up_combinations` / `generate_fill_up_from_history`
Described under C. Not called by anything reachable from the GUI (`distribute_tanda`
has its own, simpler fill-up — see A). Dead code today, same caveat as C.

**Extra tandas added for mode coverage** (beyond the mandatory 9): the plan's
matrix is fixed at 9 tandas / 3 categories / 3 VAs / 27 files and I did not
touch that — it's an explicit, literal requirement. Instead I added
*separate, isolated* scenarios (own temp DB + temp dirs, never mixed into the
27-file run) to reach the modes the fixed matrix structurally can't reach:
one `PC_SRC` tanda run through mode B across 2 cross-category accounts
(14 files), and one `FILLUP_TA` tanda run through mode A twice — once with
`fill_up=False`, once with `fill_up=True`, across 2 days — to actually
observe the divergence Task 7 Step 5 asked for.

## 3. Comandos de cierre — resultado real

Ran twice: once before the two production fixes (evidence in the bug table),
once after. Final, post-fix run:

```
$ py -m pytest tests -q
.........................s.............................................. [ 51%]
.....................................................................    [100%]
140 passed, 1 skipped in 24.39s
(the 1 skip is tests/test_dashboard_refresh.py's pre-existing
"no display available" guard -- environment-dependent, unrelated to any
change made in this pass; it passes on most runs in this same environment)

$ py -m compileall video_editor.py videos.py metadata_pool.py Organizador.py organizadortg.py gui_premium_v7.py console_encoding.py -q
(exit code 0, no output)

$ py tests/smoke_execute_plan.py
✅ Todos los símbolos importan correctamente.
   DEFAULT_SCHEDULE tiene 7 días.
   TIMEZONE_LABELS tiene 6 entradas.
   8:00 AM ET → 9:00 AM ART (Buenos Aires)

$ py -m pytest tests/smoke_e2e_pipeline.py -q
.                                                                        [100%]
1 passed in 14.62s

$ git diff --check
(exit code 0 -- one informational "LF will be replaced by CRLF" line-ending
notice from git, not a whitespace-check failure)
```

All five green. `140 passed` includes the 4 new test files from the coverage
pass (9 test functions) plus `tests/test_console_encoding.py` (4 more, added
for the `EMOJI_PRINT_CRASH` fix) plus everything that already existed;
`tests/smoke_e2e_pipeline.py` is deliberately excluded from the `tests -q`
collection (its filename doesn't match pytest's `test_*.py` default, same as
`smoke_execute_plan.py` — this is how the plan's own file naming works, not
an oversight).

The `smoke_e2e_pipeline.py` run above used **no `PYTHONIOENCODING`, no
env-var workaround of any kind** — that's the actual proof `EMOJI_PRINT_CRASH`
is fixed at the source, not papered over in the test.

## 4. run_id y conteos

Main mandatory-matrix run (from the final, post-fix `smoke_e2e_pipeline.py`
execution above, no `PYTHONIOENCODING` set):

- **run_id**: `e2e-20260727-145044-4433b468`
- **run_root**: `C:\Users\Wodahs\AppData\Local\Temp\ig_gui_e2e_pipeline\e2e-20260727-145044-4433b468`
- **audit.json**: `C:\Users\Wodahs\AppData\Local\Temp\ig_gui_e2e_pipeline\e2e-20260727-145044-4433b468\audit.json`
- **audit.md**: `C:\Users\Wodahs\AppData\Local\Temp\ig_gui_e2e_pipeline\e2e-20260727-145044-4433b468\audit.md`
- **manifest.json**: same folder, `manifest.json`

(Earlier run `e2e-20260727-142447-bada30f8`, from before both fixes, had the
same 27/27/27/0-findings result — `EMOJI_PRINT_CRASH` only manifests with a
non-UTF8 console codepage, which that run happened not to hit since
`PYTHONIOENCODING` was set at the time; see the bug table for the actual
reproduction command.)

| metric | expected | actual |
| --- | --- | --- |
| processed outputs (Edición+Tandas+Forge) | 27 | 27 |
| distributed files (CALENDARIO_POSTEO) | 27 | 27 |
| Telegram sends (fake sender) | 27 | 27 |
| audit findings | — | **0** |

Supplementary scenarios (each in its own ephemeral `make_run_root()` temp
directory, cleaned up by the test itself — no persistent run_id/audit.json by
design, these are pytest assertions, not audited campaigns):

| scenario | test | expected | actual |
| --- | --- | --- | --- |
| Por Cuentas, 2 cross-category accounts × 7 days × 1/day | `test_logistica_por_cuentas_e2e.py` | 14 files, correct tanda tag + caption on all 14 | 14 / 14, 0 mismatches |
| `distribute_tanda`, fill_up=False, day 2 starved | `test_logistica_fillup_e2e.py` | 3 files day 1, 0 day 2 | 3 / 0 (matches) |
| `distribute_tanda`, fill_up=True, day 2 starved | `test_logistica_fillup_e2e.py` | 3 files day 1, 3 files day 2, no same-account repeat | 3 / 3, 0 repeats |
| distribute_tanda, missing tanda folder | `test_logistica_negative_cases.py` | graceful error string, no crash, no files | matched |
| distribute_tanda, category with 0 accounts | `test_logistica_negative_cases.py` | graceful error string | matched |
| distribute_tanda, rerun into existing Dia_1 | `test_logistica_negative_cases.py` | no overwrite/collision on disk | matched |
| Telegram, select 1 of 2 accounts | `test_telegram_single_account_selection.py` | exactly 1 send, 1 topic, no leak to the other account | matched |

## 5. Tabla de bugs

| status | code | severity | where | what | evidence |
| --- | --- | --- | --- | --- | --- |
| **FIXED** | `LOGISTICA_NO_CROSS_RUN_ANTICOLLISION` | Real, medium-high | `Organizador.distribute_tanda` | Anti-collision (`account_lifetime_combos`) was rebuilt from scratch, in memory, on every call — never consulted `fingerprint_history`. Two separate "Distribuir" runs for the same tanda/category (re-click, or app restart) could send the **exact same video** to the **exact same account** twice. **Fix:** new `get_account_used_combinations_for_tandas(account_id, tanda_names)` seeds `account_lifetime_combos` from `fingerprint_history`, filtered to only the tanda(s) currently being distributed (matches on the `__TANDA_<name>__` tag Logística already stamps on every calendar file). **First attempt was too broad** — seeding from *all* history regardless of tanda (reusing the existing `get_account_used_combinations()`) made the mandatory 27-file matrix regress to **24/27**: Forge's `source__cNN` naming makes `parse_combination_from_filename` return the *same* (p1, p2) for a Forge copy as for the raw Edición source it was built from, so an account that had already received `ED_A`'s raw output got wrongly blocked from ever receiving `FO_A` (a different tanda, same underlying content) — exactly the ambiguity the plan itself warned about in Task 4 Step 5 ("para Forge... comparar con `forge_video_registry`, no exigir P1/P2"). Narrowing the seed to the current tanda(s) fixed the false positive and restored 27/27. | RED→GREEN in `tests/test_logistica_negative_cases.py`: `test_distribute_tanda_does_not_resend_identical_video_to_same_account_across_separate_runs` (same-tanda rerun now correctly skipped, not resent) and `test_distribute_tanda_cross_run_anticollision_is_scoped_to_the_same_tanda` (a different tanda sharing the same parsed identity is *not* blocked). Full mandatory smoke reverified at 27/27/27, 0 findings after the fix (run `e2e-20260727-145044-4433b468`). |
| **FIXED** | `EMOJI_PRINT_CRASH` | Real, environment-dependent, high impact when it hits | `videos.py`, `Organizador.py`, `organizadortg.py`, `gui_premium_v7.py` (unconditional `print(f"🎬 ...")` etc. — 11 + 17 + 36 + 1 occurrences respectively) | On a Windows console whose codepage isn't UTF-8, `print()` of an emoji raised `UnicodeEncodeError`, which `videos.render_tanda` re-raised as a hard `Exception`, aborting the whole Tandas render. This machine's default codepage is 850 and `PYTHONIOENCODING`/`PYTHONUTF8` are unset — a plausible real-world Windows/Spanish-locale default. `tests/smoke_execute_plan.py` already had its own ad hoc `sys.stdout.reconfigure(...)` (someone had already hit this once), but nothing in production code guarded against it. **Fix:** new shared `console_encoding.ensure_stdout_utf8()`, called at import time by all four modules (`stream.reconfigure(encoding="utf-8", errors="replace")` on stdout and stderr). | RED: reproduced original crash first (`UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f3ac'`, `videos.py:295`/`302`, no `PYTHONIOENCODING` set). `tests/test_console_encoding.py` (4 tests): direct unit test of `ensure_stdout_utf8()` against a strict-cp1252 stream, reload-based behavioral proof for `videos`/`Organizador` (side-effect-free to reload), static source check for `organizadortg`/`gui_premium_v7` (reload-unsafe — each has import-time state, see `PATCHED_MODULES_DEAD_DB_RESTORE` for exactly the class of bug that risks). GREEN confirmed for real: `py -m pytest tests/smoke_e2e_pipeline.py -q` with **no `PYTHONIOENCODING` set at all** — 27/27/27, 1 passed. The test-only workaround previously added to `tests/smoke_e2e_pipeline.py` was then removed since it's now redundant, and the smoke still passes. |
| **FIXED (harness only, not production)** | `PATCHED_MODULES_DEAD_DB_RESTORE` | Test-harness bug, not production | `tests/support/e2e_pipeline.py::patched_modules` | On exit, restored `organizadortg.db = saved["organizadortg.db"]` — the exact object the same context manager had already `.close()`d moments earlier when it swapped in the run-root DB. Any test running afterward in the same pytest process that touched `organizadortg.db` got `sqlite3.ProgrammingError: Cannot operate on a closed database.` It was latent because `smoke_e2e_pipeline.py`'s filename doesn't match pytest's collection pattern, so `patched_modules` never ran inside a plain `pytest tests -q` before this pass added new `test_*.py` files that also use it. | `py -m pytest tests -q` before the fix: `test_telegram_topic_reset.py::test_execute_plan_resets_selected_account_topics_before_recreating` failed with the closed-database error. Fixed by reopening a fresh `DatabaseManager()` against the restored `DB_PATH` instead of restoring the dead reference; full suite green afterward. |
| **PREVIOUSLY FIXED (confirmed closed, not reopened)** | global-captions-file mixing (the bug the original plan was written to hunt) | — | `organizadortg.py` / `gui_premium_v7.py` | The plan's addendum describes a bug where Telegram used one global captions file (`self.acct_cap_file or self.tandas_cap_file`) cycling by index, which could mix or lose per-tanda captions. Confirmed by reading current code: `execute_telegram_plan()`'s signature no longer even takes a captions-file argument; `grep` for `acct_cap_file`/`tandas_cap_file` across `gui_premium_v7.py` returns nothing. Captions are resolved strictly per-tanda via `caption_for_calendar_video()`, which extracts `__TANDA_<name>__` from the calendar filename and looks up that tanda's own `captions_file_path`. | Fixed in commit `d5e1b04` (prior session), re-verified in this pass: 0 caption-related findings across the 27-file run, both with and without any extra caption file involved (there's no such parameter anymore). |

## 6. Confirmación explícita

**No se mezclaron captions, tandas, cuentas ni VAs** en la corrida principal de
27 archivos (`audit.json` findings = 0; ver tabla de conteos arriba) ni en
ninguna de las 4 corridas suplementarias (Por Cuentas cross-category, fill-up
on/off, casos negativos, selección de una sola cuenta en Telegram) — cada una
verificó explícitamente ausencia de mezcla como parte de sus asserts, y todas
pasaron.

Los dos bugs reales de producción encontrados en la primera pasada
(`LOGISTICA_NO_CROSS_RUN_ANTICOLLISION` y `EMOJI_PRINT_CRASH`) fueron
corregidos a pedido explícito del usuario, con TDD (test que falla primero,
código mínimo, test en verde) en ambos casos. El primer intento de arreglo de
`LOGISTICA_NO_CROSS_RUN_ANTICOLLISION` era demasiado amplio y rompió la
matriz obligatoria (24/27 en vez de 27/27); se detectó al volver a correr el
smoke principal, se acotó el fix y se reverificó 27/27/27 con 0 findings. El
bug de arnés de prueba `PATCHED_MODULES_DEAD_DB_RESTORE` también quedó
corregido. El bug original que motivó el plan (captions global mezclando
tandas) ya estaba corregido antes de esta pasada y se reverificó como
cerrado.

**No se mezclaron captions, tandas, cuentas ni VAs** en ninguna corrida,
antes ni después de los fixes.
