# Normal Individual Captions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement task-by-task.

**Goal:** Add optional literal captions by Forge source to Logística > Por Cuentas.

**Architecture:** A normal-tanda map is persisted separately from Trial captions. When the switch is enabled, Por Cuentas reuses the source grouping, preview thumbnail and editor pattern already used by Trials; Telegram selects that map before its regular per-tanda caption pool. Disabled behavior is unchanged.

**Tech Stack:** Python, SQLite, CustomTkinter, FFmpeg/Pillow, pytest.

## Global Constraints

- Keep Trials unchanged.
- Disabled switch keeps current caption rotation/shuffle behavior.
- Enabled switch sends every `source__cNN` copy with its exact saved caption.
- Do not reuse or alter calendar filename format.

### Task 1: Persist and resolve normal source captions

**Files:**

- Modify: `database.py`, `organizadortg.py`
- Modify: `tests/test_telegram_caption_routing.py`

- [ ] **Step 1: Add a failing routing test**

```python
def test_normal_individual_copies_use_same_literal_caption():
    captions = {"vid1": "caption one"}
    assert caption_for_normal_individual_video("vid1__c01__TANDA_T__ACC1__D1__S1.mp4", captions) == "caption one"
    assert caption_for_normal_individual_video("vid1__c02__TANDA_T__ACC1__D1__S2.mp4", captions) == "caption one"
```

- [ ] **Step 2: Run it**

Run: `py -m pytest tests/test_telegram_caption_routing.py -q`  
Expected: FAIL because the individual resolver does not exist.

- [ ] **Step 3: Add storage and resolver**

```python
CREATE TABLE IF NOT EXISTS normal_source_captions (
    tanda_name TEXT NOT NULL, source_key TEXT NOT NULL, caption_text TEXT NOT NULL,
    PRIMARY KEY (tanda_name, source_key)
);
```

Add `set_normal_source_caption`, `get_normal_source_captions`,
`normal_tanda_has_individual_captions`, and a literal resolver based on
`extract_source_key_from_calendar_filename`.

- [ ] **Step 4: Verify**

Run: `py -m pytest tests/test_telegram_caption_routing.py tests/test_trials_storage.py -q`  
Expected: PASS.

### Task 2: Optional Por Cuentas controls

**Files:**

- Modify: `gui_premium_v7.py: _build_dist_cuentas_tab, _acct_dist_run`
- Modify: `tests/test_logistica_caption_ui.py`

- [ ] **Step 1: Add failing UI assertions**

```python
def test_por_cuentas_has_optional_individual_caption_controls():
    source = _method_source("_build_dist_cuentas_tab")
    assert "Captions individuales" in source
    assert "_acct_refresh_individual_captions" in source
```

- [ ] **Step 2: Run it**

Run: `py -m pytest tests/test_logistica_caption_ui.py -q`  
Expected: FAIL.

- [ ] **Step 3: Reuse the Trial editor pattern**

Add a switch that shows only when enabled: grouped source cards, first-copy
thumbnail, text editor and save action. Store by normal tanda/source. Before
execution require a caption for every source only if enabled.

- [ ] **Step 4: Verify**

Run: `py -m pytest tests/test_logistica_caption_ui.py tests/test_telegram_caption_routing.py -q`  
Expected: PASS.

### Task 3: Verification

- [ ] Run:

```powershell
py -m pytest tests/test_logistica_caption_ui.py tests/test_telegram_caption_routing.py tests/test_telegram_captions.py tests/test_logistica_trials.py tests/test_telegram_trials_routing.py -q
py -m py_compile database.py gui_premium_v7.py organizadortg.py trial_content.py
```

Expected: all selected tests pass and compilation exits 0.

