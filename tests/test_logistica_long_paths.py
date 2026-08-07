import os

import pytest

from gui_premium_v7 import _copy_calendar_file, _windows_long_path


@pytest.mark.skipif(os.name != "nt", reason="Windows long-path regression test")
def test_copy_calendar_file_handles_windows_calendar_paths_over_260_chars(tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"video")

    dst = (
        tmp_path
        / ("Dia_1_" + "d" * 50)
        / ("TRIALS - " + ("evelyncutebbyh " * 4).strip())
        / ("video_" + "x" * 150 + ".mp4")
    )
    assert len(str(dst)) > 260

    _copy_calendar_file(src, dst)

    with open(_windows_long_path(dst), "rb") as fh:
        assert fh.read() == b"video"
