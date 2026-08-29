import sqlite3
from types import SimpleNamespace

from database import DatabaseManager


BASE_PARAMS = {
    "crop_px": 2,
    "mirror": False,
    "zoom_pct": 1.00004,
    "rotate_deg": 0.0004,
    "brightness": 0.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "gamma": 1.0,
    "noise": 0,
    "speed": 1.00004,
    "trim_start_ms": 0,
    "trim_end_ms": 0,
}


def test_forge_variant_signature_is_stable_and_input_specific():
    from vault import forge_variant_signature

    enabled = {"crop": True, "mirror": False, "speed": True}
    same_values_different_order = dict(reversed(list(BASE_PARAMS.items())))

    first = forge_variant_signature("hash-a", "forge", enabled, BASE_PARAMS)
    second = forge_variant_signature("hash-a", "forge", enabled, same_values_different_order)

    assert first == second
    assert first != forge_variant_signature("hash-b", "forge", enabled, BASE_PARAMS)


def test_forge_variant_signature_collapses_visual_noops():
    from vault import forge_variant_signature

    enabled = {"zoom": True, "rotate": True, "speed": True}
    barely_active = dict(BASE_PARAMS, zoom_pct=1.0009, rotate_deg=0.009, speed=1.0008)
    neutral = dict(BASE_PARAMS, zoom_pct=1.0, rotate_deg=0.0, speed=1.0)

    assert forge_variant_signature("hash-a", "forge", enabled, barely_active) == forge_variant_signature(
        "hash-a", "forge", enabled, neutral
    )


def test_reserve_forge_variants_enumerates_exact_space_and_reports_capacity(tmp_path):
    from vault import forge_variant_signature, reserve_forge_variants

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    output = tmp_path / "old.mp4"
    source.write_bytes(b"in")
    output.write_bytes(b"out")
    asset = db.upsert_vault_asset(str(source))
    enabled = {"crop": True, "mirror": False, "zoom": False, "rotate": False, "color": False, "noise": False, "speed": False, "trim": False}
    overrides = {"crop": (2, 3)}
    used_params = dict(BASE_PARAMS, crop_px=2)
    used_sig = forge_variant_signature(asset["asset_hash"], "forge", enabled, used_params)
    db.save_video_transform_log(
        "forge",
        str(source),
        str(output),
        used_params,
        vault_asset_id=asset["id"],
        variant_signature=used_sig,
    )

    result = reserve_forge_variants(db, asset, "forge", 2, enabled, 1.0, overrides)

    assert result["capacity"] == {"total": 2, "used": 1, "available": 1}
    assert [item["params"]["crop_px"] for item in result["reserved"]] == [3]
    assert result["shortfall"] == 1
    assert "No quedan variantes nuevas" in result["message"]
    db.close()


def test_reserve_forge_variants_exhausts_without_attempt_limit(tmp_path):
    from vault import forge_variant_signature, reserve_forge_variants

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    output = tmp_path / "old.mp4"
    source.write_bytes(b"in")
    output.write_bytes(b"out")
    asset = db.upsert_vault_asset(str(source))
    enabled = {"crop": False, "mirror": False, "zoom": False, "rotate": False, "color": False, "noise": False, "speed": False, "trim": False}
    used_sig = forge_variant_signature(asset["asset_hash"], "forge", enabled, BASE_PARAMS)
    db.save_video_transform_log(
        "forge",
        str(source),
        str(output),
        BASE_PARAMS,
        vault_asset_id=asset["id"],
        variant_signature=used_sig,
    )

    result = reserve_forge_variants(db, asset, "forge", 1, enabled, 1.0, None)

    assert result["reserved"] == []
    assert result["shortfall"] == 1
    assert result["capacity"] == {"total": 1, "used": 1, "available": 0}
    assert "No quedan variantes nuevas" in result["message"]
    db.close()


def test_forge_variant_reservations_are_durable_across_connections(tmp_path):
    from vault import reserve_forge_variants

    db_path = tmp_path / "organizador.db"
    source = tmp_path / "input.mp4"
    source.write_bytes(b"in")
    first_db = DatabaseManager(str(db_path))
    asset = first_db.upsert_vault_asset(str(source))
    first_db.close()

    enabled = {"crop": True, "mirror": False, "zoom": False, "rotate": False, "color": False, "noise": False, "speed": False, "trim": False}
    overrides = {"crop": (2, 2)}
    db_a = DatabaseManager(str(db_path))
    db_b = DatabaseManager(str(db_path))

    first = reserve_forge_variants(db_a, asset, "forge", 1, enabled, 1.0, overrides, run_id="run-a")
    second = reserve_forge_variants(db_b, asset, "forge", 1, enabled, 1.0, overrides, run_id="run-b")

    assert len(first["reserved"]) == 1
    assert second["reserved"] == []
    assert second["capacity"] == {"total": 1, "used": 1, "available": 0}
    assert "No quedan variantes nuevas" in second["message"]
    db_a.close()
    db_b.close()


def test_failed_forge_reservation_can_be_released(tmp_path):
    from vault import reserve_forge_variants

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    source.write_bytes(b"in")
    asset = db.upsert_vault_asset(str(source))
    enabled = {"crop": True, "mirror": False, "zoom": False, "rotate": False, "color": False, "noise": False, "speed": False, "trim": False}

    first = reserve_forge_variants(db, asset, "forge", 1, enabled, 1.0, {"crop": (2, 2)}, run_id="run-a")
    db.release_forge_variant_reservation(first["reserved"][0]["reservation_id"])
    second = reserve_forge_variants(db, asset, "forge", 1, enabled, 1.0, {"crop": (2, 2)}, run_id="run-b")

    assert len(second["reserved"]) == 1
    db.close()


def test_apply_variant_and_metadata_uses_preselected_params(monkeypatch):
    import metadata_pool

    params = dict(BASE_PARAMS, crop_px=4, mirror=True, zoom_pct=1.0, speed=1.0)
    commands = []
    monkeypatch.setattr(metadata_pool, "_probe_video_info", lambda _path: (1080, 1920, 1.0, False))
    monkeypatch.setattr(
        metadata_pool,
        "generate_variant_params",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("random generator should not run")),
    )

    def run(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(metadata_pool.subprocess, "run", run)

    returned = metadata_pool.apply_variant_and_metadata(
        "source.mp4",
        "output.mp4",
        {
            "iphone_model": "iPhone 15",
            "lat": "+25.7617",
            "lon": "-080.1918",
            "ios_version": "18.0",
            "carrier": "T-Mobile",
        },
        params=params,
    )

    assert returned == params
    assert "hflip" in ",".join(commands[0])


def test_build_forge_copy_jobs_skips_exhausted_vault_inputs(tmp_path, monkeypatch):
    import gui_premium_v7

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "input.mp4"
    source.write_bytes(b"in")
    asset = db.upsert_vault_asset(str(source), tags=["forge"])

    def reserve(_db, selected_asset, _process_kind, count, *_args, **_kwargs):
        assert selected_asset["id"] == asset["id"]
        return {
            "asset": selected_asset,
            "reserved": [{"params": dict(BASE_PARAMS), "signature": "sig-1", "reservation_id": 99}],
            "shortfall": count - 1,
            "message": "No quedan variantes nuevas para input.mp4",
            "capacity": {"total": 1, "used": 0, "available": 1},
        }

    monkeypatch.setattr(gui_premium_v7, "reserve_forge_variants", reserve)
    monkeypatch.setattr(gui_premium_v7.metadata_pool, "get_video_hash", lambda _path: "hash")

    plan = gui_premium_v7._build_forge_copy_jobs(
        db=db,
        vault_assets=[asset],
        copies=2,
        output_dir=str(tmp_path / "videos_finales" / "TANDA"),
        process_kind="forge",
        fx_enabled={"crop": True},
        forge_strength=1.0,
        forge_overrides=None,
    )

    assert len(plan["jobs"]) == 1
    assert plan["jobs"][0]["variant_signature"] == "sig-1"
    assert plan["skipped"][0]["shortfall"] == 1
    db.close()


def test_build_forge_copy_jobs_uses_selected_vault_assets(tmp_path, monkeypatch):
    import gui_premium_v7

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "selected.mp4"
    source.write_bytes(b"in")
    asset = db.upsert_vault_asset(str(source), tags=["forge"])

    def reserve(_db, selected_asset, _process_kind, count, *_args, **_kwargs):
        assert selected_asset["id"] == asset["id"]
        return {
            "asset": selected_asset,
            "reserved": [
                {"params": dict(BASE_PARAMS), "signature": f"sig-{idx}", "reservation_id": idx}
                for idx in range(1, count + 1)
            ],
            "shortfall": 0,
            "message": "",
            "capacity": {"total": 2, "used": 0, "available": 2},
        }

    monkeypatch.setattr(gui_premium_v7, "reserve_forge_variants", reserve)
    monkeypatch.setattr(gui_premium_v7.metadata_pool, "get_video_hash", lambda _path: "hash")

    plan = gui_premium_v7._build_forge_copy_jobs(
        db=db,
        vault_assets=[asset],
        copies=2,
        output_dir=str(tmp_path / "videos_finales" / "TANDA"),
        process_kind="forge",
        fx_enabled={"crop": True},
        forge_strength=1.0,
        forge_overrides=None,
    )

    assert [job["variant_signature"] for job in plan["jobs"]] == ["sig-1", "sig-2"]
    assert all(job["vault_asset"]["id"] == asset["id"] for job in plan["jobs"])
    assert plan["skipped"] == []
    db.close()
