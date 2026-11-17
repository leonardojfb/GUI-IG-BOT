# TRIAL Copy Order Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global TRIAL selector that preserves the current interleaved order by default and optionally groups every copy of one logical ID before the next ID.

**Architecture:** Keep quota and account allocation in `build_trial_account_plan()`. Add one explicit ordering mode to the pool-ordering boundary, then pass the GUI selection into the same planner used by preview and manifest writes.

**Tech Stack:** Python, CustomTkinter, pytest

## Global Constraints

- `Intercalado` remains the default and must preserve v1.0.54 behavior exactly.
- `Agrupado por ID` changes only pool order; it must not duplicate files or alter account quotas.
- Verified `origin_identity` takes precedence over filename-derived source identity.
- The selector applies only to TRIAL preview and distribution.
- Existing normal Logística, caption, Telegram, and delivery-history behavior stays unchanged.

---

### Task 1: Add an explicit order mode to the TRIAL planner

**Files:**
- Modify: `trial_content.py:40-60,134-175`
- Test: `tests/test_trial_account_selection.py:81-153`

**Interfaces:**
- Consumes: filenames, tanda name, optional verified origin mapping, and `order_mode`.
- Produces: `build_trial_account_plan(..., order_mode="interleaved" | "grouped") -> TrialPlan`.

- [ ] **Step 1: Write failing planner tests**

Add tests that call the real planner with `order_mode="grouped"` and assert:

```python
assert plan.assigned["eve"] == [
    "vid1__c01.mp4", "vid1__c02.mp4", "vid1__c03.mp4",
    "vid2__c01.mp4", "vid2__c02.mp4", "vid2__c03.mp4",
]
```

Add a verified-origin case whose differently named files share an `origin_by_file` identity and stay together. Add a shared-tanda case that asserts all physical filenames remain unique and existing per-account counts do not change.

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q tests/test_trial_account_selection.py -k "grouped"
```

Expected: FAIL because `build_trial_account_plan()` does not accept `order_mode`.

- [ ] **Step 3: Implement minimal planner support**

Replace the single-purpose pool helper with an ordering helper:

```python
def _order_trial_files(filenames, tanda, origin_by_file, order_mode):
    if order_mode not in {"interleaved", "grouped"}:
        raise ValueError(f"Modo de orden TRIAL desconocido: {order_mode}")
    # Build stable origin groups and numeric __cNN copy order.
    if order_mode == "grouped":
        return [filename for copies in copies_by_origin for filename in copies]
    return [
        copies[copy_index]
        for copy_index in range(max(map(len, copies_by_origin), default=0))
        for copies in copies_by_origin
        if copy_index < len(copies)
    ]
```

Extend the public planner without breaking callers:

```python
def build_trial_account_plan(assignments, files_by_tanda, videos_per_day, days,
                             *, origin_by_file=None, existing_entries=(),
                             order_mode="interleaved"):
```

- [ ] **Step 4: Run planner tests and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_trial_account_selection.py -k "trial_plan or grouped"
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit planner behavior**

```powershell
git add -- trial_content.py tests/test_trial_account_selection.py
git commit -m "feat: support grouped trial copy order"
```

---

### Task 2: Expose the global selector and wire preview/distribution

**Files:**
- Modify: `gui_premium_v7.py:2795-2851,3047-3116`
- Test: `tests/test_trial_account_selection.py:448-520`

**Interfaces:**
- Consumes: `self.trial_order_mode`, whose displayed values are `Intercalado` and `Agrupado por ID`.
- Produces: planner argument `interleaved` or `grouped`, plus an `Orden: ...` preview line.

- [ ] **Step 1: Write failing GUI and preview tests**

Extend the existing widget-capture test to require exactly one combo with:

```python
values=["Intercalado", "Agrupado por ID"]
```

and assert the bound variable defaults to `Intercalado`.

Add a preview integration test using real `build_trial_account_plan()` with:

```python
trial_order_mode=SimpleNamespace(get=lambda: "Agrupado por ID")
```

Assert the preview includes `Orden: Agrupado por ID` and lists every `vid1` copy before the first `vid2` copy.

- [ ] **Step 2: Run the new GUI tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_trial_account_selection.py -k "order_selector or grouped_preview"
```

Expected: FAIL because the GUI has no order selector and does not pass an order mode.

- [ ] **Step 3: Add the selector and planner wiring**

In the TRIAL configuration row, create:

```python
self.trial_order_mode = tk.StringVar(value="Intercalado")
ctk.CTkComboBox(
    cfg,
    values=["Intercalado", "Agrupado por ID"],
    variable=self.trial_order_mode,
    fg_color=BG_INPUT,
    border_color=BORDER,
    width=170,
).pack(side="left", padx=(8, 20))
```

At plan construction, normalize the display value and pass it once:

```python
order_selector = getattr(self, "trial_order_mode", None)
order_label = order_selector.get().strip() if order_selector is not None else "Intercalado"
order_mode = "grouped" if order_label == "Agrupado por ID" else "interleaved"
plan = build_trial_account_plan(
    assignments, files_by_tanda, per_day, days,
    origin_by_file=origin_by_file,
    order_mode=order_mode,
)
```

Prepend `Orden: {order_label}` to the preview lines.

- [ ] **Step 4: Run GUI and full TRIAL tests and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_trial_account_selection.py tests/test_logistica_caption_ui.py
```

Expected: all tests pass.

- [ ] **Step 5: Commit the visible selector**

```powershell
git add -- gui_premium_v7.py tests/test_trial_account_selection.py
git commit -m "feat: add trial copy order selector"
```

---

### Task 3: Verify scope and release readiness

**Files:**
- Verify: `trial_content.py`
- Verify: `gui_premium_v7.py`
- Verify: `tests/test_trial_account_selection.py`

**Interfaces:**
- Consumes: both selector modes through the real planner and GUI preview path.
- Produces: fresh test evidence and a clean focused diff.

- [ ] **Step 1: Run focused regression tests**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q tests/test_trial_account_selection.py tests/test_logistica_caption_ui.py tests/test_telegram_caption_routing.py
```

Expected: all tests pass.

- [ ] **Step 2: Run static verification**

```powershell
python -m py_compile trial_content.py gui_premium_v7.py
git diff --check origin/main...HEAD
git status --short --branch
```

Expected: compilation succeeds, no whitespace errors, and only intentional committed changes remain.

- [ ] **Step 3: Review the final diff against the specification**

Confirm the default is interleaved, grouped mode is explicit, preview reports the choice, no physical output is duplicated, and normal distribution/Telegram code is untouched.
