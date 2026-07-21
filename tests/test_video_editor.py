from types import MethodType, SimpleNamespace
from unittest.mock import patch

from video_editor import _ratio_size, _xy, build_photo_video_pairs
from gui_premium_v7 import InstagramAutoPro


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
            "Duración ms": value_entry(500), "Tamaño %": value_entry(25),
            "X %": value_entry(50), "Y %": value_entry(50),
            "Transparencia %": value_entry(100),
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
