import json
from datetime import datetime

import organizadortg


def test_trial_copies_receive_identical_literal_caption():
    captions = {"vid1": "Caption 1\n#uno", "vid2": "Caption 2\n#dos"}
    first = "vid1__c01__TANDA_TRIAL_ONE__ACC1__D1__S1.mp4"
    second = "vid1__c02__TANDA_TRIAL_ONE__ACC1__D1__S2.mp4"
    assert organizadortg.caption_for_trial_calendar_video(first, captions) == captions["vid1"]
    assert organizadortg.caption_for_trial_calendar_video(second, captions) == captions["vid1"]


def test_trial_topic_state_key_is_distinct_from_normal():
    assert organizadortg.topic_state_key("-100", "eve", "normal") == "-100_eve"
    assert organizadortg.topic_state_key("-100", "eve", "trial") == "-100_eve_trials"


def test_scan_includes_only_trials_for_active_accounts(tmp_path, monkeypatch):
    trial_root = tmp_path / "CALENDARIO_TRIALS"
    active = trial_root / "Dia_1" / "eve"
    inactive = trial_root / "Dia_1" / "spam"
    active.mkdir(parents=True)
    inactive.mkdir(parents=True)
    (active / "vid1__c01__TANDA_T__ACC1__D1__S1.mp4").write_bytes(b"x")
    (inactive / "vid2__c01__TANDA_T__ACC2__D1__S1.mp4").write_bytes(b"x")
    monkeypatch.setattr(organizadortg, "base_dir", str(tmp_path))
    monkeypatch.setattr(organizadortg, "input_root", str(tmp_path / "no-normal"))
    monkeypatch.setattr(organizadortg, "trial_input_root", str(trial_root))
    monkeypatch.setattr(organizadortg, "get_accounts_with_va_info", lambda: [
        {"username": "eve", "account_type": "main", "trials_active": True},
        {"username": "spam", "account_type": "SPAM", "trials_active": False},
    ])
    scanned = organizadortg.scan_calendar_structure()
    assert [(row["username"], row["delivery_kind"]) for row in scanned] == [("eve", "trial")]


def test_telegram_account_video_count_includes_trial_calendar(tmp_path):
    normal_root = tmp_path / "CALENDARIO_POSTEO"
    trial_root = tmp_path / "CALENDARIO_TRIALS"
    (normal_root / "Dia_1" / "eve").mkdir(parents=True)
    (trial_root / "Dia_1" / "eve").mkdir(parents=True)
    (trial_root / "Dia_2" / "eve").mkdir(parents=True)
    (trial_root / "Dia_1" / "other").mkdir(parents=True)
    (normal_root / "Dia_1" / "eve" / "normal.mp4").write_bytes(b"x")
    (trial_root / "Dia_1" / "eve" / "trial-one.mp4").write_bytes(b"x")
    (trial_root / "Dia_2" / "eve" / "trial-two.mov").write_bytes(b"x")
    (trial_root / "Dia_1" / "other" / "other.mp4").write_bytes(b"x")

    counter = getattr(organizadortg, "count_account_calendar_videos", None)

    assert counter is not None
    assert counter("eve", roots=(normal_root, trial_root)) == 3


def test_telegram_account_video_count_splits_normal_and_trial(tmp_path):
    normal_root = tmp_path / "CALENDARIO_POSTEO"
    trial_root = tmp_path / "CALENDARIO_TRIALS"
    (normal_root / "Dia_1" / "eve").mkdir(parents=True)
    (trial_root / "Dia_1" / "eve").mkdir(parents=True)
    (normal_root / "Dia_1" / "eve" / "normal.mp4").write_bytes(b"x")
    (trial_root / "Dia_1" / "eve" / "trial-one.mp4").write_bytes(b"x")
    (trial_root / "Dia_1" / "eve" / "trial-two.mov").write_bytes(b"x")

    counts = organizadortg.count_account_calendar_videos_by_kind(
        "eve",
        normal_root=normal_root,
        trial_root=trial_root,
    )

    assert counts == {"normal": 1, "trial": 2}


def test_batch_account_counts_use_telegram_manifest_rows_without_origin_lookups(
    tmp_path, monkeypatch
):
    manifest = tmp_path / "calendar_manifest.json"
    normal_video = tmp_path / "normal.mp4"
    trial_video = tmp_path / "trial.mp4"
    inactive_trial_video = tmp_path / "inactive-trial.mp4"
    missing_video = tmp_path / "missing.mp4"
    for path in (normal_video, trial_video, inactive_trial_video):
        path.write_bytes(b"video")

    entries = [
        {
            "username": "eve",
            "delivery_kind": "normal",
            "source_path": str(normal_video),
            "publication_target": "instagram_reel",
        },
        {
            "username": "eve",
            "delivery_kind": "trial",
            "source_path": str(trial_video),
            "publication_target": "instagram_trial_reel",
        },
        {
            "username": "inactive",
            "delivery_kind": "trial",
            "source_path": str(inactive_trial_video),
            "publication_target": "instagram_trial_reel",
        },
        {
            "username": "eve",
            "delivery_kind": "normal",
            "source_path": str(tmp_path / "facebook.mp4"),
            "publication_target": "facebook_reel",
        },
        {
            "username": "eve",
            "delivery_kind": "normal",
            "source_path": str(missing_video),
            "publication_target": "instagram_reel",
        },
    ]
    manifest.write_text(json.dumps({"version": 1, "entries": entries}), encoding="utf-8")

    monkeypatch.setattr(organizadortg, "_manifest_exists", lambda: True)
    monkeypatch.setattr(organizadortg, "_calendar_manifest_file", lambda: str(manifest))
    original_load_entries = organizadortg.load_entries
    load_calls = []

    def counted_load_entries(path, require_source=True):
        load_calls.append((path, require_source))
        return original_load_entries(path, require_source=require_source)

    monkeypatch.setattr(organizadortg, "load_entries", counted_load_entries)
    monkeypatch.setattr(
        organizadortg,
        "_manifest_origin_identity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("origin lookup")),
    )
    monkeypatch.setattr(
        organizadortg,
        "get_accounts_with_va_info",
        lambda: (_ for _ in ()).throw(AssertionError("account database lookup")),
    )

    counts = organizadortg.count_calendar_videos_by_account()

    assert counts == {
        "eve": {"normal": 1, "trial": 1},
        "inactive": {"normal": 0, "trial": 1},
    }
    assert load_calls == [(str(manifest), True)]


def test_batch_account_counts_scan_explicit_roots_once_per_delivery_kind(tmp_path):
    normal_root = tmp_path / "normal"
    trial_root = tmp_path / "trial"
    (normal_root / "Dia_1" / "eve").mkdir(parents=True)
    (normal_root / "NotADay" / "eve").mkdir(parents=True)
    (trial_root / "Dia_2" / "eve").mkdir(parents=True)
    (normal_root / "Dia_3").write_bytes(b"not a folder")
    (normal_root / "Dia_1" / "eve" / "normal.mp4").write_bytes(b"x")
    (normal_root / "Dia_1" / "eve" / "ignored.txt").write_bytes(b"x")
    (normal_root / "NotADay" / "eve" / "ignored.mp4").write_bytes(b"x")
    (trial_root / "Dia_2" / "eve" / "trial.mov").write_bytes(b"x")

    counts = organizadortg.count_calendar_videos_by_account(
        normal_root=normal_root,
        trial_root=trial_root,
    )

    assert counts["eve"] == {"normal": 1, "trial": 1}


def test_telegram_video_label_marks_trial_only_accounts():
    assert organizadortg.format_account_calendar_video_label({"normal": 0, "trial": 125}) == "125 videos TRIALS"
    assert organizadortg.format_account_calendar_video_label({"normal": 2, "trial": 3}) == "5 videos (2 normales, 3 TRIALS)"


def test_trial_only_send_precreates_only_trial_topic(monkeypatch, tmp_path):
    created = []
    state = {}
    video_path = tmp_path / "trial.mp4"
    video_path.write_bytes(b"trial video")

    monkeypatch.setattr(organizadortg, "load_tanda_caption_pools", lambda: {})
    monkeypatch.setattr(organizadortg, "load_trial_caption_maps", lambda: {})
    monkeypatch.setattr(organizadortg, "load_normal_individual_caption_maps", lambda: {})
    monkeypatch.setattr(organizadortg, "get_accounts_with_va_info", lambda: [
        {"id": 1, "username": "eve", "account_type": "MAIN", "trials_active": True, "tg_group_id": "-1001", "assigned_va": "Leo"},
    ])
    monkeypatch.setattr(organizadortg, "scan_calendar_structure", lambda: [
        {
            "path": str(video_path),
            "filename": "vid1__c01__TANDA_T__ACC1__D1__S1.mp4",
            "category": "main",
            "day": "Dia_1",
            "username": "eve",
            "account_id": 1,
            "delivery_kind": "trial",
            "caption_mode": "general",
            "caption": "caption fijo por copia",
        },
    ])
    monkeypatch.setattr(organizadortg, "load_json", lambda _path: state)
    monkeypatch.setattr(organizadortg, "save_json", lambda _path, _data: None)
    monkeypatch.setattr(organizadortg, "_load_delivery_history", lambda _path: {})
    monkeypatch.setattr(organizadortg, "_source_sha256", lambda _path: "a" * 64)
    monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object())
    monkeypatch.setattr(
        organizadortg, "fetch_published_video_publications",
        lambda _config: (_ for _ in ()).throw(AssertionError("trial must not query Airtable publications")),
    )
    monkeypatch.setattr(organizadortg, "get_slots_for_set", lambda *_args: ["9:00 AM"])
    monkeypatch.setattr(organizadortg, "convert_et_to_va_tz", lambda slot, _tz: (slot, slot))
    monkeypatch.setattr(organizadortg.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(organizadortg, "call_tg", lambda *_args, **_kwargs: {"ok": True})
    sent_captions = []

    def fake_send(*args, **_kwargs):
        sent_captions.append(args[2])
        return True, args[1]

    monkeypatch.setattr(organizadortg, "_send_video_to_topic", fake_send)

    def fake_get_or_create(chat_id, username, tag, topics_state, is_admin=False, force_recreate=False, delivery_kind="normal"):
        state_key = organizadortg.topic_state_key(chat_id, username, delivery_kind)
        if state_key in topics_state and not force_recreate:
            return topics_state[state_key]
        created.append(delivery_kind)
        topic_id = 700 + len(created)
        topics_state[state_key] = topic_id
        return topic_id

    monkeypatch.setattr(organizadortg, "get_or_create_topic", fake_get_or_create)

    result = organizadortg.execute_telegram_plan(datetime(2026, 8, 14), selected_accounts=["eve"])

    assert result.startswith("✨ PROCESO TERMINADO")
    assert created == ["trial"]
    assert sent_captions == ["caption fijo por copia"]


def test_execute_plan_can_use_gui_database_manager(monkeypatch):
    class BrokenDb:
        def get_all_tandas(self):
            raise AssertionError("global telegram db should not be used")

    class GuiDb:
        def __init__(self):
            self.schedule_calls = []

        def get_all_tandas(self):
            return []

        def get_trial_tandas(self):
            return []

        def get_all_accounts(self):
            return [{
                "username": "eve",
                "account_type": "MAIN",
                "assigned_va": "Sin Asignar",
                "trials_active": 0,
            }]

        def get_vas(self):
            return []

        def get_schedule_config(self, va_name, category, day_of_week):
            self.schedule_calls.append((va_name, category, day_of_week))
            return None

    gui_db = GuiDb()
    state = {}
    monkeypatch.setattr(organizadortg, "db", BrokenDb())
    monkeypatch.setattr(organizadortg, "scan_calendar_structure", lambda: [{
        "path": "normal.mp4",
        "filename": "vid1__TANDA_T__ACC1__D1__S1.mp4",
        "category": "main",
        "day": "Dia_1",
        "username": "eve",
        "account_id": "1",
        "delivery_kind": "normal",
    }])
    monkeypatch.setattr(organizadortg, "load_json", lambda _path: state)
    monkeypatch.setattr(organizadortg, "save_json", lambda _path, _data: None)
    monkeypatch.setattr(organizadortg, "_load_delivery_history", lambda _path: {})
    monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object())
    monkeypatch.setattr(organizadortg, "fetch_published_video_publications", lambda _config: (set(), set()))
    monkeypatch.setattr(organizadortg, "_source_sha256", lambda _path: "a" * 64)
    monkeypatch.setattr(organizadortg, "convert_et_to_va_tz", lambda slot, _tz: (slot, slot))
    monkeypatch.setattr(organizadortg.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(organizadortg, "call_tg", lambda *_args, **_kwargs: {"ok": True, "result": True})
    monkeypatch.setattr(organizadortg, "_send_video_to_topic", lambda *args: (True, args[1]))
    monkeypatch.setattr(organizadortg, "get_or_create_topic", lambda *_args, **_kwargs: 101)

    result = organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14),
        selected_accounts=["eve"],
        db_manager=gui_db,
    )

    assert "PROCESO TERMINADO" in result
    assert gui_db.schedule_calls == [("Sin Asignar", "main", 4)]
