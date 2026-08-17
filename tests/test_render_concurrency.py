from concurrent.futures import Future
import json
from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest

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


def _video_codec(command):
    try:
        return command[command.index("-c:v") + 1]
    except ValueError:
        return None


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


def test_all_tanda_encoders_raise_a_source_and_output_specific_error(monkeypatch, tmp_path):
    output = tmp_path / "out.mp4"
    monkeypatch.setattr(videos, "get_audio", lambda _path: True)
    monkeypatch.setattr(
        videos.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stderr="encoder failed"),
    )

    with pytest.raises(RuntimeError) as raised:
        videos.render_video_pair(
            "p1-source.mp4", "p2-source.mp4", str(output), "T", "P1", "P2")

    message = str(raised.value)
    assert "p1-source.mp4" in message
    assert "p2-source.mp4" in message
    assert str(output) in message
    assert "encoder failed" in message


def test_tanda_future_failure_prevents_a_success_result(monkeypatch, tmp_path):
    p1_dir, p2_dir = tmp_path / "p1", tmp_path / "p2"
    p1_dir.mkdir()
    p2_dir.mkdir()
    (p1_dir / "one.mp4").touch()
    (p2_dir / "two.mp4").touch()
    tanda = {"tanda_name": "T", "p1_folder": "p1", "p2_folder": "p2"}

    class Database:
        def __init__(self):
            self.closed = False

        def get_all_tandas(self):
            return [tanda]

        def close(self):
            self.closed = True

    database = Database()
    monkeypatch.setattr(videos, "FOLDER_INPUTS", str(tmp_path))
    monkeypatch.setattr(videos, "FOLDER_OUTPUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setattr(videos, "DatabaseManager", lambda: database)
    monkeypatch.setattr(videos, "get_audio", lambda _path: True)
    monkeypatch.setattr(
        videos.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stderr="all encoders failed"),
    )

    with pytest.raises(Exception) as raised:
        videos.render_tanda("T", RenderPerformance(2, 1, 4, 4, None))

    assert "all encoders failed" in str(raised.value)
    assert "éxito" not in str(raised.value).lower()
    assert database.closed is True


def test_editor_prefers_nvenc_and_falls_back_to_cpu_thread_budget(monkeypatch):
    monkeypatch.setattr(video_editor, "probe_video", lambda _path: {"duration": 1.0, "width": 100, "height": 100, "fps": 30})
    captured = []

    def run(command):
        captured.append(command)
        return SimpleNamespace(returncode=0 if len(captured) == 2 else 1, stderr="nvenc failed")

    monkeypatch.setattr(video_editor, "_run", run)

    video_editor.render_video("source.mp4", "out.mp4", [OVERLAY], ffmpeg_threads=2)

    assert [_video_codec(command) for command in captured] == ["h264_nvenc", "libx264"]
    assert not _contains_threads(captured[0], 2)
    assert _contains_threads(captured[1], 2)


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


def test_process_tandas_logs_successful_outputs(tmp_path, monkeypatch):
    from database import DatabaseManager

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    p1_dir = tmp_path / "inputs" / "p1"
    p2_dir = tmp_path / "inputs" / "p2"
    p1_dir.mkdir(parents=True)
    p2_dir.mkdir(parents=True)
    (p1_dir / "one.mp4").write_bytes(b"p1")
    (p2_dir / "two.mp4").write_bytes(b"p2")
    monkeypatch.setattr(videos, "FOLDER_INPUTS", str(tmp_path / "inputs"))
    monkeypatch.setattr(videos, "FOLDER_OUTPUT_ROOT", str(tmp_path / "videos_finales"))

    def fake_render_video_pair(path_v1, path_v2, out_path, tanda_name, p1_id, p2_id, ffmpeg_threads=None):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"rendered")
        return out_path

    monkeypatch.setattr(videos, "render_video_pair", fake_render_video_pair)

    videos.process_tandas(
        db,
        [{"tanda_name": "TANDA", "p1_folder": "p1", "p2_folder": "p2"}],
        SimpleNamespace(workers=1, ffmpeg_threads=2),
    )

    rows = db.list_video_transform_logs()
    assert rows[0]["process_kind"] == "tandas"
    details = json.loads(rows[0]["details_json"])
    assert details["p1_id"] == "one"
    assert details["p2_id"] == "two"
    assert details["ffmpeg_threads"] == 2
    db.close()


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


def test_editor_single_render_uses_one_snapshot_and_blocks_repeated_clicks(monkeypatch):
    import gui_premium_v7

    performance = RenderPerformance(4, 2, 5, 10, None)
    snapshot_calls, render_calls, worker_callbacks, transform_logs = [], [], [], []

    class Widget:
        def __init__(self):
            self.states = []

        def configure(self, **kwargs):
            if "state" in kwargs:
                self.states.append(kwargs["state"])

    class Worker:
        def __init__(self, _app, done, task):
            worker_callbacks.append((done, task))

        def start(self):
            pass

    fake = SimpleNamespace(
        _editor_render_active=False,
        _editor_collect=lambda: (["source.mp4"], [OVERLAY]),
        editor_status=Widget(),
        btn_editor_render=Widget(),
        db=SimpleNamespace(save_video_transform_log=lambda *args, **kwargs: transform_logs.append((args, kwargs))),
    )
    monkeypatch.setattr(
        gui_premium_v7.render_performance,
        "get_render_performance",
        lambda: snapshot_calls.append(True) or performance,
    )
    monkeypatch.setattr(gui_premium_v7.filedialog, "asksaveasfilename", lambda **_kwargs: "out.mp4")
    monkeypatch.setattr(gui_premium_v7.messagebox, "showinfo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gui_premium_v7, "WorkerThread", Worker)
    monkeypatch.setattr(
        video_editor,
        "render_video",
        lambda *args: render_calls.append(args) or args[1],
    )

    InstagramAutoPro.editor_render(fake)
    InstagramAutoPro.editor_render(fake)

    assert snapshot_calls == [True]
    assert len(worker_callbacks) == 1
    assert fake.btn_editor_render.states == ["disabled"]
    done, task = worker_callbacks[0]
    result = task()
    done(True, result)
    assert render_calls == [("source.mp4", "out.mp4", [OVERLAY], 5)]
    assert transform_logs
    assert transform_logs[0][0][0] == "video_editor"
    assert transform_logs[0][1] == {}
    assert fake.btn_editor_render.states == ["disabled", "normal"]
    assert fake._editor_render_active is False


def test_editor_batch_blocks_repeated_clicks_until_its_worker_finishes(monkeypatch):
    import gui_premium_v7

    performance = RenderPerformance(4, 2, 4, 8, None)
    worker_callbacks = []

    class Widget:
        def __init__(self):
            self.states = []

        def configure(self, **kwargs):
            if "state" in kwargs:
                self.states.append(kwargs["state"])

    class Worker:
        def __init__(self, _app, done, task):
            worker_callbacks.append((done, task))

        def start(self):
            pass

    fake = SimpleNamespace(
        _editor_render_active=False,
        editor_status=Widget(),
        btn_editor_render=Widget(),
    )
    monkeypatch.setattr(gui_premium_v7.render_performance, "get_render_performance", lambda: performance)
    monkeypatch.setattr(gui_premium_v7.messagebox, "showinfo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gui_premium_v7, "WorkerThread", Worker)

    jobs = [("source.mp4", "out.mp4", [OVERLAY])]
    InstagramAutoPro._editor_render_batch(fake, jobs)
    InstagramAutoPro._editor_render_batch(fake, jobs)

    assert len(worker_callbacks) == 1
    assert fake.btn_editor_render.states == ["disabled"]
    done, _task = worker_callbacks[0]
    done(True, ["out.mp4"])
    assert fake.btn_editor_render.states == ["disabled", "normal"]
    assert fake._editor_render_active is False
