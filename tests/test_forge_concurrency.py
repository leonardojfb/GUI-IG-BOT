import os
import json
import hashlib
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
        self.reserved = {}
        self.next_reservation_id = 1

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

    def used_variant_signatures(self, vault_asset_id, process_kind):
        return {
            signature
            for (asset_id, kind, signature), _reservation_id in self.reserved.items()
            if asset_id == vault_asset_id and kind == process_kind
        }

    def reserve_forge_variant_signature(self, vault_asset_id, process_kind, variant_signature, _params, run_id=None):
        key = (vault_asset_id, process_kind, variant_signature)
        if key in self.reserved:
            return None
        reservation_id = self.next_reservation_id
        self.next_reservation_id += 1
        self.reserved[key] = reservation_id
        return reservation_id

    def release_forge_variant_reservation(self, reservation_id):
        for key, value in list(self.reserved.items()):
            if value == reservation_id:
                del self.reserved[key]

    def complete_forge_variant_reservation(self, _reservation_id, _transform_log_id):
        pass


def _forge_app(tmp_path, completed, video_names=None):
    video_names = video_names or ["one.mp4", "two.mp4"]
    videos = [tmp_path / name for name in video_names]
    for video in videos:
        video.touch()
    vault_assets = [
        {
            "id": idx,
            "asset_hash": hashlib.sha256(video.read_bytes()).hexdigest(),
            "source_path": str(video),
            "display_name": video.name,
        }
        for idx, video in enumerate(videos, start=1)
    ]
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
        forge_vault_assets=vault_assets,
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


def test_forge_variant_prefers_nvenc_and_falls_back_to_cpu_thread_budget(monkeypatch):
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
        return SimpleNamespace(returncode=0 if len(commands) == 2 else 1, stderr=b"nvenc failed")

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

    assert commands[0][commands[0].index("-c:v") + 1] == "h264_nvenc"
    assert commands[1][commands[1].index("-c:v") + 1] == "libx264"
    assert ["-threads", "3"] in [
        commands[1][index:index + 2] for index in range(len(commands[1]) - 1)
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
