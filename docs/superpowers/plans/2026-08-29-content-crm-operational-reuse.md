# Content CRM and Safe Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide CRM views by content root and account, then let an operator reuse eligible content through existing Logistics with explicit conflict explanations.

**Architecture:** This plan depends on the completed Vault library and production/logistics lineage plans. `content_crm.py` is a query-and-policy layer over roots, asset links, operational uses, accounts, and manifest entries. The GUI consumes it for content and account views; eligibility never lives inside widgets and the CRM never fabricates performance data.

**Tech Stack:** Python 3, SQLite, CustomTkinter/ttk, existing `Organizador.py` and manifest, `pytest`.

## Global Constraints

- Implement after `content_roots`, `content_account_uses`, and `vault_usage.py` exist.
- CRM state is operational only: no views, likes, revenue, conversion, winner, or score fields.
- Reuse cannot overwrite calendar entries, bypass existing anti-repeat behavior, or write directly to Telegram.
- An account is eligible only when it has no active same-root use and no active same-asset/day/slot collision.
- Every excluded account has a visible, concrete reason.
- Preserve selected-account scope, Trial/normal `delivery_kind`, and manifest behavior.

---

## File Structure

- `content_crm.py`: read models, eligibility policy, and reuse request.
- `database.py`: focused read helpers; no presentation formatting.
- `gui_premium_v7.py`: Content CRM frame, root/account tables, detail drawer, and reuse modal.
- `Organizador.py`: narrow adapter to schedule approved reuse with current allocation rules.
- `tests/test_content_crm.py`: root/account summaries and conflicts.
- `tests/test_content_crm_gui.py`: screen registration and UI action contracts.
- `tests/test_logistica_por_cuentas_e2e.py`: reuse scheduling regression.

### Task 1: Build deterministic CRM queries and eligibility

**Files:**
- Create: `content_crm.py`
- Modify: `database.py`
- Create: `tests/test_content_crm.py`

**Interfaces:**
- Produces `list_root_cards(db, search="", account_id=None, include_archived=False) -> list[dict]`.
- Produces `list_account_content(db, account_id) -> list[dict]`.
- Produces `evaluate_reuse(db, root_id, account_ids, delivery_kind="normal") -> {"eligible": list[dict], "excluded": list[dict]}`.
- Exclusion reasons are `already_scheduled_root`, `already_sent_root`, `same_asset_scheduled`, `missing_usable_output`, or `wrong_delivery_kind`.

- [ ] **Step 1: Write failing root and reuse policy tests**

~~~python
def seeded_crm_db(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    db.conn.executemany(
        "INSERT INTO virtual_accounts (username, account_type) VALUES (?, ?)",
        [("used", "promo"), ("free", "promo")],
    )
    db.conn.commit()
    return db

def test_reuse_excludes_active_root_use_but_allows_unused_account(tmp_path):
    db = seeded_crm_db(tmp_path)
    root_id = db.create_content_root("Night set")["id"]
    db.upsert_content_account_use({
        "calendar_entry_key": "existing", "content_root_id": root_id, "vault_asset_id": 12,
        "account_id": 1, "username": "used", "delivery_kind": "normal", "tanda_name": "T1",
        "transform_log_id": None, "day": 1, "slot": 1, "state": "scheduled",
    })

    decision = evaluate_reuse(db, root_id, [1, 2])

    assert decision["eligible"] == [{"account_id": 2, "username": "free"}]
    assert decision["excluded"] == [{
        "account_id": 1, "username": "used", "reason": "already_scheduled_root"
    }]
~~~

Add a root-card test proving `sent_telegram` is history, `failed` is not successful use, and no metric field is returned.

- [ ] **Step 2: Run the tests to verify the service is absent**

Run: `pytest tests/test_content_crm.py -v`

Expected: FAIL with `ModuleNotFoundError` for `content_crm`.

- [ ] **Step 3: Implement query and policy boundaries**

Create `content_crm.py` with explicit state sets:

~~~python
ACTIVE_USE_STATES = ("assigned", "scheduled", "sent_telegram", "published_confirmed")
SUCCESSFUL_HISTORY_STATES = ("sent_telegram", "published_confirmed")

def evaluate_reuse(db, root_id, account_ids, delivery_kind="normal"):
    root = db.get_content_root(root_id)
    if not root or root["status"] != "active":
        raise ValueError("La familia seleccionada no esta disponible.")
    return _evaluate_accounts(db, root, [int(value) for value in account_ids], delivery_kind)
~~~

Add repositories returning dictionaries: `list_root_operational_summary`, `list_root_usable_outputs`, `list_active_uses_for_root`, `list_active_uses_for_assets`, and `list_accounts_by_ids`. Usable outputs must exist on disk and belong to the root with role `forge_output`, `edited_output`, or `tanda_output`.

Evaluate account IDs in caller order. Reject delivery kind, active root use, same-output collision, then missing usable output. Do not inspect filenames or calculate an arbitrary fatigue score.

- [ ] **Step 4: Run CRM policy tests**

Run: `pytest tests/test_content_crm.py tests/test_vault_usage.py -v`

Expected: PASS; calendar state input remains idempotent.

- [ ] **Step 5: Commit CRM service**

~~~powershell
git add content_crm.py database.py tests/test_content_crm.py
git commit -m "feat(crm): expose operational content and reuse eligibility"
~~~

### Task 2: Add the CRM de contenido screen and details

**Files:**
- Modify: `gui_premium_v7.py` navigation setup and frame builders
- Create: `tests/test_content_crm_gui.py`

**Interfaces:**
- Produces `_build_content_crm_frame()`, `refresh_content_crm_roots()`, `refresh_content_crm_accounts()`, and `show_content_crm_detail(root_id)` on `InstagramAutoPro`.
- Consumes only `content_crm.list_root_cards`, `list_account_content`, and `evaluate_reuse`.

- [ ] **Step 1: Write the failing GUI contract test**

~~~python
def test_navigation_registers_separate_content_crm_without_removing_biblioteca():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    assert '("CRM de contenido", "ContentCRM")' in source
    assert "self._build_content_crm_frame()" in source
    assert "def refresh_content_crm_roots(self):" in source
    assert "def show_content_crm_detail(self, root_id):" in source
~~~

- [ ] **Step 2: Run the test to verify the CRM frame is absent**

Run: `pytest tests/test_content_crm_gui.py::test_navigation_registers_separate_content_crm_without_removing_biblioteca -v`

Expected: FAIL because only Boveda currently exists under content.

- [ ] **Step 3: Implement operational root and account views**

Register `ContentCRM` beside `Boveda`, `Forge`, `VideoEditor`, and `Tandas`. Its default root table has columns `Familia`, `Outputs utilizables`, `Programado`, `Enviado`, `Ultimo uso`, and `Accion`. A segmented control switches to account view with `Cuenta`, `Programado`, `Enviado`, `Disponible`, and `Accion`.

`show_content_crm_detail(root_id)` shows sources, usable outputs, account history by state, scheduled entries, and a compact graph chain. Technical parameters stay behind a `Trazabilidad tecnica` disclosure. Visible status labels are `Disponible`, `En produccion`, `Programado`, `Enviado a Telegram`, `Confirmado manualmente`, `Fallido`, `Descartado`, and `Archivado`.

Do not add dashboard cards, view totals, charts, synthetic alerts, or scores. With no roots, the empty state leads to Biblioteca import and classification.

- [ ] **Step 4: Run GUI and service tests**

Run: `pytest tests/test_content_crm_gui.py tests/test_content_crm.py tests/test_vault_gui.py -v`

Expected: PASS; Biblioteca and Forge navigation remain registered.

- [ ] **Step 5: Commit CRM views**

~~~powershell
git add gui_premium_v7.py tests/test_content_crm_gui.py
git commit -m "feat(crm): add operational content and account views"
~~~

### Task 3: Hand off eligible reuse to Logistics

**Files:**
- Modify: `Organizador.py:906-1091`
- Modify: `gui_premium_v7.py`, `content_crm.py`
- Modify: `tests/test_content_crm.py`, `tests/test_logistica_por_cuentas_e2e.py`

**Interfaces:**
- Produces `build_reuse_request(db, root_id, account_ids, delivery_kind="normal") -> dict`.
- Produces `distribute_root_reuse(request) -> str` in `Organizador.py`.
- Request shape is `{"root_id": int, "delivery_kind": "normal", "eligible_account_ids": list[int], "asset_ids": list[int]}`.

- [ ] **Step 1: Write failing reuse-handoff tests**

~~~python
def seed_root_with_tanda_output(db, tmp_path):
    output = tmp_path / "usable.mp4"
    output.write_bytes(b"usable")
    root = db.create_content_root("Reusable root")
    asset = db.upsert_vault_asset(output)
    db.add_asset_to_content_root(root["id"], asset["id"], "tanda_output")
    return root["id"]

def seeded_output_asset_id(db, root_id):
    return db.list_root_assets(root_id)[0]["id"]

def test_reuse_request_contains_only_eligible_accounts_and_real_output_assets(tmp_path):
    db = seeded_crm_db(tmp_path)
    root_id = seed_root_with_tanda_output(db, tmp_path)

    request = build_reuse_request(db, root_id, [1, 2])

    assert request["eligible_account_ids"] == [2]
    assert request["asset_ids"] == [seeded_output_asset_id(db, root_id)]
    assert request["delivery_kind"] == "normal"
~~~

Add an E2E regression calling `distribute_root_reuse` with temporary `videos_finales` and manifest paths. Assert it schedules only eligible accounts, preserves unrelated accounts, and returns exclusions to the caller.

- [ ] **Step 2: Run tests to verify there is no reuse handoff**

Run: `pytest tests/test_content_crm.py::test_reuse_request_contains_only_eligible_accounts_and_real_output_assets tests/test_logistica_por_cuentas_e2e.py -v`

Expected: FAIL because the current distributor accepts tanda/category inputs only.

- [ ] **Step 3: Implement a narrow adapter around existing distribution**

`build_reuse_request` calls `evaluate_reuse`; it raises `ValueError("No hay cuentas elegibles para reutilizar esta familia.")` when none remain. Return the decision with the request so the GUI can show every exclusion.

`distribute_root_reuse` does not call Telegram or copy files. Resolve assets through `get_vault_asset`, create the current `video_items` shape, restrict accounts to `eligible_account_ids`, then follow the existing day/slot, filename, anti-collision, `build_entry`, history, `replace_entries`, and `reconcile_calendar_entries` paths. Extract `_distribute_video_items(...)` only if both existing and reuse callers pass the same data contract.

The reuse modal lists eligible accounts and exclusion reasons before confirmation. It has one command, `Programar reutilizacion`, disabled with zero eligible accounts. Refresh CRM and Logistics after success.

- [ ] **Step 4: Run CRM and Logistics regressions**

Run: `pytest tests/test_content_crm.py tests/test_logistica_por_cuentas_e2e.py tests/test_logistica_negative_cases.py tests/test_calendar_manifest.py -v`

Expected: PASS; unrelated manifest rows remain and selected-account boundaries hold.

- [ ] **Step 5: Commit reuse scheduling**

~~~powershell
git add content_crm.py Organizador.py gui_premium_v7.py tests/test_content_crm.py tests/test_logistica_por_cuentas_e2e.py
git commit -m "feat(crm): schedule eligible content reuse through logistics"
~~~

### Task 4: Verify CRM behavior and release safety

- [ ] **Step 1: Run complete operational regression**

Run: `pytest tests/test_content_roots.py tests/test_vault_assets.py tests/test_vault_usage.py tests/test_content_crm.py tests/test_content_crm_gui.py tests/test_logistica_por_cuentas_e2e.py tests/test_logistica_negative_cases.py tests/test_telegram_single_account_selection.py tests/test_release_package_manifest.py -v`

Expected: PASS without live Telegram or packaged data files.

- [ ] **Step 2: Compile and smoke GUI**

Run: `py -m compileall database.py vault.py vault_usage.py content_crm.py Organizador.py gui_premium_v7.py -q`

Expected: exit code `0`.

Run: `py launcher.py`

Expected: Biblioteca classifies an asset, CRM shows root/account history, reuse explains exclusions before scheduling, and a schedule appears as `Programado`, never as published or performing.

- [ ] **Step 3: Verify package exclusions**

Run: `pytest tests/test_release_package_manifest.py -v`

Expected: PASS; database, media, calendars, and Telegram state are absent from normal package manifests.

- [ ] **Step 4: Commit only a scoped verification correction**

~~~powershell
git add database.py vault.py vault_usage.py content_crm.py Organizador.py gui_premium_v7.py tests
git commit -m "fix(crm): address operational CRM verification finding"
~~~

Do not create this commit when verification passes unchanged.
