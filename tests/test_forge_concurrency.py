import os
from types import SimpleNamespace

import metadata_pool
import render_performance
from gui_premium_v7 import InstagramAutoPro
from render_performance import RenderPerformance


class _Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Widget:
    def __init__(self):
        self.configurations = []

    def configure(self, **kwargs):
        self.configurations.append(kwargs)

    def start(self):
        pass

    def stop(self):
        pass

    def set(self, _value):
        pass


class _Database:
    def __init__(self, completed):
        self.completed = completed
        self.saved_forge_rows = []
        self.saved_fingerprints = []
        self.saved_tandas = []

    def save_forge_video(self, _tanda, source, output, _video_hash):
        assert len(self.completed) == 2
        self.saved_forge_rows.append((source, output))

    def save_metadata_fingerprints(self, fingerprints):
        assert len(self.completed) == 2
        self.saved_fingerprints = fingerprints

    def get_tanda_by_name(self, _tanda):
        return None

    def add_tanda(self, *args):
        self.saved_tandas.append(args)

    def set_tanda_trial(self, tanda_name, is_trial):
        self.trial_tandas = [(tanda_name, is_trial)]


def _forge_app(tmp_path, completed):
    videos = [tmp_path / "one.mp4", tmp_path / "two.mp4"]
    for video in videos:
        video.touch()
    metadata = [
        {
            "iphone_model": "iPhone 15",
            "city": "Miami",
            "lat": "+25.7617",
            "lon": "-080.1918",
            "carrier": "T-Mobile",
            "ios_version": "18.0",
        },
        {
            "iphone_model": "iPhone 16",
            "city": "Boston",
            "lat": "+42.3601",
            "lon": "-071.0589",
            "carrier": "Verizon",
            "ios_version": "18.1",
        },
    ]
    return SimpleNamespace(
        forge_video_paths=[str(video) for video in videos],
        forge_meta_assignments=metadata,
        e_forge_tanda=_Value("Concurrent"),
        e_forge_copies=_Value("1"),
        forge_trial_mode_var=_Value("Normal"),
        forge_fx_vars={},
        forge_efectos_var=_Value("Default"),
        forge_fuerza_var=_Value("Default"),
        FORGE_FX_DEFS=[],
        btn_forge_process=_Widget(),
        btn_forge_reshuffle=_Widget(),
        forge_pb=_Widget(),
        forge_pb_lbl=_Widget(),
        db=_Database(completed),
    )


def test_forge_records_are_saved_after_all_variants_complete(monkeypatch, tmp_path):
    import gui_premium_v7

    completed = []
    variant_kwargs = []
    worker_counts = []
    worker_tasks = []
    snapshot_calls = []
    submissions = []
    confirmation_messages = []
    performance = RenderPerformance(4, 2, 4, 8, None)

    def apply_variant(_source, output, _meta, **kwargs):
        completed.append(os.path.basename(output))
        variant_kwargs.append(kwargs)
        return {}

    class PendingFuture:
        def __init__(self, function, args):
            self.function = function
            self.args = args

        def result(self):
            assert len(submissions) == 2, "Forge waited before submitting every copy job"
            return self.function(*self.args)

    class Pool:
        def __init__(self, max_workers):
            worker_counts.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def submit(self, function, *args):
            future = PendingFuture(function, args)
            submissions.append(future)
            return future

    class Worker:
        def __init__(self, _app, _done, task):
            worker_tasks.append(task)

        def start(self):
            pass

    monkeypatch.setattr(metadata_pool, "apply_variant_and_metadata", apply_variant)
    monkeypatch.setattr(metadata_pool, "get_video_hash", lambda source: os.path.basename(source))
    monkeypatch.setattr(
        render_performance,
        "get_render_performance",
        lambda: snapshot_calls.append(True) or performance,
    )
    monkeypatch.setattr(gui_premium_v7, "ThreadPoolExecutor", Pool)
    monkeypatch.setattr(gui_premium_v7, "WorkerThread", Worker)
    monkeypatch.setattr(
        gui_premium_v7.messagebox,
        "askyesno",
        lambda _title, message: confirmation_messages.append(message) or True,
    )
    monkeypatch.setattr(gui_premium_v7, "__file__", str(tmp_path / "gui_premium_v7.py"))
    app = _forge_app(tmp_path, completed)

    InstagramAutoPro.forge_process(app)
    worker_tasks[0]()

    assert snapshot_calls == [True]
    assert worker_counts == [2]
    assert "2 videos en paralelo" in confirmation_messages[0]
    assert any(
        "2 videos en paralelo" in configuration.get("text", "")
        for configuration in app.forge_pb_lbl.configurations
    )
    assert completed == ["one__c01.mp4", "two__c01.mp4"]
    assert [kwargs["ffmpeg_threads"] for kwargs in variant_kwargs] == [4, 4]
    assert app.db.saved_forge_rows == [
        ("one.mp4", "one__c01.mp4"),
        ("two.mp4", "two__c01.mp4"),
    ]
    assert [fp["video_hash"] for fp in app.db.saved_fingerprints] == [
        "one.mp4_1",
        "two.mp4_1",
    ]
    assert app.db.saved_tandas == [("Concurrent", "Concurrent", "Concurrent", None)]
    assert app.db.trial_tandas == [("Concurrent", False)]


def test_forge_variant_cpu_command_uses_snapshot_thread_budget(monkeypatch):
    params = {
        "crop_px": 2,
        "mirror": False,
        "zoom_pct": 1.0,
        "rotate_deg": 0.0,
        "brightness": 0.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "gamma": 1.0,
        "noise": 0,
        "speed": 1.0,
        "trim_start_ms": 0,
        "trim_end_ms": 0,
    }
    commands = []
    monkeypatch.setattr(metadata_pool, "_probe_video_info", lambda _path: (100, 100, 1.0, False))
    monkeypatch.setattr(metadata_pool, "generate_variant_params", lambda *_args, **_kwargs: params)
    monkeypatch.setattr(
        metadata_pool.subprocess,
        "run",
        lambda command, **_kwargs: commands.append(command) or SimpleNamespace(returncode=0),
    )

    metadata_pool.apply_variant_and_metadata(
        "source.mp4",
        "output.mp4",
        {
            "iphone_model": "iPhone 15",
            "lat": "+25.7617",
            "lon": "-080.1918",
            "ios_version": "18.0",
            "carrier": "T-Mobile",
        },
        ffmpeg_threads=3,
    )

    assert ["-threads", "3"] in [
        commands[0][index:index + 2] for index in range(len(commands[0]) - 1)
    ]
