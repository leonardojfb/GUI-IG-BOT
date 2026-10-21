# Vault-backed Forge Input History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Vault-backed Forge flow where Forge inputs are registered assets and every rendered copy uses an unused edit combination for that input.

**Architecture:** Add focused backend modules for Vault assets and Forge variant reservation, extend SQLite transform logs with Vault linkage, then connect the existing CustomTkinter Forge screen to those services. Existing rendering remains in `metadata_pool.py`; the change is to preselect params before FFmpeg and log the stable variant signature after success.

**Tech Stack:** Python 3, SQLite via `database.py`, CustomTkinter/ttk in `gui_premium_v7.py`, pytest.

## Global Constraints

- First implementation scope is Forge only.
- Forge inputs must come from the Vault during normal use.
- Do not make Edicion de video or Tandas require Vault inputs in this version.
- Do not copy all media into a physical backup folder.
- Do not change Telegram delivery or calendar behavior.
- Failed renders do not save transform logs or consume signatures.
- Normal release packaging must still exclude client-local DBs, Telegram state, calendars, videos, histories, tokens, update config, and backup folders unless explicitly requested.

---

## File Structure

- Create `vault.py`: pure Vault asset helpers and reservation logic. No tkinter.
- Modify `database.py`: add `vault_assets`, extend `video_transform_logs`, and expose DB methods.
- Modify `metadata_pool.py`: allow `apply_variant_and_metadata(..., params=...)`.
- Modify `gui_premium_v7.py`: add Boveda navigation/screen, Vault import/list, Forge Vault selection, and reservation use.
- Create `tests/test_vault_assets.py`: DB asset registration and history tests.
- Create `tests/test_forge_variant_reservations.py`: signature and reservation tests.
- Modify `tests/test_video_transform_logs.py`: verify Vault linkage round trip.
- Modify `tests/test_forge_concurrency.py`: verify preselected params path does not break existing Forge behavior.

---

### Task 1: Vault Asset Storage

**Files:**
- Modify: `database.py`
- Create: `vault.py`
- Test: `tests/test_vault_assets.py`

**Interfaces:**
- Produces: `vault.media_type_for_path(path: str) -> str`
- Produces: `vault.hash_asset(path: str) -> str`
- Produces: `DatabaseManager.upsert_vault_asset(source_path: str, display_name: str | None = None, tags: list[str] | None = None) -> dict`
- Produces: `DatabaseManager.list_vault_assets(search: str = "") -> list[dict]`
- Produces: `DatabaseManager.get_vault_asset(asset_id: int) -> dict | None`

- [ ] **Step 1: Write the failing Vault storage tests**

Create `tests/test_vault_assets.py`:

```python
import json

from database import DatabaseManager


def test_registering_same_file_returns_same_vault_asset(tmp_path):
    from vault import hash_asset

    media = tmp_path / "clip.mp4"
    media.write_bytes(b"video-bytes")
    db = DatabaseManager(str(tmp_path / "organizador.db"))

    first = db.upsert_vault_asset(str(media), tags=["promo"])
    second = db.upsert_vault_asset(str(media), display_name="Renamed clip", tags=["forge"])

    assert second["id"] == first["id"]
    assert second["asset_hash"] == hash_asset(str(media))
    assert second["display_name"] == "Renamed clip"
    assert json.loads(second["tags_json"]) == ["forge"]
    assert len(db.list_vault_assets()) == 1
    db.close()


def test_list_vault_assets_filters_by_name_and_tag(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    a = tmp_path / "alpha.mp4"
    b = tmp_path / "beta.mov"
    a.write_bytes(b"a")
    b.write_bytes(b"b")

    db.upsert_vault_asset(str(a), tags=["main"])
    db.upsert_vault_asset(str(b), tags=["trial"])

    assert [row["display_name"] for row in db.list_vault_assets("alp")] == ["alpha.mp4"]
    assert [row["display_name"] for row in db.list_vault_assets("trial")] == ["beta.mov"]
    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_vault_assets.py -v
```

Expected: FAIL because `vault.py` and `DatabaseManager.upsert_vault_asset` do not exist.

- [ ] **Step 3: Implement `vault.py`**

Create `vault.py`:

```python
import hashlib
import os


VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def media_type_for_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in IMAGE_EXTS:
        return "image"
    return "file"


def hash_asset(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

- [ ] **Step 4: Extend `database.py` schema and methods**

In `SCHEMA`, add:

```python
CREATE TABLE IF NOT EXISTS vault_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_hash TEXT NOT NULL UNIQUE,
    source_path TEXT NOT NULL,
    display_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_vault_assets_display_name
ON vault_assets(display_name);
```

Add methods to `DatabaseManager`:

```python
    def upsert_vault_asset(self, source_path, display_name=None, tags=None):
        from vault import hash_asset, media_type_for_path

        abs_path = os.path.abspath(source_path)
        asset_hash = hash_asset(abs_path)
        name = (display_name or os.path.basename(abs_path)).strip() or os.path.basename(abs_path)
        tags_json = json.dumps(list(tags or []), ensure_ascii=False, sort_keys=True)
        media_type = media_type_for_path(abs_path)
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO vault_assets (
                asset_hash, source_path, display_name, media_type, tags_json, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(asset_hash) DO UPDATE SET
                source_path=excluded.source_path,
                display_name=excluded.display_name,
                media_type=excluded.media_type,
                tags_json=excluded.tags_json,
                last_seen_at=datetime('now')
            """,
            (asset_hash, abs_path, name, media_type, tags_json),
        )
        self.conn.commit()
        return dict(cur.execute("SELECT * FROM vault_assets WHERE asset_hash=?", (asset_hash,)).fetchone())

    def list_vault_assets(self, search=""):
        term = f"%{str(search or '').strip()}%"
        rows = self.conn.execute(
            """
            SELECT * FROM vault_assets
            WHERE ? = '%%' OR display_name LIKE ? OR source_path LIKE ? OR tags_json LIKE ?
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (term, term, term, term),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_vault_asset(self, asset_id):
        row = self.conn.execute("SELECT * FROM vault_assets WHERE id=?", (int(asset_id),)).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```powershell
pytest tests/test_vault_assets.py -v
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```powershell
git add database.py vault.py tests/test_vault_assets.py
git commit -m "feat(vault): add asset storage"
```

---

### Task 2: Transform Log Vault Linkage

**Files:**
- Modify: `database.py`
- Modify: `tests/test_video_transform_logs.py`

**Interfaces:**
- Consumes: `DatabaseManager.upsert_vault_asset(...) -> dict`
- Produces: `DatabaseManager.save_video_transform_log(..., vault_asset_id: int | None = None, variant_signature: str | None = None) -> int`
- Produces: `DatabaseManager.used_variant_signatures(vault_asset_id: int, process_kind: str) -> set[str]`
- Produces: `DatabaseManager.list_vault_asset_history(vault_asset_id: int, limit: int = 200) -> list[dict]`

- [ ] **Step 1: Write failing transform-log linkage test**

Append to `tests/test_video_transform_logs.py`:

```python
def test_video_transform_log_round_trips_vault_linkage(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"in")
    output.write_bytes(b"out")
    asset = db.upsert_vault_asset(str(source))

    log_id = db.save_video_transform_log(
        "forge",
        str(source),
        str(output),
        {"speed": 1.0},
        vault_asset_id=asset["id"],
        variant_signature="sig-123",
    )

    rows = db.list_video_transform_logs(limit=10)
    assert rows[0]["id"] == log_id
    assert rows[0]["vault_asset_id"] == asset["id"]
    assert rows[0]["variant_signature"] == "sig-123"
    assert db.used_variant_signatures(asset["id"], "forge") == {"sig-123"}
    assert db.list_vault_asset_history(asset["id"])[0]["id"] == log_id
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_video_transform_logs.py::test_video_transform_log_round_trips_vault_linkage -v
```

Expected: FAIL because `save_video_transform_log` has no `vault_asset_id` parameter.

- [ ] **Step 3: Extend schema migration and log methods**

In `SCHEMA`, add nullable columns to `video_transform_logs` table definition:

```python
    vault_asset_id INTEGER,
    variant_signature TEXT,
```

Add index:

```python
CREATE INDEX IF NOT EXISTS idx_video_transform_logs_vault_variant
ON video_transform_logs(vault_asset_id, process_kind, variant_signature);
```

In `_migrate_columns`, add:

```python
            "ALTER TABLE video_transform_logs ADD COLUMN vault_asset_id INTEGER",
            "ALTER TABLE video_transform_logs ADD COLUMN variant_signature TEXT",
```

Update `save_video_transform_log` signature and SQL to include `vault_asset_id` and `variant_signature`. Update `list_video_transform_logs` SELECT to return those columns. Add:

```python
    def used_variant_signatures(self, vault_asset_id, process_kind):
        rows = self.conn.execute(
            """
            SELECT variant_signature FROM video_transform_logs
            WHERE vault_asset_id=? AND process_kind=? AND variant_signature IS NOT NULL
            """,
            (int(vault_asset_id), process_kind),
        ).fetchall()
        return {row["variant_signature"] for row in rows}

    def list_vault_asset_history(self, vault_asset_id, limit=200):
        rows = self.conn.execute(
            """
            SELECT id, process_kind, source_path, output_path, output_filename,
                   tanda_name, source_identity, details_json, vault_asset_id,
                   variant_signature, created_at
            FROM video_transform_logs
            WHERE vault_asset_id=?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (int(vault_asset_id), int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
pytest tests/test_video_transform_logs.py tests/test_vault_assets.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add database.py tests/test_video_transform_logs.py
git commit -m "feat(vault): link transform logs to assets"
```

---

### Task 3: Forge Variant Signatures and Reservation

**Files:**
- Modify: `vault.py`
- Create: `tests/test_forge_variant_reservations.py`

**Interfaces:**
- Consumes: `DatabaseManager.used_variant_signatures(vault_asset_id, process_kind) -> set[str]`
- Produces: `vault.forge_variant_signature(asset_hash: str, process_kind: str, enabled: dict, params: dict) -> str`
- Produces: `vault.reserve_forge_variants(db, vault_asset: dict, process_kind: str, count: int, enabled: dict, strength: float, overrides: dict | None, max_attempts: int = 5000, rng=None) -> dict`
- Return shape: `{"asset": dict, "reserved": list[dict], "shortfall": int, "message": str}`

- [ ] **Step 1: Write failing signature and reservation tests**

Create `tests/test_forge_variant_reservations.py`:

```python
import random

from database import DatabaseManager
from vault import forge_variant_signature, reserve_forge_variants


BASE_PARAMS = {
    "crop_px": 2,
    "mirror": False,
    "zoom_pct": 1.00004,
    "rotate_deg": 0.0004,
    "brightness": 0.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "gamma": 1.0,
    "noise": 0,
    "speed": 1.00004,
    "trim_start_ms": 0,
    "trim_end_ms": 0,
}


def test_forge_variant_signature_is_stable_after_float_normalization():
    enabled = {"crop": True, "mirror": False}
    a = forge_variant_signature("hash-a", "forge", enabled, BASE_PARAMS)
    changed_order = dict(reversed(list(BASE_PARAMS.items())))
    b = forge_variant_signature("hash-a", "forge", enabled, changed_order)

    assert a == b
    assert a != forge_variant_signature("hash-b", "forge", enabled, BASE_PARAMS)


def test_reserve_forge_variants_avoids_used_and_current_run_duplicates(tmp_path, monkeypatch):
    import metadata_pool

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    output = tmp_path / "old.mp4"
    source.write_bytes(b"in")
    output.write_bytes(b"out")
    asset = db.upsert_vault_asset(str(source))
    used_params = dict(BASE_PARAMS)
    new_params = dict(BASE_PARAMS, crop_px=3)
    used_sig = forge_variant_signature(asset["asset_hash"], "forge", {"crop": True}, used_params)
    db.save_video_transform_log(
        "forge", str(source), str(output), used_params,
        vault_asset_id=asset["id"], variant_signature=used_sig,
    )
    candidates = iter([used_params, new_params, new_params, dict(BASE_PARAMS, crop_px=4)])
    monkeypatch.setattr(metadata_pool, "generate_variant_params", lambda **_kwargs: next(candidates))

    result = reserve_forge_variants(
        db, asset, "forge", 2, {"crop": True}, 1.0, None, rng=random.Random(1)
    )

    assert result["shortfall"] == 0
    assert [item["params"]["crop_px"] for item in result["reserved"]] == [3, 4]
    assert result["reserved"][0]["signature"] != result["reserved"][1]["signature"]
    db.close()


def test_reserve_forge_variants_reports_exhaustion(tmp_path, monkeypatch):
    import metadata_pool

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    output = tmp_path / "old.mp4"
    source.write_bytes(b"in")
    output.write_bytes(b"out")
    asset = db.upsert_vault_asset(str(source))
    sig = forge_variant_signature(asset["asset_hash"], "forge", {"crop": True}, BASE_PARAMS)
    db.save_video_transform_log(
        "forge", str(source), str(output), BASE_PARAMS,
        vault_asset_id=asset["id"], variant_signature=sig,
    )
    monkeypatch.setattr(metadata_pool, "generate_variant_params", lambda **_kwargs: dict(BASE_PARAMS))

    result = reserve_forge_variants(
        db, asset, "forge", 1, {"crop": True}, 1.0, None, max_attempts=3
    )

    assert result["reserved"] == []
    assert result["shortfall"] == 1
    assert "No quedan variantes nuevas" in result["message"]
    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_forge_variant_reservations.py -v
```

Expected: FAIL because `forge_variant_signature` and `reserve_forge_variants` do not exist.

- [ ] **Step 3: Implement signatures and reservation in `vault.py`**

Append:

```python
import json


FLOAT_FIELDS = {
    "zoom_pct": 4,
    "speed": 4,
    "brightness": 4,
    "contrast": 4,
    "saturation": 4,
    "gamma": 4,
    "rotate_deg": 3,
}
INT_FIELDS = {"crop_px", "noise", "trim_start_ms", "trim_end_ms"}
BOOL_FIELDS = {"mirror"}
FORGE_PARAM_KEYS = [
    "crop_px", "mirror", "zoom_pct", "rotate_deg", "brightness", "contrast",
    "saturation", "gamma", "noise", "speed", "trim_start_ms", "trim_end_ms",
]


def normalize_forge_params(params: dict) -> dict:
    normalized = {}
    for key in FORGE_PARAM_KEYS:
        value = (params or {}).get(key)
        if key in FLOAT_FIELDS:
            normalized[key] = round(float(value or 0), FLOAT_FIELDS[key])
        elif key in INT_FIELDS:
            normalized[key] = int(round(float(value or 0)))
        elif key in BOOL_FIELDS:
            normalized[key] = bool(value)
    return normalized


def forge_variant_signature(asset_hash: str, process_kind: str, enabled: dict, params: dict) -> str:
    payload = {
        "asset_hash": asset_hash,
        "process_kind": process_kind,
        "enabled": {key: bool((enabled or {}).get(key)) for key in sorted((enabled or {}).keys())},
        "params": normalize_forge_params(params),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def reserve_forge_variants(
    db,
    vault_asset,
    process_kind,
    count,
    enabled,
    strength,
    overrides,
    max_attempts=5000,
    rng=None,
):
    import metadata_pool

    used = set(db.used_variant_signatures(vault_asset["id"], process_kind))
    reserved_signatures = set()
    reserved = []
    attempts = 0
    target = int(count)
    while len(reserved) < target and attempts < int(max_attempts):
        attempts += 1
        params = metadata_pool.generate_variant_params(
            rng=rng, enabled=enabled, strength=strength, overrides=overrides
        )
        signature = forge_variant_signature(
            vault_asset["asset_hash"], process_kind, enabled, params
        )
        if signature in used or signature in reserved_signatures:
            continue
        reserved_signatures.add(signature)
        reserved.append({"params": params, "signature": signature})
    shortfall = target - len(reserved)
    if shortfall:
        message = (
            f"No quedan variantes nuevas para {vault_asset['display_name']} "
            "con los rangos actuales. Aumenta fuerza, activa mas efectos o amplia rangos custom."
        )
    else:
        message = ""
    return {"asset": vault_asset, "reserved": reserved, "shortfall": shortfall, "message": message}
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
pytest tests/test_forge_variant_reservations.py tests/test_vault_assets.py tests/test_video_transform_logs.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add vault.py tests/test_forge_variant_reservations.py
git commit -m "feat(forge): reserve unused vault variants"
```

---

### Task 4: Preselected Params in Metadata Pool

**Files:**
- Modify: `metadata_pool.py`
- Modify: `tests/test_forge_concurrency.py`

**Interfaces:**
- Produces: `metadata_pool.apply_variant_and_metadata(..., params: dict | None = None) -> dict`

- [ ] **Step 1: Write failing preselected params test**

Append to `tests/test_forge_concurrency.py`:

```python
def test_apply_variant_and_metadata_uses_preselected_params(monkeypatch):
    params = {
        "crop_px": 4,
        "mirror": True,
        "zoom_pct": 1.0,
        "rotate_deg": 0.0,
        "brightness": 0.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "gamma": 1.0,
        "noise": 0,
        "speed": 1.0,
        "trim_start_ms": 0,
        "trim_end_ms": 0,
    }
    commands = []
    monkeypatch.setattr(metadata_pool, "_probe_video_info", lambda _path: (1080, 1920, 1.0, False))
    monkeypatch.setattr(
        metadata_pool,
        "generate_variant_params",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("random generator should not run")),
    )

    def run(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(metadata_pool.subprocess, "run", run)

    returned = metadata_pool.apply_variant_and_metadata(
        "source.mp4",
        "output.mp4",
        {
            "iphone_model": "iPhone 15",
            "lat": "+25.7617",
            "lon": "-080.1918",
            "ios_version": "18.0",
            "carrier": "T-Mobile",
        },
        params=params,
    )

    assert returned == params
    assert "hflip" in ",".join(commands[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_forge_concurrency.py::test_apply_variant_and_metadata_uses_preselected_params -v
```

Expected: FAIL because `apply_variant_and_metadata` does not accept `params`.

- [ ] **Step 3: Add optional `params` argument**

In `metadata_pool.py`, update signature:

```python
def apply_variant_and_metadata(
    input_path: str,
    output_path: str,
    meta: dict,
    rng: "random.Random | None" = None,
    enabled: "dict | None" = None,
    strength: float = 1.0,
    overrides: "dict | None" = None,
    ffmpeg_threads: "int | None" = None,
    params: "dict | None" = None,
) -> dict:
```

Replace:

```python
    params = generate_variant_params(rng, enabled, strength, overrides)
```

With:

```python
    params = dict(params) if params is not None else generate_variant_params(rng, enabled, strength, overrides)
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
pytest tests/test_forge_concurrency.py tests/test_forge_variant_reservations.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add metadata_pool.py tests/test_forge_concurrency.py
git commit -m "feat(forge): render preselected variants"
```

---

### Task 5: Forge Uses Vault Reservations

**Files:**
- Modify: `gui_premium_v7.py`
- Test: `tests/test_forge_variant_reservations.py`

**Interfaces:**
- Consumes: `vault.reserve_forge_variants(...) -> dict`
- Consumes: `metadata_pool.apply_variant_and_metadata(..., params=...) -> dict`
- Produces: `_build_forge_copy_jobs(...) -> dict`
- Produces: `_save_forge_transform_log(..., vault_asset_id=None, variant_signature=None) -> int`

- [ ] **Step 1: Write failing copy-job planning test**

Append to `tests/test_forge_variant_reservations.py`:

```python
def test_build_forge_copy_jobs_skips_exhausted_vault_inputs(tmp_path, monkeypatch):
    import gui_premium_v7

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    source.write_bytes(b"in")
    asset = db.upsert_vault_asset(str(source))

    def reserve(_db, vault_asset, _process_kind, count, *_args, **_kwargs):
        assert vault_asset["id"] == asset["id"]
        return {
            "asset": vault_asset,
            "reserved": [{"params": dict(BASE_PARAMS), "signature": "sig-1"}],
            "shortfall": count - 1,
            "message": "No quedan variantes nuevas para input.mp4",
        }

    monkeypatch.setattr(gui_premium_v7, "reserve_forge_variants", reserve)

    plan = gui_premium_v7._build_forge_copy_jobs(
        db=db,
        vault_assets=[asset],
        copies=2,
        output_dir=str(tmp_path / "videos_finales" / "TANDA"),
        process_kind="forge",
        fx_enabled={"crop": True},
        forge_strength=1.0,
        forge_overrides=None,
    )

    assert len(plan["jobs"]) == 1
    assert plan["jobs"][0]["variant_signature"] == "sig-1"
    assert plan["skipped"][0]["shortfall"] == 1
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_forge_variant_reservations.py::test_build_forge_copy_jobs_skips_exhausted_vault_inputs -v
```

Expected: FAIL because `_build_forge_copy_jobs` does not exist.

- [ ] **Step 3: Import reservation helper and extend save helper**

Near imports in `gui_premium_v7.py`, add:

```python
from vault import reserve_forge_variants
```

Update `_save_forge_transform_log` signature:

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
    vault_asset_id=None,
    variant_signature=None,
):
```

Pass new arguments to `db.save_video_transform_log(...)`:

```python
        vault_asset_id=vault_asset_id,
        variant_signature=variant_signature,
```

- [ ] **Step 4: Add `_build_forge_copy_jobs`**

Add near `_save_forge_transform_log`:

```python
def _build_forge_copy_jobs(
    db,
    vault_assets,
    copies,
    output_dir,
    process_kind,
    fx_enabled,
    forge_strength,
    forge_overrides,
):
    import re
    import metadata_pool

    os.makedirs(output_dir, exist_ok=True)
    jobs = []
    skipped = []
    reserved_max = {}
    for asset in vault_assets:
        vid_path = asset["source_path"]
        filename = os.path.basename(vid_path)
        base, ext = os.path.splitext(filename)
        vid_id = forge_output_id_from_filename(filename)
        vh = metadata_pool.get_video_hash(vid_path)
        reservation = reserve_forge_variants(
            db, asset, process_kind, copies, fx_enabled, forge_strength, forge_overrides
        )
        if reservation["shortfall"]:
            skipped.append({
                "asset": asset,
                "shortfall": reservation["shortfall"],
                "message": reservation["message"],
            })
        existing_max = 0
        copy_pattern = re.compile(rf"^{re.escape(vid_id)}__c(\d+){re.escape(ext)}$")
        if os.path.isdir(output_dir):
            for fname in os.listdir(output_dir):
                match = copy_pattern.match(fname)
                if match:
                    existing_max = max(existing_max, int(match.group(1)))
        reservation_key = (vid_id, ext)
        existing_max = max(existing_max, reserved_max.get(reservation_key, 0))
        for offset, reserved in enumerate(reservation["reserved"], start=1):
            copy_num = existing_max + offset
            out_name = f"{vid_id}__c{copy_num:02d}{ext}"
            out_path = os.path.join(output_dir, out_name)
            jobs.append({
                "vault_asset": asset,
                "vid_path": vid_path,
                "filename": filename,
                "out_name": out_name,
                "out_path": out_path,
                "video_hash": vh,
                "variant_params": reserved["params"],
                "variant_signature": reserved["signature"],
            })
        reserved_max[reservation_key] = existing_max + len(reservation["reserved"])
    return {"jobs": jobs, "skipped": skipped}
```

- [ ] **Step 5: Run focused planning test**

Run:

```powershell
pytest tests/test_forge_variant_reservations.py::test_build_forge_copy_jobs_skips_exhausted_vault_inputs -v
```

Expected: PASS.

- [ ] **Step 6: Adapt `forge_process` to use planned jobs**

In `forge_process.task`, replace the current `copy_jobs` construction with:

```python
            vault_assets = getattr(self, "forge_vault_assets", [])
            process_kind = "forge_trial" if is_trial_tanda else "forge"
            plan = _build_forge_copy_jobs(
                db_ref, vault_assets, copies, output_dir, process_kind,
                fx_enabled, forge_strength, forge_overrides,
            )
            copy_jobs = []
            for job in plan["jobs"]:
                meta = meta_list[len(copy_jobs)]
                fingerprint = {"video_hash": f"{job['video_hash']}_{len(copy_jobs) + 1}", **meta}
                job["meta"] = meta
                job["fingerprint"] = fingerprint
                copy_jobs.append(job)
```

Update `process_copy`:

```python
            def process_copy(copy_job):
                try:
                    params = metadata_pool.apply_variant_and_metadata(
                        copy_job["vid_path"], copy_job["out_path"], copy_job["meta"],
                        enabled=fx_enabled, strength=forge_strength,
                        overrides=forge_overrides,
                        ffmpeg_threads=performance.ffmpeg_threads,
                        params=copy_job["variant_params"],
                    )
                except Exception as error:
                    raise RuntimeError(f"Forge fallo en '{copy_job['filename']}': {error}") from error
                copy_job["params"] = params
                return copy_job
```

Update the completed loop:

```python
            for job in completed:
                db_ref.save_forge_video(tanda_name, job["filename"], job["out_name"], job["video_hash"])
                _save_forge_transform_log(
                    db_ref,
                    process_kind=process_kind,
                    source_path=job["vid_path"],
                    output_path=job["out_path"],
                    tanda_name=tanda_name,
                    source_identity=job["fingerprint"].get("video_hash", ""),
                    params=job["params"],
                    meta=job["meta"],
                    vault_asset_id=job["vault_asset"]["id"],
                    variant_signature=job["variant_signature"],
                )
```

Update generated count/message to use `len(completed)` and include skipped messages.

- [ ] **Step 7: Run focused tests**

Run:

```powershell
pytest tests/test_forge_variant_reservations.py tests/test_video_transform_logs.py tests/test_forge_concurrency.py -v
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit**

```powershell
git add gui_premium_v7.py tests/test_forge_variant_reservations.py
git commit -m "feat(forge): use vault variant reservations"
```

---

### Task 6: Vault GUI Screen and Forge Picker

**Files:**
- Modify: `gui_premium_v7.py`
- Test: manual GUI smoke plus focused pytest from prior tasks

**Interfaces:**
- Consumes: `DatabaseManager.upsert_vault_asset(...) -> dict`
- Consumes: `DatabaseManager.list_vault_assets(search="") -> list[dict]`
- Consumes: `DatabaseManager.list_vault_asset_history(asset_id, limit=200) -> list[dict]`
- Produces: `InstagramAutoPro._build_vault_frame(self) -> None`
- Produces: `InstagramAutoPro.refresh_vault_table(self) -> None`
- Produces: `InstagramAutoPro.forge_select_from_vault(self) -> None`

- [ ] **Step 1: Add Boveda frame and navigation**

In `_build_sidebar`, add under `Contenido`:

```python
("Boveda", [("Boveda", "Boveda")])
```

Use the existing grouped list shape by changing the `Contenido` list to include:

```python
("Boveda", "Boveda"), ("Forge", "Forge"), ("Tandas", "Tandas")
```

In `_build_content_area`, add `"Boveda"` to the frame names and call:

```python
        self._build_vault_frame()
```

- [ ] **Step 2: Add Vault screen**

Add method:

```python
    def _build_vault_frame(self):
        f = self._frames["Boveda"]
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        PageHeader(
            f, kicker="CONTENIDO", title="Boveda",
            subtitle="Historial de inputs y outputs usados por Forge."
        ).grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 8))
        body = ctk.CTkFrame(f, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.vault_search_var = tk.StringVar(value="")
        self.vault_search_var.trace_add("write", lambda *_: self.refresh_vault_table())
        ctk.CTkEntry(actions, textvariable=self.vault_search_var, placeholder_text="Buscar en boveda").grid(row=0, column=0, sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        PrimaryButton(actions, text="Importar videos", command=self.vault_import_files).grid(row=0, column=1, padx=(8, 0))
        columns = ("name", "hash", "type", "outputs", "path")
        self.vault_tree = ttk.Treeview(body, columns=columns, show="headings", style="Premium.Treeview")
        for col, label in [("name", "Nombre"), ("hash", "Hash"), ("type", "Tipo"), ("outputs", "Outputs"), ("path", "Ruta")]:
            self.vault_tree.heading(col, text=label)
        self.vault_tree.column("name", width=220)
        self.vault_tree.column("hash", width=90)
        self.vault_tree.column("type", width=70)
        self.vault_tree.column("outputs", width=70)
        self.vault_tree.column("path", width=520)
        self.vault_tree.grid(row=1, column=0, sticky="nsew")
        self.vault_tree.bind("<<TreeviewSelect>>", lambda _event: self.refresh_vault_history())
        self.vault_history = tk.Text(body, height=8, bg=self.themed(BG_INPUT), fg=self.themed(TEXT_BODY))
        self.vault_history.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.refresh_vault_table()
```

- [ ] **Step 3: Add Vault import/list/history methods**

Add:

```python
    def vault_import_files(self):
        paths = filedialog.askopenfilenames(
            title="Importar a Boveda",
            filetypes=[("Videos", "*.mp4 *.mov *.avi *.mkv"), ("Todos los archivos", "*.*")]
        )
        for path in paths:
            self.db.upsert_vault_asset(path)
        self.refresh_vault_table()

    def refresh_vault_table(self):
        if not hasattr(self, "vault_tree"):
            return
        for item in self.vault_tree.get_children():
            self.vault_tree.delete(item)
        for row in self.db.list_vault_assets(getattr(self, "vault_search_var", tk.StringVar()).get()):
            history_count = len(self.db.list_vault_asset_history(row["id"], limit=1000))
            self.vault_tree.insert(
                "", tk.END, iid=str(row["id"]),
                values=(row["display_name"], row["asset_hash"][:10], row["media_type"], history_count, row["source_path"])
            )

    def refresh_vault_history(self):
        selection = self.vault_tree.selection()
        if not selection:
            return
        asset_id = int(selection[0])
        rows = self.db.list_vault_asset_history(asset_id)
        self.vault_history.delete("1.0", tk.END)
        for row in rows:
            self.vault_history.insert(
                tk.END,
                f"{row['created_at']} | {row['process_kind']} | {row['output_filename']} | {row.get('variant_signature') or ''}\n"
            )
```

- [ ] **Step 4: Add Forge picker**

In `_build_forge_frame`, initialize:

```python
        self.forge_vault_assets = []
```

Add button near existing add/remove controls:

```python
GhostButton(top, text="Seleccionar desde Boveda", command=self.forge_select_from_vault).grid(row=0, column=0, padx=(0, 8))
```

Add method:

```python
    def forge_select_from_vault(self):
        assets = self.db.list_vault_assets()
        if not assets:
            messagebox.showwarning("Boveda", "Primero importa videos en la Boveda.", parent=self)
            return
        win = ctk.CTkToplevel(self)
        win.title("Seleccionar desde Boveda")
        win.geometry("820x520")
        win.transient(self)
        win.grab_set()
        tree = ttk.Treeview(win, columns=("name", "hash", "path"), show="headings", style="Premium.Treeview", selectmode="extended")
        for col, label in [("name", "Nombre"), ("hash", "Hash"), ("path", "Ruta")]:
            tree.heading(col, text=label)
        tree.pack(fill="both", expand=True, padx=14, pady=14)
        for asset in assets:
            tree.insert("", tk.END, iid=str(asset["id"]), values=(asset["display_name"], asset["asset_hash"][:10], asset["source_path"]))

        def accept():
            selected = [self.db.get_vault_asset(int(item)) for item in tree.selection()]
            selected = [asset for asset in selected if asset]
            self.forge_vault_assets = selected
            self.forge_video_paths = [asset["source_path"] for asset in selected]
            self.forge_lst.delete(0, tk.END)
            for asset in selected:
                self.forge_lst.insert(tk.END, asset["display_name"])
            self.forge_lbl_count.configure(text=f"{len(selected)} videos")
            win.destroy()

        PrimaryButton(win, text="Usar seleccionados", command=accept).pack(pady=(0, 14))
```

- [ ] **Step 5: Guard normal Forge processing**

At the start of `forge_process`, after checking `self.forge_video_paths`, add:

```python
        if not getattr(self, "forge_vault_assets", None):
            return messagebox.showwarning("Boveda", "Selecciona los inputs desde la Boveda antes de procesar.")
```

- [ ] **Step 6: Run focused automated tests**

Run:

```powershell
pytest tests/test_vault_assets.py tests/test_forge_variant_reservations.py tests/test_video_transform_logs.py tests/test_forge_concurrency.py -v
```

Expected: all selected tests pass.

- [ ] **Step 7: Manual GUI smoke**

Run:

```powershell
python launcher.py
```

Manual checks:

- Sidebar shows `Boveda` under Contenido.
- Boveda imports a small `.mp4`.
- Forge can select that imported input from Boveda.
- Forge blocks processing when no Vault input is selected.
- No Telegram send is triggered.

- [ ] **Step 8: Commit**

```powershell
git add gui_premium_v7.py
git commit -m "feat(gui): add vault screen and forge picker"
```

---

### Task 7: Final Verification

**Files:**
- No code changes unless verification finds a bug.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
pytest tests/test_vault_assets.py tests/test_forge_variant_reservations.py tests/test_video_transform_logs.py tests/test_forge_concurrency.py -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Run import/compile check**

Run:

```powershell
python -m compileall database.py vault.py metadata_pool.py gui_premium_v7.py -q
```

Expected: exit code `0`.

- [ ] **Step 3: Inspect release-sensitive diff**

Run:

```powershell
git diff --stat HEAD~7..HEAD
git status --short
```

Expected:

- Only intentional source/test/docs files changed.
- Existing local DBs, backups, Telegram state, calendars, videos, tokens, and release download checks remain untracked and unstaged.

- [ ] **Step 4: Commit verification note if needed**

Only if a test report doc is added:

```powershell
git add docs/test-reports/<report>.md
git commit -m "docs: record vault forge verification"
```

Otherwise do not create a documentation-only commit.

---

## Self-Review

- Spec coverage: Tasks 1-2 cover Vault data and transform linkage; Tasks 3-5 cover unique Forge variants and exhaustion; Task 6 covers GUI; Task 7 covers verification and release constraints.
- Placeholder scan: no TBD/TODO/fill-in steps remain.
- Type consistency: `vault_asset_id`, `variant_signature`, `forge_variant_signature`, `reserve_forge_variants`, and `params` signatures are defined before downstream tasks consume them.
