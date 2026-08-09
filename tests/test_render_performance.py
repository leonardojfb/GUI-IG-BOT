import json

import render_performance as performance


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
