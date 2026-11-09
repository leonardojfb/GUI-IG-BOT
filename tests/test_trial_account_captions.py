from types import SimpleNamespace
import sqlite3
from datetime import datetime

from database import DatabaseManager
import gui_premium_v7
import organizadortg


def _account_id(db, username):
    return next(row["id"] for row in db.get_all_accounts() if row["username"] == username)


def test_account_trial_caption_persists_by_verified_origin_without_changing_global(tmp_path):
    path = tmp_path / "captions.db"
    db = DatabaseManager(str(path))
    db.add_virtual_account("eve", "MAIN")
    db.add_virtual_account("luna", "MAIN")
    for tanda, source in (("OLD", "original"), ("NEW", "renamed")):
        db.set_tanda_trial(tanda, True)
        db.save_forge_video(tanda, source + ".mp4", source + "__c01.mp4", "a" * 64)
    db.set_trial_source_caption("OLD", "original", "global")
    eve = _account_id(db, "eve")
    luna = _account_id(db, "luna")

    db.set_trial_account_source_caption(eve, "OLD", "original", "solo Eve")
    assert db.get_trial_account_source_caption(eve, "NEW", "renamed") == "solo Eve"
    assert db.get_trial_account_source_caption(luna, "NEW", "renamed") is None
    assert db.get_trial_source_captions("OLD")["original"] == "global"
    db.close()

    db = DatabaseManager(str(path))
    try:
        assert db.get_trial_account_source_caption(eve, "NEW", "renamed") == "solo Eve"
        assert db.get_trial_source_captions("NEW")["renamed"] == "global"
    finally:
        db.close()


def test_account_trial_caption_without_verified_origin_is_local_and_can_be_cleared(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        db.add_virtual_account("eve", "MAIN")
        eve = _account_id(db, "eve")
        db.set_trial_account_source_caption(eve, "A", "same", "caption A")
        assert db.get_trial_account_source_caption(eve, "A", "same") == "caption A"
        assert db.get_trial_account_source_caption(eve, "B", "same") is None
        db.set_trial_account_source_caption(eve, "A", "same", "")
        assert db.get_trial_account_source_caption(eve, "A", "same") is None
    finally:
        db.close()


def test_account_caption_survives_later_forge_origin_registration(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        db.add_virtual_account("eve", "MAIN")
        eve = _account_id(db, "eve")
        db.set_trial_account_source_caption(eve, "T", "clip", "guardado antes de Forge")
        db.save_forge_video("T", "clip.mp4", "clip__c01.mp4", "a" * 64)
        assert db.get_trial_account_source_caption(eve, "T", "clip") == "guardado antes de Forge"
        db.set_trial_account_source_caption(eve, "T", "clip", "")
        assert db.get_trial_account_source_caption(eve, "T", "clip") is None
    finally:
        db.close()


def test_account_caption_satisfies_individual_trial_without_global_caption(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        db.add_virtual_account("eve", "MAIN")
        db.add_virtual_account("luna", "MAIN")
        eve = _account_id(db, "eve")
        luna = _account_id(db, "luna")
        db.set_trial_account_source_caption(eve, "T", "clip", "solo Eve")
        fake = SimpleNamespace(
            db=db,
            trial_account_ids={"eve": eve, "luna": luna},
            _trial_tanda_files=lambda _tanda: ["clip__c01.mp4", "clip__c02.mp4"],
        )
        missing = gui_premium_v7.InstagramAutoPro._trial_missing_caption_sources
        assert missing(fake, "T", "eve") == []
        assert missing(fake, "T", "luna") == ["clip"]
    finally:
        db.close()


def test_existing_database_adds_account_caption_table_without_changing_global(tmp_path):
    path = tmp_path / "captions.db"
    db = DatabaseManager(str(path))
    db.set_tanda_trial("T", True)
    db.set_trial_source_caption("T", "clip", "global antes")
    db.close()
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE trial_account_source_captions")

    db = DatabaseManager(str(path))
    try:
        assert db.get_trial_source_captions("T")["clip"] == "global antes"
        assert db.conn.execute(
            "SELECT name FROM sqlite_master WHERE name='trial_account_source_captions'"
        ).fetchone() is not None
    finally:
        db.close()


def test_trial_editor_saves_different_captions_for_each_account(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        db.add_virtual_account("eve", "MAIN")
        db.add_virtual_account("luna", "MAIN")
        db.set_tanda_trial("T", True)
        db.set_trial_source_caption("T", "clip", "global")
        ids = {row["username"]: row["id"] for row in db.get_all_accounts()}

        class Editor:
            def __init__(self, text):
                self.text = text

            def get(self, *_args):
                return self.text

        fake = SimpleNamespace(
            db=db,
            trial_account_ids=ids,
            trial_caption_editors={
                ("eve", "T", "clip"): Editor("para Eve"),
                ("luna", "T", "clip"): Editor("para Luna"),
            },
            _trial_saving_silently=True,
        )
        gui_premium_v7.InstagramAutoPro._save_trial_captions(fake)
        assert db.get_trial_source_captions("T")["clip"] == "global"
        assert db.get_trial_account_source_caption(ids["eve"], "T", "clip") == "para Eve"
        assert db.get_trial_account_source_caption(ids["luna"], "T", "clip") == "para Luna"
    finally:
        db.close()


def test_saving_unchanged_global_caption_keeps_account_inherited(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        db.add_virtual_account("eve", "MAIN")
        eve = _account_id(db, "eve")
        db.set_tanda_trial("T", True)
        db.set_trial_source_caption("T", "clip", "global")
        fake = SimpleNamespace(
            db=db,
            trial_account_ids={"eve": eve},
            trial_caption_editors={
                ("eve", "T", "clip"): SimpleNamespace(get=lambda *_args: "global")
            },
            _trial_saving_silently=True,
        )
        gui_premium_v7.InstagramAutoPro._save_trial_captions(fake)
        assert db.get_trial_account_source_caption(eve, "T", "clip") is None
        db.set_trial_source_caption("T", "clip", "global actualizado")
        assert db.get_trial_source_captions("T")["clip"] == "global actualizado"
    finally:
        db.close()


def test_trial_editor_reloads_saved_account_caption(tmp_path, monkeypatch):
    path = tmp_path / "captions.db"
    db = DatabaseManager(str(path))
    db.add_virtual_account("eve", "MAIN")
    db.set_tanda_trial("T", True)
    db.set_trial_source_caption("T", "clip", "global")
    eve = _account_id(db, "eve")
    db.set_trial_account_source_caption(eve, "T", "clip", "para Eve")
    db.close()
    db = DatabaseManager(str(path))
    try:
        class Widget:
            def __init__(self, parent=None, **_kwargs):
                self.children = []
                self.value = ""
                if parent is not None:
                    parent.children.append(self)

            def winfo_children(self):
                return self.children

            def destroy(self):
                return None

            def pack(self, **_kwargs):
                return self

            def insert(self, _index, value):
                self.value = value

        monkeypatch.setattr(gui_premium_v7.ctk, "CTkFrame", Widget)
        monkeypatch.setattr(gui_premium_v7.ctk, "CTkLabel", Widget)
        monkeypatch.setattr(gui_premium_v7.ctk, "CTkTextbox", Widget)
        fake = SimpleNamespace(
            db=db,
            trial_account_ids={"eve": eve},
            trial_account_vars={"eve": SimpleNamespace(get=lambda: "T")},
            trial_account_panel_frames={"eve": Widget()},
            trial_caption_editors={},
            trial_thumbnail_images=[],
            _trial_tanda_files=lambda _tanda: ["clip__c01.mp4"],
            _trial_load_thumbnail=lambda *_args: None,
        )
        gui_premium_v7.InstagramAutoPro._trial_render_account_panel(fake, "eve")
        assert fake.trial_caption_editors[("eve", "T", "clip")].value == "para Eve"
    finally:
        db.close()


def test_trial_sender_uses_account_caption_and_general_manifest_caption(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        db.add_virtual_account("eve", "MAIN")
        db.add_virtual_account("luna", "MAIN")
        eve = _account_id(db, "eve")
        luna = _account_id(db, "luna")
        db.set_trial_account_source_caption(eve, "T", "clip", "para Eve")
        video = {
            "filename": "clip__c01__TANDA_T__ACC1__D1__S1.mp4",
            "tanda": "T", "account_id": eve, "caption_mode": "individual",
        }
        assert organizadortg.resolve_trial_caption(video, {"clip": "global"}, db) == "para Eve"
        video["account_id"] = luna
        assert organizadortg.resolve_trial_caption(video, {"clip": "global"}, db) == "global"
        video["caption_mode"] = "general"
        video["caption"] = "caption general por copia"
        assert organizadortg.resolve_trial_caption(video, {"clip": "global"}, db) == "caption general por copia"
    finally:
        db.close()


def test_telegram_send_uses_each_accounts_saved_trial_caption(tmp_path, monkeypatch):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        for username in ("eve", "luna"):
            db.add_virtual_account(username, "MAIN")
        ids = {row["username"]: row["id"] for row in db.get_all_accounts()}
        db.set_trial_account_source_caption(ids["eve"], "T", "clip", "para Eve")
        db.set_trial_account_source_caption(ids["luna"], "T", "clip", "para Luna")
        video_path = tmp_path / "clip__c01.mp4"
        video_path.write_bytes(b"video")
        videos = [
            {
                "path": str(video_path),
                "filename": f"clip__c01__TANDA_T__ACC{ids[user]}__D1__S1.mp4",
                "day": "Dia_1", "slot": 1, "username": user,
                "account_id": ids[user], "delivery_kind": "trial",
                "tanda": "T", "caption_mode": "individual",
            }
            for user in ("eve", "luna")
        ]
        monkeypatch.setattr(organizadortg, "load_tanda_caption_pools", lambda: {})
        monkeypatch.setattr(organizadortg, "load_trial_caption_maps", lambda: {"T": {"clip": "global"}})
        monkeypatch.setattr(organizadortg, "load_normal_individual_caption_maps", lambda: {})
        monkeypatch.setattr(organizadortg, "scan_calendar_structure", lambda: videos)
        monkeypatch.setattr(organizadortg, "get_accounts_with_va_info", lambda: [
            {"username": user, "account_type": "MAIN", "tg_group_id": "-1001",
             "assigned_va": "VA", "va_timezone": "America/Argentina/Buenos_Aires"}
            for user in ("eve", "luna")
        ])
        monkeypatch.setattr(organizadortg, "_load_delivery_history", lambda _path: {})
        monkeypatch.setattr(organizadortg, "load_json", lambda _path: {})
        monkeypatch.setattr(organizadortg, "save_json", lambda *_args: None)
        monkeypatch.setattr(organizadortg, "get_or_create_topic", lambda *_args, **_kwargs: 701)
        monkeypatch.setattr(organizadortg, "get_slots_for_set", lambda *_args: ["9:00 AM"])
        monkeypatch.setattr(organizadortg, "convert_et_to_va_tz", lambda slot, _tz: (slot, slot))
        monkeypatch.setattr(organizadortg.time, "sleep", lambda _seconds: None)
        sent = {}

        def fake_send(_chat, topic, caption, _path, _state, username, *_args, **_kwargs):
            sent[username] = caption
            return True, topic

        monkeypatch.setattr(organizadortg, "_send_video_to_topic", fake_send)
        result = organizadortg.execute_telegram_plan(
            datetime(2026, 11, 9), selected_accounts=["eve", "luna"],
            express_mode=True, db_manager=db,
        )
        assert "Se enviaron 2 videos" in result
        assert sent == {"eve": "para Eve", "luna": "para Luna"}
    finally:
        db.close()
