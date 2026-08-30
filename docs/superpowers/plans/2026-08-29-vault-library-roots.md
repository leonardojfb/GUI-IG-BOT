# Vault Library and Content Roots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Vault from a Forge input registry into a library with logical collections, reusable content roots, and asset-level provenance.

**Architecture:** Start from `vault-forge-history`, where `vault_assets`, Forge selection, and variant reservation already exist. Extend `DatabaseManager` with root, collection, and asset-link records; make Boveda a library UI over those records. A path remains a location, while the Vault hash and database ID remain the asset identity.

**Tech Stack:** Python 3, SQLite via `database.py`, CustomTkinter/ttk in `gui_premium_v7.py`, `pytest`.

## Global Constraints

- Create the implementation branch from `vault-forge-history`; do not recreate or regress its Forge reservation behavior.
- Do not copy media files into a new Vault directory.
- Existing Video Editor and Tandas loose-file workflows remain valid in this delivery.
- No Instagram metrics, performance scores, or inferred publication state.
- Normal releases exclude `organizador.db`, media, calendars, account history, and Telegram state.
- Preserve SQLite migrations for an existing Vault/Forge database and run focused tests before every commit.

---

## File Structure

- `database.py`: schema migrations and library repositories.
- `gui_premium_v7.py`: Biblioteca controls, root/collection assignment, and asset detail.
- `tests/test_content_roots.py`: schema and repository behavior.
- `tests/test_vault_assets.py`: output asset and graph coverage.
- `tests/test_vault_gui.py`: Biblioteca GUI coverage.

### Task 1: Persist collections and content roots

**Files:**
- Modify: `database.py:112-158`, `database.py:730-804`
- Create: `tests/test_content_roots.py`

**Interfaces:**
- Produces `create_vault_collection(name) -> dict`, `list_vault_collections() -> list[dict]`, and `list_collection_assets(collection_id) -> list[dict]`.
- Produces `create_content_root(name, tags=None, notes="") -> dict`, `get_content_root(root_id) -> dict | None`, `get_content_root_by_name(name) -> dict | None`, and `list_content_roots(search="", status="active") -> list[dict]`.
- Produces `add_asset_to_collection(collection_id, asset_id)`, `add_asset_to_content_root(root_id, asset_id, role)`, `list_root_assets(root_id)`, and `list_asset_roots(asset_id)`.

- [ ] **Step 1: Write the failing repository test**

~~~python
def test_root_and_collection_keep_one_asset_without_duplicate_membership(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    asset = db.upsert_vault_asset(source)

    collection = db.create_vault_collection("Ideas agosto")
    root = db.create_content_root("Late night 01", tags=["night"], notes="source set")
    db.add_asset_to_collection(collection["id"], asset["id"])
    db.add_asset_to_collection(collection["id"], asset["id"])
    db.add_asset_to_content_root(root["id"], asset["id"], "original_video")
    db.add_asset_to_content_root(root["id"], asset["id"], "original_video")

    assert [row["display_name"] for row in db.list_root_assets(root["id"])] == ["source.mp4"]
    assert db.list_asset_roots(asset["id"])[0]["name"] == "Late night 01"
    assert db.list_collection_assets(collection["id"])[0]["id"] == asset["id"]
~~~

- [ ] **Step 2: Run the test to verify the API is absent**

Run: `pytest tests/test_content_roots.py::test_root_and_collection_keep_one_asset_without_duplicate_membership -v`

Expected: FAIL with `AttributeError` for `create_vault_collection`.

- [ ] **Step 3: Add schema, indexes, and repository methods**

Add these tables to `SCHEMA` after `vault_assets`; call a dedicated `_ensure_content_library_indexes()` from `initialize()` after `_ensure_vault_indexes()`.

~~~sql
CREATE TABLE IF NOT EXISTS vault_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS vault_collection_assets (
    collection_id INTEGER NOT NULL,
    vault_asset_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (collection_id, vault_asset_id)
);
CREATE TABLE IF NOT EXISTS content_roots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'archived')),
    tags_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at TEXT
);
CREATE TABLE IF NOT EXISTS content_root_assets (
    content_root_id INTEGER NOT NULL,
    vault_asset_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN (
        'original_video', 'original_image', 'overlay', 'p1', 'p2',
        'forge_output', 'edited_output', 'tanda_output', 'reference'
    )),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (content_root_id, vault_asset_id, role)
);
~~~

Implement root insertion with sorted JSON and return the inserted row:

~~~python
def create_content_root(self, name, tags=None, notes=""):
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValueError("El nombre de la familia es obligatorio.")
    self.conn.execute(
        "INSERT INTO content_roots (name, tags_json, notes) VALUES (?, ?, ?)",
        (clean_name, json.dumps(list(tags or []), ensure_ascii=False, sort_keys=True), str(notes or "")),
    )
    self.conn.commit()
    return self.get_content_root_by_name(clean_name)
~~~

Use `INSERT OR IGNORE` for membership methods. `list_content_roots` returns `asset_count` and `output_count`, filters name/tags case-insensitively, and supports only `active`, `archived`, or `all`.

- [ ] **Step 4: Run root and migration tests**

Run: `pytest tests/test_content_roots.py tests/test_vault_assets.py -v`

Expected: PASS, including the existing Vault migration test.

- [ ] **Step 5: Commit the persistence layer**

~~~powershell
git add database.py tests/test_content_roots.py tests/test_vault_assets.py
git commit -m "feat(vault): add library roots and collections"
~~~

### Task 2: Register output assets and explicit parent-child links

**Files:**
- Modify: `database.py:654-706`, `database.py:730-804`
- Modify: `tests/test_vault_assets.py`

**Interfaces:**
- Produces `link_vault_assets(parent_asset_id, child_asset_id, relation_kind, transform_log_id=None)`.
- Produces `register_transform_output(transform_log_id, output_path, parent_links, root_ids=None) -> dict`.
- Produces `list_vault_asset_links(asset_id) -> list[dict]`.
- `parent_links` is `list[tuple[int, str]]`, where relation kind is `source`, `overlay`, `p1`, `p2`, or `derived`.

- [ ] **Step 1: Write the failing asset-graph test**

~~~python
def test_register_transform_output_links_two_parents_and_a_root(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    p1, p2, out = [tmp_path / name for name in ("p1.mp4", "p2.mp4", "mix.mp4")]
    p1.write_bytes(b"p1"); p2.write_bytes(b"p2"); out.write_bytes(b"mix")
    a1, a2 = db.upsert_vault_asset(p1), db.upsert_vault_asset(p2)
    root = db.create_content_root("Mix family")
    log_id = db.save_video_transform_log("tandas", p1, out, {"p1_path": str(p1), "p2_path": str(p2)})

    output = db.register_transform_output(log_id, out, [(a1["id"], "p1"), (a2["id"], "p2")], [root["id"]])

    assert {link["relation_kind"] for link in db.list_vault_asset_links(output["id"])} == {"p1", "p2"}
    assert db.list_root_assets(root["id"])[0]["role"] == "tanda_output"
~~~

- [ ] **Step 2: Run the test to verify the graph API is absent**

Run: `pytest tests/test_vault_assets.py::test_register_transform_output_links_two_parents_and_a_root -v`

Expected: FAIL with `AttributeError` for `register_transform_output`.

- [ ] **Step 3: Add transform-output persistence**

Add `output_vault_asset_id INTEGER` to `video_transform_logs` in `SCHEMA`, append it through `_migrate_columns()`, and include it in `save_video_transform_log()` and `list_video_transform_logs()`. Add this table:

~~~sql
CREATE TABLE IF NOT EXISTS vault_asset_links (
    parent_asset_id INTEGER NOT NULL,
    child_asset_id INTEGER NOT NULL,
    relation_kind TEXT NOT NULL CHECK(relation_kind IN ('source', 'overlay', 'p1', 'p2', 'derived')),
    transform_log_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (parent_asset_id, child_asset_id, relation_kind, transform_log_id)
);
~~~

Implement `register_transform_output()` in one transaction: call `upsert_vault_asset(output_path)`, update the log's `output_vault_asset_id`, insert parent links, and add the output to supplied roots with the role mapped from process kind. Reject an unknown log and a self-parent link with Spanish `ValueError`.

- [ ] **Step 4: Run graph and Forge regression tests**

Run: `pytest tests/test_vault_assets.py tests/test_forge_variant_reservations.py tests/test_forge_concurrency.py -v`

Expected: PASS; Forge signatures and reservations are unchanged.

- [ ] **Step 5: Commit output provenance**

~~~powershell
git add database.py tests/test_vault_assets.py
git commit -m "feat(vault): link transform outputs to source assets"
~~~

### Task 3: Replace the narrow Vault page with Biblioteca

**Files:**
- Modify: `gui_premium_v7.py:_build_vault_frame`, `vault_import_files`, `refresh_vault_table`, `refresh_vault_history`
- Modify: `tests/test_vault_gui.py`

**Interfaces:**
- Produces `vault_create_root()`, `vault_assign_selected_asset()`, `refresh_vault_roots()`, and `refresh_vault_asset_detail()` on `InstagramAutoPro`.
- Consumes Task 1 and Task 2 APIs only; the GUI does not execute SQL directly.

- [ ] **Step 1: Write the failing GUI contract test**

~~~python
def test_biblioteca_exposes_import_roots_collections_and_asset_detail():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    for token in (
        'title="Biblioteca"', "vault_create_root", "vault_assign_selected_asset",
        "refresh_vault_roots", "list_content_roots", "list_collection_assets",
    ):
        assert token in source
~~~

- [ ] **Step 2: Run the test to verify the old screen fails**

Run: `pytest tests/test_vault_gui.py::test_biblioteca_exposes_import_roots_collections_and_asset_detail -v`

Expected: FAIL because the current screen only describes Forge input/output history.

- [ ] **Step 3: Implement Biblioteca layout and actions**

Keep the `Boveda` frame and navigation key so existing links remain valid. Replace the body with a left root/collection list, a central asset `Treeview`, and a right detail panel; only the detail panel can scroll.

Import accepts existing video and image extensions without moving files:

~~~python
def vault_import_files(self):
    paths = filedialog.askopenfilenames(
        title="Importar a Biblioteca",
        filetypes=[("Medios", "*.mp4 *.mov *.avi *.mkv *.png *.jpg *.jpeg *.webp"), ("Todos", "*.*")],
    )
    for path in paths:
        self.db.upsert_vault_asset(path)
    self.refresh_vault_table()
    self.refresh_vault_roots()
~~~

`vault_create_root()` requires a nonempty name. `vault_assign_selected_asset()` requires one selected asset, one selected root, and a schema role. Its confirmation says `Agregar a familia`, never `Mover archivo`. Detail shows path, hash, media type, collections, roots/roles, parent links, child links, and recent transforms. Do not add content scores or publication totals.

- [ ] **Step 4: Run Biblioteca and Forge UI tests**

Run: `pytest tests/test_vault_gui.py tests/test_forge_ui.py -v`

Expected: PASS; `Seleccionar desde Boveda` remains available in Forge.

- [ ] **Step 5: Commit Biblioteca UI**

~~~powershell
git add gui_premium_v7.py tests/test_vault_gui.py
git commit -m "feat(vault): organize assets through Biblioteca roots"
~~~

### Task 4: Validate on the real GUI shell

**Files:**
- Modify: none unless a verification failure identifies a scoped defect.
- Test: `tests/test_content_roots.py`, `tests/test_vault_assets.py`, `tests/test_vault_gui.py`, Forge reservation suites.

- [ ] **Step 1: Run focused automated verification**

Run: `pytest tests/test_content_roots.py tests/test_vault_assets.py tests/test_vault_gui.py tests/test_forge_variant_reservations.py tests/test_forge_concurrency.py -v`

Expected: PASS.

- [ ] **Step 2: Compile touched runtime modules**

Run: `py -m compileall database.py vault.py gui_premium_v7.py -q`

Expected: exit code `0`.

- [ ] **Step 3: Perform Windows GUI smoke**

Run: `py launcher.py`

Expected: Biblioteca imports one video and one image without copying them, creates a root, assigns both roles, and Forge still selects the video from Boveda. Verify at supported Windows DPI/logical resolutions.

- [ ] **Step 4: Commit only a scoped verification fix when required**

~~~powershell
git add database.py vault.py gui_premium_v7.py tests
git commit -m "fix(vault): address Biblioteca verification finding"
~~~

Do not create this commit when verification passes unchanged.
