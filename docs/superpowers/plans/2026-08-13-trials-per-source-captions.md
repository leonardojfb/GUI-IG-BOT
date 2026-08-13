# Trials activos y captions por video fuente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir Trials independientes por cuenta, con captions literales por video fuente.

**Architecture:** SQLite persistirá cuentas Trial activas, tanda Trial y captions por fuente. Forge mantendrá `source__cNN`; Logística agrupará las copias, calendarizará solo cuentas activas en `CALENDARIO_TRIALS`, y Telegram resolverá un topic/caption Trial explícito sin alterar el flujo normal.

**Tech Stack:** Python 3, SQLite, CustomTkinter, pytest.

## Global Constraints

- No usar `account_type == "TRIALS"`; la categoría normal permanece intacta.
- Migraciones aditivas y compatibles con `organizador.db` existente.
- Trial usa caption literal, sin rotación ni `shuffle_hashtags`.
- Forge no distribuye automáticamente; mantener rutas largas y distribución normal.

---

### Task 1: Persistencia explícita de Trials

**Files:**

- Modify: `database.py: SCHEMA, _migrate_columns, account/tanda methods`
- Create: `tests/test_trials_storage.py`

**Interfaces:**

- Produces: `set_account_trials_active(username: str, active: bool) -> bool`
- Produces: `get_trials_active_accounts() -> list[dict]`
- Produces: `set_tanda_trial(name: str, is_trial: bool) -> bool`
- Produces: `get_trial_tandas() -> list[str]`
- Produces: `set_trial_source_caption(tanda_name: str, source_key: str, caption_text: str) -> None`
- Produces: `get_trial_source_captions(tanda_name: str) -> dict[str, str]`

- [ ] **Step 1: Write the failing tests**

```python
def test_trials_active_preserves_category(tmp_path):
    db = temporary_db(tmp_path)
    db.add_virtual_account("eve", "main")
    assert db.set_account_trials_active("eve", True) is True
    assert db.get_all_accounts()[0]["account_type"] == "main"
    assert db.get_all_accounts()[0]["trials_active"] == 1

def test_trial_captions_are_keyed_by_source(tmp_path):
    db = temporary_db(tmp_path)
    db.add_tanda("TRIAL_01", "TRIAL_01", "TRIAL_01", None)
    assert db.set_tanda_trial("TRIAL_01", True) is True
    db.set_trial_source_caption("TRIAL_01", "vid1", "caption 1")
    assert db.get_trial_tandas() == ["TRIAL_01"]
    assert db.get_trial_source_captions("TRIAL_01") == {"vid1": "caption 1"}
```

- [ ] **Step 2: Run the failing tests**

Run: `py -m pytest tests/test_trials_storage.py -q`  
Expected: FAIL because the methods do not exist.

- [ ] **Step 3: Implement the migration and methods**

```python
# _migrate_columns:
"ALTER TABLE virtual_accounts ADD COLUMN trials_active INTEGER NOT NULL DEFAULT 0",

# SCHEMA:
CREATE TABLE IF NOT EXISTS trial_tandas (
    tanda_name TEXT PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS trial_source_captions (
    tanda_name TEXT NOT NULL,
    source_key TEXT NOT NULL,
    caption_text TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tanda_name, source_key)
);

def set_account_trials_active(self, username, active):
    cur = self.conn.cursor()
    cur.execute("UPDATE virtual_accounts SET trials_active=? WHERE username=?",
                (int(bool(active)), username))
    self.conn.commit()
    return bool(cur.rowcount)
```

Implement the remaining interfaces with parameterized SQL and an upsert using `ON CONFLICT(tanda_name, source_key)`.

- [ ] **Step 4: Verify storage**

Run: `py -m pytest tests/test_trials_storage.py tests/test_telegram_caption_routing.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add database.py tests/test_trials_storage.py
git commit -m "feat: persist active trials and source captions"
```

### Task 2: Forge Trial mode and source grouping

**Files:**

- Create: `trial_content.py`
- Modify: `gui_premium_v7.py: _build_forge_frame, forge_preview_metadata, forge_process`
- Create: `tests/test_trial_content.py`
- Modify: `tests/test_forge_ui.py`

**Interfaces:**

- Produces: `source_key_from_filename(filename: str) -> str`
- Produces: `group_trial_sources(filenames: list[str]) -> list[tuple[str, list[str]]]`
- Consumes: `set_tanda_trial`.

- [ ] **Step 1: Write the failing tests**

```python
def test_group_trial_sources_returns_one_row_per_source():
    assert group_trial_sources([
        "vid1__c01.mp4", "vid2__c01.mp4", "vid1__c02.mp4"
    ]) == [
        ("vid1", ["vid1__c01.mp4", "vid1__c02.mp4"]),
        ("vid2", ["vid2__c01.mp4"]),
    ]

def test_source_key_removes_only_copy_suffix():
    assert source_key_from_filename("my__source__c03.mov") == "my__source"
```

Add UI assertions for `Normal`, `Trials`, `forge_trial_mode_var`, and `set_tanda_trial`, preserving the existing no-auto-distribution test.

- [ ] **Step 2: Run the failing tests**

Run: `py -m pytest tests/test_trial_content.py tests/test_forge_ui.py -q`  
Expected: FAIL because the helper and mode controls do not exist.

- [ ] **Step 3: Implement source grouping and Forge mode**

```python
_COPY_SUFFIX = re.compile(r"__c\d+$", re.IGNORECASE)

def source_key_from_filename(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    return _COPY_SUFFIX.sub("", stem)

def group_trial_sources(filenames):
    groups = {}
    for filename in sorted(filenames):
        groups.setdefault(source_key_from_filename(filename), []).append(filename)
    return list(groups.items())
```

Add a `Normal`/ `Trials` selector backed by `self.forge_trial_mode_var`. After the existing `add_tanda(...)`, call `set_tanda_trial(tanda_name, mode == "Trials")`. Do not alter the executor, filename format, or add distribution controls.

- [ ] **Step 4: Verify Forge behavior**

Run: `py -m pytest tests/test_trial_content.py tests/test_forge_ui.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add gui_premium_v7.py trial_content.py tests/test_trial_content.py tests/test_forge_ui.py
git commit -m "feat: add forge trials mode"
```

### Task 3: Logística > Trials and isolated calendar

**Files:**

- Modify: `gui_premium_v7.py: _build_dist_frame, reload_dist_lists, new Trial controls/run`
- Create: `tests/test_logistica_trials.py`
- Modify: `tests/test_logistica_caption_ui.py`

**Interfaces:**

- Consumes: `group_trial_sources`, `get_trial_tandas`, `get_trials_active_accounts`, Trial caption methods.
- Produces: `_trial_missing_caption_sources(tanda_name: str) -> list[str]`.
- Produces: `_trial_calendar_root() -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_trials_tab_has_one_multiline_caption_editor_per_source():
    source = gui_method("_build_dist_trials_tab")
    assert "group_trial_sources" in source
    assert "CTkTextbox" in source
    assert "Guardar captions Trial" in source

def test_missing_trial_caption_blocks_run(tmp_path):
    db = trial_db(tmp_path, ["vid1__c01.mp4", "vid2__c01.mp4"])
    db.set_trial_source_caption("TRIAL_01", "vid1", "caption 1")
    assert missing_trial_caption_sources(db, "TRIAL_01") == ["vid2"]

def test_trial_output_is_separate_and_only_active_accounts():
    assert trial_calendar_root("C:/repo").endswith("CALENDARIO_TRIALS")
    assert selected_trial_usernames([active_main, inactive_spam]) == ["main_active"]
```

- [ ] **Step 2: Run the failing tests**

Run: `py -m pytest tests/test_logistica_trials.py tests/test_logistica_caption_ui.py -q`  
Expected: FAIL because Trial controls/helpers do not exist.

- [ ] **Step 3: Implement the guarded Trial distribution**

Add the third `CTkTabview` tab `Trials`; leave existing tabs unmodified. Its tanda selector gets only `get_trial_tandas()`. Scan `videos_finales/<tanda>`, group with `group_trial_sources`, and render one `CTkTextbox` per key preloaded from the database. Save every text box with `set_trial_source_caption`.

Before preview/run call `_trial_missing_caption_sources`; reject missing keys with:

```python
messagebox.showwarning(
    "Captions Trial faltantes",
    "Falta asignar caption a: " + ", ".join(missing),
)
```

Reuse the existing anti-collision/copy planning, but select only `get_trials_active_accounts()` and write exclusively to `CALENDARIO_TRIALS/Dia_N/<username>`. Continue using `build_calendar_video_filename`.

- [ ] **Step 4: Verify Logistics**

Run: `py -m pytest tests/test_logistica_trials.py tests/test_logistica_caption_ui.py tests/test_logistica_long_paths.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add gui_premium_v7.py tests/test_logistica_trials.py tests/test_logistica_caption_ui.py
git commit -m "feat: add trials logistics captions"
```

### Task 4: Explicit Telegram Trial routing

**Files:**

- Modify: `organizadortg.py: scan_calendar_structure, topic helpers, execute_telegram_plan`
- Modify: `tests/test_telegram_caption_routing.py`
- Create: `tests/test_telegram_trials_routing.py`

**Interfaces:**

- Produces: `extract_source_key_from_calendar_filename(filename: str) -> str`.
- Produces: `caption_for_trial_calendar_video(filename: str, captions: dict[str, str]) -> str | None`.
- Produces: `get_or_create_topic(..., delivery_kind: str = "normal") -> int | None`.

- [ ] **Step 1: Write the failing routing tests**

```python
def test_trial_copies_receive_the_identical_literal_caption():
    captions = {"vid1": "Caption 1\n#uno", "vid2": "Caption 2\n#dos"}
    assert caption_for_trial_calendar_video(
        "vid1__c01__TANDA_T__ACC1__D1__S1.mp4", captions
    ) == captions["vid1"]
    assert caption_for_trial_calendar_video(
        "vid1__c02__TANDA_T__ACC1__D1__S2.mp4", captions
    ) == captions["vid1"]

def test_trial_topic_key_is_separate_from_normal():
    assert topic_state_key("-100", "eve", "normal") == "-100_eve"
    assert topic_state_key("-100", "eve", "trial") == "-100_eve_trials"
```

Also test that normal and Trial calendar roots scan as `delivery_kind == "normal"` and `"trial"` respectively.

- [ ] **Step 2: Run the failing tests**

Run: `py -m pytest tests/test_telegram_trials_routing.py tests/test_telegram_caption_routing.py -q`  
Expected: FAIL because Trial routing interfaces do not exist.

- [ ] **Step 3: Implement explicit routing**

Make `scan_calendar_structure` scan both `CALENDARIO_POSTEO` and `CALENDARIO_TRIALS`, recording `delivery_kind`. Skip Trial files whose account is absent or not `trials_active`. Extract the source by stripping the calendar suffix then calling `source_key_from_filename`.

For a Trial item, resolve captions with `get_trial_source_captions(tanda_name)` and return that stored text directly. Do not call `caption_for_video` or `shuffle_hashtags`.

Extend topic state/key creation with `delivery_kind`. For Trial use `<chat>_<username>_trials` and a title prefixed `TRIALS - `; normal keys and titles remain unchanged. Select the resolver/topic by `vid["delivery_kind"]` inside `execute_telegram_plan`.

- [ ] **Step 4: Verify Telegram and regression routing**

Run: `py -m pytest tests/test_telegram_trials_routing.py tests/test_telegram_caption_routing.py tests/test_telegram_captions.py tests/test_telegram_topic_reset.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add organizadortg.py tests/test_telegram_caption_routing.py tests/test_telegram_trials_routing.py
git commit -m "feat: route trials with source captions"
```

### Task 5: Local-only end-to-end verification

**Files:**

- Test: focused Trial and existing regression suites.
- Modify: `README.txt` only if it contains the operating workflow and needs a Trial note.

- [ ] **Step 1: Run all focused tests**

Run:

```powershell
py -m pytest tests/test_trials_storage.py tests/test_trial_content.py tests/test_logistica_trials.py tests/test_telegram_trials_routing.py tests/test_forge_ui.py tests/test_logistica_caption_ui.py tests/test_logistica_long_paths.py tests/test_telegram_captions.py tests/test_telegram_caption_routing.py tests/test_telegram_topic_reset.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Compile touched modules**

Run: `py -m py_compile database.py trial_content.py gui_premium_v7.py Organizador.py organizadortg.py`  
Expected: exit code 0.

- [ ] **Step 3: Run a fake Telegram smoke**

Use temporary normal and Trial calendar trees and patch the transport to record calls. Verify the same account gets one normal topic and one `TRIALS -` topic, and that `vid1__c01` and `vid1__c02` carry identical captions. Do not call the live Bot API.

- [ ] **Step 4: Commit verification artifacts only if created**

```powershell
git add README.txt tests
git commit -m "test: verify active trials delivery flow"
```


### Task 6: Selección individual, pools no reutilizables y miniaturas

**Files:**

- Modify: `trial_content.py: per-account planning and preview-cache helpers`
- Modify: `gui_premium_v7.py: Logística > Trials controls and run`
- Create: `tests/test_trial_account_selection.py`

**Interfaces:**

- Produces: `build_trial_account_plan(assignments, files_by_tanda, videos_per_day, days) -> TrialPlan`.
- Produces: `reused_trial_tanda_warnings(plan) -> list[str]`.
- Produces: `trial_preview_path(video_path: str) -> str`.

- [ ] **Step 1: Write the failing planner tests**

```python
def test_duplicate_tanda_uses_each_output_only_once():
    plan = build_trial_account_plan(
        {"eve": "T1", "luna": "T1"}, {"T1": ["a.mp4", "b.mp4", "c.mp4"]}, 2, 1
    )
    assert plan.assigned["eve"] == ["a.mp4", "b.mp4"]
    assert plan.assigned["luna"] == ["c.mp4"]
    assert plan.shortfalls == {"luna": 1}
    assert "T1" in reused_trial_tanda_warnings(plan)[0]
```

- [ ] **Step 2: Verify it fails**

Run: `py -m pytest tests/test_trial_account_selection.py -q`  
Expected: FAIL because the planner does not exist.

- [ ] **Step 3: Implement one shared pool per tanda**

The planner consumes each tanda's sorted output list once across all accounts
that selected it. It reports selected accounts, available, requested, assigned
and shortfall; it never cycles/reuses an output name.

- [ ] **Step 4: Add UI and async thumbnail loading**

Render one row per active account (`@user [category]` plus Trial tanda combo).
When selection changes, rebuild `(tanda, source)` caption cards. Each card has
the source name, copy count, a 120x68 first-frame thumbnail and its editor.
Generate/copy thumbnails in a worker using existing FFmpeg/Pillow support,
cache them under the local temp directory keyed by absolute source path plus
mtime, then apply the `CTkImage` on the GUI thread.

Before distribution, show repeated-tanda warnings with selected accounts,
available/requested/shortfall. Confirmation is allowed; execute the planner's
assigned unique files only and render every shortfall in the result text.

- [ ] **Step 5: Verify and commit**

Run: `py -m pytest tests/test_trial_account_selection.py tests/test_logistica_trials.py tests/test_trial_content.py -q`  
Expected: PASS.

```powershell
git add trial_content.py gui_premium_v7.py tests/test_trial_account_selection.py
git commit -m "feat: select trial tanda per account"
```
