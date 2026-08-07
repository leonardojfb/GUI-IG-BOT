# v1.0.15 Backup Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a complete code-only backup release of the active Metodo IG GUI changes before larger app work begins.

**Architecture:** The existing GitHub updater consumes `version.json` and `release-manifest.json`; `build_release.ps1` creates a ZIP solely from its fixed allowlist. The release will package the changed runtime modules and keep local mutable data, caches, credentials configuration, test fixtures, and database/history snapshots out of the ZIP.

**Tech Stack:** Python, pytest, PowerShell packaging script, Git, GitHub Releases.

## Global Constraints

- Release version is `1.0.15` with tag `v1.0.15`.
- Include the current GUI/Telegram runtime changes exactly as present in the active checkout.
- Exclude `organizador.db`, `dist_accounts_history.json`, `telegram_state_v11.json`, DB backups, calendar media, downloaded release checks, and `update_config.json`.
- Do not alter the current bot credential/configuration as explicitly directed by the user; this release is a snapshot backup before larger changes.
- Only commit the changed runtime modules, their regression tests, release metadata, and this plan; preserve unrelated local files.

---

### Task 1: Freeze and validate the candidate change set

**Files:**
- Modify: `gui_premium_v7.py`
- Modify: `organizadortg.py`
- Test: `tests/test_logistica_long_paths.py`
- Test: `tests/test_telegram_long_paths.py`
- Test: `tests/test_telegram_calendar_cleanup.py`
- Test: `tests/test_telegram_topic_reset.py`

**Interfaces:**
- Consumes: existing Python runtime and local test suite.
- Produces: a verified candidate containing the GUI long-path helpers, selected-calendar cleanup, safe TRIALS topic handling, and conservative Telegram recompression.

- [ ] **Step 1: Inspect the candidate inventory**

Run: `git diff --name-only; git ls-files --others --exclude-standard`

Expected: only the runtime modules and four regression tests are selected; local data/backups remain excluded.

- [ ] **Step 2: Run targeted regressions**

Run: `py -m pytest tests/test_logistica_long_paths.py tests/test_telegram_long_paths.py tests/test_telegram_calendar_cleanup.py tests/test_telegram_topic_reset.py -q`

Expected: all selected regressions pass.

- [ ] **Step 3: Run the complete suite and syntax checks**

Run: `py -m pytest tests -q; py -m compileall gui_premium_v7.py organizadortg.py -q`

Expected: test suite exits zero and both changed runtime modules compile.

### Task 2: Build the code-only updater payload

**Files:**
- Modify: `version.json`
- Modify: `release-manifest.json`
- Modify: `releases/MetodoIG-v1.0.15.zip`
- Test: `tests/test_release_package_manifest.py`

**Interfaces:**
- Consumes: `build_release.ps1` fixed `$ReleaseFiles` allowlist and `version.json`.
- Produces: `MetodoIG-v1.0.15.zip` and a matching manifest with the SHA-256 and GitHub-release metadata.

- [ ] **Step 1: Set release identity**

Update `version.json` to `{"version":"1.0.15","release_date":"2026-08-07","channel":"github-releases"}`.

- [ ] **Step 2: Verify the package allowlist**

Run: `py -m pytest tests/test_release_package_manifest.py -q`

Expected: the shipped modules have no missing local imports.

- [ ] **Step 3: Build without data inclusion switches**

Run: `powershell -ExecutionPolicy Bypass -File .\build_release.ps1 -OutputDirectory releases -Notes "Backup previo a cambios mayores: rutas largas Windows en Logistica y Telegram, recompresion segura tras 413, topics TRIALS protegidos y borrado selectivo de calendarizaciones."`

Expected: ZIP and manifest are generated; their `files` list does not include the database, history, state, config, or backups.

- [ ] **Step 4: Inspect the final ZIP and manifest**

Run: compare normalized ZIP paths against manifest `files`, confirm SHA-256, and confirm excluded mutable files are absent.

Expected: ZIP contents exactly match the manifest and the computed digest.

### Task 3: Commit, publish, and independently verify the backup

**Files:**
- Modify: `gui_premium_v7.py`
- Modify: `organizadortg.py`
- Modify: `tests/test_telegram_topic_reset.py`
- Create: `tests/test_logistica_long_paths.py`
- Create: `tests/test_telegram_long_paths.py`
- Create: `tests/test_telegram_calendar_cleanup.py`
- Modify: `version.json`
- Modify: `release-manifest.json`
- Create: `docs/superpowers/plans/2026-08-07-v1-0-15-backup-release.md`

**Interfaces:**
- Consumes: verified ZIP and manifest from Task 2.
- Produces: committed/tagged source and a GitHub release whose uploaded ZIP matches the repository manifest.

- [ ] **Step 1: Stage only release inputs**

Run: `git add gui_premium_v7.py organizadortg.py tests/test_telegram_topic_reset.py tests/test_logistica_long_paths.py tests/test_telegram_long_paths.py tests/test_telegram_calendar_cleanup.py version.json release-manifest.json docs/superpowers/plans/2026-08-07-v1-0-15-backup-release.md`

Expected: `git diff --cached --name-only` contains no database, history, backup, state, or release ZIP.

- [ ] **Step 2: Commit and tag**

Run: `git commit -m "release: publish v1.0.15"; git tag -a v1.0.15 -m "Metodo IG GUI v1.0.15 backup"`

Expected: a single source commit and matching annotated tag.

- [ ] **Step 3: Push and create the GitHub release**

Run: `git push origin HEAD; git push origin v1.0.15; gh release create v1.0.15 releases/MetodoIG-v1.0.15.zip --title "Metodo IG GUI v1.0.15" --notes "Backup previo a cambios mayores. Incluye rutas largas Windows en Logistica y Telegram, recompresion segura tras 413, topics TRIALS protegidos y borrado selectivo de calendarizaciones."`

Expected: the tag and source commit are remote, with exactly one uploaded ZIP asset.

- [ ] **Step 4: Verify the remote release**

Run: `gh release view v1.0.15 --json tagName,targetCommitish,assets; download the asset; compare its SHA-256 and normalized file list against release-manifest.json`.

Expected: remote tag/commit/asset exist and downloaded asset is byte-identical to the verified local ZIP.
