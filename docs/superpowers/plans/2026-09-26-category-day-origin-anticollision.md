# Category-Day Origin Anti-Collision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Por Cuentas avoid same-category, same-day logical-origin repeats first, then fill up with the least-used origin when unavoidable.

**Architecture:** `MainApp._acct_dist_run` already derives logical origins with `source_key_from_filename`. Track per-day category origin use counts and prioritize the least-used origin before existing scoring. Tests exercise the real GUI distribution task synchronously with a temporary base directory.

**Tech Stack:** Python 3.14, pytest, Tk/CustomTkinter application helpers.

## Global Constraints

- Do not alter runtime `calendar_manifest.json`, `organizador.db`, media, or active GUI process.
- Treat `__cNN` copies as one logical origin.
- Prefer uniqueness only inside one category and calendar day.
- Fill up with the least-used origin when unique daily capacity is insufficient, and report each repeat.

---

### Task 1: Prove and enforce least-used category/day fill-up

**Files:**

- Modify: `tests/test_logistica_por_cuentas_e2e.py`
- Modify: `gui_premium_v7.py:3514-3559`

**Interfaces:**

- Consumes: `source_key_from_filename(filename) -> str` and `self.db.get_all_accounts()` records containing `username` and `account_type`.
- Produces: a distribution plan that uses each `(category, day, source_key)` once before reusing its least-used origin.

- [ ] **Step 1: Write the failing test**

```python
def test_por_cuentas_fills_up_same_category_day_with_least_used_origins(tmp_path, monkeypatch):
    # Create 40 accounts in TALKING and 35 logical origins with 40 __cNN copies.
    # Request one video for each account on day 1.
    # Assert the run completes and each day has 30 origins once and 5 twice.
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -s tests/test_logistica_por_cuentas_e2e.py::test_por_cuentas_blocks_same_category_day_origin_reuse`

Expected: FAIL because the current capacity guard rejects the requested fill-up.

- [ ] **Step 3: Write minimal implementation**

```python
origin_usage = day_category_origin_usage.get((category_key(acc), vid_id), 0)
candidates.append((origin_usage, score, item))
...
day_category_origin_usage[usage_key] = origin_usage + 1
```

Use the category keyed by username from `self.db.get_all_accounts()`. Keep the existing account/day hard exclusion. Include a result line for each category/day fill-up count.

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `python -m pytest -s tests/test_logistica_por_cuentas_e2e.py`

Expected: all focused Por Cuentas tests pass, including the capacity regression.

- [ ] **Step 5: Compile and inspect scope**

Run: `python -m py_compile gui_premium_v7.py` and `git diff --check`

Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add gui_premium_v7.py tests/test_logistica_por_cuentas_e2e.py docs/superpowers/specs/2026-09-26-category-day-origin-anticollision-design.md docs/superpowers/plans/2026-09-26-category-day-origin-anticollision.md
git commit -m "fix: block same-category daily origin repeats"
```
