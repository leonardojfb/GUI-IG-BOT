"""Hardware-bounded render concurrency settings."""

import ctypes
import json
import os
from dataclasses import dataclass
from pathlib import Path


GIB = 1024 ** 3
MEMORY_PER_WORKER_BYTES = 2 * GIB


@dataclass(frozen=True)
class RenderPerformance:
    max_workers: int
    workers: int
    ffmpeg_threads: int
    logical_cpus: int
    available_memory_bytes: int | None


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def get_available_memory_bytes() -> int | None:
    if os.name != "nt":
        return None
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return status.ullAvailPhys


def get_render_performance_path() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "MetodoIG" / "render_performance.json"


def clamp_workers(workers: int | None, max_workers: int) -> int:
    if workers is None:
        workers = min(2, max_workers)
    return max(1, min(int(workers), max_workers))


def load_workers() -> int | None:
    try:
        with get_render_performance_path().open(encoding="utf-8") as file:
            return json.load(file).get("workers")
    except (FileNotFoundError, OSError, ValueError, AttributeError):
        return None


def get_render_performance(requested_workers: int | None = None) -> RenderPerformance:
    logical_cpus = max(1, os.cpu_count() or 1)
    available_memory = get_available_memory_bytes()
    memory_max = max(1, available_memory // MEMORY_PER_WORKER_BYTES) if available_memory else logical_cpus
    max_workers = max(1, min(logical_cpus, memory_max))
    workers = clamp_workers(
        requested_workers if requested_workers is not None else load_workers(), max_workers)
    return RenderPerformance(
        max_workers=max_workers,
        workers=workers,
        ffmpeg_threads=max(1, logical_cpus // workers),
        logical_cpus=logical_cpus,
        available_memory_bytes=available_memory,
    )


def save_render_workers(workers: int) -> RenderPerformance:
    snapshot = get_render_performance(workers)
    path = get_render_performance_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"workers": snapshot.workers}), encoding="utf-8")
    return snapshot
