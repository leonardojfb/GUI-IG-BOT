"""Coverage for complete per-account tanda delivery and origin non-repetition."""
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
                "FILLUP_TA", "PRUEBA_FILLUP_CAT", 1, fill_up, "MAX"
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


def test_fillup_disabled_still_sends_the_complete_tanda_to_every_account():
    outcome = _run_distribution(fill_up=False)
    assert outcome["by_day"].get("Dia_1") == 3, outcome["by_day"]
    assert outcome["by_day"].get("Dia_2") == 3, outcome["by_day"]
    assert outcome["by_day"].get("Dia_3") == 3, outcome["by_day"]
    assert outcome["total_files"] == 9


def test_fillup_never_repeats_an_origin_within_an_account():
    outcome = _run_distribution(fill_up=True)
    assert outcome["by_day"].get("Dia_1") == 3, outcome["by_day"]
    assert outcome["by_day"].get("Dia_2") == 3, (
        f"the full tanda should continue on day 2 for every account: {outcome['by_day']}"
    )
    assert outcome["by_day"].get("Dia_3") == 3, outcome["by_day"]
    assert outcome["total_files"] == 9

    for entry in outcome["files"]:
        assert "__TANDA_FILLUP_TA__" in entry["telegram_filename"], (
            f"fill-up manifest entry lost its tanda tag: {entry['telegram_filename']}"
        )

    origins_by_account = {}
    for entry in outcome["files"]:
        origin = entry["telegram_filename"].split("__TANDA_", 1)[0]
        origins_by_account.setdefault(entry["username"], []).append(origin)

    assert len(origins_by_account) == 3
    assert all(len(origins) == len(set(origins)) == 3 for origins in origins_by_account.values())
    assert "Fill-up omitido" in outcome["result"]
