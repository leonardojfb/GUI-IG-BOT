# Forge Current Date and Device Floor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Forge output use its real processing timestamp and restrict generated and validated fingerprints to iPhone 16+ with iOS 26+.

**Architecture:** Keep one metadata contract in `metadata_pool.py` for model/iOS floors and QuickTime timestamp formatting. Call that contract from both Legacy metadata-copy output and `forge_iphone_profile.py` MOV rendering, while `validate_probe` enforces timestamp and device metadata on published iPhone outputs.

**Tech Stack:** Python, pytest, FFmpeg/ffprobe, QuickTime/MOV metadata, existing PySide6/CustomTkinter Forge pipeline.

## Global Constraints

- Forge must use the current date and time at the moment each output is processed.
- Allowed device generations are iPhone 16 or higher.
- Allowed operating systems are iOS 26.0 or higher.
- Existing unrelated working-tree changes must remain untouched.
- Existing color, codec, audio, visual-QC, retry, and no-overwrite contracts must remain passing.

---

### Task 1: Add failing tests for the metadata contract

**Files:**
- Modify: `tests/test_forge_iphone_profile.py`
- Modify: `tests/test_forge_concurrency.py` for Legacy Forge fixtures that intentionally pass metadata through the variant path.
- Modify: `tests/support/e2e_pipeline.py` only if its fixture metadata requires the new contract; otherwise do not change it.

**Interfaces:**
- Tests will exercise `metadata_pool.validate_iphone_metadata(meta)` and `metadata_pool.current_creation_tags(now)`.
- Tests will exercise `forge_iphone_profile.validate_probe(..., expected_meta=...)` and real `render_iphone_video` output.

- [ ] **Step 1: Add unit tests for model and iOS floors.**

Add tests that assert `iPhone 16 Pro Max` with `26.0.1` is accepted, `iPhone 15 Pro Max` with `26.0` is rejected, and `iPhone 16` with `18.7.9` is rejected. Add a generator test using the existing fake DB pattern that asserts every returned item has an iPhone generation of at least 16 and an iOS major version of at least 26.

- [ ] **Step 2: Add timestamp-format tests.**

Use a fixed aware datetime such as `datetime(2026, 9, 25, 12, 34, 56, tzinfo=timezone.utc)` and assert that `current_creation_tags` returns an ISO UTC `creation_time` ending in `Z` plus a local-offset `com.apple.quicktime.creationdate` representing the same instant.

- [ ] **Step 3: Add a failing validation test for missing timestamps.**

Build the existing `_probe()` fixture with valid iPhone metadata but no `creation_time` or `com.apple.quicktime.creationdate` tags and assert `validate_probe` reports both missing fields.

- [ ] **Step 4: Extend the real render test with timestamp assertions.**

After `render_iphone_video` creates a MOV, parse its format tags, assert both timestamp tags exist, parse them as dates, and assert the timestamp is within the test execution window.

- [ ] **Step 5: Run the focused tests and verify RED.**

Run:

```powershell
python -m pytest tests/test_forge_iphone_profile.py -q
```

Expected result: the newly added contract tests fail because the helper, floor validation, and timestamp injection do not yet exist; unrelated existing tests should still collect successfully.

### Task 2: Implement the shared metadata contract and current timestamps

**Files:**
- Modify: `metadata_pool.py`
- Modify: `forge_iphone_profile.py`

**Interfaces:**
- Produce `validate_iphone_metadata(meta) -> None` that raises `ValueError` with field-specific messages.
- Produce `current_creation_tags(now=None) -> dict[str, str]` with `creation_time` and `com.apple.quicktime.creationdate`.

- [ ] **Step 1: Add reusable floor constants and parsers in `metadata_pool.py`.**

Define `MIN_IPHONE_GENERATION = 16` and `MIN_IOS_VERSION = (26, 0)`. Parse the generation from names matching `iPhone <number>` and parse dot-separated numeric iOS components. Reject malformed values and values below the floors with explicit Spanish error messages.

- [ ] **Step 2: Filter the generator pool.**

Change `_ios_pool_for` to include only versions whose parsed value is at least `(26, 0)`. Change `generate_unique_metadata` to iterate only models whose parsed generation is at least 16. Validate each generated metadata object before returning it.

- [ ] **Step 3: Add timestamp formatting.**

Use `datetime.now(timezone.utc)` when no test instant is supplied. Format `creation_time` as UTC ISO-8601 with `Z`, and format `com.apple.quicktime.creationdate` from the local timezone with a numeric offset. Keep the helper injectable with `now` for deterministic tests.

- [ ] **Step 4: Apply the contract and date tags to Legacy output.**

Call `validate_iphone_metadata(meta)` before constructing the Legacy FFmpeg command. Add both current timestamp tags to the command after metadata cleanup. Do not copy source metadata.

- [ ] **Step 5: Apply the contract and date tags to iPhone MOV output.**

Call the shared validator at the start of `render_iphone_video`. Add both current timestamp tags beside the existing Apple model/software tags. Keep location handling unchanged.

- [ ] **Step 6: Make iPhone output validation require timestamps.**

Extend `validate_probe` to report missing or malformed `creation_time` and `com.apple.quicktime.creationdate` tags. Preserve its existing expected model/software and codec/color/audio checks.

- [ ] **Step 7: Run the focused tests and verify GREEN.**

Run:

```powershell
python -m pytest tests/test_forge_iphone_profile.py -q
```

Expected result: all focused Forge profile tests pass, including real FFmpeg render/decode checks.

### Task 3: Run regressions and inspect the focused diff

**Files:**
- Modify: none beyond the files listed above.

- [ ] **Step 1: Run the adjacent Forge tests.**

Run:

```powershell
python -m pytest tests/test_forge_presets.py tests/test_forge_ui.py tests/test_forge_concurrency.py -q
```

Expected result: all tests pass.

- [ ] **Step 2: Run the broader test suite.**

Run:

```powershell
python -m pytest -q
```

Expected result: no new failures attributable to the Forge metadata contract.

- [ ] **Step 3: Review only the intended diff.**

Run:

```powershell
git diff --check HEAD -- metadata_pool.py forge_iphone_profile.py tests/test_forge_iphone_profile.py
git diff HEAD -- metadata_pool.py forge_iphone_profile.py tests/test_forge_iphone_profile.py
```

Confirm no unrelated dirty files are staged or modified by this task.

### Task 4: Commit the implementation and merge into main

**Files:**
- Commit only: `metadata_pool.py`, `forge_iphone_profile.py`, `tests/test_forge_iphone_profile.py`, and the implementation plan if it has not already been committed.

- [ ] **Step 1: Stage only task files.**

Run:

```powershell
git add -- metadata_pool.py forge_iphone_profile.py tests/test_forge_iphone_profile.py docs/superpowers/plans/2026-09-25-forge-current-date-device-floor.md
```

- [ ] **Step 2: Commit the implementation.**

Run:

```powershell
git commit -m "feat: constrain Forge iPhone metadata and preserve current date"
```

- [ ] **Step 3: Verify branch status and commit contents.**

Run:

```powershell
git show --stat --oneline HEAD
git status --short --branch
```

Expected result: the implementation commit contains only the intended task files, while unrelated pre-existing changes remain outside the commit.

- [ ] **Step 4: Merge the feature branch into local main without discarding work.**

Run:

```powershell
git fetch origin main
git switch main
git merge --no-ff feature/meta-compatible-manual-calendar -m "merge: Forge current date and iPhone 16 iOS 26 floor"
```

If the dirty unrelated files prevent switching, preserve them with a non-destructive temporary stash of only unrelated paths or stop and report the exact blocker; never reset or discard them.

- [ ] **Step 5: Verify the merged main checkout.**

Run:

```powershell
python -m pytest tests/test_forge_iphone_profile.py tests/test_forge_presets.py tests/test_forge_ui.py -q
git log -3 --oneline --decorate
git status --short --branch
```

Expected result: Forge tests pass on `main`, and the merge commit is visible without losing unrelated user changes.
