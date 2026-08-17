"""Functional coverage for distribute_tanda()'s fill-up path and multi-day runs.

tests/smoke_e2e_pipeline.py always calls Organizador.distribute_tanda(tanda, category,
1, False, "1") for all nine tandas -- fill_up is always False and days_to_organize is
always fixed at "1". That means the fill-up fallback (falling back to full_tanda_pool
once the fresh, shared video pool is drained) and multi-day distribution were never
exercised by the mandatory matrix run. This test forces exactly that: three accounts
sharing three videos (one per account on day 1 drains the fresh pool), then a second
day where fresh inventory is gone and the two modes should visibly diverge.
"""
import random
import shutil

from tests.support.e2e_pipeline import (
    create_video,
    make_run_root,
    patched_modules,
    sha256_file,
)
from calendar_manifest import load_entries, manifest_path


def _seed_and_render(run_root, colors=("teal", "brown", "gray")):
    import database

    db_path = run_root / "organizador.db"
    shutil.copy2(
        __import__("tests.support.e2e_pipeline", fromlist=["REPO_ROOT"]).REPO_ROOT / "organizador.db",
        db_path,
    )

    old_path = database.DB_PATH
    database.DB_PATH = str(db_path)
    db = database.DatabaseManager()
    try:
        db.add_category("PRUEBA_FILLUP_CAT")
        db.add_va("PRUEBA_FILLUP_VA")
        for i in range(1, 4):
            db.add_virtual_account(f"fillup_acc_{i}", "PRUEBA_FILLUP_CAT")
            db.update_account(f"fillup_acc_{i}", assigned_va="PRUEBA_FILLUP_VA")
        db.add_tanda("FILLUP_TA", "FILLUP_TA_P1", "FILLUP_TA_P2", "")
    finally:
        db.close()
        database.DB_PATH = old_path

    p1 = run_root / "inputs" / "FILLUP_TA_P1" / "FILLUP_TA_P1ID.mp4"
    create_video(p1, colors[0], "FILLUP_TA_P1ID")
    for i, color in zip(range(1, 4), colors):
        p2 = run_root / "inputs" / "FILLUP_TA_P2" / f"FILLUP_TA_P2ID_{i}.mp4"
        create_video(p2, color, f"FILLUP_TA_P2ID_{i}")

    return db_path


def _run_distribution(fill_up: bool) -> dict:
    run_root = make_run_root()
    try:
        db_path = _seed_and_render(run_root)
        with patched_modules(run_root) as mods:
            _, videos, _, _, Organizador, _ = mods
            db_path = run_root / "organizador.db"
            videos.render_tanda("FILLUP_TA")

            outputs = sorted((run_root / "videos_finales" / "FILLUP_TA").glob("*.mp4"))
            output_hashes = {p.name: sha256_file(p) for p in outputs}

            random.seed(260726)
            result = Organizador.distribute_tanda(
                "FILLUP_TA", "PRUEBA_FILLUP_CAT", 1, fill_up, "2"
            )

            manifest_entries = load_entries(manifest_path(run_root))
            by_day = {}
            for entry in manifest_entries:
                by_day.setdefault(f"Dia_{entry['day']}", []).append(entry)

            return {
                "result": result,
                "output_hashes": output_hashes,
                "total_files": len(manifest_entries),
                "by_day": {day: len(entries) for day, entries in by_day.items()},
                "files": manifest_entries,
            }
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


def test_fillup_disabled_leaves_day_two_partial_when_pool_is_drained():
    outcome = _run_distribution(fill_up=False)
    assert outcome["by_day"].get("Dia_1") == 3, outcome["by_day"]
    assert outcome["by_day"].get("Dia_2", 0) == 0, (
        "with fill_up=False and only 3 unique videos shared by 3 accounts, day 2 must "
        f"have nothing to assign (drained pool, no fallback) -- got {outcome['by_day']}"
    )
    assert outcome["total_files"] == 3


def test_fillup_enabled_fills_day_two_by_reusing_other_accounts_videos():
    outcome = _run_distribution(fill_up=True)
    assert outcome["by_day"].get("Dia_1") == 3, outcome["by_day"]
    assert outcome["by_day"].get("Dia_2") == 3, (
        "with fill_up=True the day-2 slots must be filled by reusing videos the "
        f"*other* accounts already used on day 1 -- got {outcome['by_day']}"
    )
    assert outcome["total_files"] == 6

    for entry in outcome["files"]:
        assert "__TANDA_FILLUP_TA__" in entry["telegram_filename"], (
            f"fill-up manifest entry lost its tanda tag: {entry['telegram_filename']}"
        )

    day1_choice_by_account = {}
    day2_choice_by_account = {}
    for entry in outcome["files"]:
        account = entry["username"]
        day = f"Dia_{entry['day']}"
        bucket = day1_choice_by_account if day == "Dia_1" else day2_choice_by_account
        for name in outcome["output_hashes"]:
            if entry["telegram_filename"].startswith(name.rsplit(".", 1)[0]):
                bucket[account] = name
                break

    for account in day1_choice_by_account:
        assert day1_choice_by_account[account] != day2_choice_by_account.get(account), (
            f"{account} reused the exact same source video on day 2 as day 1 -- the "
            "hard anti-collision rule (never repeat a P1+P2 combo for the same "
            "account) was violated by the fill-up fallback"
        )
