# v1.0.49 Console Encoding Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the updater/Forge mismatch that can make Preview SDR or HLG fail silently after an apparently successful update.

**Architecture:** The updater allowlist becomes consistent with the release allowlist. Because installed v1.0.48 updaters already omit the helper, the v1.0.49 Forge profile contains a narrow backward-compatible resolver for FFmpeg commands. GUI preflight imports execute inside the existing error boundary so user-visible errors replace Tkinter-only tracebacks.

**Tech Stack:** Python 3.10+, unittest/pytest, CustomTkinter, PowerShell release builder.

## Global Constraints

- Base every code change on tag `v1.0.48`.
- v1.0.49 is code-only: never package DBs, configuration, calendars, media, or runtime history.
- Preserve CPU FFmpeg rendering; do not introduce GPU requirements.
- Validate package hash and ZIP file list before publication.
- This environment cannot run FFmpeg subprocess tests (`WinError 50`); report that boundary and run all non-FFmpeg tests.

---

### Task 1: Permit the helper in future updates

**Files:**
- Modify: `updater.py:30-65`
- Modify: `tests/test_updater.py:146-173`

**Interfaces:**
- Consumes: `DEFAULT_UPDATEABLE_FILES`, `apply_package(app_dir, package_path, manifest)`.
- Produces: transactional installation of `console_encoding.py` when it is listed by a verified release manifest.

- [ ] **Step 1: Write the failing test**

Add a dedicated test next to bundled-FFmpeg installation coverage:

```python
def test_apply_package_can_install_console_encoding_helper(self):
    package_path = self.app_dir / "release.zip"
    package_path.write_bytes(_zip_bytes({
        "version.json": json.dumps({"version": "1.0.1"}),
        "console_encoding.py": "def ffmpeg_tool_command(name): return name\n",
    }))

    updater.apply_package(
        self.app_dir, package_path,
        {"version": "1.0.1", "files": ["version.json", "console_encoding.py"]},
    )

    self.assertIn(
        "ffmpeg_tool_command",
        (self.app_dir / "console_encoding.py").read_text(),
    )
```

- [ ] **Step 2: Run it to verify RED**

Run: `python -m pytest -q tests/test_updater.py::UpdaterTest::test_apply_package_can_install_console_encoding_helper`

Expected: FAIL because `console_encoding.py` is excluded from `DEFAULT_UPDATEABLE_FILES`.

- [ ] **Step 3: Write the minimal implementation**

Insert the missing allowlist item adjacent to `updater.py`:

```python
"updater.py",
"console_encoding.py",
"organizador.db",
```

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest -q tests/test_updater.py`

Expected: all updater tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add updater.py tests/test_updater.py
git commit -m "fix: update console encoding helper"
```

### Task 2: Keep Preview compatible with already-broken v1.0.48 installations

**Files:**
- Modify: `forge_iphone_profile.py:14-18`
- Modify: `tests/test_forge_iphone_profile.py:1-14`

**Interfaces:**
- Consumes: a possibly old `console_encoding` module that has no `ffmpeg_tool_command`.
- Produces: `ffmpeg_tool_command(tool_name: str) -> str` that prefers bundled tools and otherwise returns `ffmpeg` or `ffprobe` by name.

- [ ] **Step 1: Write the failing test**

Add a test that substitutes a `console_encoding` module exposing no helper, imports a fresh copy of `forge_iphone_profile.py`, and asserts a usable command resolver:

```python
def test_profile_import_has_ffmpeg_fallback_when_old_helper_lacks_command(monkeypatch):
    old_helper = types.ModuleType("console_encoding")
    monkeypatch.setitem(sys.modules, "console_encoding", old_helper)
    sys.modules.pop("forge_iphone_profile", None)

    profile = importlib.import_module("forge_iphone_profile")

    assert profile.ffmpeg_tool_command("ffprobe").endswith("ffprobe")
```

Restore the normal profile module after the assertion so later test modules use the real helper.

- [ ] **Step 2: Run it to verify RED**

Run: `python -m pytest -q tests/test_forge_iphone_profile.py::test_profile_import_has_ffmpeg_fallback_when_old_helper_lacks_command`

Expected: FAIL with `ImportError: cannot import name 'ffmpeg_tool_command'`.

- [ ] **Step 3: Write the minimal implementation**

Replace the unconditional import with `try/except ImportError`. In the exception branch define only a local resolver using `Path(__file__).resolve().parent / "tools" / "ffmpeg" / "bin"` and `os.name`; return the bundled path if it is a file, otherwise return the tool name. Do not alter color classification, preflight rules, encoders, or rendering parameters.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest -q tests/test_forge_iphone_profile.py -k "not real and not render and not visual"`

Expected: non-FFmpeg profile/preflight tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add forge_iphone_profile.py tests/test_forge_iphone_profile.py
git commit -m "fix: keep Forge compatible with old helper"
```

### Task 3: Surface Preview import failures to the user

**Files:**
- Modify: `gui_premium_v7.py:5596-5603`
- Modify: `tests/test_forge_ui.py`

**Interfaces:**
- Consumes: any exception from importing `forge_iphone_profile`, probing a selected source, or preflight classification.
- Produces: `messagebox.showerror("Preflight iPhone", str(error))` and an early return.

- [ ] **Step 1: Write the failing test**

Create a minimal `InstagramAutoPro` instance with one selected video and profile `iPhone SDR`, patch the profile import to raise `ImportError("helper incompatible")`, and assert:

```python
showerror.assert_called_once_with("Preflight iPhone", "helper incompatible")
assert not app.btn_forge_process.configure.called
```

- [ ] **Step 2: Run it to verify RED**

Run: `python -m pytest -q tests/test_forge_ui.py -k preview_import_error`

Expected: FAIL with the uncaught import error.

- [ ] **Step 3: Write the minimal implementation**

Wrap both the profile import and existing `probe_file`/`preflight_batch` calls in the same `try` block:

```python
try:
    from forge_iphone_profile import preflight_batch, probe_file
    probes = {path: probe_file(path) for path in self.forge_video_paths}
    preflight = preflight_batch(probes, profile_key)
except Exception as error:
    return messagebox.showerror("Preflight iPhone", str(error))
```

Keep unknown-source confirmation and blocked-source messaging unchanged.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest -q tests/test_forge_ui.py -k "preview or iphone"`

Expected: selected UI tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add gui_premium_v7.py tests/test_forge_ui.py
git commit -m "fix: show Forge preview import errors"
```

### Task 4: Package v1.0.49 and validate the update boundary

**Files:**
- Modify: `version.json`
- Modify: `release-manifest.json`
- Modify: `tests/test_release_package_manifest.py` only if a contract test needs an explicit helper assertion.

**Interfaces:**
- Consumes: `build_release.ps1` explicit code allowlist and version metadata.
- Produces: `MetodoIG-v1.0.49.zip` plus a manifest with the matching SHA-256.

- [ ] **Step 1: Write the failing package-contract test if absent**

Add an assertion that the released file set contains `console_encoding.py` and that `updater.DEFAULT_UPDATEABLE_FILES` contains the same path. Keep the test free of network and FFmpeg calls.

- [ ] **Step 2: Run it to verify RED**

Run: `python -m pytest -q tests/test_release_package_manifest.py`

Expected: FAIL only if the new cross-allowlist assertion is not yet implemented.

- [ ] **Step 3: Set version and build**

Set `version.json` to `1.0.49`, then run:

```powershell
.\build_release.ps1 -Notes "Repara la actualizacion de console_encoding y muestra errores de Preview Forge SDR/HLG."
```

Regenerate `release-manifest.json` from the build output; do not hand-edit its hash or file list.

- [ ] **Step 4: Verify package and source**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q tests/test_updater.py tests/test_release_package_manifest.py tests/test_forge_iphone_profile.py -k "not real and not render and not visual"
python -m compileall -q updater.py console_encoding.py forge_iphone_profile.py gui_premium_v7.py
git diff --check
```

Expected: all non-FFmpeg tests PASS, compilation succeeds, and no whitespace errors. Inspect the ZIP to confirm it has `console_encoding.py` and no runtime data. Record that real FFmpeg Preview SDR remains to be exercised on a compatible Windows machine.

- [ ] **Step 5: Commit release inputs**

```powershell
git add version.json release-manifest.json tests/test_release_package_manifest.py
git commit -m "release: prepare v1.0.49"
```

