"""Task 7 negative case for Telegram: selecting a single account must not leak

other accounts' calendarized files into that account's chat, and must not send
anything on the other accounts' behalf. tests/smoke_e2e_pipeline.py always
selects *all* nine matrix accounts in its one send, so a single-account
selection was never exercised.
"""
import shutil
import json

from tests.support.e2e_pipeline import (
    _run_telegram,
    make_run_root,
    patched_modules,
)


def test_selecting_one_account_only_sends_that_accounts_files():
    run_root = make_run_root()
    try:
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
            db.add_category("PRUEBA_TG_CAT")
            db.add_va("PRUEBA_TG_VA")
            db.update_va_telegram_group("PRUEBA_TG_VA", "TEST_CHAT_TG")
            db.add_virtual_account("tg_acc_one", "PRUEBA_TG_CAT")
            db.update_account("tg_acc_one", assigned_va="PRUEBA_TG_VA")
            db.add_virtual_account("tg_acc_two", "PRUEBA_TG_CAT")
            db.update_account("tg_acc_two", assigned_va="PRUEBA_TG_VA")
            db.add_tanda("TG_TEST", "TG_TEST", "TG_TEST", "")
        finally:
            db.close()
            database.DB_PATH = old_path

        with patched_modules(run_root) as mods:
            _, _, _, _, Organizador, organizadortg = mods

            tanda_dir = run_root / "videos_finales" / "TG_TEST"
            tanda_dir.mkdir(parents=True)
            (tanda_dir / "TG_TEST__P1__P2A.mp4").write_bytes(b"TG_A")
            (tanda_dir / "TG_TEST__P1__P2B.mp4").write_bytes(b"TG_B")

            Organizador.distribute_tanda("TG_TEST", "PRUEBA_TG_CAT", 1, False, "1")

            manifest = json.loads((run_root / "calendar_manifest.json").read_text(encoding="utf-8"))
            entries = [entry for entry in manifest["entries"] if entry["delivery_kind"] == "normal"]
            assert len(entries) == 2, entries
            by_account = {entry["username"]: entry for entry in entries}
            assert set(by_account) == {"tg_acc_one", "tg_acc_two"}
            assert not list((run_root / "CALENDARIO_POSTEO").rglob("*.mp4"))

            try:
                organizadortg.db.close()
            except Exception:
                pass
            organizadortg.db = database.DatabaseManager()

            result, events = _run_telegram(organizadortg, ["tg_acc_one"])

        video_events = [e for e in events if e.get("event") == "video"]
        assert len(video_events) == 1, (
            f"selecting only tg_acc_one must send exactly its own 1 file, got {len(video_events)}: {video_events}"
        )
        assert video_events[0]["username"] == "tg_acc_one"
        assert by_account["tg_acc_one"]["source_path"] == video_events[0]["video_path"]

        topic_events = [e for e in events if e.get("event") == "topic"]
        assert all(e["username"] == "tg_acc_one" for e in topic_events), (
            f"a topic was pre-created for an account that wasn't selected: {topic_events}"
        )
    finally:
        shutil.rmtree(run_root, ignore_errors=True)
