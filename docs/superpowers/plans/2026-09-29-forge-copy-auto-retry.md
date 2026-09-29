# Forge Copy Auto Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reintentar cada copia iPhone de Forge hasta cinco veces sin registrar una salida que no pase QC.

**Architecture:** Un helper puro de `gui_premium_v7.py` conserva el contador y el último error. El worker lo usa sólo alrededor de renderizar/validar una copia; el preflight y la identidad de fuente permanecen fuera.

**Tech Stack:** Python, ThreadPoolExecutor, FFmpeg, pytest.

## Global Constraints

- El máximo es exactamente cinco intentos por copia y ejecución.
- Los fallos de preflight, perfil, manifest o hash de la fuente no se reintentan.
- Sólo las copias que superen las validaciones actuales se publican y registran.
- Una copia validada nunca se regenera ni sobrescribe.

---

### Task 1: Helper de reintento

**Files:**
- Modify: `gui_premium_v7.py:42-54`
- Test: `tests/test_forge_iphone_profile.py`

**Interfaces:**
- Produces: `FORGE_COPY_MAX_ATTEMPTS = 5`.
- Produces: `ForgeCopyRetryError(RuntimeError)`.
- Produces: `_run_forge_copy_with_retries(operation, max_attempts=FORGE_COPY_MAX_ATTEMPTS) -> tuple[object, int]`.

- [ ] **Step 1: Write two failing tests**

```python
def test_forge_copy_retry_returns_successful_attempt_number():
    from gui_premium_v7 import _run_forge_copy_with_retries
    attempts = []
    def operation():
        attempts.append(None)
        if len(attempts) < 3:
            raise RuntimeError(f"transient-{len(attempts)}")
        return {"output": "ok"}
    result, attempt_number = _run_forge_copy_with_retries(operation)
    assert result == {"output": "ok"}
    assert attempt_number == 3
    assert len(attempts) == 3

def test_forge_copy_retry_reports_last_error_after_five_attempts():
    from gui_premium_v7 import ForgeCopyRetryError, _run_forge_copy_with_retries
    attempts = []
    def operation():
        attempts.append(None)
        raise RuntimeError(f"failure-{len(attempts)}")
    with pytest.raises(ForgeCopyRetryError, match=r"5 intentos.*failure-5"):
        _run_forge_copy_with_retries(operation)
    assert len(attempts) == 5
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_forge_iphone_profile.py -k "forge_copy_retry" -v`

Expected: import failure because the helper and exception do not exist.

- [ ] **Step 3: Write the minimal helper**

```python
FORGE_COPY_MAX_ATTEMPTS = 5

class ForgeCopyRetryError(RuntimeError):
    pass

def _run_forge_copy_with_retries(operation, max_attempts=FORGE_COPY_MAX_ATTEMPTS):
    errors = []
    for attempt_number in range(1, max_attempts + 1):
        try:
            return operation(), attempt_number
        except Exception as error:
            errors.append(str(error))
    raise ForgeCopyRetryError(
        f"Forge agotó {max_attempts} intentos para la copia; último error: {errors[-1]}"
    )
```

- [ ] **Step 4: Verify GREEN**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_forge_iphone_profile.py -k "forge_copy_retry" -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

Run: `git add gui_premium_v7.py tests/test_forge_iphone_profile.py; git commit -m "feat: retry transient Forge copy failures"`

### Task 2: Worker integration

**Files:**
- Modify: `gui_premium_v7.py:5842-5872`
- Test: `tests/test_forge_iphone_profile.py`

**Interfaces:**
- Consumes: `_run_forge_copy_with_retries`.
- Produces: `params["forge_attempts"]` for completed copies.

- [ ] **Step 1: Add the retry metadata assertion**

```python
def test_forge_copy_retry_exposes_successful_attempt_in_params():
    from gui_premium_v7 import _run_forge_copy_with_retries
    calls = 0
    def render():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("QC visual iPhone rechazó la copia")
        return {"iphone_visual_qc": {"errors": []}}
    params, attempt_number = _run_forge_copy_with_retries(render)
    params["forge_attempts"] = attempt_number
    assert params["forge_attempts"] == 2
    assert params["iphone_visual_qc"]["errors"] == []
```

- [ ] **Step 2: Verify the focused regression and suite**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_forge_iphone_profile.py -k "forge_copy_retry" -v; python -m pytest tests/test_forge_iphone_profile.py -v`

Expected: all selected tests pass; FFmpeg skips are allowed.

- [ ] **Step 3: Wrap only render/recovery in the helper**

Define `render_or_recover()` inside `process_copy` with the existing iPhone render/recovery branch and legacy render branch. Replace its direct invocation with `params, attempt_number = _run_forge_copy_with_retries(render_or_recover)`, then set `params["forge_attempts"] = attempt_number` before appending existing output-profile fields. Keep preflight/hash checks outside this closure.

- [ ] **Step 4: Verify GREEN**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_forge_iphone_profile.py -v`

Expected: no failures.

- [ ] **Step 5: Commit**

Run: `git add gui_premium_v7.py tests/test_forge_iphone_profile.py; git commit -m "feat: retry Forge copies before marking incomplete"`

### Task 3: Final gate

- [ ] **Step 1: Run `git diff origin/feature/meta-compatible-manual-calendar...HEAD --check`**

Expected: exit 0.

- [ ] **Step 2: Confirm `render_validated_copy` remains the only new-output publication path and only completed results reach `save_forge_video`.**

- [ ] **Step 3: Run `git status --short` and leave no uncommitted changes.**
