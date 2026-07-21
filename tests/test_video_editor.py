from video_editor import _ratio_size, _xy, build_photo_video_pairs


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
