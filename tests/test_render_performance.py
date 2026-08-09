import json
from types import SimpleNamespace

import pytest

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


@pytest.mark.parametrize("saved_workers", [
    {"unexpected": 3},
    [3],
    "3",
    0,
    -3,
    True,
])
def test_malformed_saved_workers_use_the_safe_default(monkeypatch, tmp_path, saved_workers):
    path = tmp_path / "perf.json"
    path.write_text(json.dumps({"workers": saved_workers}), encoding="utf-8")
    monkeypatch.setattr(performance, "get_render_performance_path", lambda: path)
    monkeypatch.setattr(performance.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(performance, "get_available_memory_bytes", lambda: 16 * performance.GIB)

    snapshot = performance.get_render_performance()

    assert snapshot.workers == 2


def test_unreadable_json_uses_the_safe_default(monkeypatch, tmp_path):
    path = tmp_path / "perf.json"
    path.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(performance, "get_render_performance_path", lambda: path)
    monkeypatch.setattr(performance.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(performance, "get_available_memory_bytes", lambda: 16 * performance.GIB)

    assert performance.get_render_performance().workers == 2


def test_hardware_reclamp_is_atomically_persisted_and_reported(monkeypatch, tmp_path):
    path = tmp_path / "perf.json"
    path.write_text(json.dumps({"workers": 9}), encoding="utf-8")
    monkeypatch.setattr(performance, "get_render_performance_path", lambda: path)
    monkeypatch.setattr(performance.os, "cpu_count", lambda: 4)
    monkeypatch.setattr(performance, "get_available_memory_bytes", lambda: 32 * performance.GIB)
    real_replace = performance.os.replace
    replacements = []

    def replace(source, destination):
        replacements.append((source, destination))
        return real_replace(source, destination)

    monkeypatch.setattr(performance.os, "replace", replace)

    snapshot = performance.get_render_performance()

    assert snapshot.workers == 4
    assert snapshot.workers_were_reclamped is True
    assert json.loads(path.read_text(encoding="utf-8")) == {"workers": 4}
    assert len(replacements) == 1
    assert replacements[0][1] == path


def test_memory_query_exceptions_are_treated_as_unknown(monkeypatch):
    class Kernel32:
        @staticmethod
        def GlobalMemoryStatusEx(_status):
            raise OSError("memory query unavailable")

    monkeypatch.setattr(performance.os, "name", "nt")
    monkeypatch.setattr(performance.ctypes, "windll", SimpleNamespace(kernel32=Kernel32()))

    assert performance.get_available_memory_bytes() is None


def test_zero_available_memory_limits_rendering_to_one_worker(monkeypatch, tmp_path):
    monkeypatch.setattr(performance, "get_render_performance_path", lambda: tmp_path / "perf.json")
    monkeypatch.setattr(performance.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(performance, "get_available_memory_bytes", lambda: 0)

    snapshot = performance.get_render_performance()

    assert snapshot.max_workers == 1
    assert snapshot.workers == 1
