# Logística Global Daily Anti-Collision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `Logística > Por Cuentas` reject same-origin video collisions across accounts on the same day, treating `__cNN` files as copies of one logical origin.

**Architecture:** Keep the existing `source_key_from_filename()` identity and plan structure. Change only candidate eligibility in `_acct_dist_run()` so the daily global origin set is a hard exclusion, while preserving physical-file assignment, randomization, manifest writing, and caption routing.

**Tech Stack:** Python, CustomTkinter legacy GUI, pytest, temporary SQLite/filesystem fixtures.

## Global Constraints

- Work only in the isolated `feature/logistica-global-daily-anticollision` worktree based on `origin/main`.
- Preserve all pre-existing changes in the original dirty checkout.
- Do not alter cross-day rotation, captions, Telegram routing, or manifest schema.
- Verify the regression in RED before changing production code.

---

### Task 1: Add the failing cross-account same-origin regression

**Files:**
- Modify: `tests/test_logistica_por_cuentas_e2e.py`
- Read: `trial_content.py::source_key_from_filename`

**Interfaces:**
- Consumes: the existing `_make_app()` and `_SyncWorkerThread` test harness.
- Produces: `test_por_cuentas_rejects_same_origin_across_accounts_on_same_day`.

- [ ] **Step 1: Write the failing test**

Create two accounts and one tanda containing exactly two physical files, `PC_DAILY__ORIGIN_A__P2__c01.mp4` and `PC_DAILY__ORIGIN_A__P2__c02.mp4`. Run Por Cuentas with both accounts, `1` video/day, and `MAX`. Assert the result reports `Sin candidatos` and writes no manifest, because both files represent one origin and cannot fill two account slots on the same day.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
py -m pytest tests/test_logistica_por_cuentas_e2e.py::test_por_cuentas_rejects_same_origin_across_accounts_on_same_day -q
```

Expected: FAIL because the current scoring only penalizes `day_vid_ids_used` and assigns both physical copies.

### Task 2: Make daily global origin uniqueness a hard rule

**Files:**
- Modify: `gui_premium_v7.py:3531-3549`

**Interfaces:**
- Consumes: `day_vid_ids_used`, `acc_today_vid_ids`, and `source_key_from_filename()` already used by `_acct_dist_run()`.
- Produces: a candidate pool that excludes any `vid_id` already selected for the current day, regardless of account.

- [ ] **Step 1: Write the minimal production change**

Inside the candidate loop, after the same-account/day check, add a hard `continue` when `vid_id in day_vid_ids_used`. Remove the old `score += 100` branch for that condition. Leave the existing lifetime penalty and slot penalty unchanged.

The essential logic becomes:

```python
vid_id = forge_vid_id(item_name(v))
if vid_id in acc_today_vid_ids:
    continue
if vid_id in day_vid_ids_used:
    continue
score = 0
if vid_id in acc_lifetime_vid_ids[acc]:
    score += 200
if vid_id in slot_vid_ids_used:
    score += 50
```

- [ ] **Step 2: Run the regression to verify it passes**

Run:

```powershell
py -m pytest tests/test_logistica_por_cuentas_e2e.py::test_por_cuentas_rejects_same_origin_across_accounts_on_same_day -q
```

Expected: PASS with the existing `Sin candidatos` error path and no calendar manifest entries.

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
