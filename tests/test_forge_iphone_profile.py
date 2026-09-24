"""Observable output contract for Forge's iPhone profile."""

import copy
import importlib
import subprocess

import pytest

from console_encoding import ffmpeg_tool_command, ffmpeg_tool_exists


def _probe(*, hdr=True, audio=True):
    video = {
        "index": 0,
        "codec_type": "video",
        "codec_name": "hevc",
        "codec_tag_string": "hvc1",
        "profile": "Main 10" if hdr else "Main",
        "pix_fmt": "yuv420p10le" if hdr else "yuv420p",
        "width": 720,
        "height": 1280,
        "avg_frame_rate": "24/1",
        "color_range": "tv",
        "color_primaries": "bt2020" if hdr else "bt709",
        "color_transfer": "arib-std-b67" if hdr else "bt709",
        "color_space": "bt2020nc" if hdr else "bt709",
    }
    streams = [video]
    if audio:
        streams.append({
            "index": 1,
            "codec_type": "audio",
            "codec_name": "aac",
            "profile": "LC",
            "sample_rate": "48000",
            "channels": 2,
            "channel_layout": "stereo",
        })
    return {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "tags": {"major_brand": "qt  "}},
        "streams": streams,
    }


def test_hlg_contract_accepts_matching_mov():
    profile = importlib.import_module("forge_iphone_profile")
    assert profile.validate_probe(_probe(), "iphone_hlg", expect_audio=True) == []


def test_hlg_contract_rejects_sdr_transfer_even_when_container_matches():
    profile = importlib.import_module("forge_iphone_profile")
    data = _probe()
    data["streams"][0]["color_transfer"] = "bt709"
    assert any("color_transfer" in problem for problem in profile.validate_probe(
        data, "iphone_hlg", expect_audio=True,
    ))


def test_sdr_contract_accepts_8bit_bt709_without_audio():
    profile = importlib.import_module("forge_iphone_profile")
    assert profile.validate_probe(_probe(hdr=False, audio=False), "iphone_sdr", expect_audio=False) == []


def test_contract_rejects_unexpected_data_tracks_and_wrong_audio_rate():
    profile = importlib.import_module("forge_iphone_profile")
    data = copy.deepcopy(_probe())
    data["streams"][1]["sample_rate"] = "32000"
    data["streams"].append({"index": 2, "codec_type": "data", "codec_tag_string": "mebx"})
    problems = profile.validate_probe(data, "iphone_hlg", expect_audio=True)
    assert any("sample_rate" in problem for problem in problems)
    assert any("data" in problem for problem in problems)


def test_contract_rejects_frame_rate_outside_24_fps_target():
    profile = importlib.import_module("forge_iphone_profile")
    data = _probe()
    data["streams"][0]["avg_frame_rate"] = "30/1"
    assert any("frame_rate" in problem for problem in profile.validate_probe(
        data, "iphone_hlg", expect_audio=True,
    ))


def test_probe_file_reads_a_real_video(tmp_path):
    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        pytest.skip("FFmpeg tools not installed")
    source = tmp_path / "source.mp4"
    subprocess.run([
        ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24", "-t", "0.25",
        "-c:v", "mpeg4", "-an", str(source),
    ], check=True, capture_output=True)

    profile = importlib.import_module("forge_iphone_profile")
    data = profile.probe_file(source)
    assert data["streams"][0]["codec_name"] == "mpeg4"
    assert float(data["format"]["duration"]) > 0


def test_runtime_capabilities_include_required_encoder_and_color_filter():
    if not ffmpeg_tool_exists("ffmpeg"):
        pytest.skip("FFmpeg not installed")
    profile = importlib.import_module("forge_iphone_profile")
    available = profile.runtime_capabilities()
    assert {"libx265", "aac", "zscale"} <= available
