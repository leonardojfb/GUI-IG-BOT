from pathlib import Path
import subprocess
from types import MethodType, SimpleNamespace
from unittest.mock import patch

import pytest

import video_editor
from video_editor import _ratio_size, _xy, build_photo_video_pairs, render_video
from gui_premium_v7 import InstagramAutoPro


DURATION_LABEL = "Duraci\u00f3n ms"
SIZE_LABEL = "Tama\u00f1o %"
X_LABEL = "X %"
Y_LABEL = "Y %"
OPACITY_LABEL = "Transparencia %"


class _FakeEntry:
    def __init__(self, value):
        self.value = str(value)

    def get(self):
        return self.value

    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _index, value):
        self.value = str(value)


class _FakeSlider:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def configure(self, **_kwargs):
        pass

    def set(self, value):
        self.value = value


class _FakeCombo(_FakeSlider):
    def __init__(self, value, values=()):
        super().__init__(value)
        self.values = list(values)

    def configure(self, **kwargs):
        if "values" in kwargs:
            self.values = list(kwargs["values"])


class _FakeGuiWidget(_FakeEntry):
    def __init__(self, *_args, text="", **_kwargs):
        super().__init__("")
        self.text = text
        self.grid_calls = []
        self.destroyed = False

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]

    def grid(self, **kwargs):
        self.grid_calls.append(kwargs)

    def grid_columnconfigure(self, *_args, **_kwargs):
        pass

    def pack(self, **_kwargs):
        pass

    def destroy(self):
        self.destroyed = True

    def set(self, value):
        self.value = str(value)


def _editor_fake(video_paths, timeline_fps=60, timeline_frame=299, photo_paths=("a.png", "b.png")):
    def value_entry(value):
        return _FakeEntry(value)

    def photo_row(photo):
        return {
            "photo": value_entry(photo),
            "manual_var": SimpleNamespace(get=lambda: False),
            "Frame": value_entry(0),
            DURATION_LABEL: value_entry(500),
            SIZE_LABEL: value_entry(25),
            X_LABEL: value_entry(50),
            Y_LABEL: value_entry(50),
            OPACITY_LABEL: value_entry(100),
            "ratio": SimpleNamespace(get=lambda: "9:16"),
            "position": SimpleNamespace(get=lambda: "Manual X/Y"),
        }

    fake = SimpleNamespace(
        editor_video_paths=video_paths,
        editor_rows=[photo_row(photo) for photo in photo_paths],
        editor_global_enabled=SimpleNamespace(get=lambda: True),
        editor_global_entries={
            DURATION_LABEL: value_entry(500), SIZE_LABEL: value_entry(25),
            X_LABEL: value_entry(50), Y_LABEL: value_entry(50),
            OPACITY_LABEL: value_entry(100),
        },
        editor_global_ratio=SimpleNamespace(get=lambda: "9:16"),
        editor_global_position=SimpleNamespace(get=lambda: "Manual X/Y"),
        editor_timeline_info={"duration": 10, "fps": timeline_fps},
        editor_timeline_slider=_FakeSlider(timeline_frame),
        editor_timeline_changed=lambda _frame: None,
        editor_video_info={
            path: {"duration": 10, "fps": 24 if index == 0 else 60}
            for index, path in enumerate(video_paths)
        },
        editor_timeline_map={"Timeline": video_paths[0]},
        editor_timeline_video=_FakeCombo("Timeline"),
        editor_status=SimpleNamespace(configure=lambda **_kwargs: None),
    )
    fake._editor_photo_video_batch_enabled = MethodType(
        InstagramAutoPro._editor_photo_video_batch_enabled, fake)
    fake._editor_update_timeline_range = MethodType(
        InstagramAutoPro._editor_update_timeline_range, fake)
    fake._editor_read_overlay_config = MethodType(
        InstagramAutoPro._editor_read_overlay_config, fake)
    fake._editor_collect = MethodType(InstagramAutoPro._editor_collect, fake)
    fake._editor_cartesian_batch = MethodType(InstagramAutoPro._editor_cartesian_batch, fake)
    def unchanged_overlays(_self, _source, overlays):
        return overlays

    fake._editor_overlays_for_source = MethodType(
        getattr(InstagramAutoPro, "_editor_overlays_for_source", unchanged_overlays), fake)
    return fake


def test_timestamp_to_source_frame_converts_shared_60fps_moment_for_24fps_video():
    timestamp = 299 / 60

    assert timestamp < 5
    assert video_editor.timestamp_to_source_frame(timestamp, 24) == 120


def test_editor_preview_converts_shared_timestamp_to_the_preview_source_fps():
    fake = _editor_fake(["v24.mp4", "v60.mp4"])
    workers = []

    class CapturingWorker:
        def __init__(self, _app, _done, task):
            workers.append(task)

        def start(self):
            pass

    with patch("gui_premium_v7.os.path.isfile", return_value=True), patch(
        "gui_premium_v7.WorkerThread", CapturingWorker
    ), patch("video_editor.render_preview", return_value=("preview.png", 1.0)) as preview:
        InstagramAutoPro.editor_preview(fake)
        workers[0]()

    preview.assert_called_once()
    assert preview.call_args.args[1][0]["frame"] == 120


def test_editor_render_converts_shared_timestamp_for_every_source_fps(tmp_path):
    fake = _editor_fake(["v24.mp4", "v60.mp4"])
    jobs = []

    def capture_jobs(_self, planned_jobs):
        jobs.extend(planned_jobs)
        return "scheduled"

    fake._editor_render_batch = MethodType(capture_jobs, fake)
    with patch("gui_premium_v7.os.path.isfile", return_value=True), patch(
        "gui_premium_v7.os.path.exists", return_value=False
    ), patch("gui_premium_v7.filedialog.askdirectory", return_value=str(tmp_path)):
        assert InstagramAutoPro.editor_render(fake) == "scheduled"

    assert [job[2][0]["frame"] for job in jobs] == [120, 299, 120, 299]
    assert [row["Frame"].get() for row in fake.editor_rows] == ["299", "299"]


def test_editor_accepts_zero_size_as_an_invisible_overlay_and_keeps_100_percent():
    def config(size):
        entries = {
            DURATION_LABEL: _FakeEntry(500), SIZE_LABEL: _FakeEntry(size),
            X_LABEL: _FakeEntry(50), Y_LABEL: _FakeEntry(50),
            OPACITY_LABEL: _FakeEntry(100),
        }
        return InstagramAutoPro._editor_read_overlay_config(
            None, entries, SimpleNamespace(get=lambda: "9:16"),
            SimpleNamespace(get=lambda: "Manual X/Y"), 0, "la configuración global",
        )

    zero = config(0)
    full = config(100)

    assert zero["size"] == 0
    assert video_editor._overlay_geometry({"width": 1080, "height": 1920, "fps": 30}, zero)["opacity"] == 0
    assert full["size"] == 100


def test_editor_collect_reports_every_selected_video_that_disappeared():
    fake = _editor_fake(["available.mp4", "missing.mp4"])

    with patch("gui_premium_v7.os.path.isfile", side_effect=lambda path: path != "missing.mp4"):
        with pytest.raises(ValueError, match="missing\\.mp4"):
            InstagramAutoPro._editor_collect(fake)


@pytest.mark.parametrize("error", [FileNotFoundError("ffmpeg"), OSError("access denied")])
def test_run_turns_missing_executable_and_os_errors_into_actionable_runtime_errors(error):
    with patch("video_editor.subprocess.run", side_effect=error):
        with pytest.raises(RuntimeError, match="No se pudo iniciar.*FFmpeg/FFprobe"):
            video_editor._run(["ffmpeg", "-version"])


def test_probe_video_error_includes_stderr_and_source_path():
    result = SimpleNamespace(returncode=1, stdout="", stderr="invalid video stream")

    with patch("video_editor._run", return_value=result):
        with pytest.raises(RuntimeError) as error:
            video_editor.probe_video("broken-source.mp4")

    assert "broken-source.mp4" in str(error.value)
    assert "invalid video stream" in str(error.value)


def test_editor_collect_clamps_typed_multi_photo_video_timeline_to_five_seconds():
    def value_entry(value):
        return _FakeEntry(value)

    def photo_row(photo):
        return {
            "photo": value_entry(photo),
            "manual_var": SimpleNamespace(get=lambda: False),
            "Frame": value_entry(0),
        }

    fake = SimpleNamespace(
        editor_video_paths=["v1.mp4", "v2.mp4"],
        editor_rows=[photo_row("a.png"), photo_row("b.png")],
        editor_global_enabled=SimpleNamespace(get=lambda: True),
        editor_global_entries={
            DURATION_LABEL: value_entry(500), SIZE_LABEL: value_entry(25),
            X_LABEL: value_entry(50), Y_LABEL: value_entry(50),
            OPACITY_LABEL: value_entry(100),
        },
        editor_global_ratio=SimpleNamespace(get=lambda: "9:16"),
        editor_global_position=SimpleNamespace(get=lambda: "Manual X/Y"),
        editor_timeline_info={"duration": 10, "fps": 30},
        editor_timeline_slider=_FakeSlider(200),
        editor_timeline_changed=lambda _frame: None,
    )
    fake._editor_photo_video_batch_enabled = MethodType(
        InstagramAutoPro._editor_photo_video_batch_enabled, fake)
    fake._editor_update_timeline_range = MethodType(
        InstagramAutoPro._editor_update_timeline_range, fake)
    fake._editor_read_overlay_config = MethodType(
        InstagramAutoPro._editor_read_overlay_config, fake)

    with patch("gui_premium_v7.os.path.isfile", return_value=True):
        _videos, overlays = InstagramAutoPro._editor_collect(fake)

    assert [overlay["frame"] for overlay in overlays] == [149, 149]
    assert fake.editor_timeline_slider.get() == 149


def test_editor_treats_any_multi_pair_selection_as_a_batch():
    method = InstagramAutoPro._editor_cartesian_batch
    assert method(None, ["v.mp4"], [{"photo": "a.png"}, {"photo": "b.png"}])
    assert method(None, ["v1.mp4", "v2.mp4"], [{"photo": "a.png"}])
    assert not method(None, ["v.mp4"], [{"photo": "a.png"}])


def test_manual_timeline_target_overrides_global_frame_for_target_apply_and_preview():
    fake = _editor_fake(["v.mp4"], timeline_frame=11)
    fake.editor_rows[0]["Frame"] = _FakeEntry(12)
    fake.editor_rows[1]["Frame"] = _FakeEntry(73)
    fake.editor_rows[1]["manual_var"] = SimpleNamespace(get=lambda: True)
    fake.editor_timeline_target = _FakeCombo("Foto 2", ["Foto 1", "Foto 2"])
    fake.editor_timeline_target_changed = MethodType(
        InstagramAutoPro.editor_timeline_target_changed, fake)
    fake._editor_timeline_item = MethodType(InstagramAutoPro._editor_timeline_item, fake)
    fake.editor_apply_timeline_frame = MethodType(
        InstagramAutoPro.editor_apply_timeline_frame, fake)
    workers = []

    class CapturingWorker:
        def __init__(self, _app, _done, task):
            workers.append(task)

        def start(self):
            pass

    InstagramAutoPro.editor_timeline_target_changed(fake, "Foto 2")
    assert fake.editor_timeline_slider.get() == 73

    fake.editor_timeline_slider.set(91)
    InstagramAutoPro.editor_apply_timeline_frame(fake)

    with patch("gui_premium_v7.os.path.isfile", return_value=True), patch(
        "gui_premium_v7.WorkerThread", CapturingWorker
    ), patch("video_editor.render_preview", return_value=("preview.png", 91 / 60)) as preview:
        InstagramAutoPro.editor_preview_timeline(fake)
        workers[0]()

    assert fake.editor_rows[0]["Frame"].get() == "12"
    assert fake.editor_rows[1]["Frame"].get() == "91"
    assert preview.call_args.args[1][0]["photo"] == "b.png"
    assert preview.call_args.kwargs["timestamp"] == 91 / 60


def test_multi_video_multi_photo_timeline_stays_shared_for_all_rows():
    fake = _editor_fake(["v1.mp4", "v2.mp4"], timeline_frame=91)
    fake.editor_rows[1]["manual_var"] = SimpleNamespace(get=lambda: True)
    fake.editor_rows[1]["Frame"] = _FakeEntry(73)
    fake.editor_timeline_target = _FakeCombo("Foto 2", ["Foto 1", "Foto 2"])
    fake._editor_timeline_item = MethodType(InstagramAutoPro._editor_timeline_item, fake)

    InstagramAutoPro.editor_timeline_target_changed(fake, "Foto 2")
    InstagramAutoPro.editor_apply_timeline_frame(fake)

    assert fake.editor_timeline_slider.get() == 91
    assert [row["Frame"].get() for row in fake.editor_rows] == ["91", "91"]


def test_editor_rows_reindex_labels_and_grid_rows_after_middle_remove_then_add():
    labels = []

    def label_factory(*args, **kwargs):
        label = _FakeGuiWidget(*args, **kwargs)
        labels.append(label)
        return label

    first, middle, third = (_FakeGuiWidget() for _ in range(3))
    first_label = _FakeGuiWidget(text="Foto 1")
    middle_label = _FakeGuiWidget(text="Foto 2")
    third_label = _FakeGuiWidget(text="Foto 3")
    for row, grid_row in zip((first, middle, third), (2, 3, 4)):
        row.grid(row=grid_row)
    fake = SimpleNamespace(
        editor_rows_frame=_FakeGuiWidget(),
        editor_rows=[
            {"frame": first, "label": first_label},
            {"frame": middle, "label": middle_label},
            {"frame": third, "label": third_label},
        ],
        _editor_refresh_timeline_targets=lambda: None,
        _editor_refresh_config_modes=lambda: None,
        _editor_update_timeline_range=lambda: None,
    )
    fake._editor_reindex_rows = MethodType(InstagramAutoPro._editor_reindex_rows, fake)
    fake_ctk = SimpleNamespace(
        CTkFrame=_FakeGuiWidget,
        CTkLabel=label_factory,
        CTkEntry=_FakeGuiWidget,
        CTkButton=_FakeGuiWidget,
        CTkSwitch=_FakeGuiWidget,
        CTkComboBox=_FakeGuiWidget,
        CTkSlider=_FakeGuiWidget,
        CTkFont=lambda **_kwargs: None,
    )

    with patch("gui_premium_v7.ctk", fake_ctk), patch(
        "gui_premium_v7.tk.BooleanVar", return_value=SimpleNamespace(get=lambda: False)
    ):
        InstagramAutoPro.editor_remove_row(fake, middle)
        InstagramAutoPro.editor_add_row(fake)

    photo_labels = [first_label, third_label, *[label for label in labels if label.text.startswith("Foto ")]]
    assert [label.text for label in photo_labels] == ["Foto 1", "Foto 2", "Foto 3"]
    assert [item["frame"].grid_calls[-1]["row"] for item in fake.editor_rows] == [2, 3, 4]


def test_render_video_error_names_render_paths_and_bounded_stderr(tmp_path, monkeypatch):
    stderr = "discard-this-prefix-" + "x" * 1900 + "render-tail"
    result = SimpleNamespace(returncode=1, stderr=stderr)
    photo = tmp_path / "photo.png"
    photo.write_bytes(b"fake image")
    monkeypatch.setattr(video_editor, "_OVERLAY_CACHE_DIR", tmp_path / "cache")

    def run(command):
        if "-frames:v" in command:
            Path(command[-1]).write_bytes(b"prepared")
            return SimpleNamespace(returncode=0, stderr="")
        return result

    with patch("video_editor.probe_video", return_value={"width": 100, "height": 100, "fps": 30, "duration": 1}), patch(
        "video_editor._run", side_effect=run
    ):
        with pytest.raises(RuntimeError) as error:
            render_video("source.mp4", "rendered.mp4", [{"photo": str(photo), "frame": 0, "duration_ms": 100,
                                                         "size": 25, "ratio": "1:1", "position": "Centro",
                                                         "x": 50, "y": 50, "opacity": 100}])

    text = str(error.value)
    assert "render" in text.lower()
    assert "source.mp4" in text and "rendered.mp4" in text
    assert "render-tail" in text and "discard-this-prefix-" not in text


def test_render_preview_error_names_preview_input_and_bounded_stderr():
    stderr = "discard-this-prefix-" + "x" * 1900 + "preview-tail"
    result = SimpleNamespace(returncode=1, stderr=stderr)

    with patch("video_editor.probe_video", return_value={"width": 100, "height": 100, "fps": 30, "duration": 1}), patch(
        "video_editor._run", return_value=result
    ):
        with pytest.raises(RuntimeError) as error:
            video_editor.render_preview("source.mp4", [], output_path="preview.png", timestamp=0)

    text = str(error.value)
    assert "preview" in text.lower()
    assert "source.mp4" in text
    assert "preview-tail" in text and "discard-this-prefix-" not in text


@pytest.mark.parametrize(
    ("video_paths", "photo_paths", "expected_frame"),
    [
        (["v1.mp4", "v2.mp4"], ("a.png", "b.png"), 149),
        (["v1.mp4"], ("a.png", "b.png"), 400),
        (["v1.mp4", "v2.mp4"], ("a.png",), 400),
        (["v1.mp4"], ("a.png",), 400),
    ],
)
def test_editor_collect_only_clamps_typed_frames_for_multi_video_multi_photo(
    video_paths, photo_paths, expected_frame,
):
    fake = _editor_fake(
        video_paths, timeline_fps=30, timeline_frame=200, photo_paths=photo_paths,
    )
    for row in fake.editor_rows:
        row["Frame"] = _FakeEntry(400)
        row["manual_var"] = SimpleNamespace(get=lambda: True)

    with patch("gui_premium_v7.os.path.isfile", return_value=True):
        _videos, overlays = InstagramAutoPro._editor_collect(fake)

    assert [overlay["frame"] for overlay in overlays] == [expected_frame] * len(photo_paths)
    assert [row["Frame"].get() for row in fake.editor_rows] == [str(expected_frame)] * len(photo_paths)


@pytest.mark.parametrize(("field", "value"), [(X_LABEL, 101), (Y_LABEL, -1)])
def test_editor_rejects_typed_xy_values_outside_slider_range(field, value):
    entries = {
        DURATION_LABEL: _FakeEntry(500), SIZE_LABEL: _FakeEntry(25),
        X_LABEL: _FakeEntry(50), Y_LABEL: _FakeEntry(50), OPACITY_LABEL: _FakeEntry(100),
    }
    entries[field] = _FakeEntry(value)

    with pytest.raises(ValueError):
        InstagramAutoPro._editor_read_overlay_config(
            None, entries, SimpleNamespace(get=lambda: "9:16"),
            SimpleNamespace(get=lambda: "Manual X/Y"), 0, "la Foto 1",
        )


def test_pairs_one_video_many_photos():
    assert build_photo_video_pairs(["v.mp4"], [{"photo": "a.png"}, {"photo": "b.png"}]) == [
        ("v.mp4", {"photo": "a.png"}, 1),
        ("v.mp4", {"photo": "b.png"}, 2),
    ]


def test_pairs_many_videos_one_photo():
    assert build_photo_video_pairs(["v1.mp4", "v2.mp4"], [{"photo": "a.png"}]) == [
        ("v1.mp4", {"photo": "a.png"}, 1),
        ("v2.mp4", {"photo": "a.png"}, 1),
    ]


def test_pairs_are_photo_major():
    pairs = build_photo_video_pairs(["v1.mp4", "v2.mp4"], [{"photo": "a.png"}, {"photo": "b.png"}])
    assert [(video, overlay["photo"], index) for video, overlay, index in pairs] == [
        ("v1.mp4", "a.png", 1), ("v2.mp4", "a.png", 1),
        ("v1.mp4", "b.png", 2), ("v2.mp4", "b.png", 2),
    ]


def test_render_reuses_prepared_overlay_for_same_photo_config_and_resolution(monkeypatch, tmp_path):
    photo = tmp_path / "photo.png"
    photo.write_bytes(b"fake image")
    monkeypatch.setattr(video_editor, "_OVERLAY_CACHE_DIR", tmp_path / "cache", raising=False)
    monkeypatch.setattr(
        video_editor,
        "probe_video",
        lambda _path: {"duration": 1.0, "width": 1080, "height": 1920, "fps": 30},
    )
    commands = []

    def run(command):
        commands.append(command)
        if "-frames:v" in command:
            Path(command[-1]).write_bytes(b"prepared")
        return SimpleNamespace(returncode=0, stderr="")

    overlay = {
        "photo": str(photo),
        "frame": 0,
        "duration_ms": 250,
        "size": 25,
        "x": 50,
        "y": 50,
        "opacity": 80,
        "ratio": "9:16",
        "position": "Manual X/Y",
    }
    monkeypatch.setattr(video_editor, "_run", run)

    render_video("source-a.mp4", str(tmp_path / "a.mp4"), [overlay])
    render_video("source-b.mp4", str(tmp_path / "b.mp4"), [overlay])

    prepare_commands = [command for command in commands if "-frames:v" in command]
    render_commands = [command for command in commands if "-filter_complex" in command]
    prepared_inputs = [
        command[command.index("-loop") + 3]
        for command in render_commands
    ]
    assert len(prepare_commands) == 1
    assert len(render_commands) == 2
    assert prepared_inputs[0] == prepared_inputs[1]
    assert prepared_inputs[0] != str(photo)


def test_run_bounds_timeout_and_reports_external_process_timeout():
    command = ["ffmpeg", "-version"]
    with patch(
        "video_editor.subprocess.run",
        side_effect=subprocess.TimeoutExpired(command, 60),
    ) as run:
        with pytest.raises(RuntimeError, match="super[oó] el tiempo"):
            video_editor._run(command)

    assert run.call_args.kwargs["timeout"] > 0


@pytest.mark.parametrize("video_count,photo_count,expected", [(1, 3, 3), (3, 1, 3), (2, 2, 4)])
def test_pair_count_equals_photo_times_video(video_count, photo_count, expected):
    videos = [f"v{index}.mp4" for index in range(video_count)]
    overlays = [{"photo": f"p{index}.png"} for index in range(photo_count)]

    assert len(build_photo_video_pairs(videos, overlays)) == expected


def test_cartesian_smoke_renders_one_file_per_pair(tmp_path):
    videos = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    photos = [tmp_path / "a.png", tmp_path / "b.png"]
    for color, video in zip(("black", "white"), videos):
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=160x240:r=10", "-t", "1", str(video)],
            check=True,
            capture_output=True,
            timeout=15,
        )
    for color, photo in zip(("red", "blue"), photos):
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=60x100", "-frames:v", "1", str(photo)],
            check=True,
            capture_output=True,
            timeout=15,
        )
    overlays = [
        {
            "photo": str(photo), "frame": 0, "duration_ms": 250, "size": 25,
            "x": 50, "y": 50, "opacity": 100, "ratio": "9:16",
            "position": "Manual X/Y",
        }
        for photo in photos
    ]
    outputs = []
    for source, overlay, index in build_photo_video_pairs([str(video) for video in videos], overlays):
        output = tmp_path / f"{Path(source).stem}_foto{index:02d}.mp4"
        render_video(source, str(output), [overlay])
        outputs.append(output)

    assert len(outputs) == 4 and all(output.stat().st_size > 0 for output in outputs)


def test_full_size_covers_the_complete_video_frame():
    overlay_width, overlay_height = _ratio_size(1080, 1920, 100, "9:16")

    assert (overlay_width, overlay_height) == (1080, 1920)


def test_full_size_covers_video_even_with_a_different_selected_ratio():
    overlay_width, overlay_height = _ratio_size(1080, 1920, 100, "1:1")

    assert overlay_width >= 1080
    assert overlay_height >= 1920


def test_manual_xy_percentages_describe_the_placement_range():
    assert _xy(100, 200, 40, 80, "Manual X/Y", 0, 0) == (0, 0)
    assert _xy(100, 200, 40, 80, "Manual X/Y", 50, 50) == (30, 60)
    assert _xy(100, 200, 40, 80, "Manual X/Y", 100, 100) == (60, 120)


def test_manual_xy_centers_an_overlay_larger_than_the_video():
    assert _xy(100, 200, 140, 300, "Manual X/Y", 50, 50) == (-20, -50)
