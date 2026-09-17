from pathlib import Path
from types import SimpleNamespace

import pytest

from durable_jobs import create_job
from producer_jobs import (
    build_editor_job_spec,
    build_forge_job_spec,
    build_tanda_job_spec,
    make_editor_handler,
    make_forge_handler,
    make_tanda_handler,
    submit_editor_job,
    validate_video_profile,
)


def test_builders_freeze_r10_recipes_and_steps(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    specs = [
        build_tanda_job_spec(
            [{"tanda_name": "T1", "p1_folder": "P1", "p2_folder": "P2"}],
            source_root=tmp_path / "inputs", output_root=tmp_path / "outputs",
        ),
        build_forge_job_spec([source], output_dir=tmp_path / "forge", copies=2, metadata=[{"iphone_model": "iPhone"}]),
        build_editor_job_spec([source], output_dir=tmp_path / "edit", overlays=[{"photo": "logo.png"}]),
    ]

    assert [spec["job_type"] for spec in specs] == ["tandas.cartesian.v1", "forge.copy.v1", "editor.render.v1"]
    assert all(spec["recipe"]["recipe_version"] == 1 for spec in specs)
    assert len(specs[1]["steps"]) == 2
    assert specs[1]["steps"][1]["payload"]["copy_number"] == 2
    assert specs[2]["steps"][0]["payload"]["overlays"] == [{"photo": "logo.png"}]
    assert all(step["step_id"] for spec in specs for step in spec["steps"])


def test_profile_validation_is_deterministic_and_rejects_invalid_probe():
    info = validate_video_profile("clip.mp4", probe_fn=lambda _: {"width": 1080, "height": 1920, "fps": 30, "duration": 12}, profile="instagram_reel")
    assert info["profile"] == "instagram_reel"
    assert info["aspect_ratio"] == 0.5625
    with pytest.raises(ValueError, match="dimensiones"):
        validate_video_profile("bad.mp4", probe_fn=lambda _: {"width": 0, "height": 0, "duration": 0}, profile="instagram_reel")


def test_editor_handler_is_resumable_and_records_transform_log(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    output = tmp_path / "out.mp4"
    conn = SimpleNamespace(logs=[])
    conn.save_video_transform_log = lambda *args, **kwargs: conn.logs.append((args, kwargs)) or 11
    calls = []
    monkeypatch.setattr("video_editor.probe_video", lambda _: {"width": 1080, "height": 1920, "fps": 30, "duration": 2})
    monkeypatch.setattr("video_editor.render_video", lambda *args, **kwargs: calls.append(args) or Path(args[1]).write_bytes(b"rendered") or str(args[1]))
    handler = make_editor_handler(conn)
    step = {"job_id": "j", "step_id": "s", "payload": {"source_path": str(source), "output_path": str(output), "overlays": [], "profile": "instagram_reel", "ffmpeg_threads": 2}}

    first = handler(step, {}, lambda _: None)
    second = handler(step, {}, lambda _: None)

    assert first["output_path"] == str(output)
    assert second["resumed"] is True
    assert len(calls) == 1
    assert len(conn.logs) == 1


def test_forge_handler_uses_existing_engine_and_records_profile(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    output = tmp_path / "out.mp4"
    db = SimpleNamespace(logs=[])
    db.save_video_transform_log = lambda *args, **kwargs: db.logs.append((args, kwargs)) or 12
    monkeypatch.setattr("video_editor.probe_video", lambda _: {"width": 1080, "height": 1920, "fps": 30, "duration": 2})
    monkeypatch.setattr("metadata_pool.apply_variant_and_metadata", lambda *_args, **_kwargs: output.write_bytes(b"forge") or {"mirror": False})
    handler = make_forge_handler(db)
    step = {"payload": {"source_path": str(source), "output_path": str(output), "metadata": {"iphone_model": "iPhone", "lat": "0", "lon": "0", "carrier": "x", "ios_version": "1"}, "tanda_name": "T1", "copy_number": 1}}

    result = handler(step, {}, lambda _: None)

    assert result["profile"]["profile"] == "forge"
    assert len(db.logs) == 1


def test_tanda_handler_delegates_legacy_cartesian_entrypoint_with_scoped_paths(tmp_path, monkeypatch):
    import videos
    calls = []
    monkeypatch.setattr(videos, "process_tandas", lambda db, tandas, performance: calls.append((db, tandas, performance)))
    db = object()
    handler = make_tanda_handler(db)
    step = {"payload": {"tanda": {"tanda_name": "T1", "p1_folder": "P1", "p2_folder": "P2"}, "source_root": str(tmp_path / "in"), "output_root": str(tmp_path / "out"), "performance": {"workers": 2, "ffmpeg_threads": 3}}}

    result = handler(step, {}, lambda _: None)

    assert result["tanda_name"] == "T1"
    assert calls[0][1][0]["tanda_name"] == "T1"
    assert calls[0][2].workers == 2
    assert videos.FOLDER_INPUTS != str(tmp_path / "in")


def test_submit_editor_job_persists_r09_job(tmp_path):
    import sqlite3
    from durable_jobs import get_job

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    job = submit_editor_job(conn, [source], output_dir=tmp_path / "out", overlays=[])

    assert get_job(conn, job["job_id"])["recipe"]["producer"] == "editor"
