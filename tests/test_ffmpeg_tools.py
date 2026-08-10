from pathlib import Path

import ffmpeg_tools


def test_tool_command_prefers_bundled_windows_binary(tmp_path, monkeypatch):
    bundled_bin = tmp_path / "tools" / "ffmpeg" / "bin"
    bundled_bin.mkdir(parents=True)
    ffmpeg_path = bundled_bin / "ffmpeg.exe"
    ffmpeg_path.write_bytes(b"binary")
    monkeypatch.setattr(ffmpeg_tools, "APP_DIR", tmp_path)

    assert ffmpeg_tools.tool_command("ffmpeg") == str(ffmpeg_path)


def test_tool_command_falls_back_to_path_name_when_bundled_binary_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_tools, "APP_DIR", tmp_path)

    assert ffmpeg_tools.tool_command("ffprobe") == "ffprobe"


def test_ffmpeg_and_ffprobe_helpers_return_expected_commands(tmp_path, monkeypatch):
    bundled_bin = tmp_path / "tools" / "ffmpeg" / "bin"
    bundled_bin.mkdir(parents=True)
    ffmpeg_path = bundled_bin / "ffmpeg.exe"
    ffprobe_path = bundled_bin / "ffprobe.exe"
    ffmpeg_path.write_bytes(b"binary")
    ffprobe_path.write_bytes(b"binary")
    monkeypatch.setattr(ffmpeg_tools, "APP_DIR", tmp_path)

    assert ffmpeg_tools.ffmpeg_command() == str(ffmpeg_path)
    assert ffmpeg_tools.ffprobe_command() == str(ffprobe_path)
