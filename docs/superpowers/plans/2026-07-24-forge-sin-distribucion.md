# Forge sin distribución automática Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplificar Forge para que genere y registre tandas, dejando la distribución exclusivamente en Logística.

**Architecture:** Mantener la generación de variantes y el registro de Forge en `gui_premium_v7.py`, eliminando únicamente los widgets y la rama de distribución automática. Agregar una prueba estática de regresión para proteger el contrato de que Forge no contiene esos controles ni llama al distribuidor.

**Tech Stack:** Python, Tkinter/customtkinter, pytest, compilación Python.

## Global Constraints

- Mantener la generación de variantes, el registro de la tanda y los controles restantes de Forge sin cambios.
- Mantener sin cambios la categoría y la distribución de la pestaña Logística.
- No modificar los cambios ajenos ya presentes en el checkout.

---

## Mapa de archivos

- Modify: `gui_premium_v7.py` — construcción de Forge y `forge_process`.
- Create: `tests/test_forge_ui.py` — regresión estática acotada al flujo Forge.

### Task 1: Añadir la regresión que demuestra la ausencia de distribución automática

**Files:**
- Create: `tests/test_forge_ui.py`

- [ ] **Step 1: Escribir la prueba que debe fallar con el código actual**

```python
from pathlib import Path


SOURCE = Path(__file__).parents[1] / "gui_premium_v7.py"


def _forge_source() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("    def _build_forge_frame(self):")
    end = source.index("\n\n# ", start)
    return source[start:end]


def test_forge_does_not_expose_or_execute_automatic_distribution():
    forge = _forge_source()

    assert "Categoría destino:" not in forge
    assert "Distribuir automáticamente al procesar" not in forge
    assert "Organizador.distribute_tanda" not in forge
    assert "distribuir automáticamente" not in forge.lower()
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla por los controles actuales**

Run: `py -m pytest tests/test_forge_ui.py -q`

Expected: FAIL because the current Forge source contains `Categoría destino:` and `Distribuir automáticamente al procesar`.

### Task 2: Retirar los controles y la rama automática de Forge

**Files:**
- Modify: `gui_premium_v7.py:3904-3938` — remove the Forge category row and automatic-distribution toggle while preserving row layout for the remaining controls.
- Modify: `gui_premium_v7.py:4109-4115` — remove Forge category reload handling.
- Modify: `gui_premium_v7.py:4174-4268` — remove category/checkbox reads, category validation, confirmation lines, and `Organizador.distribute_tanda`; retain video generation and DB registration.

- [ ] **Step 1: Eliminar el campo y el checkbox de `_build_forge_frame`**

Remove the `("Categoría destino:", "c_forge_cat", "combo", None)` row and the `forge_dist_var`/`ToggleRow` block. Keep the remaining Forge configuration rows and subsequent effects controls functioning.

- [ ] **Step 2: Eliminar referencias de refresco a la categoría de Forge**

Remove only the `hasattr(self, "c_forge_cat")` branches from `reload_dist_lists` and `_forge_reload_cats` if the helper becomes unused. Do not change category handling for Logística.

- [ ] **Step 3: Eliminar la distribución automática del procesamiento**

In `forge_process`, remove:

```python
category = self.c_forge_cat.get()
auto_dist = self.forge_dist_var.get()
if not category:
    return messagebox.showwarning("⚠️", "Seleccioná una categoría destino.")
```

Remove the category and automatic-distribution lines from the confirmation text, and remove the conditional `Organizador.distribute_tanda(...)` block. The worker must still call `save_forge_video`, `save_metadata_fingerprints`, `add_tanda`, and return the Forge completion message.

- [ ] **Step 4: Ejecutar la prueba de regresión**

Run: `py -m pytest tests/test_forge_ui.py -q`

Expected: PASS.

- [ ] **Step 5: Verificar compilación y alcance**

Run: `py -m py_compile gui_premium_v7.py tests/test_forge_ui.py`

Run: `py -m pytest -q`

Run: `git diff --check`

Expected: compile succeeds, the test suite has zero failures, and the diff has no whitespace errors. Review `git diff -- gui_premium_v7.py tests/test_forge_ui.py` to confirm no Logística code changed.

- [ ] **Step 6: Commit the implementation**

```powershell
git add -- gui_premium_v7.py tests/test_forge_ui.py
git commit -m "fix(forge): remove automatic distribution controls"
```
