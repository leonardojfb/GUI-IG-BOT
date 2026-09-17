"""R10 adapters: freeze legacy producer inputs into durable-job recipes."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from durable_jobs import create_job


PROFILE_RULES = {
    "instagram_reel": {"min_width": 2, "min_height": 2, "min_aspect": 0.5, "max_aspect": 2.0, "max_duration": 90.0},
    "tandas": {"min_width": 2, "min_height": 2, "min_aspect": 0.1, "max_aspect": 10.0, "max_duration": 300.0},
    "forge": {"min_width": 2, "min_height": 2, "min_aspect": 0.1, "max_aspect": 10.0, "max_duration": 300.0},
}


def build_tanda_job_spec(tandas: list[dict], *, source_root, output_root, performance=None) -> dict:
    if not tandas:
        raise ValueError("tandas debe contener al menos una tanda")
    perf = _performance_snapshot(performance)
    normalized = []
    steps = []
    for index, tanda in enumerate(tandas, start=1):
        name = str(tanda.get("tanda_name") or "").strip()
        if not name:
            raise ValueError("tanda_name es obligatorio")
        item = {"tanda_name": name, "p1_folder": str(tanda.get("p1_folder") or ""), "p2_folder": str(tanda.get("p2_folder") or "")}
        normalized.append(item)
        steps.append({"step_id": f"tanda-{index:04d}", "kind": "tandas.cartesian", "payload": {"tanda": item, "source_root": str(Path(source_root).resolve()), "output_root": str(Path(output_root).resolve()), "performance": perf}})
    return {"job_type": "tandas.cartesian.v1", "recipe": {"recipe_version": 1, "producer": "tandas", "source_root": str(Path(source_root).resolve()), "output_root": str(Path(output_root).resolve()), "performance": perf, "tandas": normalized}, "steps": steps}


def build_forge_job_spec(video_paths: list[str | os.PathLike], *, output_dir, copies: int, metadata: list[dict], enabled=None, strength: float = 1.0, overrides=None, performance=None, tanda_name: str = "") -> dict:
    paths = [str(Path(path).resolve()) for path in video_paths]
    if not paths or any(not Path(path).is_file() for path in paths):
        raise ValueError("todos los videos Forge deben existir")
    copies = int(copies)
    if copies < 1 or not metadata:
        raise ValueError("copies y metadata son obligatorios")
    perf = _performance_snapshot(performance)
    out_root = Path(output_dir).resolve()
    steps = []
    for source_index, source in enumerate(paths):
        stem, suffix = Path(source).stem, Path(source).suffix
        for copy_number in range(1, copies + 1):
            output = out_root / f"{stem}__c{copy_number:02d}{suffix}"
            steps.append({"step_id": f"forge-{source_index:04d}-{copy_number:02d}", "kind": "forge.copy", "payload": {"source_path": source, "output_path": str(output), "copy_number": copy_number, "metadata": dict(metadata[(len(steps)) % len(metadata)]), "enabled": dict(enabled or {}), "strength": float(strength), "overrides": dict(overrides or {}), "ffmpeg_threads": perf["ffmpeg_threads"], "tanda_name": tanda_name}})
    return {"job_type": "forge.copy.v1", "recipe": {"recipe_version": 1, "producer": "forge", "output_dir": str(out_root), "copies": copies, "performance": perf, "enabled": dict(enabled or {}), "strength": float(strength), "overrides": dict(overrides or {}), "tanda_name": tanda_name}, "steps": steps}


def build_editor_job_spec(video_paths: list[str | os.PathLike], *, output_dir, overlays: list[dict], performance=None, profile: str = "instagram_reel") -> dict:
    paths = [str(Path(path).resolve()) for path in video_paths]
    if not paths or any(not Path(path).is_file() for path in paths):
        raise ValueError("todos los videos de Edicion deben existir")
    _profile_rule(profile)
    perf = _performance_snapshot(performance)
    out_root = Path(output_dir).resolve()
    steps = []
    for index, source in enumerate(paths, start=1):
        output = out_root / f"{Path(source).stem}__edit{index:02d}{Path(source).suffix}"
        steps.append({"step_id": f"editor-{index:04d}", "kind": "editor.render", "payload": {"source_path": source, "output_path": str(output), "overlays": [dict(item) for item in overlays], "profile": profile, "ffmpeg_threads": perf["ffmpeg_threads"]}})
    return {"job_type": "editor.render.v1", "recipe": {"recipe_version": 1, "producer": "editor", "output_dir": str(out_root), "profile": profile, "performance": perf, "overlays": [dict(item) for item in overlays]}, "steps": steps}


def submit_tanda_job(connection, tandas: list[dict], *, source_root, output_root, performance=None, idempotency_key: str | None = None) -> dict:
    spec = build_tanda_job_spec(tandas, source_root=source_root, output_root=output_root, performance=performance)
    return create_job(connection, **spec, idempotency_key=idempotency_key)


def submit_forge_job(connection, video_paths, *, output_dir, copies, metadata, enabled=None, strength=1.0, overrides=None, performance=None, tanda_name="", idempotency_key: str | None = None) -> dict:
    spec = build_forge_job_spec(video_paths, output_dir=output_dir, copies=copies, metadata=metadata, enabled=enabled, strength=strength, overrides=overrides, performance=performance, tanda_name=tanda_name)
    return create_job(connection, **spec, idempotency_key=idempotency_key)


def submit_editor_job(connection, video_paths, *, output_dir, overlays, performance=None, profile="instagram_reel", idempotency_key: str | None = None) -> dict:
    spec = build_editor_job_spec(video_paths, output_dir=output_dir, overlays=overlays, performance=performance, profile=profile)
    return create_job(connection, **spec, idempotency_key=idempotency_key)


def validate_video_profile(path: str, *, probe_fn, profile: str = "instagram_reel") -> dict:
    rule = _profile_rule(profile)
    info = dict(probe_fn(path) or {})
    width, height = int(info.get("width") or 0), int(info.get("height") or 0)
    duration = float(info.get("duration") or 0.0)
    if width < rule["min_width"] or height < rule["min_height"] or duration <= 0:
        raise ValueError(f"El video no cumple dimensiones/duracion del perfil {profile}")
    aspect = width / height
    if not rule["min_aspect"] <= aspect <= rule["max_aspect"]:
        raise ValueError(f"El video no cumple el aspect ratio del perfil {profile}")
    if duration > rule["max_duration"]:
        raise ValueError(f"El video supera la duracion maxima del perfil {profile}")
    return {"profile": profile, "width": width, "height": height, "fps": float(info.get("fps") or 0), "duration": duration, "aspect_ratio": round(aspect, 6)}


def make_editor_handler(db=None, *, default_profile: str = "instagram_reel"):
    def handler(step, checkpoint, save_checkpoint):
        import video_editor
        payload = step["payload"]
        source, output = payload["source_path"], payload["output_path"]
        if Path(output).is_file() and Path(output).stat().st_size > 0:
            return {"output_path": output, "resumed": True}
        profile = payload.get("profile") or default_profile
        source_info = validate_video_profile(source, probe_fn=video_editor.probe_video, profile=profile)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        save_checkpoint({"phase": "rendering", "source_info": source_info})
        video_editor.render_video(source, output, payload.get("overlays") or [], payload.get("ffmpeg_threads"))
        output_info = validate_video_profile(output, probe_fn=video_editor.probe_video, profile=profile)
        if db is not None and hasattr(db, "save_video_transform_log"):
            db.save_video_transform_log("video_editor", os.path.abspath(source), os.path.abspath(output), {"profile": profile, "source_info": source_info, "output_info": output_info, "overlays": payload.get("overlays") or [], "ffmpeg_threads": payload.get("ffmpeg_threads")})
        return {"output_path": output, "profile": output_info, "resumed": False}
    return handler


def make_forge_handler(db=None):
    def handler(step, checkpoint, save_checkpoint):
        import metadata_pool
        import video_editor
        payload = step["payload"]
        source, output = payload["source_path"], payload["output_path"]
        if Path(output).is_file() and Path(output).stat().st_size > 0:
            return {"output_path": output, "resumed": True}
        source_info = validate_video_profile(source, probe_fn=video_editor.probe_video, profile="forge")
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        save_checkpoint({"phase": "forge", "source_info": source_info})
        params = metadata_pool.apply_variant_and_metadata(source, output, payload["metadata"], enabled=payload.get("enabled"), strength=payload.get("strength", 1.0), overrides=payload.get("overrides"), ffmpeg_threads=payload.get("ffmpeg_threads"))
        output_info = validate_video_profile(output, probe_fn=video_editor.probe_video, profile="forge")
        if db is not None and hasattr(db, "save_video_transform_log"):
            db.save_video_transform_log("forge", os.path.abspath(source), os.path.abspath(output), {"profile": "forge", "params": params, "source_info": source_info, "output_info": output_info, "copy_number": payload.get("copy_number")}, tanda_name=payload.get("tanda_name"), source_identity=f"{Path(source).name}__c{payload.get('copy_number', 1)}")
        return {"output_path": output, "profile": output_info, "params": params, "resumed": False}
    return handler


def make_tanda_handler(db, *, performance=None):
    def handler(step, checkpoint, save_checkpoint):
        import videos
        payload = step["payload"]
        old_inputs, old_outputs = videos.FOLDER_INPUTS, videos.FOLDER_OUTPUT_ROOT
        videos.FOLDER_INPUTS, videos.FOLDER_OUTPUT_ROOT = payload["source_root"], payload["output_root"]
        perf = SimpleNamespace(**(payload.get("performance") or _performance_snapshot(performance)))
        try:
            save_checkpoint({"phase": "tandas", "tanda_name": payload["tanda"]["tanda_name"]})
            videos.process_tandas(db, [payload["tanda"]], performance=perf)
        finally:
            videos.FOLDER_INPUTS, videos.FOLDER_OUTPUT_ROOT = old_inputs, old_outputs
        return {"tanda_name": payload["tanda"]["tanda_name"], "resumed": False}
    return handler


def _profile_rule(profile):
    try:
        return PROFILE_RULES[str(profile)]
    except KeyError as exc:
        raise ValueError(f"Perfil no soportado: {profile}") from exc


def _performance_snapshot(performance):
    return {"workers": int(getattr(performance, "workers", 1)), "ffmpeg_threads": int(getattr(performance, "ffmpeg_threads", 1))}
