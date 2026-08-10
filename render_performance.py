"""Hardware-bounded render concurrency settings."""

import ctypes
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


GIB = 1024 ** 3
MEMORY_PER_WORKER_BYTES = 2 * GIB


@dataclass(frozen=True)
class RenderPerformance:
    # max_workers is the hardware ceiling shown by the UI. available_workers is
    # the current RAM-limited ceiling used to keep active renders safe.
    max_workers: int
    workers: int
    ffmpeg_threads: int
    logical_cpus: int
    available_memory_bytes: int | None
    workers_were_reclamped: bool = False
    available_workers: int | None = None


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
    try:
        query_succeeded = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    except Exception:
        return None
    if not query_succeeded:
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
            workers = json.load(file).get("workers")
    except (FileNotFoundError, OSError, ValueError, AttributeError):
        return None
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        return None
    return workers


def _persist_workers(workers: int) -> None:
    path = get_render_performance_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            json.dump({"workers": workers}, temporary)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def get_render_performance(requested_workers: int | None = None) -> RenderPerformance:
    logical_cpus = max(1, os.cpu_count() or 1)
    available_memory = get_available_memory_bytes()
    memory_max = (
        logical_cpus if available_memory is None
        else max(1, available_memory // MEMORY_PER_WORKER_BYTES)
    )
    max_workers = logical_cpus
    available_workers = max(1, min(max_workers, memory_max))
    selected_workers = requested_workers if requested_workers is not None else load_workers()
    hardware_clamped_workers = clamp_workers(selected_workers, max_workers)
    workers = clamp_workers(selected_workers, available_workers)
    workers_were_reclamped = selected_workers is not None and workers != selected_workers
    if (
        requested_workers is None
        and selected_workers is not None
        and hardware_clamped_workers != selected_workers
    ):
        _persist_workers(hardware_clamped_workers)
    return RenderPerformance(
        max_workers=max_workers,
        workers=workers,
        ffmpeg_threads=max(1, logical_cpus // workers),
        logical_cpus=logical_cpus,
        available_memory_bytes=available_memory,
        workers_were_reclamped=workers_were_reclamped,
        available_workers=available_workers,
    )


def save_render_workers(workers: int) -> RenderPerformance:
    max_workers = max(1, os.cpu_count() or 1)
    selected_workers = clamp_workers(workers, max_workers)
    _persist_workers(selected_workers)
    return get_render_performance(selected_workers)
