# Direct Calendar Manifest And Transform Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace calendar media copies with a shared manifest that points Telegram to already processed files, and persist effective transform logs for Tandas, Video Editor, Forge, and Forge Trials.

**Architecture:** Add one focused `calendar_manifest.py` module for JSON read, validation, replacement, and cleanup. Add transform-log schema and query methods to `DatabaseManager`, then wire existing distribution, Telegram scan/count/cleanup, render, editor, and Forge call sites to those interfaces without changing caption/topic/scheduling semantics.

**Tech Stack:** Python 3, SQLite via existing `database.py`, JSON, pathlib/os/shutil, pytest, existing Tk/ttk GUI patterns.

## Global Constraints

- Normal and Trial distributions write one shared `calendar_manifest.json`.
- No new distribution path copies media into `CALENDARIO_POSTEO` or `CALENDARIO_TRIALS`.
- Telegram preview, account counts, account filtering, sending, and selected account cleanup use the manifest when it exists.
- Legacy calendar-folder scanning remains a read-only fallback when no manifest exists.
- Successful Tandas, Video Editor, Forge, and Forge Trial outputs receive a durable transformation log row.
- Do not move, rename, or mutate source media during distribution.
- Do not delete existing legacy calendar copies automatically.
- Do not change caption, topic, account-selection, or delivery scheduling rules.
- Do not add a second metadata randomization after Forge.
- Forge output is the exact media Telegram sends.
- Invalid or missing source paths are skipped with an explicit diagnostic and never sent.

---

## File Structure

- Create `calendar_manifest.py`: Owns manifest path resolution, entry construction, validation, atomic writes, replacement, and account cleanup. It has no GUI or Telegram dependency.
- Modify `database.py`: Adds `video_transform_logs` schema and `DatabaseManager` methods for inserts and reads.
- Modify `Organizador.py`: Normal Logistica distribution writes manifest entries and history against the processed source path instead of copying to `CALENDARIO_POSTEO`.
- Modify `gui_premium_v7.py`: Normal per-account distribution and Trial distribution write manifest entries; Forge and Forge Trial log exact returned params; Video Editor completion logs overlay details; GUI gains a transform-log table.
- Modify `organizadortg.py`: Reads manifest rows exclusively when `calendar_manifest.json` exists; folder scanning remains the absent-manifest fallback. Counts and selected-account cleanup use manifest records.
- Modify `videos.py`: Tandas render completion writes transform logs with P1/P2 inputs and render settings.
- Modify `video_editor.py`: Exposes a pure helper to normalize overlay details for logging; render behavior stays unchanged.
- Add and update focused pytest files under `tests/`.

---

### Task 1: Calendar Manifest Module

**Files:**
- Create: `calendar_manifest.py`
- Test: `tests/test_calendar_manifest.py`

**Interfaces:**
- Produces: `manifest_path(base_dir: str | os.PathLike) -> pathlib.Path`
- Produces: `build_entry(username: str, account_id: int | None, delivery_kind: str, day: int, slot: int, tanda: str, source_path: str, telegram_filename: str, transform_log_id: int | None = None, created_at: str | None = None) -> dict`
- Produces: `load_entries(path: str | os.PathLike, require_source: bool = True) -> list[dict]`
- Produces: `replace_entries(path: str | os.PathLike, entries: list[dict], usernames: set[str], delivery_kind: str) -> list[dict]`
- Produces: `remove_entries_for_accounts(path: str | os.PathLike, usernames: set[str]) -> int`

- [ ] **Step 1: Write failing manifest tests**

```python
# tests/test_calendar_manifest.py
import json
from pathlib import Path

from calendar_manifest import (
    build_entry,
    load_entries,
    manifest_path,
    remove_entries_for_accounts,
    replace_entries,
)


def test_manifest_path_is_app_root_json(tmp_path):
    assert manifest_path(tmp_path) == tmp_path / "calendar_manifest.json"


def test_replace_entries_preserves_unrelated_account_and_kind(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source_a = tmp_path / "a.mp4"
    source_b = tmp_path / "b.mp4"
    source_c = tmp_path / "c.mp4"
    source_a.write_bytes(b"a")
    source_b.write_bytes(b"b")
    source_c.write_bytes(b"c")

    existing = [
        build_entry("alice", 1, "normal", 1, 1, "T1", str(source_a), "a__TANDA_T1.mp4"),
        build_entry("bob", 2, "trial", 1, 1, "T2", str(source_b), "b__TANDA_T2.mp4"),
    ]
    replace_entries(manifest, existing, {"alice", "bob"}, "normal")

    new_entry = build_entry("alice", 1, "normal", 2, 3, "T3", str(source_c), "c__TANDA_T3.mp4")
    merged = replace_entries(manifest, [new_entry], {"alice"}, "normal")

    assert [(e["username"], e["delivery_kind"], e["tanda"]) for e in merged] == [
        ("bob", "trial", "T2"),
        ("alice", "normal", "T3"),
    ]
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert len(payload["entries"]) == 2


def test_load_entries_skips_missing_source_when_required(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    present = tmp_path / "present.mp4"
    missing = tmp_path / "missing.mp4"
    present.write_bytes(b"video")
    entries = [
        build_entry("ok", 10, "normal", 1, 1, "T", str(present), "ok__TANDA_T.mp4"),
        build_entry("skip", 11, "normal", 1, 2, "T", str(missing), "skip__TANDA_T.mp4"),
    ]
    replace_entries(manifest, entries, {"ok", "skip"}, "normal")

    loaded = load_entries(manifest, require_source=True)

    assert [e["username"] for e in loaded] == ["ok"]


def test_remove_entries_for_accounts_removes_all_kinds(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    source = tmp_path / "v.mp4"
    source.write_bytes(b"v")
    entries = [
        build_entry("alice", 1, "normal", 1, 1, "T", str(source), "a__TANDA_T.mp4"),
        build_entry("alice", 1, "trial", 1, 1, "T", str(source), "at__TANDA_T.mp4"),
        build_entry("bob", 2, "normal", 1, 1, "T", str(source), "b__TANDA_T.mp4"),
    ]
    replace_entries(manifest, entries, {"alice", "bob"}, "normal")

    removed = remove_entries_for_accounts(manifest, {"alice"})

    assert removed == 2
    assert [e["username"] for e in load_entries(manifest)] == ["bob"]
```

- [ ] **Step 2: Run tests and verify the new module is missing**

Run: `pytest tests/test_calendar_manifest.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'calendar_manifest'`.

- [ ] **Step 3: Add minimal manifest implementation**

```python
# calendar_manifest.py
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

MANIFEST_VERSION = 1
MANIFEST_FILENAME = "calendar_manifest.json"


def manifest_path(base_dir: str | os.PathLike) -> Path:
    return Path(base_dir) / MANIFEST_FILENAME


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_entry(
    username: str,
    account_id: int | None,
    delivery_kind: str,
    day: int,
    slot: int,
    tanda: str,
    source_path: str,
    telegram_filename: str,
    transform_log_id: int | None = None,
    created_at: str | None = None,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "username": str(username),
        "account_id": account_id,
        "delivery_kind": str(delivery_kind),
        "day": int(day),
        "slot": int(slot),
        "tanda": str(tanda),
        "source_path": str(Path(source_path).resolve()),
        "telegram_filename": str(telegram_filename),
        "transform_log_id": transform_log_id,
        "created_at": created_at or _now_utc(),
    }


def _read_payload(path: Path) -> dict:
    if not path.exists():
        return {"version": MANIFEST_VERSION, "entries": []}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("version") != MANIFEST_VERSION:
        raise ValueError(f"Unsupported calendar manifest version: {payload.get('version')}")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("calendar_manifest.json must contain an entries list")
    return payload


def _write_payload(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": MANIFEST_VERSION, "entries": entries}
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def load_entries(path: str | os.PathLike, require_source: bool = True) -> list[dict]:
    manifest = Path(path)
    entries = list(_read_payload(manifest)["entries"])
    if not require_source:
        return entries
    return [entry for entry in entries if Path(entry.get("source_path", "")).exists()]


def replace_entries(
    path: str | os.PathLike,
    entries: list[dict],
    usernames: set[str],
    delivery_kind: str,
) -> list[dict]:
    manifest = Path(path)
    current = list(_read_payload(manifest)["entries"])
    affected = {str(name) for name in usernames}
    kept = [
        entry
        for entry in current
        if not (entry.get("username") in affected and entry.get("delivery_kind") == delivery_kind)
    ]
    merged = kept + list(entries)
    _write_payload(manifest, merged)
    return merged


def remove_entries_for_accounts(path: str | os.PathLike, usernames: set[str]) -> int:
    manifest = Path(path)
    current = list(_read_payload(manifest)["entries"])
    affected = {str(name) for name in usernames}
    kept = [entry for entry in current if entry.get("username") not in affected]
    removed = len(current) - len(kept)
    _write_payload(manifest, kept)
    return removed
```

- [ ] **Step 4: Run manifest tests**

Run: `pytest tests/test_calendar_manifest.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add calendar_manifest.py tests/test_calendar_manifest.py
git commit -m "feat: add direct calendar manifest store"
```

---

### Task 2: Transform Log Schema And Database API

**Files:**
- Modify: `database.py`
- Test: `tests/test_video_transform_logs.py`

**Interfaces:**
- Consumes: existing `DatabaseManager`
- Produces: optional test database path: `DatabaseManager(db_path: str | None = None)`
- Produces: `DatabaseManager.save_video_transform_log(process_kind: str, source_path: str, output_path: str, details: dict, tanda_name: str | None = None, source_identity: str | None = None) -> int`
- Produces: `DatabaseManager.get_video_transform_log_id(output_path: str) -> int | None`
- Produces: `DatabaseManager.list_video_transform_logs(limit: int = 500) -> list[dict]`

- [ ] **Step 1: Write failing DB tests**

```python
# tests/test_video_transform_logs.py
import json

from database import DatabaseManager


def test_save_video_transform_log_round_trips_json(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"in")
    output.write_bytes(b"out")

    log_id = db.save_video_transform_log(
        "forge",
        str(source),
        str(output),
        {"rotate_deg": 0.8, "crop_px": 2, "speed": 1.003},
        tanda_name="TANDA_A",
        source_identity="hash123",
    )

    assert db.get_video_transform_log_id(str(output)) == log_id
    rows = db.list_video_transform_logs(limit=10)
    assert rows[0]["id"] == log_id
    assert rows[0]["process_kind"] == "forge"
    assert rows[0]["tanda_name"] == "TANDA_A"
    assert json.loads(rows[0]["details_json"])["speed"] == 1.003


def test_save_video_transform_log_updates_same_output_path(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"in")
    output.write_bytes(b"out")

    first_id = db.save_video_transform_log("forge", str(source), str(output), {"rotate_deg": 0.1})
    second_id = db.save_video_transform_log("forge", str(source), str(output), {"rotate_deg": 0.2})

    assert second_id == first_id
    rows = db.list_video_transform_logs(limit=10)
    assert json.loads(rows[0]["details_json"])["rotate_deg"] == 0.2
```

- [ ] **Step 2: Run tests and verify missing methods**

Run: `pytest tests/test_video_transform_logs.py -v`

Expected: FAIL with `AttributeError: 'DatabaseManager' object has no attribute 'save_video_transform_log'`.

- [ ] **Step 3: Add table creation to the existing schema path**

Add this SQL to the schema initialization block in `database.py`:

```python
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS video_transform_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        process_kind TEXT NOT NULL,
        source_path TEXT NOT NULL,
        output_path TEXT NOT NULL UNIQUE,
        output_filename TEXT NOT NULL,
        tanda_name TEXT,
        source_identity TEXT,
        details_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """
)
cur.execute(
    "CREATE INDEX IF NOT EXISTS idx_video_transform_logs_process_created "
    "ON video_transform_logs(process_kind, created_at)"
)
```

- [ ] **Step 4: Allow isolated test DBs and add DatabaseManager methods**

```python
def __init__(self, db_path=None):
    self.db_path = db_path or DB_PATH
    self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
    self.conn.row_factory = sqlite3.Row
    self.initialize()


def save_video_transform_log(
    self,
    process_kind,
    source_path,
    output_path,
    details,
    tanda_name=None,
    source_identity=None,
):
    source_path = os.path.abspath(source_path)
    output_path = os.path.abspath(output_path)
    details_json = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
    output_filename = os.path.basename(output_path)
    cur = self.conn.cursor()
    cur.execute(
        """
        INSERT INTO video_transform_logs (
            process_kind, source_path, output_path, output_filename,
            tanda_name, source_identity, details_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(output_path) DO UPDATE SET
            process_kind=excluded.process_kind,
            source_path=excluded.source_path,
            output_filename=excluded.output_filename,
            tanda_name=excluded.tanda_name,
            source_identity=excluded.source_identity,
            details_json=excluded.details_json,
            created_at=datetime('now')
        """,
        (
            process_kind,
            source_path,
            output_path,
            output_filename,
            tanda_name,
            source_identity,
            details_json,
        ),
    )
    self.conn.commit()
    row = cur.execute("SELECT id FROM video_transform_logs WHERE output_path=?", (output_path,)).fetchone()
    return int(row[0])


def get_video_transform_log_id(self, output_path):
    output_path = os.path.abspath(output_path)
    row = self.conn.execute(
        "SELECT id FROM video_transform_logs WHERE output_path=?",
        (output_path,),
    ).fetchone()
    return int(row[0]) if row else None


def list_video_transform_logs(self, limit=500):
    rows = self.conn.execute(
        """
        SELECT id, process_kind, source_path, output_path, output_filename,
               tanda_name, source_identity, details_json, created_at
        FROM video_transform_logs
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    return [dict(row) for row in rows]
```

Ensure `database.py` imports `json` and `os` if they are not already imported.

- [ ] **Step 5: Run DB tests**

Run: `pytest tests/test_video_transform_logs.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_video_transform_logs.py
git commit -m "feat: persist video transform logs"
```

---

### Task 3: Normal And Trial Distribution Write Manifest Entries

**Files:**
- Modify: `Organizador.py`
- Modify: `gui_premium_v7.py`
- Test: `tests/test_logistica_por_cuentas_e2e.py`
- Test: `tests/test_telegram_trials_routing.py`

**Interfaces:**
- Consumes: `calendar_manifest.manifest_path`, `build_entry`, `replace_entries`
- Consumes: `DatabaseManager.get_video_transform_log_id(output_path: str) -> int | None`
- Produces: normal and Trial distribution records in `calendar_manifest.json`

- [ ] **Step 1: Update failing normal distribution test**

Add assertions to `tests/test_logistica_por_cuentas_e2e.py` after distribution finishes:

```python
import json
from pathlib import Path


def assert_manifest_has_direct_sources(base_dir, usernames):
    manifest = base_dir / "calendar_manifest.json"
    assert manifest.exists()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    rows = [e for e in payload["entries"] if e["username"] in usernames and e["delivery_kind"] == "normal"]
    assert rows
    for row in rows:
        source = Path(row["source_path"])
        assert source.exists()
        assert "videos_finales" in source.parts
        assert row["telegram_filename"].endswith(".mp4")
        assert "__TANDA_" in row["telegram_filename"]
    assert not any((base_dir / "CALENDARIO_POSTEO").rglob("*.mp4"))
```

- [ ] **Step 2: Update failing Trial distribution test**

In `tests/test_telegram_trials_routing.py`, add a distribution test that reads the manifest:

```python
def test_trial_distribution_writes_trial_manifest_entries(tmp_path):
    manifest = tmp_path / "calendar_manifest.json"
    video = tmp_path / "videos_finales" / "TRIAL_TANDA" / "clip.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")

    from calendar_manifest import build_entry, replace_entries

    entry = build_entry(
        "TRIALS - user1",
        100,
        "trial",
        1,
        1,
        "TRIAL_TANDA",
        str(video),
        "clip__TANDA_TRIAL_TANDA__ACC100__D1__S1.mp4",
    )
    replace_entries(manifest, [entry], {"TRIALS - user1"}, "trial")

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["entries"][0]["delivery_kind"] == "trial"
    assert payload["entries"][0]["source_path"] == str(video.resolve())
```

- [ ] **Step 3: Run updated distribution tests and verify old copy behavior fails**

Run: `pytest tests/test_logistica_por_cuentas_e2e.py tests/test_telegram_trials_routing.py -v`

Expected: FAIL because existing code still writes copied files under `CALENDARIO_POSTEO` or `CALENDARIO_TRIALS`.

- [ ] **Step 4: Replace `Organizador.distribute_tanda` copy logic**

At the point where it currently builds `dst`, calls `shutil.copy2(src, dst)`, and calls `change_video_metadata(dst)`, change it to accumulate manifest entries:

```python
from calendar_manifest import build_entry, manifest_path, replace_entries

manifest_entries = []
affected_usernames = set()

# inside the selected account/video loop
logical_name = build_calendar_video_filename(
    original_name=os.path.basename(src),
    tanda=tanda_name,
    account_id=acc_id,
    day=day,
    slot=slot,
)
log_id = db.get_video_transform_log_id(src) if hasattr(db, "get_video_transform_log_id") else None
manifest_entries.append(
    build_entry(
        username=username,
        account_id=acc_id,
        delivery_kind="normal",
        day=day,
        slot=slot,
        tanda=tanda_name,
        source_path=src,
        telegram_filename=logical_name,
        transform_log_id=log_id,
    )
)
affected_usernames.add(username)
db.add_video_to_history(acc_id, src, tanda_name=tanda_name, day=day, slot=slot)

# after a successful loop
replace_entries(
    manifest_path(os.path.dirname(os.path.abspath(__file__))),
    manifest_entries,
    affected_usernames,
    "normal",
)
```

Remove `change_video_metadata(dst)` from this distribution path. Keep `change_video_metadata` defined for legacy callers that may still import it.

- [ ] **Step 5: Replace normal per-account GUI copy logic**

In `gui_premium_v7.py` inside `_acct_dist_run`, replace `_copy_calendar_file(src, dst)` with manifest entry creation:

```python
from calendar_manifest import build_entry, manifest_path, replace_entries

entries = []
affected = set()

logical_name = build_calendar_video_filename(
    original_name=vid_name,
    tanda=os.path.basename(folder),
    account_id=getattr(acc, "id", None) or acc.get("id"),
    day=day_idx + 1,
    slot=slot_idx + 1,
)
source_path = os.path.abspath(os.path.join(folder, vid_name))
entries.append(
    build_entry(
        username=username,
        account_id=getattr(acc, "id", None) or acc.get("id"),
        delivery_kind="normal",
        day=day_idx + 1,
        slot=slot_idx + 1,
        tanda=os.path.basename(folder),
        source_path=source_path,
        telegram_filename=logical_name,
        transform_log_id=self.db.get_video_transform_log_id(source_path),
    )
)
affected.add(username)

replace_entries(manifest_path(_BASE_DIR), entries, affected, "normal")
```

Keep collision checks for logical filenames within the in-memory plan, not for filesystem destination paths.

- [ ] **Step 6: Replace Trial scheduler copy logic**

In `gui_premium_v7.py` Trial scheduler task, replace `_copy_calendar_file(os.path.join(...), target)` with:

```python
from calendar_manifest import build_entry, manifest_path, replace_entries

entries = []
affected = set()
for user, files in plan.assigned.items():
    tanda = assignments[user]
    for index, name in enumerate(files):
        day, slot = plan.day_slot_for(user, index)
        source_path = os.path.abspath(os.path.join(_BASE_DIR, "videos_finales", tanda, name))
        logical_name = build_calendar_video_filename(
            original_name=name,
            tanda=tanda,
            account_id=account_ids.get(user),
            day=day,
            slot=slot,
        )
        entries.append(
            build_entry(
                username=user,
                account_id=account_ids.get(user),
                delivery_kind="trial",
                day=day,
                slot=slot,
                tanda=tanda,
                source_path=source_path,
                telegram_filename=logical_name,
                transform_log_id=self.db.get_video_transform_log_id(source_path),
            )
        )
        affected.add(user)

replace_entries(manifest_path(_BASE_DIR), entries, affected, "trial")
count = len(entries)
```

Use the existing account-id lookup already available in that method; if it does not exist, build it once from selected virtual-account rows before the task starts.

- [ ] **Step 7: Run distribution tests**

Run: `pytest tests/test_logistica_por_cuentas_e2e.py tests/test_telegram_trials_routing.py -v`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add Organizador.py gui_premium_v7.py tests/test_logistica_por_cuentas_e2e.py tests/test_telegram_trials_routing.py
git commit -m "feat: route logistics through calendar manifest"
```

---

### Task 4: Telegram Manifest Adapter, Counts, And Cleanup

**Files:**
- Modify: `organizadortg.py`
- Test: `tests/test_telegram_caption_routing.py`
- Test: `tests/test_telegram_calendar_cleanup.py`
- Test: `tests/test_telegram_topic_reset.py`
- Test: `tests/test_telegram_trials_routing.py`
- Test: `tests/test_telegram_single_account_selection.py`

**Interfaces:**
- Consumes: `calendar_manifest.load_entries`, `remove_entries_for_accounts`, `manifest_path`
- Produces: `_scan_manifest_calendar_structure(manifest_file: str | os.PathLike) -> list[dict]`
- Preserves: video row fields `path`, `filename`, `category`, `day`, `username`, `delivery_kind`, `tanda`

- [ ] **Step 1: Add failing manifest-backed Telegram scan tests**

Add this helper and test to `tests/test_telegram_caption_routing.py`:

```python
def test_scan_calendar_structure_uses_manifest_when_present(tmp_path, monkeypatch):
    import organizadortg
    from calendar_manifest import build_entry, replace_entries

    video = tmp_path / "videos_finales" / "T1" / "clip.mp4"
    legacy = tmp_path / "CALENDARIO_POSTEO" / "Dia_1" / "legacy" / "legacy.mp4"
    video.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    video.write_bytes(b"manifest")
    legacy.write_bytes(b"legacy")
    entry = build_entry("alice", 1, "normal", 1, 1, "T1", str(video), "clip__TANDA_T1__ACC1__D1__S1.mp4")
    replace_entries(tmp_path / "calendar_manifest.json", [entry], {"alice"}, "normal")

    monkeypatch.setattr(organizadortg, "BASE_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(organizadortg, "input_root", str(tmp_path / "CALENDARIO_POSTEO"), raising=False)
    monkeypatch.setattr(organizadortg, "trial_input_root", str(tmp_path / "CALENDARIO_TRIALS"), raising=False)

    rows = organizadortg.scan_calendar_structure()

    assert len(rows) == 1
    assert rows[0]["path"] == str(video.resolve())
    assert rows[0]["filename"] == "clip__TANDA_T1__ACC1__D1__S1.mp4"
    assert rows[0]["username"] == "alice"
    assert rows[0]["delivery_kind"] == "normal"
```

- [ ] **Step 2: Add failing manifest cleanup test**

Add to `tests/test_telegram_calendar_cleanup.py`:

```python
def test_delete_calendarizations_removes_manifest_rows_only(tmp_path, monkeypatch):
    import organizadortg
    from calendar_manifest import build_entry, load_entries, replace_entries

    video = tmp_path / "videos_finales" / "T" / "clip.mp4"
    legacy = tmp_path / "CALENDARIO_POSTEO" / "Dia_1" / "alice" / "legacy.mp4"
    video.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    legacy.write_bytes(b"legacy")
    entries = [
        build_entry("alice", 1, "normal", 1, 1, "T", str(video), "a__TANDA_T.mp4"),
        build_entry("bob", 2, "normal", 1, 1, "T", str(video), "b__TANDA_T.mp4"),
    ]
    replace_entries(tmp_path / "calendar_manifest.json", entries, {"alice", "bob"}, "normal")
    monkeypatch.setattr(organizadortg, "BASE_DIR", str(tmp_path), raising=False)

    removed = organizadortg.delete_calendarizations_for_accounts(["alice"])

    assert removed == 1
    assert [row["username"] for row in load_entries(tmp_path / "calendar_manifest.json")] == ["bob"]
    assert legacy.exists()
```

- [ ] **Step 3: Run Telegram tests and verify folder-first behavior fails**

Run: `pytest tests/test_telegram_caption_routing.py tests/test_telegram_calendar_cleanup.py tests/test_telegram_topic_reset.py tests/test_telegram_trials_routing.py tests/test_telegram_single_account_selection.py -v`

Expected: FAIL in the new manifest scan and cleanup tests because `organizadortg.py` does not consume the manifest yet.

- [ ] **Step 4: Add manifest adapter to `organizadortg.py`**

```python
from calendar_manifest import load_entries, manifest_path, remove_entries_for_accounts


def _calendar_manifest_file():
    return manifest_path(BASE_DIR)


def _scan_manifest_calendar_structure(manifest_file=None):
    manifest_file = manifest_file or _calendar_manifest_file()
    rows = []
    for entry in load_entries(manifest_file, require_source=True):
        rows.append(
            {
                "path": entry["source_path"],
                "filename": entry["telegram_filename"],
                "category": entry.get("tanda") or "",
                "tanda": entry.get("tanda") or "",
                "day": int(entry["day"]),
                "slot": int(entry["slot"]),
                "username": entry["username"],
                "delivery_kind": entry.get("delivery_kind", "normal"),
                "account_id": entry.get("account_id"),
                "transform_log_id": entry.get("transform_log_id"),
            }
        )
    rows.sort(key=lambda row: (row["day"], row.get("slot", 0), row["username"], row["filename"]))
    return rows
```

- [ ] **Step 5: Split current folder scanner into legacy helper and gate manifest first**

Rename the existing folder implementation to `_scan_legacy_calendar_structure`, then make `scan_calendar_structure`:

```python
def scan_calendar_structure():
    manifest_file = _calendar_manifest_file()
    if os.path.exists(manifest_file):
        return _scan_manifest_calendar_structure(manifest_file)
    return _scan_legacy_calendar_structure()
```

Do not extend Trial folder scan when the manifest exists; Trial entries are already in the shared manifest.

- [ ] **Step 6: Update count helpers to use manifest rows**

For `count_account_calendar_videos_by_kind` and `count_account_calendar_videos`, branch on manifest presence:

```python
def _manifest_counts_by_account(kind=None):
    counts = {}
    for row in _scan_manifest_calendar_structure(_calendar_manifest_file()):
        if kind and row.get("delivery_kind") != kind:
            continue
        counts[row["username"]] = counts.get(row["username"], 0) + 1
    return counts
```

Keep legacy count code under the absent-manifest branch.

- [ ] **Step 7: Update selected cleanup to edit manifest first**

At the top of `delete_calendarizations_for_accounts`:

```python
manifest_file = _calendar_manifest_file()
if os.path.exists(manifest_file):
    return remove_entries_for_accounts(manifest_file, set(account_names))
```

Leave existing physical folder deletion code for no-manifest legacy schedules.

- [ ] **Step 8: Run Telegram tests**

Run: `pytest tests/test_telegram_caption_routing.py tests/test_telegram_calendar_cleanup.py tests/test_telegram_topic_reset.py tests/test_telegram_trials_routing.py tests/test_telegram_single_account_selection.py -v`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add organizadortg.py tests/test_telegram_caption_routing.py tests/test_telegram_calendar_cleanup.py tests/test_telegram_topic_reset.py tests/test_telegram_trials_routing.py tests/test_telegram_single_account_selection.py
git commit -m "feat: read telegram calendar from manifest"
```

---

### Task 5: Tandas And Video Editor Transform Logging

**Files:**
- Modify: `videos.py`
- Modify: `video_editor.py`
- Modify: `gui_premium_v7.py`
- Test: `tests/test_render_concurrency.py`
- Test: `tests/test_video_editor_transform_logs.py`

**Interfaces:**
- Consumes: `DatabaseManager.save_video_transform_log`
- Produces: `video_editor.describe_overlay_log(overlays: list[dict]) -> list[dict]`
- Logs process kinds: `tandas`, `video_editor`

- [ ] **Step 1: Add failing Tandas log test**

Add to `tests/test_render_concurrency.py`:

```python
import json
from pathlib import Path


def test_process_tandas_logs_successful_outputs(tmp_path, monkeypatch):
    import videos
    from database import DatabaseManager

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    p1 = tmp_path / "p1.mp4"
    p2 = tmp_path / "p2.mp4"
    p1.write_bytes(b"p1")
    p2.write_bytes(b"p2")

    def fake_render_video_pair(path_v1, path_v2, out_path, tanda_name, p1_id, p2_id, ffmpeg_threads=None):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"rendered")
        return out_path

    monkeypatch.setattr(videos, "render_video_pair", fake_render_video_pair)

    videos.process_tandas(
        [(str(p1), str(p2), str(tmp_path / "videos_finales" / "TANDA" / "out.mp4"), "TANDA", 7, 8)],
        db,
        ffmpeg_threads=2,
    )

    rows = db.list_video_transform_logs()
    assert rows[0]["process_kind"] == "tandas"
    details = json.loads(rows[0]["details_json"])
    assert details["p1_id"] == 7
    assert details["p2_id"] == 8
    assert details["ffmpeg_threads"] == 2
```

- [ ] **Step 2: Add failing Video Editor overlay log test**

```python
# tests/test_video_editor_transform_logs.py
import json

from database import DatabaseManager
from video_editor import describe_overlay_log


def test_describe_overlay_log_keeps_effective_overlay_values():
    overlays = [
        {
            "photo_path": "C:/imgs/a.png",
            "start_frame": 12,
            "end_frame": 36,
            "position": "custom",
            "x": 120,
            "y": 40,
            "size": 0.25,
            "opacity": 0.8,
        }
    ]

    assert describe_overlay_log(overlays) == [
        {
            "photo_path": "C:/imgs/a.png",
            "start_frame": 12,
            "end_frame": 36,
            "position": "custom",
            "x": 120,
            "y": 40,
            "size": 0.25,
            "opacity": 0.8,
        }
    ]


def test_video_editor_completion_can_persist_overlay_details(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    src = tmp_path / "src.mp4"
    out = tmp_path / "out.mp4"
    src.write_bytes(b"src")
    out.write_bytes(b"out")

    log_id = db.save_video_transform_log(
        "video_editor",
        str(src),
        str(out),
        {"overlays": describe_overlay_log([{"photo_path": "x.png", "start_frame": 1, "end_frame": 2}])},
    )

    row = db.list_video_transform_logs()[0]
    assert row["id"] == log_id
    assert json.loads(row["details_json"])["overlays"][0]["photo_path"] == "x.png"
```

- [ ] **Step 3: Run tests and verify missing logging/helper**

Run: `pytest tests/test_render_concurrency.py tests/test_video_editor_transform_logs.py -v`

Expected: FAIL because Tandas do not save transform logs and `describe_overlay_log` is missing.

- [ ] **Step 4: Add Video Editor overlay description helper**

```python
def describe_overlay_log(overlays):
    result = []
    for overlay in overlays or []:
        result.append(
            {
                "photo_path": overlay.get("photo_path") or overlay.get("path"),
                "start_frame": overlay.get("start_frame"),
                "end_frame": overlay.get("end_frame"),
                "start_time": overlay.get("start_time"),
                "end_time": overlay.get("end_time"),
                "position": overlay.get("position"),
                "x": overlay.get("x"),
                "y": overlay.get("y"),
                "size": overlay.get("size"),
                "opacity": overlay.get("opacity"),
            }
        )
    return result
```

- [ ] **Step 5: Log Tandas after successful render futures**

In `videos.process_tandas`, after `future.result()` confirms output success:

```python
details = {
    "p1_path": os.path.abspath(path_v1),
    "p2_path": os.path.abspath(path_v2),
    "p1_id": p1_id,
    "p2_id": p2_id,
    "tanda_name": tanda_name,
    "ffmpeg_threads": ffmpeg_threads,
}
db.save_video_transform_log(
    "tandas",
    os.path.abspath(path_v1),
    os.path.abspath(out_path),
    details,
    tanda_name=tanda_name,
    source_identity=f"p1:{p1_id}|p2:{p2_id}",
)
```

Use the actual local variable names from the future job tuple.

- [ ] **Step 6: Log Video Editor after render completion in GUI**

In `gui_premium_v7.py` around the Video Editor render completion callback:

```python
from video_editor import describe_overlay_log

details = {
    "input_path": os.path.abspath(input_path),
    "overlays": describe_overlay_log(overlays),
    "ffmpeg_threads": performance.ffmpeg_threads if performance else None,
}
self.db.save_video_transform_log(
    "video_editor",
    os.path.abspath(input_path),
    os.path.abspath(output_path),
    details,
)
```

Execute this only after `video_editor.render_video(...)` returns and the output path exists.

- [ ] **Step 7: Run Tandas and Video Editor tests**

Run: `pytest tests/test_render_concurrency.py tests/test_video_editor_transform_logs.py -v`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add videos.py video_editor.py gui_premium_v7.py tests/test_render_concurrency.py tests/test_video_editor_transform_logs.py
git commit -m "feat: log tandas and editor transforms"
```

---

### Task 6: Forge And Forge Trial Exact Transform Logging

**Files:**
- Modify: `gui_premium_v7.py`
- Test: `tests/test_forge_concurrency.py`
- Test: `tests/test_trial_content.py`

**Interfaces:**
- Consumes: `metadata_pool.apply_variant_and_metadata(...) -> dict`
- Consumes: `DatabaseManager.save_video_transform_log`
- Logs process kinds: `forge`, `forge_trial`

- [ ] **Step 1: Add failing Forge log test**

Add to `tests/test_forge_concurrency.py`:

```python
import json
from pathlib import Path


def test_forge_logs_exact_variant_params_after_success(tmp_path, monkeypatch):
    import gui_premium_v7
    from database import DatabaseManager

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    src = tmp_path / "input.mp4"
    out = tmp_path / "videos_finales" / "TANDA" / "input__c01.mp4"
    src.write_bytes(b"input")

    def fake_apply_variant_and_metadata(vid_path, out_path, meta, **kwargs):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"out")
        return {
            "crop_px": 2,
            "mirror": False,
            "zoom_pct": 0.004,
            "rotate_deg": 0.8,
            "brightness": 0.01,
            "contrast": 1.01,
            "saturation": 0.99,
            "gamma": 1.0,
            "noise": 0.002,
            "speed": 1.003,
            "trim_start_ms": 2,
            "trim_end_ms": 0,
            "iphone_metadata": {"model": "iPhone 15 Pro"},
        }

    monkeypatch.setattr(gui_premium_v7.metadata_pool, "apply_variant_and_metadata", fake_apply_variant_and_metadata)

    log_id = gui_premium_v7._save_forge_transform_log(
        db,
        process_kind="forge",
        source_path=str(src),
        output_path=str(out),
        tanda_name="TANDA",
        source_identity="fingerprint",
        params=fake_apply_variant_and_metadata(str(src), str(out), {}),
        meta={"model": "iPhone 15 Pro"},
    )

    rows = db.list_video_transform_logs()
    assert rows[0]["id"] == log_id
    assert rows[0]["process_kind"] == "forge"
    details = json.loads(rows[0]["details_json"])
    assert details["rotate_deg"] == 0.8
    assert details["crop_px"] == 2
    assert details["speed"] == 1.003
    assert details["iphone_metadata"]["model"] == "iPhone 15 Pro"
```

- [ ] **Step 2: Add failing Forge Trial process-kind test**

Add to `tests/test_trial_content.py`:

```python
def test_forge_trial_logs_trial_process_kind(tmp_path):
    import gui_premium_v7
    from database import DatabaseManager

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    src = tmp_path / "src.mp4"
    out = tmp_path / "videos_finales" / "TRIAL" / "src__c17.mp4"
    src.write_bytes(b"src")
    out.parent.mkdir(parents=True)
    out.write_bytes(b"out")

    gui_premium_v7._save_forge_transform_log(
        db,
        process_kind="forge_trial",
        source_path=str(src),
        output_path=str(out),
        tanda_name="TRIAL",
        source_identity="hash",
        params={"rotate_deg": 0.8, "crop_px": 2, "speed": 1.003},
        meta={"device": "iphone"},
    )

    row = db.list_video_transform_logs()[0]
    assert row["process_kind"] == "forge_trial"
    assert row["tanda_name"] == "TRIAL"
```

- [ ] **Step 3: Run Forge tests and verify helper is missing**

Run: `pytest tests/test_forge_concurrency.py tests/test_trial_content.py -v`

Expected: FAIL with `AttributeError` for `_save_forge_transform_log`.

- [ ] **Step 4: Add Forge log helper**

```python
def _save_forge_transform_log(
    db,
    process_kind,
    source_path,
    output_path,
    tanda_name,
    source_identity,
    params,
    meta,
):
    details = dict(params or {})
    details["iphone_metadata"] = meta or {}
    return db.save_video_transform_log(
        process_kind,
        os.path.abspath(source_path),
        os.path.abspath(output_path),
        details,
        tanda_name=tanda_name,
        source_identity=source_identity,
    )
```

- [ ] **Step 5: Preserve returned params in `forge_process`**

Change `process_copy` to return the params from `metadata_pool.apply_variant_and_metadata`:

```python
params = metadata_pool.apply_variant_and_metadata(
    vid_path,
    out_path,
    meta,
    enabled=fx_enabled,
    strength=forge_strength,
    overrides=forge_overrides,
    ffmpeg_threads=performance.ffmpeg_threads,
)
return filename, out_name, vh, fingerprint, vid_path, out_path, meta, params
```

In the completed future block, save the log after the output save succeeds:

```python
filename, out_name, vh, fingerprint, vid_path, out_path, meta, params = future.result()
process_kind = "forge_trial" if is_trial_tanda else "forge"
_save_forge_transform_log(
    db_ref,
    process_kind=process_kind,
    source_path=vid_path,
    output_path=out_path,
    tanda_name=tanda_name,
    source_identity=fingerprint,
    params=params,
    meta=meta,
)
```

Keep the existing `db_ref.save_forge_video` and `save_metadata_fingerprints` calls.

- [ ] **Step 6: Run Forge tests**

Run: `pytest tests/test_forge_concurrency.py tests/test_trial_content.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add gui_premium_v7.py tests/test_forge_concurrency.py tests/test_trial_content.py
git commit -m "feat: log forge transform details"
```

---

### Task 7: Transform Log GUI Table

**Files:**
- Modify: `gui_premium_v7.py`
- Test: `tests/test_transform_log_formatting.py`

**Interfaces:**
- Consumes: `DatabaseManager.list_video_transform_logs(limit: int = 500) -> list[dict]`
- Produces: `_format_transform_summary(details: dict) -> dict[str, str]`
- Produces: GUI table with process, output, source, tanda, rotation, crop, speed, created time, and raw JSON details on selection

- [ ] **Step 1: Add failing formatter test**

```python
# tests/test_transform_log_formatting.py
from gui_premium_v7 import _format_transform_summary


def test_format_transform_summary_outputs_table_values():
    formatted = _format_transform_summary(
        {"rotate_deg": 0.8, "crop_px": 2, "speed": 1.003, "trim_start_ms": 2}
    )

    assert formatted["rotation"] == "0.80 deg"
    assert formatted["crop"] == "2 px"
    assert formatted["speed"] == "x1.0030"
    assert formatted["trim"] == "2 ms / 0 ms"
```

- [ ] **Step 2: Run formatter test and verify helper is missing**

Run: `pytest tests/test_transform_log_formatting.py -v`

Expected: FAIL with `ImportError` or `AttributeError` for `_format_transform_summary`.

- [ ] **Step 3: Add formatter helper**

```python
def _format_transform_summary(details):
    details = details or {}
    trim_start = details.get("trim_start_ms") or 0
    trim_end = details.get("trim_end_ms") or 0
    return {
        "rotation": f"{float(details.get('rotate_deg') or 0):.2f} deg",
        "crop": f"{int(details.get('crop_px') or 0)} px",
        "speed": f"x{float(details.get('speed') or 1):.4f}",
        "trim": f"{int(trim_start)} ms / {int(trim_end)} ms",
    }
```

- [ ] **Step 4: Add GUI table using existing ttk style**

Add a tab or section beside existing operational tables in `gui_premium_v7.py`:

```python
columns = ("process", "output", "source", "tanda", "rotation", "crop", "speed", "created")
self.transform_log_tree = ttk.Treeview(parent, columns=columns, show="headings", height=12)
for column in columns:
    self.transform_log_tree.heading(column, text=column.title())
    self.transform_log_tree.column(column, width=120, anchor="w")
self.transform_log_tree.bind("<<TreeviewSelect>>", self._on_transform_log_select)
self.transform_log_detail = tk.Text(parent, height=10, wrap="word")
```

Populate it with:

```python
def refresh_transform_log_table(self):
    for item in self.transform_log_tree.get_children():
        self.transform_log_tree.delete(item)
    self._transform_log_rows = {}
    for row in self.db.list_video_transform_logs(limit=500):
        details = json.loads(row["details_json"])
        summary = _format_transform_summary(details)
        item = self.transform_log_tree.insert(
            "",
            "end",
            values=(
                row["process_kind"],
                row["output_filename"],
                os.path.basename(row["source_path"]),
                row.get("tanda_name") or "",
                summary["rotation"],
                summary["crop"],
                summary["speed"],
                row["created_at"],
            ),
        )
        self._transform_log_rows[item] = row
```

Selection callback:

```python
def _on_transform_log_select(self, event=None):
    selection = self.transform_log_tree.selection()
    if not selection:
        return
    row = self._transform_log_rows.get(selection[0])
    details = json.loads(row["details_json"]) if row else {}
    self.transform_log_detail.delete("1.0", "end")
    self.transform_log_detail.insert("1.0", json.dumps(details, ensure_ascii=False, indent=2))
```

- [ ] **Step 5: Run formatter test**

Run: `pytest tests/test_transform_log_formatting.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add gui_premium_v7.py tests/test_transform_log_formatting.py
git commit -m "feat: show video transform logs in gui"
```

---

### Task 8: Final Integration And No-Send Smoke

**Files:**
- Modify only files needed to resolve failures from the focused test suite.
- Test: existing Telegram, Forge, Trial, and render tests touched by this plan.

**Interfaces:**
- Consumes: all tasks above.
- Produces: verified manifest-backed flow with no real Telegram send.

- [ ] **Step 1: Run focused suite**

Run:

```bash
pytest tests/test_calendar_manifest.py tests/test_video_transform_logs.py tests/test_logistica_por_cuentas_e2e.py tests/test_telegram_caption_routing.py tests/test_telegram_calendar_cleanup.py tests/test_telegram_topic_reset.py tests/test_telegram_trials_routing.py tests/test_telegram_single_account_selection.py tests/test_render_concurrency.py tests/test_video_editor_transform_logs.py tests/test_forge_concurrency.py tests/test_trial_content.py tests/test_transform_log_formatting.py -v
```

Expected: PASS.

- [ ] **Step 2: Run broader legacy suite around Telegram and Forge**

Run:

```bash
pytest tests/test_telegram_long_paths.py tests/test_telegram_express_parallel.py tests/test_trial_account_selection.py tests/test_trial_content.py tests/test_forge_concurrency.py tests/test_render_concurrency.py -v
```

Expected: PASS or SKIP for environment-gated tests that already skip without credentials.

- [ ] **Step 3: Run no-send Telegram smoke**

Use the repository's existing fake execution path. The smoke must assert rows are built from `calendar_manifest.json`, `path` points under `videos_finales`, `filename` contains `__TANDA_`, and no Telegram send method is invoked.

Command:

```bash
pytest tests/test_telegram_caption_routing.py::test_scan_calendar_structure_uses_manifest_when_present tests/test_telegram_trials_routing.py -v
```

Expected: PASS and no live Telegram messages sent.

- [ ] **Step 4: Inspect working tree**

Run: `git status --short`

Expected: only files touched by this plan plus pre-existing unrelated dirty files remain.

- [ ] **Step 5: Commit final fixes if Step 1 or Step 2 required changes**

```bash
git add calendar_manifest.py database.py Organizador.py gui_premium_v7.py organizadortg.py videos.py video_editor.py tests/test_calendar_manifest.py tests/test_video_transform_logs.py tests/test_logistica_por_cuentas_e2e.py tests/test_telegram_caption_routing.py tests/test_telegram_calendar_cleanup.py tests/test_telegram_topic_reset.py tests/test_telegram_trials_routing.py tests/test_telegram_single_account_selection.py tests/test_render_concurrency.py tests/test_video_editor_transform_logs.py tests/test_forge_concurrency.py tests/test_trial_content.py tests/test_transform_log_formatting.py
git commit -m "test: verify manifest logistics flow"
```

Skip this commit only when no files changed after the previous task commit.

---

## Self-Review Checklist

- Spec coverage: Task 1 covers shared JSON manifest and valid source filtering. Task 2 covers durable SQLite logs. Task 3 covers normal and Trial distribution without calendar copies or post-copy metadata mutation. Task 4 covers Telegram scan/count/filter/cleanup manifest behavior and legacy absent-manifest fallback. Task 5 covers Tandas and Video Editor logs. Task 6 covers Forge and Forge Trial exact returned params. Task 7 covers the GUI table. Task 8 covers integration and no-send verification.
- Placeholder scan: This plan contains concrete file paths, function names, test bodies, commands, expected outcomes, and commit commands.
- Type consistency: The same manifest functions and DB methods are used across tasks: `manifest_path`, `build_entry`, `load_entries`, `replace_entries`, `remove_entries_for_accounts`, `save_video_transform_log`, `get_video_transform_log_id`, and `list_video_transform_logs`.
