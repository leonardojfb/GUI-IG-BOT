# Logística Global Daily Anti-Collision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `Logística > Por Cuentas` reject same-origin video collisions inside one account/day while allowing each account to consume its own physical copy set.

**Architecture:** Keep the existing `source_key_from_filename()` identity and plan structure. Preserve the per-account/day hard exclusion and restore the cross-account daily origin score as a soft preference, while preserving physical-file assignment, randomization, manifest writing, and caption routing.

**Tech Stack:** Python, CustomTkinter legacy GUI, pytest, temporary SQLite/filesystem fixtures.

## Global Constraints

- Work only in the isolated `feature/logistica-global-daily-anticollision` worktree based on `origin/main`.
- Preserve all pre-existing changes in the original dirty checkout.
- Do not alter cross-day rotation, captions, Telegram routing, or manifest schema.
- Verify the regression in RED before changing production code.

---

### Task 1: Add the failing copy-set regression

**Files:**
- Modify: `tests/test_logistica_por_cuentas_e2e.py`
- Read: `trial_content.py::source_key_from_filename`

**Interfaces:**
- Consumes: the existing `_make_app()` and `_SyncWorkerThread` test harness.
- Produces: `test_por_cuentas_reuses_copy_sets_across_accounts_without_daily_origin_collisions`.

- [ ] **Step 1: Write the failing test**

Create 20 accounts and one tanda containing 20 physical copies of each of 30 logical origins. Run Por Cuentas with 3 videos/day and `MAX`. Assert that the run creates 600 entries, gives every account 30 logical origins, and never repeats an origin within one account/day. Also assert that day 1 has fewer unique origins than total rows, proving cross-account reuse is allowed.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
py -m pytest tests/test_logistica_por_cuentas_e2e.py::test_por_cuentas_reuses_copy_sets_across_accounts_without_daily_origin_collisions -q
```

Expected: FAIL because the current global daily hard filter rejects the second account once the 30 shared origins are exhausted.

### Task 2: Restore per-account daily origin uniqueness

**Files:**
- Modify: `gui_premium_v7.py:3531-3549`

**Interfaces:**
- Consumes: `day_vid_ids_used`, `acc_today_vid_ids`, and `source_key_from_filename()` already used by `_acct_dist_run()`.
- Produces: a candidate pool that excludes any `vid_id` already selected for the current account/day while retaining a soft cross-account spread preference.

- [ ] **Step 1: Write the minimal production change**

Inside the candidate loop, keep the hard `continue` for `acc_today_vid_ids`, remove the hard `continue` for `day_vid_ids_used`, and restore `score += 100` for that condition. Leave the existing lifetime penalty and slot penalty unchanged.

The essential logic becomes:

```python
vid_id = forge_vid_id(item_name(v))
if vid_id in acc_today_vid_ids:
    continue
score = 0
if vid_id in acc_lifetime_vid_ids[acc]:
    score += 200
if vid_id in day_vid_ids_used:
    score += 100
if vid_id in slot_vid_ids_used:
    score += 50
```

- [ ] **Step 2: Run the regression to verify it passes**

Run:

```powershell
py -m pytest tests/test_logistica_por_cuentas_e2e.py::test_por_cuentas_rejects_same_origin_across_accounts_on_same_day -q
```

Expected: PASS with 600 manifest entries and 30 logical origins per account.

### Task 3: Verify the focused suite and diff

**Files:**
- Read: `tests/test_logistica_por_cuentas_e2e.py`
- Read: `gui_premium_v7.py`

- [ ] **Step 1: Run the full Por Cuentas E2E suite**

```powershell
py -m pytest tests/test_logistica_por_cuentas_e2e.py -q
```

Expected: all runnable tests pass; display-dependent tests may remain skipped as in the baseline.

- [ ] **Step 2: Run syntax and focused related tests**

```powershell
py -m py_compile gui_premium_v7.py trial_content.py
py -m pytest tests/test_logistica_caption_ui.py tests/test_calendar_manifest.py -q
```

Expected: exit code 0 and no new failures.

- [ ] **Step 3: Review the isolated diff**

```powershell
git diff --check
git diff --stat
git status --short
```

Expected: only the design/plan documents, the regression test, and the focused `gui_premium_v7.py` change are modified in this worktree.

- [ ] **Step 4: Commit the implementation**

```powershell
git add gui_premium_v7.py tests/test_logistica_por_cuentas_e2e.py
git commit -m "fix: block daily origin collisions in account logistics"
```
