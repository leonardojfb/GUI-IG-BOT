import os
import json
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
        self.saved_transform_logs = []

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

    def save_video_transform_log(self, *args, **kwargs):
        self.saved_transform_logs.append((args, kwargs))
        return len(self.saved_transform_logs)


def _forge_app(tmp_path, completed, video_names=None):
    video_names = video_names or ["one.mp4", "two.mp4"]
    videos = [tmp_path / name for name in video_names]
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
    assert len(app.db.saved_transform_logs) == 2
    assert app.db.saved_transform_logs[0][0][0] == "forge"
    assert app.db.saved_transform_logs[0][1]["tanda_name"] == "Concurrent"


def test_iphone_sdr_gui_publishes_mov_and_registers_only_validated_copies(monkeypatch, tmp_path):
    import subprocess
    import gui_premium_v7
    import forge_iphone_profile
    from console_encoding import ffmpeg_tool_command, ffmpeg_tool_exists

    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        import pytest
        pytest.skip("FFmpeg tools not installed")
    completed = []
    app = _forge_app(tmp_path, completed)

    class ValidatedDatabase(_Database):
        def save_forge_video(self, _tanda, source, output, _video_hash):
            assert (tmp_path / "videos_finales" / _tanda / output).is_file()
            self.saved_forge_rows.append((source, output))

        def save_metadata_fingerprints(self, fingerprints):
            assert len(self.saved_forge_rows) == len(fingerprints)
            self.saved_fingerprints = fingerprints

    app.db = ValidatedDatabase(completed)
    app.forge_profile_var = _Value("iPhone SDR")
    app.forge_efectos_var = _Value("Custom")
    app.forge_fx_vars = {key: _Value(False) for key in metadata_pool.DEFAULT_VARIANT_EFFECTS}
    app.forge_fuerza_var = _Value("Light")
    for path in app.forge_video_paths:
        subprocess.run([
            ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24:duration=0.5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            path,
        ], check=True, capture_output=True)
    tasks = []

    class Worker:
        def __init__(self, _app, _done, task):
            tasks.append(task)

        def start(self):
            pass

    monkeypatch.setattr(render_performance, "get_render_performance",
                        lambda: RenderPerformance(2, 2, 2, 2, None))
    monkeypatch.setattr(gui_premium_v7, "WorkerThread", Worker)
    monkeypatch.setattr(gui_premium_v7, "__file__", str(tmp_path / "gui_premium_v7.py"))
    monkeypatch.setattr(gui_premium_v7.messagebox, "askyesno", lambda *_args: True)
    real_render = forge_iphone_profile.render_validated_copy

    def check_processing_status(*args, **kwargs):
        status = json.loads((tmp_path / "videos_finales" / "Concurrent" /
                             "forge_batch_status.json").read_text(encoding="utf-8"))
        assert status["state"] == "processing"
        return real_render(*args, **kwargs)

    monkeypatch.setattr(forge_iphone_profile, "render_validated_copy", check_processing_status)
    InstagramAutoPro.forge_process(app)
    tasks[0]()
    assert [row[1] for row in app.db.saved_forge_rows] == ["one__c01.mov", "two__c01.mov"]
    for _source, name in app.db.saved_forge_rows:
        assert (tmp_path / "videos_finales" / "Concurrent" / name).is_file()


def test_iphone_batch_registers_successes_and_reports_incomplete_on_copy_failure(monkeypatch, tmp_path):
    import subprocess
    import gui_premium_v7
    import forge_iphone_profile
    from console_encoding import ffmpeg_tool_command, ffmpeg_tool_exists

    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        import pytest
        pytest.skip("FFmpeg tools not installed")
    app = _forge_app(tmp_path, [])

    class RecordingDatabase(_Database):
        def save_forge_video(self, _tanda, source, output, _video_hash):
            assert (tmp_path / "videos_finales" / _tanda / output).is_file()
            self.saved_forge_rows.append((source, output))

        def save_metadata_fingerprints(self, fingerprints):
            self.saved_fingerprints = fingerprints

    app.db = RecordingDatabase([])
    app.forge_profile_var = _Value("iPhone SDR")
    app.forge_efectos_var = _Value("Custom")
    app.forge_fx_vars = {key: _Value(False) for key in metadata_pool.DEFAULT_VARIANT_EFFECTS}
    app.forge_fuerza_var = _Value("Light")
    for path in app.forge_video_paths:
        subprocess.run([
            ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24:duration=0.5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709", path,
        ], check=True, capture_output=True)
    real_render = forge_iphone_profile.render_validated_copy

    def fail_second(source, *args, **kwargs):
        if os.path.basename(source) == "two.mp4":
            raise RuntimeError("fallo deliberado de la segunda copia")
        return real_render(source, *args, **kwargs)

    tasks = []

    class Worker:
        def __init__(self, _app, _done, task):
            tasks.append(task)

        def start(self):
            pass

    monkeypatch.setattr(forge_iphone_profile, "render_validated_copy", fail_second)
    monkeypatch.setattr(render_performance, "get_render_performance",
                        lambda: RenderPerformance(2, 2, 2, 2, None))
    monkeypatch.setattr(gui_premium_v7, "WorkerThread", Worker)
    monkeypatch.setattr(gui_premium_v7, "__file__", str(tmp_path / "gui_premium_v7.py"))
    monkeypatch.setattr(gui_premium_v7.messagebox, "askyesno", lambda *_args: True)
    InstagramAutoPro.forge_process(app)
    result = tasks[0]()
    assert "incompleta" in result.lower()
    assert app.db.saved_forge_rows == [("one.mp4", "one__c01.mov")]
    assert not (tmp_path / "videos_finales" / "Concurrent" / "two__c01.mov").exists()
    status_path = tmp_path / "videos_finales" / "Concurrent" / "forge_batch_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["state"] == "incomplete"
    assert [item["output_name"] for item in status["pending"]] == ["two__c01.mov"]

    class PreviewTree:
        def __init__(self):
            self.rows = []

        def get_children(self):
            return []

        def delete(self, *_args):
            pass

        def insert(self, _parent, _position, **kwargs):
            self.rows.append(kwargs["values"])

    app.forge_tree = PreviewTree()
    InstagramAutoPro.forge_preview_metadata(app)
    assert app.forge_meta_assignments == [status["pending"][0]["meta"]]
    assert len(app.forge_tree.rows) == 1

    monkeypatch.setattr(forge_iphone_profile, "render_validated_copy", real_render)
    InstagramAutoPro.forge_process(app)
    result = tasks[1]()
    assert "complet" in result.lower()
    assert app.db.saved_forge_rows == [
        ("one.mp4", "one__c01.mov"), ("two.mp4", "two__c01.mov")]
    assert json.loads(status_path.read_text(encoding="utf-8"))["state"] == "complete"


def test_forge_preserves_edited_video_identity_in_output_names(monkeypatch, tmp_path):
    import gui_premium_v7

    completed = []
    worker_tasks = []
    performance = RenderPerformance(2, 2, 4, 8, None)

    def apply_variant(_source, output, _meta, **_kwargs):
        completed.append(os.path.basename(output))
        return {}

    class Worker:
        def __init__(self, _app, _done, task):
            worker_tasks.append(task)

        def start(self):
            pass

    monkeypatch.setattr(metadata_pool, "apply_variant_and_metadata", apply_variant)
    monkeypatch.setattr(metadata_pool, "get_video_hash", lambda source: os.path.basename(source))
    monkeypatch.setattr(render_performance, "get_render_performance", lambda: performance)
    monkeypatch.setattr(gui_premium_v7, "WorkerThread", Worker)
    monkeypatch.setattr(gui_premium_v7.messagebox, "askyesno", lambda *_args: True)
    monkeypatch.setattr(gui_premium_v7, "__file__", str(tmp_path / "gui_premium_v7.py"))
    app = _forge_app(
        tmp_path,
        completed,
        video_names=[
            "PROMO EVE__Output 14__foto05_editado.mp4",
            "PROMO EVE__Output 14__foto06_editado.mp4",
        ],
    )

    InstagramAutoPro.forge_process(app)
    worker_tasks[0]()

    assert completed == [
        "PROMO EVE__Output 14__foto05_editado__c01.mp4",
        "PROMO EVE__Output 14__foto06_editado__c01.mp4",
    ]
    assert app.db.saved_forge_rows == [
        (
            "PROMO EVE__Output 14__foto05_editado.mp4",
            "PROMO EVE__Output 14__foto05_editado__c01.mp4",
        ),
        (
            "PROMO EVE__Output 14__foto06_editado.mp4",
            "PROMO EVE__Output 14__foto06_editado__c01.mp4",
        ),
    ]


def test_forge_logs_exact_variant_params_after_success(tmp_path):
    import gui_premium_v7
    from database import DatabaseManager

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    src = tmp_path / "input.mp4"
    out = tmp_path / "videos_finales" / "TANDA" / "input__c01.mp4"
    src.write_bytes(b"input")
    out.parent.mkdir(parents=True)
    out.write_bytes(b"out")

    log_id = gui_premium_v7._save_forge_transform_log(
        db,
        process_kind="forge",
        source_path=str(src),
        output_path=str(out),
        tanda_name="TANDA",
        source_identity="fingerprint",
        params={
            "crop_px": 2,
            "mirror": False,
            "zoom_pct": 0.004,
            "rotate_deg": 0.8,
            "brightness": 0.01,
            "contrast": 1.01,
            "saturation": 0.99,
            "gamma": 1.0,
            "noise": 0.002,
            "speed": 1.003,
            "trim_start_ms": 2,
            "trim_end_ms": 0,
        },
        meta={"model": "iPhone 15 Pro"},
    )

    rows = db.list_video_transform_logs()
    assert rows[0]["id"] == log_id
    assert rows[0]["process_kind"] == "forge"
    details = json.loads(rows[0]["details_json"])
    assert details["rotate_deg"] == 0.8
    assert details["crop_px"] == 2
    assert details["speed"] == 1.003
    assert details["iphone_metadata"]["model"] == "iPhone 15 Pro"
    db.close()


def test_forge_variant_uses_high_profile_libx264_and_strips_ffmpeg_encoder_tags(monkeypatch):
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
    def run(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(metadata_pool.subprocess, "run", run)

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

    assert len(commands) == 1
    assert commands[0][commands[0].index("-c:v") + 1] == "libx264"
    assert "h264_nvenc" not in commands[0]
    assert ["-profile:v", "high"] in [
        commands[0][index:index + 2] for index in range(len(commands[0]) - 1)
    ]
    assert ["-threads", "3"] in [
        commands[0][index:index + 2] for index in range(len(commands[0]) - 1)
    ]
    assert ["-map_metadata", "-1"] in [
        commands[0][index:index + 2] for index in range(len(commands[0]) - 1)
    ]
    assert ["-metadata", "encoder="] in [
        commands[0][index:index + 2] for index in range(len(commands[0]) - 1)
    ]
    assert ["-metadata:s:v:0", "encoder="] in [
        commands[0][index:index + 2] for index in range(len(commands[0]) - 1)
    ]


def test_forge_variant_normalizes_square_pixels_and_compatible_pix_fmt(monkeypatch):
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
    monkeypatch.setattr(metadata_pool, "_probe_video_info", lambda _path: (1080, 1920, 1.0, False))
    monkeypatch.setattr(metadata_pool, "generate_variant_params", lambda *_args, **_kwargs: params)

    def run(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(metadata_pool.subprocess, "run", run)

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
    )

    vf = commands[0][commands[0].index("-vf") + 1]
    assert vf.endswith("crop=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1")
    assert ["-pix_fmt", "yuv420p"] in [
        commands[0][index:index + 2] for index in range(len(commands[0]) - 1)
    ]
