# Trial General Captions Per Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each distributed Trial Forge file one TXT caption, exhausting the tanda pool across accounts before cycling.

**Architecture:** Select one Trial caption mode and one TXT above the account list, parse it with a shared pure function, assign captions from the completed Trial plan in chronological order per tanda, persist each assignment in the manifest, and read it at Telegram send time. Individual and legacy Trial entries keep their source-caption routing.

**Tech Stack:** Python, SQLite, CustomTkinter, JSON manifest, pytest.

## Global Constraints

- Use the current dirty checkout and preserve unrelated edits and data.
- Individual remains the initial mode and retains verified-origin caption synchronization.
- General captions are assigned per physical Forge file, with one caption sequence per tanda shared across all selected accounts.
- An absent or empty TXT blocks General distribution before the manifest changes.
- Existing calendars are not rewritten.

### Task 1: Trial TXT persistence and shared parser

**Files:** Modify `database.py`, `trial_content.py`, `organizadortg.py`; test `tests/test_trials_storage.py`, `tests/test_telegram_captions.py`.

**Interfaces:** `DatabaseManager.set_trial_tanda_captions(tanda, path)` and `get_trial_tanda_captions(tanda)` persist a Trial-only path. `trial_content.load_clean_captions(path)` reads the existing TXT formats and `organizadortg.load_clean_captions` remains available.

- [ ] Write tests asserting a Trial tanda without a `batch_tandas` row can save, read, and clear its TXT and that an existing database gains the new column without losing rows.
- [ ] Run those tests to observe missing API and migration failures.
- [ ] Add the column to the new schema and existing-schema migration; add the two DB methods. Move the existing parser unchanged to `trial_content.py` and import it into `organizadortg.py`.
- [ ] Run the focused storage and parser tests until green.

### Task 2: Pure per-video caption plan

**Files:** Modify `trial_content.py`; test `tests/test_logistica_trials.py`.

**Interfaces:** `assign_trial_general_captions(plan, assignments, modes, pools, videos_per_day) -> dict[tuple[str, str], str]` returns `(username, filename)` to literal caption for General only.

- [ ] Write a failing test with two accounts sharing one tanda, two copies of one origin, three captions, and a fourth file; assert the sequence is A/B/C/A and all copies are addressed individually.
- [ ] Add tests for separate tandas and Individual accounts not consuming the sequence.
- [ ] Implement stable day/slot/account/filename sorting and modulo assignment.
- [ ] Run focused planner tests until green.

### Task 3: TRIAL GUI and manifest

**Files:** Modify `gui_premium_v7.py`; test `tests/test_trial_account_selection.py`.

**Interfaces:** `trial_caption_mode` and `trial_general_txt_path` are single controls above the account list. Distribution applies the mode to all selected accounts, uses the chosen TXT as the pool for each selected tanda, calls `assign_trial_general_captions`, previews the mapping, and passes `caption_mode` plus `caption` to `build_entry`.

- [ ] Write integration tests for preview and written manifest agreeing across shared-tanda accounts, a missing TXT blocking General before write, and Individual default preserving old behavior.
- [ ] Run those tests to observe the missing behavior.
- [ ] Add one General/Individual selector and one TXT picker above the account list. Show account caption editors only in Individual. Validate the chosen TXT, assign captions once from the completed plan, display them in preview, and persist them in Trial entries.
- [ ] Run focused GUI tests until green.

### Task 4: Telegram routing and final verification

**Files:** Modify `organizadortg.py`; test `tests/test_telegram_caption_routing.py`, `tests/test_telegram_trials_routing.py`.

**Interfaces:** Manifest scan carries `caption` to Telegram rows. For Trial `caption_mode=general`, Telegram uses that stored text; for Individual or absent mode, it resolves the source caption as before.

- [ ] Write a failing send-plan test showing two copies of one origin use different stored General captions, and a legacy Trial entry still uses its source caption.
- [ ] Run the test to observe the old source-only routing.
- [ ] Carry the manifest caption through scan and switch Trial caption resolution by mode.
- [ ] Run focused Trial, calendar, and Telegram tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, compile edited Python modules, and inspect the diff for unrelated changes.
