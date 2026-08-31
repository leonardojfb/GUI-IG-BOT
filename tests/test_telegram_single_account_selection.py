"""Task 7 negative case for Telegram: selecting a single account must not leak

other accounts' calendarized files into that account's chat, and must not send
anything on the other accounts' behalf. tests/smoke_e2e_pipeline.py always
selects *all* nine matrix accounts in its one send, so a single-account
selection was never exercised.
"""
import shutil
import json
from datetime import datetime

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


def test_selected_account_observer_records_only_its_manifest_delivery(monkeypatch):
    import organizadortg

    sent_paths = []
    observed = []
    state = {}
    sent_entry = {
        "id": "alice-sent",
        "username": "alice",
        "account_id": 1,
        "delivery_kind": "normal",
        "day": 1,
        "slot": 1,
        "tanda": "T1",
        "source_path": "alice-sent.mp4",
        "telegram_filename": "alice-sent.mp4",
    }
    failed_entry = {
        "id": "alice-failed",
        "username": "alice",
        "account_id": 1,
        "delivery_kind": "normal",
        "day": 1,
        "slot": 2,
        "tanda": "T1",
        "source_path": "alice-failed.mp4",
        "telegram_filename": "alice-failed.mp4",
    }
    excluded_entry = {
        "id": "bob-excluded",
        "username": "bob",
        "account_id": 2,
        "delivery_kind": "normal",
        "day": 1,
        "slot": 1,
        "tanda": "T1",
        "source_path": "bob.mp4",
        "telegram_filename": "bob.mp4",
    }

    def row(entry):
        return {
            "path": entry["source_path"],
            "filename": entry["telegram_filename"],
            "category": "main",
            "day": "Dia_1",
            "username": entry["username"],
            "delivery_kind": "normal",
            "manifest_entry": entry,
        }

    monkeypatch.setattr(organizadortg, "load_tanda_caption_pools", lambda: {})
    monkeypatch.setattr(organizadortg, "load_trial_caption_maps", lambda: {})
    monkeypatch.setattr(organizadortg, "load_normal_individual_caption_maps", lambda: {})
    monkeypatch.setattr(organizadortg, "get_accounts_with_va_info", lambda: [
        {"username": "alice", "account_type": "MAIN", "tg_group_id": "-1001", "assigned_va": "Leo"},
        {"username": "bob", "account_type": "MAIN", "tg_group_id": "-1002", "assigned_va": "Leo"},
    ])
    monkeypatch.setattr(organizadortg, "scan_calendar_structure", lambda: [
        row(sent_entry), row(failed_entry), row(excluded_entry),
    ])
    monkeypatch.setattr(organizadortg, "load_json", lambda _path: state)
    monkeypatch.setattr(organizadortg, "save_json", lambda _path, _data: None)
    monkeypatch.setattr(organizadortg, "get_slots_for_set", lambda *_args: ["9:00 AM"])
    monkeypatch.setattr(organizadortg, "convert_et_to_va_tz", lambda slot, _tz: (slot, slot))
    monkeypatch.setattr(organizadortg, "get_or_create_topic", lambda *_args, **_kwargs: 77)
    monkeypatch.setattr(organizadortg, "call_tg", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(organizadortg.time, "sleep", lambda _seconds: None)

    def fake_send(_chat, _topic, _caption, path, *_args):
        sent_paths.append(path)
        return path == "alice-sent.mp4", 77

    monkeypatch.setattr(organizadortg, "_send_video_to_topic", fake_send)

    organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14),
        selected_accounts=["alice"],
        delivery_observer=lambda entry, state, reason=None: observed.append((entry, state, reason)),
    )

    assert sent_paths == ["alice-sent.mp4", "alice-failed.mp4"]
    assert observed[0] == (sent_entry, "sent_telegram", None)
    assert observed[1][0] == failed_entry
    assert observed[1][1] == "failed"
    assert observed[1][2]


def test_controller_closes_short_lived_delivery_database(monkeypatch):
    import organizadortg

    databases = []
    delivered = []

    class FakeDatabase:
        def __init__(self):
            self.closed = False
            databases.append(self)

        def close(self):
            self.closed = True

    entry = {
        "account_id": 1,
        "delivery_kind": "normal",
        "day": 1,
        "slot": 1,
        "tanda": "T1",
        "source_path": "clip.mp4",
        "telegram_filename": "clip.mp4",
    }

    def fake_execute(_start_date, *_args, delivery_observer=None, **_kwargs):
        delivery_observer(entry, "sent_telegram")
        return "ok"

    monkeypatch.setattr(organizadortg, "DatabaseManager", FakeDatabase)
    monkeypatch.setattr(organizadortg, "mark_manifest_delivery", lambda db, *args: delivered.append((db, args)))
    monkeypatch.setattr(organizadortg, "execute_telegram_plan", fake_execute)

    organizadortg.TelegramBotController("2026-08-14").start()

    assert len(databases) == 1
    assert databases[0].closed is True
    assert delivered[0][0] is databases[0]
