"""Task 7 negative cases for Logistica's distribute_tanda() path.

Covers error handling that the mandatory 27-file matrix run never exercises
because every tanda/category pair in it is valid and has inventory: a missing
tanda folder, a category with zero accounts, and re-running a distribution
into a calendar day that already has files from a previous run (collision).
"""
import shutil
import json

import pytest

from calendar_manifest import load_entries, manifest_path
from tests.support.e2e_pipeline import create_video, make_run_root


@pytest.fixture
def isolated_organizador(monkeypatch):
    import database
    import Organizador

    run_root = make_run_root()
    db_path = run_root / "organizador.db"
    shutil.copy2(
        __import__("tests.support.e2e_pipeline", fromlist=["REPO_ROOT"]).REPO_ROOT / "organizador.db",
        db_path,
    )
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(Organizador, "base_dir", str(run_root))
    monkeypatch.setattr(Organizador, "source_root", str(run_root / "videos_finales"))
    monkeypatch.setattr(Organizador, "output_root", str(run_root / "CALENDARIO_POSTEO"))
    try:
        yield run_root, Organizador, database
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


def test_distribute_tanda_missing_folder_returns_graceful_error(isolated_organizador):
    run_root, Organizador, database = isolated_organizador
    db = database.DatabaseManager()
    db.add_category("PRUEBA_NEG_CAT")
    db.add_virtual_account("neg_acc_1", "PRUEBA_NEG_CAT")
    db.close()

    result = Organizador.distribute_tanda("DOES_NOT_EXIST", "PRUEBA_NEG_CAT", 1, False, "1")

    assert "No existe la tanda" in result
    assert not (run_root / "CALENDARIO_POSTEO").exists() or not list(
        (run_root / "CALENDARIO_POSTEO").rglob("*.mp4")
    )


def test_distribute_tanda_refuses_incomplete_iphone_forge_batch(isolated_organizador):
    run_root, Organizador, database = isolated_organizador
    tanda_dir = run_root / "videos_finales" / "IPHONE_INCOMPLETE"
    tanda_dir.mkdir(parents=True)
    (tanda_dir / "clip__c01.mov").write_bytes(b"validated-placeholder")
    (tanda_dir / "forge_batch_status.json").write_text(json.dumps({
        "state": "incomplete", "profile": "iphone_sdr",
        "validated": ["clip__c01.mov"],
        "pending": [{"output_name": "clip__c02.mov"}],
    }), encoding="utf-8")
    db = database.DatabaseManager()
    db.add_category("PRUEBA_IPHONE_INCOMPLETE")
    db.add_virtual_account("iphone_acc", "PRUEBA_IPHONE_INCOMPLETE")
    db.close()

    result = Organizador.distribute_tanda(
        "IPHONE_INCOMPLETE", "PRUEBA_IPHONE_INCOMPLETE", 1, False, "1")
    assert "incompleta" in result.lower()
    assert not list((run_root / "CALENDARIO_POSTEO").rglob("*.mov"))


def test_distribute_tanda_uses_only_validated_mov_from_complete_forge_batch(isolated_organizador):
    run_root, Organizador, database = isolated_organizador
    tanda_dir = run_root / "videos_finales" / "IPHONE_COMPLETE"
    tanda_dir.mkdir(parents=True)
    valid = "IPHONE_COMPLETE__P1__P2__c01.mov"
    stray = "IPHONE_COMPLETE__P3__P4__c02.mov"
    create_video(tanda_dir / valid, "black", "VALID_MOV")
    create_video(tanda_dir / stray, "white", "STRAY_MOV")
    (tanda_dir / "forge_batch_status.json").write_text(json.dumps({
        "state": "complete", "profile": "iphone_sdr", "validated": [valid], "pending": [],
    }), encoding="utf-8")
    db = database.DatabaseManager()
    db.add_category("PRUEBA_IPHONE_COMPLETE")
    db.add_virtual_account("iphone_complete_acc", "PRUEBA_IPHONE_COMPLETE")
    db.close()

    result = Organizador.distribute_tanda(
        "IPHONE_COMPLETE", "PRUEBA_IPHONE_COMPLETE", 1, False, "1")
    entries = load_entries(manifest_path(run_root))
    assert "1 videos procesados" in result
    assert len(entries) == 1
    assert entries[0]["source_path"].endswith(valid)
    assert entries[0]["telegram_filename"].endswith(".mov")


def test_iphone_mov_flows_from_forge_through_logistics_to_telegram_upload(
    isolated_organizador, monkeypatch,
):
    import subprocess
    import forge_iphone_profile
    import organizadortg
    from console_encoding import ffmpeg_tool_command
    from types import SimpleNamespace

    run_root, Organizador, database = isolated_organizador
    source = run_root / "input_sdr.mp4"
    subprocess.run([
        ffmpeg_tool_command("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=24:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        str(source),
    ], check=True, capture_output=True)
    tanda_dir = run_root / "videos_finales" / "IPHONE_FLOW"
    output = tanda_dir / "IPHONE_FLOW__P1__P2__c01.mov"
    forge_iphone_profile.render_validated_copy(source, output, {
        "iphone_model": "iPhone 14 Pro Max", "ios_version": "26.4",
    }, "iphone_sdr", "sdr")
    (tanda_dir / "forge_batch_status.json").write_text(json.dumps({
        "state": "complete", "profile": "iphone_sdr",
        "validated": [output.name], "pending": [],
    }), encoding="utf-8")
    db = database.DatabaseManager()
    db.add_category("PRUEBA_IPHONE_FLOW")
    db.add_virtual_account("iphone_flow_acc", "PRUEBA_IPHONE_FLOW")
    db.close()

    result = Organizador.distribute_tanda("IPHONE_FLOW", "PRUEBA_IPHONE_FLOW", 1, False, "1")
    entries = load_entries(manifest_path(run_root))
    assert "1 videos procesados" in result
    assert len(entries) == 1
    assert entries[0]["source_path"] == str(output)

    posted = []

    def fake_post(url, data, files):
        name, handle, mime = files["video"]
        posted.append((name, mime, handle.read()))
        return SimpleNamespace(status_code=200, text="ok")

    monkeypatch.setattr(organizadortg.requests, "post", fake_post)
    ok, _topic = organizadortg._send_video_to_topic(
        "-1001", 123, "caption", entries[0]["source_path"], {}, "iphone_flow_acc", "MAIN")
    assert ok
    assert posted == [(output.name, "video/quicktime", output.read_bytes())]


def test_distribute_tanda_category_without_accounts_returns_graceful_error(isolated_organizador):
    run_root, Organizador, database = isolated_organizador
    tanda_dir = run_root / "videos_finales" / "NEG_TA"
    tanda_dir.mkdir(parents=True)
    create_video(tanda_dir / "NEG_TA__P1__P2.mp4", "black", "NEG_TA_SOURCE")

    db = database.DatabaseManager()
    db.add_category("PRUEBA_NEG_EMPTY_CAT")
    db.close()

    result = Organizador.distribute_tanda("NEG_TA", "PRUEBA_NEG_EMPTY_CAT", 1, False, "1")

    assert "No hay cuentas" in result


def test_distribute_tanda_rerun_into_existing_day_uses_collision_suffix_not_overwrite(
    isolated_organizador,
):
    run_root, Organizador, database = isolated_organizador
    tanda_dir = run_root / "videos_finales" / "NEG_COLLIDE"
    tanda_dir.mkdir(parents=True)
    create_video(tanda_dir / "NEG_COLLIDE__P1__P2A.mp4", "black", "NEG_A")
    create_video(tanda_dir / "NEG_COLLIDE__P1__P2B.mp4", "white", "NEG_B")

    db = database.DatabaseManager()
    db.add_category("PRUEBA_NEG_COLLIDE_CAT")
    db.add_virtual_account("neg_collide_acc", "PRUEBA_NEG_COLLIDE_CAT")
    db.add_tanda("NEG_COLLIDE", "NEG_COLLIDE", "NEG_COLLIDE", "")
    db.close()

    import random

    random.seed(1)
    first = Organizador.distribute_tanda("NEG_COLLIDE", "PRUEBA_NEG_COLLIDE_CAT", 1, False, "1")
    random.seed(1)
    second = Organizador.distribute_tanda("NEG_COLLIDE", "PRUEBA_NEG_COLLIDE_CAT", 1, False, "1")

    assert "Error" not in first
    assert "Error" not in second

    entries = load_entries(manifest_path(run_root))
    names = [entry["telegram_filename"] for entry in entries]
    assert len(names) == len(set(names)), (
        f"a rerun into the same Dia_1/account created duplicate manifest names: {names}"
    )
    assert len(entries) == 1, (
        "normal manifest distribution replaces the affected account's previous run; "
        f"expected 1 latest entry, got {len(entries)}"
    )
    assert entries[0]["source_path"].endswith(("NEG_COLLIDE__P1__P2A.mp4", "NEG_COLLIDE__P1__P2B.mp4"))


def test_distribute_tanda_does_not_resend_identical_video_to_same_account_across_separate_runs(
    isolated_organizador,
):
    """Regression test for LOGISTICA_NO_CROSS_RUN_ANTICOLLISION.

    Organizador.py has get_account_used_combinations()/get_all_used_combinations(), which
    read fingerprint_history to avoid resending a P1+P2 combo an account already got.
    distribute_tanda() used to never call them -- its account_lifetime_combos dict was built
    fresh in local memory on every call and forgotten when the call returned. Two separate
    "Distribuir" runs for the same tanda/category (e.g. the user re-runs it, or restarts
    the app) could send the exact same account the exact same video twice, because nothing
    persisted the fact that fingerprint_history already recorded that combo.

    Fixture: 1 account, 1 source video. Run 1 sends it. Run 2 (fresh calendar, same
    account, same and only source video, no new inventory) must find no valid, unused
    combo left for that account and skip the slot -- not resend the same video.
    """
    run_root, Organizador, database = isolated_organizador
    tanda_dir = run_root / "videos_finales" / "DUP_CHECK"
    tanda_dir.mkdir(parents=True)
    create_video(tanda_dir / "DUP_CHECK__P1__ONLY.mp4", "black", "ONLY_ONE")

    db = database.DatabaseManager()
    db.add_category("PRUEBA_DUP_CAT")
    db.add_virtual_account("dup_acc", "PRUEBA_DUP_CAT")
    db.add_tanda("DUP_CHECK", "DUP_CHECK", "DUP_CHECK", "")
    db.close()

    Organizador.distribute_tanda("DUP_CHECK", "PRUEBA_DUP_CAT", 1, False, "1")
    first_run_files = {
        entry["telegram_filename"].split("__TANDA")[0]
        for entry in load_entries(manifest_path(run_root))
    }
    assert first_run_files == {"DUP_CHECK__P1__ONLY"}

    Organizador.distribute_tanda("DUP_CHECK", "PRUEBA_DUP_CAT", 1, False, "1")
    second_run_files = load_entries(manifest_path(run_root))

    assert second_run_files == [], (
        "dup_acc already received DUP_CHECK__P1__ONLY in run 1 (recorded in "
        "fingerprint_history); with only that one source video available, run 2 must "
        f"clear the normal manifest for that account instead of resending it. Got: {second_run_files}"
    )


def test_distribute_tanda_cross_run_anticollision_is_scoped_to_the_same_tanda(
    isolated_organizador,
):
    """A different tanda that happens to parse to the same (p1, p2) identity as an
    already-distributed tanda must NOT be blocked for that account.

    This is exactly what happens between an Edicion tanda and a Forge tanda built
    from one of its outputs: Forge's `source__cNN` naming means
    parse_combination_from_filename() returns the *same* (p1, p2) for the Forge
    copy as for the original Edicion source it was built from, even though they
    are two different tandas with two different videos_finales/ folders. The
    cross-run history check (LOGISTICA_NO_CROSS_RUN_ANTICOLLISION's fix) must only
    compare a tanda's re-run against *its own* prior distributions, not any tanda
    that happens to share a parsed identity -- otherwise it wrongly starves the
    second tanda of an account it never actually sent anything to.
    """
    run_root, Organizador, database = isolated_organizador

    tanda_one_dir = run_root / "videos_finales" / "SCOPE_ONE"
    tanda_one_dir.mkdir(parents=True)
    create_video(tanda_one_dir / "SHARED__P1__P2.mp4", "black", "SHARED_SOURCE")

    tanda_two_dir = run_root / "videos_finales" / "SCOPE_TWO"
    tanda_two_dir.mkdir(parents=True)
    # Same first three "__"-separated segments as tanda one on purpose: this is
    # what a Forge copy of tanda one's output looks like once parsed.
    create_video(tanda_two_dir / "SHARED__P1__P2__c01.mp4", "gray", "SHARED_SOURCE_FORGE_COPY")

    db = database.DatabaseManager()
    db.add_category("PRUEBA_SCOPE_CAT")
    db.add_virtual_account("scope_acc", "PRUEBA_SCOPE_CAT")
    db.add_tanda("SCOPE_ONE", "SCOPE_ONE", "SCOPE_ONE", "")
    db.add_tanda("SCOPE_TWO", "SCOPE_TWO", "SCOPE_TWO", "")
    db.close()

    result_one = Organizador.distribute_tanda("SCOPE_ONE", "PRUEBA_SCOPE_CAT", 1, False, "1")
    assert "1 videos procesados" in result_one, result_one

    result_two = Organizador.distribute_tanda("SCOPE_TWO", "PRUEBA_SCOPE_CAT", 1, False, "1")
    assert "1 videos procesados" in result_two, (
        f"SCOPE_TWO must be delivered to scope_acc even though it parses to the same "
        f"(p1, p2) as SCOPE_ONE, which scope_acc already received -- they are different "
        f"tandas. Got: {result_two}"
    )
