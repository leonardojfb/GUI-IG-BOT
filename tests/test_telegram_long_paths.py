from types import SimpleNamespace
import os
import tempfile

import organizadortg


def test_send_video_to_topic_handles_calendar_paths_over_260_chars(tmp_path, monkeypatch):
    long_name = "nested_" + ("x" * 120)
    calendar_dir = tmp_path / long_name / long_name
    filename = (
        "07C1K197bpvOfnIn1A0XwHhx_1785360012_00001_EAID_foto02_editado__c01__"
        "TANDA_SUICIDE_DE_MIERDA_NOJODA_ME_TIENE_ARRECHO_ESTA_MIERDA__"
        "ACC97__D1__S1.mp4"
    )
    video_path = calendar_dir / filename
    os.makedirs(organizadortg._windows_long_path(calendar_dir))
    with open(organizadortg._windows_long_path(video_path), "wb") as fh:
        fh.write(b"fake-video")

    normal_path = str(video_path)
    assert len(normal_path) > 260

    posted = []

    def fake_post(url, data, files):
        assert url.endswith("/sendDocument")
        _filename, handle, content_type = files["document"]
        assert handle.read() == b"fake-video"
        assert content_type == "application/octet-stream"
        assert data["disable_content_type_detection"] == "true"
        posted.append((url, dict(data)))
        return SimpleNamespace(status_code=200, text="ok")

    monkeypatch.setattr(organizadortg.requests, "post", fake_post)
    ok, topic_id = organizadortg._send_video_to_topic(
        "-1001",
        123,
        "caption",
        normal_path,
        {},
        "evexpeachyy",
        "SPAM",
    )

    assert ok is True
    assert topic_id == 123
    assert posted


def test_send_video_to_topic_recompresses_from_original_after_413(tmp_path, monkeypatch):
    original_video = tmp_path / "large-original.mp4"
    original_video.write_bytes(b"original")
    readable_original = organizadortg._windows_long_path(original_video)

    temp_paths = []
    compress_inputs = []
    real_getsize = os.path.getsize

    def make_temp_video(contents):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tmp.write(contents)
        tmp.close()
        temp_paths.append(tmp.name)
        return tmp.name

    def fake_getsize(path):
        if os.fspath(path) in {str(original_video), readable_original}:
            return organizadortg.TG_MAX_BYTES + 1
        return real_getsize(path)

    def fake_compress(path, target_bytes=None):
        compress_inputs.append((os.fspath(path), target_bytes))
        if len(compress_inputs) == 1:
            return make_temp_video(b"first-compressed")
        return make_temp_video(b"second-compressed")

    responses = [
        SimpleNamespace(status_code=413, text="Request Entity Too Large"),
        SimpleNamespace(status_code=200, text="ok"),
    ]

    def fake_post(url, data, files):
        return responses.pop(0)

    monkeypatch.setattr(organizadortg.os.path, "getsize", fake_getsize)
    monkeypatch.setattr(organizadortg, "_compress_video_for_tg", fake_compress)
    monkeypatch.setattr(organizadortg.requests, "post", fake_post)

    ok, topic_id = organizadortg._send_video_to_topic(
        "-1001",
        123,
        "caption",
        str(original_video),
        {},
        "evexsparklyy",
        "SPAM",
    )

    assert ok is True
    assert topic_id == 123
    assert compress_inputs == [
        (readable_original, 45 * 1024 * 1024),
        (readable_original, 40 * 1024 * 1024),
    ]
    assert responses == []
    assert all(not os.path.exists(path) for path in temp_paths)


def test_telegram_compression_prefers_nvenc_and_falls_back_to_cpu(monkeypatch):
    commands = []

    monkeypatch.setattr(organizadortg.os.path, "getsize", lambda _path: organizadortg.TG_MAX_BYTES + 1)
    monkeypatch.setattr(organizadortg, "_ffmpeg_tool_exists", lambda _tool: True)

    def run(command, **_kwargs):
        commands.append(command)
        if "ffprobe" in os.path.basename(command[0]):
            return SimpleNamespace(returncode=0, stdout="10.0", stderr="")
        return SimpleNamespace(returncode=0 if len(commands) == 3 else 1, stdout="", stderr="nvenc failed")

    monkeypatch.setattr(organizadortg.subprocess, "run", run)

    compressed = organizadortg._compress_video_for_tg("source.mp4")

    assert compressed is not None
    assert commands[1][commands[1].index("-vcodec") + 1] == "h264_nvenc"
    assert commands[2][commands[2].index("-vcodec") + 1] == "libx264"
    os.unlink(compressed)
