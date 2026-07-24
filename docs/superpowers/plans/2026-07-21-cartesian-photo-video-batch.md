# Lote cartesiano de fotos y videos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generar una salida por cada pareja foto-video, incluidos los casos 1xN y Nx1.

**Architecture:** Añadir una función pura de parejas foto-video en `video_editor.py`. La GUI usará la cantidad de parejas para elegir entre salida individual y carpeta de lote, y cada trabajo recibirá un solo overlay.

**Tech Stack:** Python 3, CustomTkinter, FFmpeg, Pillow, pytest.

## Global Constraints

- Si `len(videos) * len(fotos) > 1`, generar una salida por pareja.
- Solo 1x1 conserva el selector de nombre de archivo individual.
- Mantener configuración global y excepciones `Editar individual`.
- Mantener el límite de timeline de cinco segundos únicamente con varias fotos y varios videos.
- No sobrescribir resultados existentes.

---

### Task 1: Función pura de parejas foto-video

**Files:**

- Modify: `video_editor.py:48-83`
- Modify: `tests/test_video_editor.py:1-26`

**Interfaces:**

- Produces: `build_photo_video_pairs(videos: list[str], overlays: list[dict]) -> list[tuple[str, dict, int]]`.
- The tuple is `(video_path, overlay, one_based_photo_index)` and is ordered by photo first, video second.

- [ ] **Step 1: Write failing tests**

```python
from video_editor import build_photo_video_pairs

def test_pairs_one_video_many_photos():
    assert build_photo_video_pairs(["v.mp4"], [{"photo": "a.png"}, {"photo": "b.png"}]) == [
        ("v.mp4", {"photo": "a.png"}, 1),
        ("v.mp4", {"photo": "b.png"}, 2),
    ]

def test_pairs_many_videos_one_photo():
    assert build_photo_video_pairs(["v1.mp4", "v2.mp4"], [{"photo": "a.png"}]) == [
        ("v1.mp4", {"photo": "a.png"}, 1),
        ("v2.mp4", {"photo": "a.png"}, 1),
    ]

def test_pairs_are_photo_major():
    pairs = build_photo_video_pairs(["v1.mp4", "v2.mp4"], [{"photo": "a.png"}, {"photo": "b.png"}])
    assert [(video, overlay["photo"], index) for video, overlay, index in pairs] == [
        ("v1.mp4", "a.png", 1), ("v2.mp4", "a.png", 1),
        ("v1.mp4", "b.png", 2), ("v2.mp4", "b.png", 2),
    ]
```

- [ ] **Step 2: Verify RED**

Run: `py -3 -m pytest -q tests/test_video_editor.py`

Expected: import error because `build_photo_video_pairs` does not exist.

- [ ] **Step 3: Implement the minimal function**

```python
def build_photo_video_pairs(videos: list[str], overlays: list[dict]) -> list[tuple[str, dict, int]]:
    return [(video, overlay, photo_index)
            for photo_index, overlay in enumerate(overlays, start=1)
            for video in videos]
```

- [ ] **Step 4: Verify GREEN**

Run: `py -3 -m pytest -q tests/test_video_editor.py`

Expected: all pair assertions pass.

- [ ] **Step 5: Commit**

Run: `git add video_editor.py tests/test_video_editor.py`

Run: `git commit -m "feat: define photo video batch pairs"`

### Task 2: Un trabajo por pareja en la GUI

**Files:**

- Modify: `gui_premium_v7.py:3367-3778`
- Modify: `tests/test_video_editor.py`

**Interfaces:**

- Consumes: `video_editor.build_photo_video_pairs`.
- Produces: `(source, output, [overlay])` for `_editor_render_batch`.
- A batch is `len(pairs) > 1`; then preview uses the selected photo only.

- [ ] **Step 1: Write the failing batch-decision test**

```python
from gui_premium_v7 import InstagramAutoPro

def test_editor_treats_any_multi_pair_selection_as_a_batch():
    method = InstagramAutoPro._editor_cartesian_batch
    assert method(None, ["v.mp4"], [{"photo": "a.png"}, {"photo": "b.png"}])
    assert method(None, ["v1.mp4", "v2.mp4"], [{"photo": "a.png"}])
    assert not method(None, ["v.mp4"], [{"photo": "a.png"}])
```

- [ ] **Step 2: Verify RED**

Run: `py -3 -m pytest -q tests/test_video_editor.py::test_editor_treats_any_multi_pair_selection_as_a_batch`

Expected: assertion failure for 1xN because the current method only returns true when both groups have more than one item.

- [ ] **Step 3: Replace the batch branch**

```python
pairs = video_editor.build_photo_video_pairs(videos, overlays)
if len(pairs) > 1:
    output_dir = filedialog.askdirectory(title="Carpeta donde guardar los videos editados")
    if not output_dir:
        return
    jobs = []
    for source, overlay, photo_index in pairs:
        stem = os.path.splitext(os.path.basename(source))[0]
        jobs.append((source, reserve_output(stem, f"foto{photo_index:02d}"), [overlay]))
    return self._editor_render_batch(jobs)
```

Keep `asksaveasfilename` only when there is exactly one pair. Use `len(videos) * len(overlays) > 1` for batch previews, but preserve the separate five-second condition requiring both groups to be plural.

- [ ] **Step 4: Verify GREEN and syntax**

Run: `py -3 -m py_compile gui_premium_v7.py video_editor.py`

Expected: exit code 0.

Run: `py -3 -m pytest -q tests/test_video_editor.py`

- [ ] **Step 5: Commit**

Run: `git add gui_premium_v7.py tests/test_video_editor.py`

Run: `git commit -m "feat: render one output per photo video pair"`

### Task 3: Cardinality and FFmpeg regression coverage

**Files:**

- Modify: `tests/test_video_editor.py:1-110`

**Interfaces:**

- Consumes: `build_photo_video_pairs` and `render_video`.
- Produces: count tests for 1xN, Nx1 and NxM, plus a temporary FFmpeg 2x2 smoke test.

- [ ] **Step 1: Add the FFmpeg smoke test**

```python
def test_cartesian_smoke_renders_one_file_per_pair(tmp_path):
    videos = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    photos = [tmp_path / "a.png", tmp_path / "b.png"]
    for color, video in zip(("black", "white"), videos):
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=160x240:r=10", "-t", "1", str(video)], check=True, capture_output=True)
    for color, photo in zip(("red", "blue"), photos):
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=60x100", "-frames:v", "1", str(photo)], check=True, capture_output=True)
    overlays = [{"photo": str(photo), "frame": 0, "duration_ms": 250, "size": 25, "x": 50, "y": 50, "opacity": 100, "ratio": "9:16", "position": "Manual X/Y"} for photo in photos]
    outputs = []
    for source, overlay, index in build_photo_video_pairs([str(video) for video in videos], overlays):
        output = tmp_path / f"{Path(source).stem}_foto{index:02d}.mp4"
        render_video(source, str(output), [overlay])
        outputs.append(output)
    assert len(outputs) == 4 and all(output.stat().st_size > 0 for output in outputs)
```

Add `from pathlib import Path`, `import subprocess`, and imports for `build_photo_video_pairs` and `render_video` at the test module top. The test uses `tmp_path`, so no fixture media is written into the repository.

- [ ] **Step 2: Verify focused and full suites**

Run: `py -3 -m pytest -q tests/test_video_editor.py`

Expected: all video-editor tests pass.

Run: `py -3 -m pytest -q`

Expected: exit code 0 with no failures.

- [ ] **Step 3: Commit**

Run: `git add tests/test_video_editor.py`

Run: `git commit -m "test: cover photo video batch cardinalities"`

### Task 4: Robustez de lotes y errores de procesos

**Files:**

- Modify: `gui_premium_v7.py`
- Modify: `video_editor.py`
- Modify: `tests/test_video_editor.py`

**Binding constraints:**

- En un lote con varias fotos y varios videos, el momento compartido se expresa como tiempo y se convierte al frame correspondiente para cada FPS de video; nunca puede superar los primeros cinco segundos.
- Aceptar tamaño `0%` como overlay visualmente ausente; `100%` sigue cubriendo el frame del video.
- Si cualquiera de los videos seleccionados falta, detener el render antes de reducir silenciosamente la cardinalidad del lote.
- Traducir `FileNotFoundError` y fallos de probe a errores accionables en español que indiquen el ejecutable, archivo o detalle relevante.
- Corregir los literales de interfaz con mojibake.

- [ ] **Step 1: Write failing regression tests**

Add focused tests for a shared timestamp selected at 60 FPS that becomes the correct frame at 24 FPS, zero-size validation, missing selected video, missing executable, and probe stderr.

- [ ] **Step 2: Verify RED**

Run: `py -3 -m pytest -q tests/test_video_editor.py -k "mixed_fps or zero_size or missing_selected_video or missing_executable or probe_error"`

Expected: failures against the current implementation.

- [ ] **Step 3: Implement the minimum fixes**

Convert shared batch timestamps per source FPS in preview/render jobs, validate every selected video, accept invisible size zero, surface process/probe errors, and correct the affected UI strings.

- [ ] **Step 4: Verify GREEN**

Run: `py -3 -m py_compile gui_premium_v7.py video_editor.py`

Run: `py -3 -m pytest -q tests/test_video_editor.py`

Run: `py -3 -m pytest -q`

- [ ] **Step 5: Commit**

Run: `git add gui_premium_v7.py video_editor.py tests/test_video_editor.py`

Run: `git commit -m "fix: harden cartesian batch edge cases"`

### Task 5: Flujos de edición individual y errores de render

**Files:**

- Modify: `gui_premium_v7.py`
- Modify: `video_editor.py`
- Modify: `tests/test_video_editor.py`

**Binding constraints:**

- En modo global, una fila con `Editar individual` usa su propio frame al cambiar objetivo, aplicar frame y ver preview, excepto en N x M donde el tiempo compartido obliga todas las fotos.
- Al quitar una foto y volver a agregarla, cada fila conserva etiqueta `Foto N` y una fila de grid única y consecutiva.
- Fallos no nulos de render y preview informan operación, ruta relevante y stderr conciso.
- Las pruebas deben usar valores de `Frame` escritos en las filas: N x M los limita/reemplaza dentro de los primeros cinco segundos, mientras 1xN, Nx1 y 1x1 conservan su comportamiento temporal normal.

- [ ] **Step 1: Write failing regression tests**

Add direct fake-GUI tests for manual frame target/apply/preview under global mode, remove-middle-then-add row reindexing, nonzero render/preview errors, and typed frame fields across all cardinalities.

- [ ] **Step 2: Verify RED**

Run the new focused tests and record assertion failures caused by the missing behavior.

- [ ] **Step 3: Implement minimal fixes**

Respect manual frame overrides outside N x M, reindex row widgets after mutations, and improve render/preview error messages. Validate typed X/Y as percentages if it is touched by the common config validator.

- [ ] **Step 4: Verify GREEN**

Run `py -3 -m py_compile gui_premium_v7.py video_editor.py`, the focused tests, `py -3 -m pytest -q tests/test_video_editor.py`, and `py -3 -m pytest -q`.

- [ ] **Step 5: Commit**

Run: `git add gui_premium_v7.py video_editor.py tests/test_video_editor.py`

Run: `git commit -m "fix: complete video editor interaction flows"`
