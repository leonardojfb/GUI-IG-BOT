from concurrent.futures import Future
from types import MethodType, SimpleNamespace

import video_editor
import videos
from gui_premium_v7 import InstagramAutoPro
from render_performance import RenderPerformance


OVERLAY = {
    "photo": "photo.png", "frame": 0, "duration_ms": 100,
    "size": 25, "ratio": "1:1", "position": "Centro",
    "x": 50, "y": 50, "opacity": 100,
}


def _contains_threads(command, threads):
    return ["-threads", str(threads)] in [command[index:index + 2] for index in range(len(command) - 1)]


def test_cpu_tanda_fallback_uses_the_snapshot_thread_budget(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(videos, "get_audio", lambda _path: True)

    def run(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0 if len(commands) == 3 else 1, stderr="")

    monkeypatch.setattr(videos.subprocess, "run", run)

    videos.render_video_pair("p1.mp4", "p2.mp4", str(tmp_path / "out.mp4"), "T", "P1", "P2", ffmpeg_threads=3)

    assert not _contains_threads(commands[0], 3)
    assert not _contains_threads(commands[1], 3)
    assert _contains_threads(commands[2], 3)


def test_editor_command_uses_requested_thread_budget(monkeypatch):
    monkeypatch.setattr(video_editor, "probe_video", lambda _path: {"duration": 1.0, "width": 100, "height": 100, "fps": 30})
    captured = []
    monkeypatch.setattr(video_editor, "_run", lambda command: captured.append(command) or SimpleNamespace(returncode=0, stderr=""))

    video_editor.render_video("source.mp4", "out.mp4", [OVERLAY], ffmpeg_threads=2)

    assert _contains_threads(captured[0], 2)


def test_tandas_use_one_snapshot_for_workers_and_cpu_thread_budget(monkeypatch, tmp_path):
    performance = RenderPerformance(4, 3, 5, 15, None)
    p1_dir, p2_dir = tmp_path / "p1", tmp_path / "p2"
    p1_dir.mkdir()
    p2_dir.mkdir()
    (p1_dir / "one.mp4").touch()
    (p2_dir / "two.mp4").touch()
    monkeypatch.setattr(videos, "FOLDER_INPUTS", str(tmp_path))
    monkeypatch.setattr(videos, "FOLDER_OUTPUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setattr(videos, "get_render_performance", lambda: performance)
    submissions, worker_counts = [], []

    class Pool:
        def __init__(self, max_workers):
            worker_counts.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def submit(self, function, *args):
            submissions.append((function, args))
            future = Future()
            future.set_result(None)
            return future

    monkeypatch.setattr(videos, "ThreadPoolExecutor", Pool)
    monkeypatch.setattr(videos, "as_completed", lambda futures: futures)

    videos.process_tandas(None, [{"tanda_name": "T", "p1_folder": "p1", "p2_folder": "p2"}])

    assert worker_counts == [3]
    assert submissions[0][1][-1] == 5


def test_editor_batch_uses_one_snapshot_for_workers_and_cpu_thread_budget(monkeypatch):
    performance = RenderPerformance(4, 3, 5, 15, None)
    monkeypatch.setattr("gui_premium_v7.render_performance.get_render_performance", lambda: performance)
    submitted, worker_counts, worker_tasks = [], [], []

    class Pool:
        def __init__(self, max_workers):
            worker_counts.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def submit(self, function, *args):
            submitted.append((function, args))
            future = Future()
            future.set_result(args[1])
            return future

    class Worker:
        def __init__(self, _app, _done, task):
            worker_tasks.append(task)

        def start(self):
            pass

    monkeypatch.setattr("gui_premium_v7.ThreadPoolExecutor", Pool)
    monkeypatch.setattr("gui_premium_v7.WorkerThread", Worker)
    fake = SimpleNamespace(editor_status=SimpleNamespace(configure=lambda **_kwargs: None))

    InstagramAutoPro._editor_render_batch(fake, [("source.mp4", "out.mp4", [OVERLAY])])
    worker_tasks[0]()

    assert worker_counts == [3]
    assert submitted[0][1][-1] == 5
