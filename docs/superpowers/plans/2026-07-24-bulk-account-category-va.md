# Edición masiva de categoría y VA para cuentas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Permitir actualizar la categoría, el VA o ambos para varias cuentas seleccionadas desde un único diálogo del dashboard.

**Architecture:** La tabla existente conservará su selección múltiple. Un helper puro convertirá las selecciones del diálogo en un diccionario de campos a actualizar; el handler resolverá los IDs seleccionados y llamará una sola vez a `DatabaseManager.bulk_update_accounts`. La UI mostrará advertencias antes de persistir y refrescará solo después de una actualización exitosa.

**Tech Stack:** Python 3, Tkinter/customtkinter, SQLite, unittest/pytest.

## Global Constraints

- Modificar únicamente el flujo de gestión de cuentas del dashboard principal.
- Mantener la selección múltiple existente de la tabla.
- Mantener sin cambios la distribución, programación, OAuth, publicaciones y mensajería.
- Reutilizar `DatabaseManager.bulk_update_accounts(...)` para persistir el cambio masivo.
- La opción `Sin cambios` no se incluirá en el diccionario enviado a la base de datos.
- No usar `git add -A`; incluir en cada commit solo los archivos de esta tarea.

---

### Task 1: Cubrir la construcción de cambios masivos y la persistencia

**Files:**
- Create: `tests/test_bulk_account_edit.py`
- Modify: `gui_premium_v7.py` (helper puro cercano a los helpers de cuentas)
- Modify: `database.py` solo si una prueba demuestra que la operación bulk necesita una corrección

**Interfaces:**
- Produce `build_bulk_account_updates(category: str, assigned_va: str) -> dict` y `resolve_selected_account_ids(accounts: list[dict], usernames: list[str]) -> list[int]` en `gui_premium_v7.py`.
- El helper devuelve `{}` cuando ambos valores son `Sin cambios`, y solo incluye `account_type` y/o `assigned_va` cuando fueron elegidos.
- Consume `DatabaseManager.bulk_update_accounts(account_ids, **updates)` sin cambiar su firma.

- [ ] **Step 1: Write the failing tests**

```python
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import DatabaseManager
from gui_premium_v7 import build_bulk_account_updates


class BulkAccountEditTest(unittest.TestCase):
    def test_builds_only_selected_fields(self):
        self.assertEqual(
            build_bulk_account_updates("PROMO", "Sin cambios"),
            {"account_type": "PROMO"},
        )
        self.assertEqual(
            build_bulk_account_updates("Sin cambios", "Laura"),
            {"assigned_va": "Laura"},
        )
        self.assertEqual(
            build_bulk_account_updates("SUICIDE", "Laura"),
            {"account_type": "SUICIDE", "assigned_va": "Laura"},
        )

    def test_rejects_empty_bulk_update(self):
        self.assertEqual(build_bulk_account_updates("Sin cambios", "Sin cambios"), {})

    def test_updates_only_selected_accounts_and_preserves_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager()
            original_path = db.db_path
            db.close()
            db.db_path = os.path.join(tmp, "accounts.db")
            db.conn = __import__("sqlite3").connect(db.db_path)
            db.conn.row_factory = __import__("sqlite3").Row
            db.initialize()
            db.add_virtual_account("one", "PROMO")
            db.add_virtual_account("two", "PROMO")
            db.add_virtual_account("three", "SUICIDE")
            selected = db.get_all_accounts()[:2]
            db.bulk_update_accounts(
                [account["id"] for account in selected],
                account_type="SUICIDE",
                assigned_va="Laura",
            )
            values = {a["username"]: a for a in db.get_all_accounts()}
            self.assertEqual(values["one"]["account_type"], "SUICIDE")
            self.assertEqual(values["one"]["assigned_va"], "Laura")
            self.assertEqual(values["two"]["account_type"], "SUICIDE")
            self.assertEqual(values["three"]["account_type"], "SUICIDE")
            self.assertEqual(values["three"]["assigned_va"], "Sin Asignar")
            db.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify the helper test fails**

Run: `py -m pytest tests/test_bulk_account_edit.py -q`
Expected: FAIL because `build_bulk_account_updates` does not yet exist.

- [ ] **Step 3: Write the minimal helper implementation**

Add this module-level helper to `gui_premium_v7.py`:

```python
def build_bulk_account_updates(category: str, assigned_va: str) -> dict:
    updates = {}
    if category and category != "Sin cambios":
        updates["account_type"] = category
    if assigned_va and assigned_va != "Sin cambios":
        updates["assigned_va"] = assigned_va
    return updates
```

- [ ] **Step 4: Run the focused tests**

Run: `py -m pytest tests/test_bulk_account_edit.py -q`
Expected: PASS with 3 tests passed.

- [ ] **Step 5: Commit the data/helper test cycle**

```powershell
git add -- tests/test_bulk_account_edit.py gui_premium_v7.py
git commit -m "test: cover bulk account category and VA updates"
```

### Task 2: Replace the two account actions with one bulk-edit dialog

**Files:**
- Modify: `gui_premium_v7.py:1230-1370` (dashboard action bar and account actions)

**Interfaces:**
- Consume `build_bulk_account_updates(category, assigned_va)`.
- Add `bulk_edit_accounts()` as the command for the new action button.
- Preserve `delete_account()` and its extended selection behavior.

- [ ] **Step 1: Add the failing UI-logic tests**

Extend `tests/test_bulk_account_edit.py` with a fake object test for selected username resolution and no-op behavior:

```python
from gui_premium_v7 import resolve_selected_account_ids


class BulkAccountHandlerTest(unittest.TestCase):
    def test_selected_usernames_resolve_to_database_ids(self):
        rows = [
            {"id": 10, "username": "one"},
            {"id": 11, "username": "two"},
            {"id": 12, "username": "three"},
        ]
        self.assertEqual(
            resolve_selected_account_ids(rows, ["one", "three"]),
            [10, 12],
        )

    def test_no_fields_means_no_database_call(self):
        self.assertEqual(build_bulk_account_updates("Sin cambios", "Sin cambios"), {})
```

- [ ] **Step 2: Run the focused tests to verify the new behavior is not yet wired**

Run: `py -m pytest tests/test_bulk_account_edit.py -q`
Expected: FAIL because `resolve_selected_account_ids` does not yet exist.

- [ ] **Step 3: Implement the dialog and handler**

Replace the two dashboard buttons with one:

```python
GhostButton(btn_bar, text="Editar cuentas seleccionadas",
            command=self.bulk_edit_accounts).pack(side="left", padx=(0, 8))
```

Add this helper and implement `bulk_edit_accounts()` with this behavior:

```python
def resolve_selected_account_ids(accounts: list[dict], usernames: list[str]) -> list[int]:
    selected = set(usernames)
    return [account["id"] for account in accounts if account["username"] in selected]
```

1. Read `self.get_selected_accounts()`; warn and return when empty.
2. Open a modal `ctk.CTkToplevel` containing two `CTkOptionMenu` controls whose values are `['Sin cambios'] + categories` and `['Sin cambios', 'Sin Asignar'] + VAs`.
3. Show `len(usernames)` in the dialog text.
4. On confirm, call `build_bulk_account_updates(...)`; warn and keep the dialog open if it returns `{}`.
5. Add the selected category with `self.db.add_category(category)` when it is not `Sin cambios`.
6. Resolve IDs from `self.db.get_all_accounts()` by selected username, then call `self.db.bulk_update_accounts(account_ids, **updates)` once.
7. Destroy the dialog, call `self.refresh_dashboard()`, and show a success message only after the call returns.
8. Catch persistence exceptions, show an error message, and do not refresh or show success.

The existing `change_account_category()` and `reassign_va()` methods may be removed after the new button no longer references them; `delete_account()` remains unchanged.

- [ ] **Step 4: Run focused tests and static checks**

Run: `py -m pytest tests/test_bulk_account_edit.py -q`
Expected: PASS with all focused tests passing.

Run: `py -m compileall database.py gui_premium_v7.py -q`
Expected: exit code 0 with no compilation errors.

- [ ] **Step 5: Commit the UI implementation**

```powershell
git add -- gui_premium_v7.py tests/test_bulk_account_edit.py
git commit -m "feat: edit category and VA for selected accounts"
```

### Task 3: Full verification and manual flow check

**Files:**
- Modify: none unless verification exposes a scoped defect

- [ ] **Step 1: Run the complete test suite**

Run: `py -m pytest tests -q`
Expected: all existing and new tests pass with 0 failures.

- [ ] **Step 2: Check the diff and repository scope**

Run: `git diff HEAD~2..HEAD --check`
Expected: no whitespace errors.

Run: `git show --stat --oneline HEAD~2..HEAD`
Expected: only the new bulk-edit test and the scoped `gui_premium_v7.py` changes appear in the two feature commits; unrelated pre-existing worktree changes remain unstaged.

- [ ] **Step 3: Manually verify the user flow**

Launch the legacy GUI with the repository's normal command. In the dashboard:

1. Select at least two accounts with Ctrl/Shift.
2. Choose only a category and confirm; verify both rows show the new category while their VAs remain unchanged.
3. Select the same or different accounts, choose only a VA and confirm; verify their categories remain unchanged.
4. Select multiple accounts and choose both fields; verify both values change.
5. Open the dialog with no selection and verify the warning.
6. Open it and leave both fields as `Sin cambios`; verify no update occurs.

Record the command used and the observed result in the final handoff.
