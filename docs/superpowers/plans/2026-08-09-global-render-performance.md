# Global Render Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persisted, hardware-bounded shared concurrency setting for Forge, Tandas, and video editing.

**Architecture:** `render_performance.py` owns hardware capacity, persistence, and immutable execution snapshots. The GUI synchronizes three controls through that module, and each execution path receives a snapshot so worker counts cannot change mid-run. FFmpeg CPU encoder threads are divided among concurrent jobs.

**Tech Stack:** Python 3.14, CustomTkinter, `concurrent.futures.ThreadPoolExecutor`, FFmpeg, Windows `ctypes`, pytest.

## Global Constraints

- Persist user preference only under `%LOCALAPPDATA%\MetodoIG\render_performance.json`; do not store it in `organizador.db` or a release ZIP.
- Default to `min(2, hardware max)` and clamp every saved or requested value to `1..hardware max`.
- Calculate max from logical CPU count and free RAM with a 2 GiB per-job memory budget.
- Pass `-threads max(1, logical_cpus // workers)` only to CPU FFmpeg encoders.
- Keep Forge SQLite writes sequential after concurrent FFmpeg work finishes.
- Preserve current GPU/QSV-first fallback behavior, output naming, metadata, and Tanda registration.

---

### Task 1: Capacity and persistence module

**Files:**
- Create: `render_performance.py`
- Create: `tests/test_render_performance.py`

**Interfaces:**
- Produces: `RenderPerformance`, `get_render_performance()`, `save_render_workers(workers)`, `get_render_performance_path()`.
- Consumes: `os.cpu_count`, Windows memory status through `ctypes`, `%LOCALAPPDATA%`.

- [ ] **Step 1: Write the failing tests**

```python
def test_hardware_max_is_bounded_by_cpu_and_available_memory(monkeypatch, tmp_path):
    monkeypatch.setattr(performance, "get_render_performance_path", lambda: tmp_path / "perf.json")
    monkeypatch.setattr(performance.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(performance, "get_available_memory_bytes", lambda: 10 * performance.GIB)

    snapshot = performance.get_render_performance()

    assert snapshot.max_workers == 5
    assert snapshot.workers == 2
    assert snapshot.ffmpeg_threads == 6


def test_saved_workers_are_clamped_and_persisted(monkeypatch, tmp_path):
    path = tmp_path / "perf.json"
    monkeypatch.setattr(performance, "get_render_performance_path", lambda: path)
    monkeypatch.setattr(performance.os, "cpu_count", lambda: 4)
    monkeypatch.setattr(performance, "get_available_memory_bytes", lambda: 32 * performance.GIB)

    snapshot = performance.save_render_workers(99)

    assert snapshot.workers == 4
    assert json.loads(path.read_text(encoding="utf-8")) == {"workers": 4}
```

- [ ] **Step 2: Run test to verify RED**

Run: `py -3.14 -m pytest tests/test_render_performance.py -q`

Expected: FAIL because `render_performance` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
GIB = 1024 ** 3
MEMORY_PER_WORKER_BYTES = 2 * GIB

@dataclass(frozen=True)
class RenderPerformance:
    max_workers: int
    workers: int
    ffmpeg_threads: int
    logical_cpus: int
    available_memory_bytes: int | None

def get_render_performance(requested_workers: int | None = None) -> RenderPerformance:
    logical_cpus = max(1, os.cpu_count() or 1)
    available_memory = get_available_memory_bytes()
    memory_max = max(1, available_memory // MEMORY_PER_WORKER_BYTES) if available_memory else logical_cpus
    max_workers = max(1, min(logical_cpus, memory_max))
    workers = clamp_workers(requested_workers if requested_workers is not None else load_workers(), max_workers)
    return RenderPerformance(max_workers, workers, max(1, logical_cpus // workers), logical_cpus, available_memory)
```

- [ ] **Step 4: Run test to verify GREEN**

Run: `py -3.14 -m pytest tests/test_render_performance.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add render_performance.py tests/test_render_performance.py
git commit -m "feat: add persisted render performance settings"
```

### Task 2: Apply a snapshot to Tandas and batch editing

**Files:**
- Modify: `videos.py:103-161,219-271`
- Modify: `video_editor.py:129-149`
- Modify: `gui_premium_v7.py:2238-2258,4148-4168`
- Create: `tests/test_render_concurrency.py`

**Interfaces:**
- Consumes: `RenderPerformance.workers` and `RenderPerformance.ffmpeg_threads`.
- Produces: `videos.process_tandas(..., performance=None)`, `videos.render_video_pair(..., ffmpeg_threads=None)`, `video_editor.render_video(..., ffmpeg_threads=None)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_cpu_tanda_fallback_uses_the_snapshot_thread_budget(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(videos, "get_audio", lambda _path: True)
    monkeypatch.setattr(videos.subprocess, "run", lambda cmd, **_kwargs: commands.append(cmd) or SimpleNamespace(returncode=0, stderr=""))

    videos.render_video_pair("p1.mp4", "p2.mp4", str(tmp_path / "out.mp4"), "T", "P1", "P2", ffmpeg_threads=3)

    assert ["-threads", "3"] in [commands[-1][index:index + 2] for index in range(len(commands[-1]) - 1)]


def test_editor_command_uses_requested_thread_budget(monkeypatch):
    monkeypatch.setattr(video_editor, "probe_video", lambda _path: {"duration": 1.0, "width": 100, "height": 100, "fps": 30})
    captured = []
    monkeypatch.setattr(video_editor, "_run", lambda cmd: captured.append(cmd) or SimpleNamespace(returncode=0, stderr=""))

    video_editor.render_video("source.mp4", "out.mp4", [overlay], ffmpeg_threads=2)

    assert ["-threads", "2"] in [captured[0][index:index + 2] for index in range(len(captured[0]) - 1)]
```

- [ ] **Step 2: Run test to verify RED**

Run: `py -3.14 -m pytest tests/test_render_concurrency.py -q`

Expected: FAIL because the render functions do not accept `ffmpeg_threads`.

- [ ] **Step 3: Implement the minimal propagation**

```python
def render_video(input_path, output_path, overlays, ffmpeg_threads=None):
    # existing command construction
    if ffmpeg_threads:
        cmd += ["-threads", str(ffmpeg_threads)]
```

```python
def _editor_render_batch(self, jobs):
    performance = render_performance.get_render_performance()
    with ThreadPoolExecutor(max_workers=performance.workers) as pool:
        futures = [pool.submit(video_editor.render_video, source, output, overlays, performance.ffmpeg_threads)
                   for source, output, overlays in jobs]
        return [future.result() for future in futures]
```

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `py -3.14 -m pytest tests/test_render_concurrency.py tests/test_video_editor.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add videos.py video_editor.py gui_premium_v7.py tests/test_render_concurrency.py
git commit -m "feat: use shared concurrency for tandas and editing"
```

### Task 3: Forge concurrency and sequential registry persistence

**Files:**
- Modify: `gui_premium_v7.py:4501-4612`
- Create: `tests/test_forge_concurrency.py`

**Interfaces:**
- Consumes: one `RenderPerformance` snapshot at the start of `forge_process`.
- Produces: per-copy result records `(source_name, output_name, video_hash, metadata)` collected before database writes.

- [ ] **Step 1: Write the failing test**

```python
def test_forge_records_are_saved_after_all_variants_complete(monkeypatch, forge_app):
    completed = []
    monkeypatch.setattr(metadata_pool, "apply_variant_and_metadata", lambda source, output, meta, **_kwargs: completed.append(output) or {})
    monkeypatch.setattr(render_performance, "get_render_performance", lambda: snapshot(workers=2))

    task = start_forge_task(forge_app)
    task()

    assert completed == ["one__c01.mp4", "two__c01.mp4"]
    assert forge_app.db.saved_forge_rows == [("one.mp4", "one__c01.mp4"), ("two.mp4", "two__c01.mp4")]
```

- [ ] **Step 2: Run test to verify RED**

Run: `py -3.14 -m pytest tests/test_forge_concurrency.py -q`

Expected: FAIL because Forge invokes FFmpeg and SQLite writes in one sequential loop.

- [ ] **Step 3: Implement concurrent jobs and ordered writes**

```python
with ThreadPoolExecutor(max_workers=performance.workers) as pool:
    futures = [pool.submit(process_copy, copy_job) for copy_job in copy_jobs]
    completed = [future.result() for future in futures]
for source_name, output_name, video_hash, metadata in completed:
    db_ref.save_forge_video(tanda_name, source_name, output_name, video_hash)
db_ref.save_metadata_fingerprints([metadata for *_row, metadata in completed])
```

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `py -3.14 -m pytest tests/test_forge_concurrency.py tests/test_forge_ui.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gui_premium_v7.py tests/test_forge_concurrency.py
git commit -m "feat: process forge variants concurrently"
```

### Task 4: Shared UI controls and end-to-end verification

**Files:**
- Modify: `gui_premium_v7.py:2116-2172,3601-3839,4173-4425`
- Create: `tests/test_render_performance_ui.py`
- Modify: `docs/superpowers/specs/2026-08-09-global-render-performance-design.md`

**Interfaces:**
- Consumes: `get_render_performance()` and `save_render_workers(workers)`.
- Produces: `_build_render_performance_control(parent, context)`, `_on_render_workers_changed(value)`, and one synchronized value across all three screen controls.

- [ ] **Step 1: Write the failing UI contract tests**

```python
def test_all_three_content_screens_build_the_shared_performance_control():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    for method in ("_build_mix_frame", "_build_video_editor_frame", "_build_forge_frame"):
        body = extract_method(source, method)
        assert "_build_render_performance_control" in body
```

- [ ] **Step 2: Run test to verify RED**

Run: `py -3.14 -m pytest tests/test_render_performance_ui.py -q`

Expected: FAIL because shared-control methods are absent.

- [ ] **Step 3: Implement the shared control**

```python
def _build_render_performance_control(self, parent, context):
    snapshot = render_performance.get_render_performance()
    slider = ctk.CTkSlider(parent, from_=1, to=snapshot.max_workers,
                           number_of_steps=max(1, snapshot.max_workers - 1),
                           command=self._on_render_workers_changed)
    slider.set(snapshot.workers)
    self._render_worker_controls.append((slider, label))
```

- [ ] **Step 4: Run full verification**

Run: `py -3.14 -m pytest -q`

Expected: PASS with all existing and new tests.

- [ ] **Step 5: Check packaging and commit**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only intended source, tests, and docs are staged.

```bash
git add gui_premium_v7.py tests/test_render_performance_ui.py docs/superpowers/specs/2026-08-09-global-render-performance-design.md
git commit -m "feat: expose shared render performance controls"
```

