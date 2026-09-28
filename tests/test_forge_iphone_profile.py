"""Observable output contract for Forge's iPhone profile."""

import copy
import importlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

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
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "tags": {
            "major_brand": "qt  ",
            "creation_time": "2026-09-25T12:34:56.000000Z",
            "com.apple.quicktime.creationdate": "2026-09-25T09:34:56-0300",
        }},
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


def test_contract_checks_quicktime_identity_when_expected():
    profile = importlib.import_module("forge_iphone_profile")
    data = _probe()
    data["format"]["tags"].update({
        "com.apple.quicktime.make": "Apple",
        "com.apple.quicktime.model": "iPhone 15 Pro",
        "com.apple.quicktime.software": "iOS 26.4",
        "com.apple.quicktime.network": "T-Mobile",
    })
    problems = profile.validate_probe(data, "iphone_hlg", expect_audio=True,
                                      expected_meta={"iphone_model": "iPhone 17 Pro Max",
                                                     "ios_version": "26.4"})
    assert any("quicktime.model" in problem for problem in problems)
    assert any("quicktime.software" in problem for problem in problems)
    assert any("quicktime.network" in problem for problem in problems)


def test_metadata_floor_accepts_iphone_17_and_ios_26():
    pool = importlib.import_module("metadata_pool")
    assert pool.validate_iphone_metadata({
        "iphone_model": "iPhone 17 Pro Max", "ios_version": "26.0.1",
    }) is None


def test_metadata_floor_rejects_iphone_16_and_older_or_old_ios():
    pool = importlib.import_module("metadata_pool")
    with pytest.raises(ValueError, match="iPhone 17"):
        pool.validate_iphone_metadata({
            "iphone_model": "iPhone 16 Pro Max", "ios_version": "26.0",
        })
    with pytest.raises(ValueError, match="iOS 26"):
        pool.validate_iphone_metadata({
            "iphone_model": "iPhone 17", "ios_version": "18.7.9",
        })


def test_variant_engine_rejects_old_fingerprint_before_render():
    pool = importlib.import_module("metadata_pool")
    with pytest.raises(ValueError, match="iPhone 17"):
        pool.apply_variant_and_metadata(
            "missing-source.mp4", "output.mp4",
            {"iphone_model": "iPhone 15 Pro", "ios_version": "26.0"},
        )


def test_metadata_generator_only_returns_current_floor():
    pool = importlib.import_module("metadata_pool")

    class EmptyDb:
        def get_all_used_metadata_combos(self):
            return set()

    result = pool.generate_unique_metadata(EmptyDb(), 20)
    assert result
    assert all(int(item["iphone_model"].split()[1]) >= 17 for item in result)
    assert all(tuple(int(part) for part in item["ios_version"].split(".")) >= (26, 0)
               for item in result)


def test_metadata_model_tables_do_not_include_iphone_16_or_older():
    pool = importlib.import_module("metadata_pool")
    assert pool.IPHONE_MODELS
    assert all(pool._iphone_generation(model) >= 17 for model in pool.IPHONE_MODELS)
    assert set(pool._MODEL_IOS_RANGE) == set(pool.IPHONE_MODELS)


def test_creation_tags_format_same_instant_in_utc_and_local_offset():
    pool = importlib.import_module("metadata_pool")
    now = datetime(2026, 9, 25, 12, 34, 56, tzinfo=timezone.utc)
    tags = pool.current_creation_tags(now)
    assert tags["creation_time"] == "2026-09-25T12:34:56.000000Z"
    assert tags["com.apple.quicktime.creationdate"].startswith("2026-09-25T")
    assert tags["com.apple.quicktime.creationdate"].endswith(("+0000", "-0300", "-0400", "+0100"))


def test_contract_rejects_missing_creation_tags():
    profile = importlib.import_module("forge_iphone_profile")
    data = _probe()
    data["format"]["tags"].pop("creation_time")
    data["format"]["tags"].pop("com.apple.quicktime.creationdate")
    problems = profile.validate_probe(
        data, "iphone_hlg", expect_audio=True,
        expected_meta={"iphone_model": "iPhone 17 Pro Max", "ios_version": "26.4"},
    )
    assert any("creation_time" in problem for problem in problems)
    assert any("creationdate" in problem for problem in problems)


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


@pytest.mark.parametrize("source_profile,audio_rate,target_profile", [
    ("sdr", 32000, "iphone_sdr"),
    ("sdr", 44100, "iphone_hlg"),
    ("hlg", 48000, "iphone_hlg"),
    ("sdr", None, "iphone_sdr"),
])
def test_render_iphone_profile_real_sources(tmp_path, source_profile, audio_rate, target_profile):
    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        pytest.skip("FFmpeg tools not installed")
    profile = importlib.import_module("forge_iphone_profile")
    source = tmp_path / "source.mp4"
    output = tmp_path / "render.mov"
    cmd = [ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24:duration=0.5"]
    if audio_rate:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate={audio_rate}:duration=0.5"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if source_profile == "hlg":
        cmd += ["-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
                "-colorspace", "bt2020nc"]
    else:
        cmd += ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
    cmd += ["-c:a", "aac", "-shortest", str(source)]
    subprocess.run(cmd, check=True, capture_output=True)

    profile.render_iphone_video(source, output, {
        "iphone_model": "iPhone 17 Pro Max", "ios_version": "26.4",
        "lat": "+25.7617", "lon": "-080.1918",
    }, target_profile, source_profile, threads=2)
    data = profile.probe_file(output)
    assert profile.validate_probe(data, target_profile,
                                  expect_audio=audio_rate is not None) == []
    tags = data["format"]["tags"]
    datetime.fromisoformat(tags["creation_time"].replace("Z", "+00:00"))
    datetime.fromisoformat(tags["com.apple.quicktime.creationdate"])
    assert data["format"]["tags"]["com.apple.quicktime.make"] == "Apple"
    assert data["format"]["tags"]["com.apple.quicktime.model"] == "iPhone 17 Pro Max"
    assert data["format"]["tags"]["com.apple.quicktime.software"] == "26.4"
    assert "com.apple.quicktime.network" not in data["format"]["tags"]
    assert "com.apple.quicktime.location.ISO6709" not in data["format"]["tags"]
    assert "encoder" not in data["format"]["tags"]
    boxes = profile.top_level_boxes(output)
    assert boxes[0] == "ftyp"
    assert boxes.index("mdat") < boxes.index("moov")


def test_preflight_classifies_and_blocks_unknown_color():
    profile = importlib.import_module("forge_iphone_profile")
    sdr = _probe(hdr=False)
    hlg = _probe(hdr=True)
    untagged = _probe(hdr=False)
    for field in ("color_primaries", "color_transfer", "color_space"):
        del untagged["streams"][0][field]
    findings = profile.preflight_batch({"sdr.mp4": sdr, "hlg.mov": hlg,
                                        "unknown.mp4": untagged}, "iphone_hlg")
    assert findings["counts"] == {"sdr": 1, "hlg": 1, "unknown": 1}
    assert "unknown.mp4" in findings["blocked"]
    findings = profile.preflight_batch({"known-generator.mp4": untagged}, "iphone_sdr")
    assert "known-generator.mp4" in findings["blocked"]


def test_preflight_can_assume_unknown_sources_are_sdr_when_confirmed():
    profile = importlib.import_module("forge_iphone_profile")
    untagged = _probe(hdr=False)
    for field in ("color_primaries", "color_transfer", "color_space"):
        del untagged["streams"][0][field]
    findings = profile.preflight_batch(
        {"hf_batch.mp4": untagged}, "iphone_hlg", assume_unknown_sdr=True,
    )
    assert findings["counts"] == {"sdr": 1, "hlg": 0, "unknown": 0}
    assert findings["sources"]["hf_batch.mp4"] == "sdr"
    assert findings["blocked"] == {}
    assert "hf_batch.mp4" in findings["assumptions"]


@pytest.mark.parametrize("output_profile", ["iphone_sdr", "iphone_hlg"])
def test_wavespeed_without_color_tags_is_classified_automatically(output_profile):
    profile = importlib.import_module("forge_iphone_profile")
    probe = _probe(hdr=False)
    video = probe["streams"][0]
    video["codec_name"] = "h264"
    for field in ("color_primaries", "color_transfer", "color_space"):
        del video[field]
    probe["format"]["tags"]["AIGC"] = '{"Label":"1"}'
    probe["format"]["tags"]["major_brand"] = "isom"
    name = "wavespeed_223c4e71308a474a8834c39de5acccc5.mp4"
    findings = profile.preflight_batch({name: probe}, output_profile)
    assert findings["sources"][name] == "sdr"
    assert findings["blocked"] == {}
    assert name in findings["assumptions"]


@pytest.mark.parametrize("change", ["name", "container", "aigc", "malformed_aigc", "codec",
                                    "pixel_format", "partial_color"])
def test_wavespeed_auto_color_rejects_missing_evidence(change):
    profile = importlib.import_module("forge_iphone_profile")
    probe = _probe(hdr=False)
    video = probe["streams"][0]
    video["codec_name"] = "h264"
    for field in ("color_primaries", "color_transfer", "color_space"):
        del video[field]
    probe["format"]["tags"]["AIGC"] = '{"Label":"1"}'
    probe["format"]["tags"]["major_brand"] = "isom"
    name = "wavespeed_223c4e71308a474a8834c39de5acccc5.mp4"
    if change == "name":
        name = "unknown.mp4"
    elif change == "container":
        probe["format"]["tags"]["major_brand"] = "qt  "
    elif change == "aigc":
        del probe["format"]["tags"]["AIGC"]
    elif change == "malformed_aigc":
        probe["format"]["tags"]["AIGC"] = "not-json"
    elif change == "codec":
        video["codec_name"] = "hevc"
    elif change == "pixel_format":
        video["pix_fmt"] = "yuv420p10le"
    elif change == "partial_color":
        video["color_primaries"] = "bt709"
    findings = profile.preflight_batch({name: probe}, "iphone_sdr")
    assert name in findings["blocked"]


def test_variant_engine_transcodes_iphone_even_without_effects(tmp_path):
    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        pytest.skip("FFmpeg tools not installed")
    import metadata_pool
    profile = importlib.import_module("forge_iphone_profile")
    source = tmp_path / "source.mp4"
    subprocess.run([ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24:duration=0.5",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
                   check=True, capture_output=True)
    metadata = {"iphone_model": "iPhone 17 Pro Max", "ios_version": "26.4"}
    disabled = {key: False for key in metadata_pool.DEFAULT_VARIANT_EFFECTS}
    for suffix, effects in (("none", disabled), ("mirror", {**disabled, "mirror": True})):
        output = tmp_path / f"{suffix}.mov"
        params = metadata_pool.apply_variant_and_metadata(
            str(source), str(output), metadata, enabled=effects, strength=2,
            output_profile="iphone_sdr", source_color="sdr", ffmpeg_threads=2,
        )
        assert profile.validate_probe(profile.probe_file(output), "iphone_sdr",
                                      expect_audio=False) == []
        if suffix == "mirror":
            assert params["mirror"] is True


def test_hlg_variant_keeps_main10_and_reports_unsafe_effects(tmp_path):
    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        pytest.skip("FFmpeg tools not installed")
    import metadata_pool
    import random
    profile = importlib.import_module("forge_iphone_profile")
    source = tmp_path / "hlg_source.mov"
    output = tmp_path / "hlg_variant.mov"
    subprocess.run([
        ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=24:duration=0.5",
        "-c:v", "libx265", "-pix_fmt", "yuv420p10le", "-profile:v", "main10",
        "-x265-params", "colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc",
        str(source),
    ], check=True, capture_output=True)
    params = metadata_pool.apply_variant_and_metadata(
        str(source), str(output), {"iphone_model": "iPhone 17 Pro Max", "ios_version": "26.4"},
        rng=random.Random(2), output_profile="iphone_hlg", source_color="hlg",
        ffmpeg_threads=2,
    )
    assert "color" in params["iphone_effects_skipped"]
    assert profile.validate_probe(profile.probe_file(output), "iphone_hlg",
                                  expect_audio=False) == []


def test_validated_copy_does_not_publish_invalid_or_overwrite_existing(tmp_path):
    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        pytest.skip("FFmpeg tools not installed")
    profile = importlib.import_module("forge_iphone_profile")
    source = tmp_path / "source.mp4"
    subprocess.run([ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24:duration=0.5",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
                   check=True, capture_output=True)
    output = tmp_path / "source__c01.mov"
    metadata = {"iphone_model": "iPhone 17 Pro Max", "ios_version": "26.4"}
    with pytest.raises(ValueError, match="color"):
        profile.render_validated_copy(source, output, metadata, "iphone_sdr", "unknown")
    assert not output.exists()
    assert not list(tmp_path.glob("*.partial.mov"))

    params = profile.render_validated_copy(source, output, metadata, "iphone_sdr", "sdr")
    assert params["iphone_visual_qc"]["errors"] == []
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        profile.render_validated_copy(source, output, metadata, "iphone_sdr", "sdr")
    assert output.read_bytes() == original


def test_validated_copy_rejects_dark_sdr_to_hlg_grade(tmp_path, monkeypatch):
    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        pytest.skip("FFmpeg tools not installed")
    profile = importlib.import_module("forge_iphone_profile")
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mov"
    subprocess.run([ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=24:duration=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
                   check=True, capture_output=True)
    monkeypatch.setattr(profile, "SDR_TO_HLG_NPL", 100)
    with pytest.raises(RuntimeError, match="YAVG|YHIGH|SATAVG"):
        profile.render_validated_copy(source, output, {
            "iphone_model": "iPhone 17 Pro Max", "ios_version": "26.4",
        }, "iphone_hlg", "sdr", threads=2)
    assert not output.exists()
    assert not list(tmp_path.glob("*.partial.mov"))


def test_unvalidated_mov_is_not_visible_in_logistics_folder(tmp_path, monkeypatch):
    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        pytest.skip("FFmpeg tools not installed")
    import metadata_pool
    profile = importlib.import_module("forge_iphone_profile")
    source = tmp_path / "source.mp4"
    output_dir = tmp_path / "tanda"
    output = output_dir / "source__c01.mov"
    subprocess.run([ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24:duration=0.5",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
                   check=True, capture_output=True)
    real_apply = metadata_pool.apply_variant_and_metadata

    def inspect_while_rendering(input_path, temporary_path, meta, **kwargs):
        assert output.parent != Path(temporary_path).parent
        assert not list(output_dir.glob("*.mov"))
        return real_apply(input_path, temporary_path, meta, **kwargs)

    monkeypatch.setattr(metadata_pool, "apply_variant_and_metadata", inspect_while_rendering)
    profile.render_validated_copy(source, output, {
        "iphone_model": "iPhone 17 Pro Max", "ios_version": "26.4",
    }, "iphone_sdr", "sdr")
    assert output.is_file()


def test_processing_status_exposes_published_outputs_only(tmp_path):
    from Organizador import _tanda_video_inventory

    (tmp_path / "clip__c01.mov").touch()
    (tmp_path / "forge_batch_status.json").write_text(json.dumps({
        "state": "processing", "profile": "iphone_sdr",
        "expected_count": 2, "validated": [],
        "pending": [
            {"output_name": "clip__c01.mov"},
            {"output_name": "clip__c02.mov"},
        ],
    }), encoding="utf-8")

    names, diagnostic = _tanda_video_inventory(str(tmp_path))

    assert names == ["clip__c01.mov"]
    assert "parcial" in diagnostic.lower()
    assert "1" in diagnostic


def test_por_cuentas_accepts_processing_published_outputs(tmp_path):
    from gui_premium_v7 import _acct_inventory_items

    (tmp_path / "clip__c01.mov").touch()
    (tmp_path / "forge_batch_status.json").write_text(json.dumps({
        "state": "processing", "profile": "iphone_sdr",
        "pending": [
            {"output_name": "clip__c01.mov"},
            {"output_name": "clip__c02.mov"},
        ],
    }), encoding="utf-8")

    assert _acct_inventory_items({"PARTIAL": str(tmp_path)}) == [
        {"tanda": "PARTIAL", "name": "clip__c01.mov"},
    ]


def test_por_cuentas_inventory_uses_validated_incomplete_forge_outputs_and_preserves_legacy_avi(tmp_path):
    from gui_premium_v7 import _acct_inventory_items

    iphone_dir = tmp_path / "IPHONE"
    iphone_dir.mkdir()
    (iphone_dir / "clip__c01.mov").touch()
    (iphone_dir / "forge_batch_status.json").write_text(json.dumps({
        "state": "incomplete", "profile": "iphone_sdr",
        "validated": ["clip__c01.mov"], "pending": [{"output_name": "clip__c02.mov"}],
    }), encoding="utf-8")
    assert _acct_inventory_items({"IPHONE": str(iphone_dir)}) == [
        {"tanda": "IPHONE", "name": "clip__c01.mov"},
    ]

    legacy_dir = tmp_path / "LEGACY"
    legacy_dir.mkdir()
    (legacy_dir / "old.avi").touch()
    assert _acct_inventory_items({"LEGACY": str(legacy_dir)}) == [
        {"tanda": "LEGACY", "name": "old.avi"}]


def test_por_cuentas_inventory_summary_reports_partial_forge_without_blocking(tmp_path):
    from gui_premium_v7 import _acct_inventory_summary

    iphone_dir = tmp_path / "IPHONE"
    iphone_dir.mkdir()
    (iphone_dir / "clip__c01.mov").touch()
    (iphone_dir / "forge_batch_status.json").write_text(json.dumps({
        "state": "incomplete", "profile": "iphone_sdr",
        "validated": ["clip__c01.mov"], "pending": [{"output_name": "clip__c02.mov"}],
    }), encoding="utf-8")

    items, notices = _acct_inventory_summary({"IPHONE": str(iphone_dir)})

    assert items == [{"tanda": "IPHONE", "name": "clip__c01.mov"}]
    assert notices == ["IPHONE: Tanda Forge parcial: usando 1 copias validadas; 1 pendientes."]


def test_forge_retry_resolves_relocated_source_by_persisted_hash(tmp_path):
    from gui_premium_v7 import _resolve_forge_retry_sources
    import metadata_pool

    original = tmp_path / "original" / "clip.mp4"
    relocated = tmp_path / "relocated" / "clip.mp4"
    original.parent.mkdir()
    relocated.parent.mkdir()
    original.write_bytes(b"same video content")
    relocated.write_bytes(b"same video content")
    pending = [{"source_path": str(original),
                "video_hash": metadata_pool.get_video_hash(str(original))}]

    assert _resolve_forge_retry_sources(pending, [str(relocated)]) == [str(relocated)]


def test_copy_number_reservation_counts_mp4_and_mov(tmp_path):
    profile = importlib.import_module("forge_iphone_profile")
    (tmp_path / "clip__c01.mp4").touch()
    (tmp_path / "clip__c03.mov").touch()
    (tmp_path / "clip__c99.txt").touch()
    assert profile.next_copy_number(tmp_path, "clip") == 4


def test_visual_qc_rejects_dark_washed_and_clipped_variants(tmp_path):
    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        pytest.skip("FFmpeg tools not installed")
    profile = importlib.import_module("forge_iphone_profile")
    source = tmp_path / "source.mp4"
    subprocess.run([ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=24:duration=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
                   check=True, capture_output=True)
    for label, filter_spec in (("dark", "eq=brightness=-0.25"),
                               ("washed", "eq=saturation=0.05"),
                               ("clipped", "eq=contrast=2.5")):
        damaged = tmp_path / f"{label}.mp4"
        subprocess.run([ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(source), "-vf", filter_spec, "-an", "-c:v", "libx264",
                        str(damaged)], check=True, capture_output=True)
        errors, _metrics = profile.assess_visual_change(
            source, damaged, source_color="sdr", output_color="sdr")
        assert errors, label


def test_visual_qc_accepts_iphone_hlg_from_sdr_with_calibrated_midtones(tmp_path):
    if not ffmpeg_tool_exists("ffmpeg") or not ffmpeg_tool_exists("ffprobe"):
        pytest.skip("FFmpeg tools not installed")
    profile = importlib.import_module("forge_iphone_profile")
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mov"
    subprocess.run([ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=24:duration=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
                   check=True, capture_output=True)
    profile.render_iphone_video(source, output, {
        "iphone_model": "iPhone 17 Pro Max", "ios_version": "26.4",
    }, "iphone_hlg", "sdr", threads=2)
    errors, metrics = profile.assess_visual_change(
        source, output, source_color="sdr", output_color="hlg")
    assert not errors, metrics


def test_visual_qc_rejects_damage_only_at_end(tmp_path):
    if not ffmpeg_tool_exists("ffmpeg"):
        pytest.skip("FFmpeg not installed")
    profile = importlib.import_module("forge_iphone_profile")
    source = tmp_path / "source.mp4"
    damaged = tmp_path / "damaged.mp4"
    subprocess.run([ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=24:duration=4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
                   check=True, capture_output=True)
    subprocess.run([ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(source), "-vf", "eq=brightness=-0.25:enable='gte(t,2)'",
                    "-an", "-c:v", "libx264", str(damaged)], check=True, capture_output=True)
    errors, _ = profile.assess_visual_change(
        source, damaged, source_color="sdr", output_color="sdr")
    assert any("segundo" in error for error in errors)
