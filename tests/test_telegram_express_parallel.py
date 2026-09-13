from datetime import datetime

import database
import organizadortg
from vault.lineage import VaultLineage
from vault.storage import VaultStorage


def _stub_common_telegram_plan(monkeypatch, videos, accounts):
    state = {}
    sent_videos = []
    calls = []

    monkeypatch.setattr(organizadortg, "load_tanda_caption_pools", lambda: {})
    monkeypatch.setattr(organizadortg, "load_trial_caption_maps", lambda: {})
    monkeypatch.setattr(organizadortg, "load_normal_individual_caption_maps", lambda: {})
    monkeypatch.setattr(organizadortg, "get_accounts_with_va_info", lambda: accounts)
    monkeypatch.setattr(organizadortg, "scan_calendar_structure", lambda: videos)
    monkeypatch.setattr(organizadortg, "load_json", lambda _path: state)
    monkeypatch.setattr(organizadortg, "save_json", lambda _path, _data: None)
    monkeypatch.setattr(organizadortg, "get_slots_for_set", lambda *_args: ["9:00 AM"])
    monkeypatch.setattr(organizadortg, "convert_et_to_va_tz", lambda slot, _tz: (slot, slot))
    monkeypatch.setattr(organizadortg.time, "sleep", lambda _seconds: None)

    def fake_get_or_create(chat_id, username, tag, topics_state, is_admin=False, force_recreate=False, delivery_kind="normal"):
        state_key = organizadortg.topic_state_key(chat_id, username, delivery_kind)
        if state_key not in topics_state or force_recreate:
            topics_state[state_key] = 700 + len(topics_state)
        return topics_state[state_key]

    def fake_call_tg(method, data, silent=False):
        calls.append((method, dict(data), silent))
        return {"ok": True}

    def fake_send_video(chat_id, topic_id, caption, video_path, topics_state, username, tag):
        sent_videos.append((chat_id, topic_id, username, video_path))
        return True, topic_id

    monkeypatch.setattr(organizadortg, "get_or_create_topic", fake_get_or_create)
    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    monkeypatch.setattr(organizadortg, "_send_video_to_topic", fake_send_video)
    return calls, sent_videos


def test_express_mode_skips_metadata_send_message(monkeypatch, tmp_path):
    video = tmp_path / "one.mp4"
    video.write_bytes(b"fake")
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch,
        videos=[{
            "path": str(video),
            "filename": "one__TANDA_T__ACC1__D1__S1.mp4",
            "category": "promo",
            "day": "Dia_1",
            "username": "alpha",
        }],
        accounts=[{
            "username": "alpha",
            "account_type": "promo",
            "assigned_va": "VA1",
            "tg_group_id": "-1001",
            "va_timezone": "America/Argentina/Buenos_Aires",
        }],
    )

    result = organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14),
        selected_accounts=["alpha"],
        express_mode=True,
    )

    assert result.startswith("✨ PROCESO TERMINADO")
    assert [method for method, _data, _silent in calls] == []
    assert sent_videos == [("-1001", 700, "alpha", str(video))]


def test_telegram_plan_submits_one_worker_per_chat_by_default(monkeypatch, tmp_path):
    videos = []
    accounts = []
    for index, (username, chat_id) in enumerate([("alpha", "-1001"), ("beta", "-1002")], start=1):
        video = tmp_path / f"{username}.mp4"
        video.write_bytes(b"fake")
        videos.append({
            "path": str(video),
            "filename": f"{username}__TANDA_T__ACC{index}__D1__S1.mp4",
            "category": "promo",
            "day": "Dia_1",
            "username": username,
        })
        accounts.append({
            "username": username,
            "account_type": "promo",
            "assigned_va": f"VA{index}",
            "tg_group_id": chat_id,
            "va_timezone": "America/Argentina/Buenos_Aires",
        })
    _calls, sent_videos = _stub_common_telegram_plan(monkeypatch, videos, accounts)
    submitted = []
    worker_counts = []

    class ImmediateFuture:
        def __init__(self, result):
            self._result = result

        def result(self):
            return self._result

    class ImmediatePool:
        def __init__(self, max_workers):
            worker_counts.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def submit(self, function, *args):
            submitted.append(args[0])
            return ImmediateFuture(function(*args))

    monkeypatch.setattr(organizadortg, "ThreadPoolExecutor", ImmediatePool, raising=False)

    result = organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14),
        selected_accounts=["alpha", "beta"],
    )

    assert result.startswith("✨ PROCESO TERMINADO")
    assert worker_counts == [2]
    assert len(submitted) == 2
    assert {job["chat_id"] for batch in submitted for job in batch} == {"-1001", "-1002"}
    assert len(sent_videos) == 2


def test_telegram_plan_records_vault_usage_after_successful_send(monkeypatch, tmp_path):
    db = database.DatabaseManager(str(tmp_path / "organizador.db"))
    try:
        video = tmp_path / "one.mp4"
        video.write_bytes(b"fake")
        asset = VaultStorage(db, tmp_path / "vault").register_external(video)
        entry_id = "calendar-entry-1"
        _calls, sent_videos = _stub_common_telegram_plan(
            monkeypatch,
            videos=[{
                "id": entry_id,
                "path": str(video.resolve()),
                "source_path": str(video.resolve()),
                "filename": "one__TANDA_T__ACC1__D1__S1.mp4",
                "category": "promo",
                "day": "Dia_1",
                "username": "alpha",
                "delivery_kind": "normal",
            }],
            accounts=[{
                "username": "alpha",
                "account_type": "promo",
                "assigned_va": "VA1",
                "tg_group_id": "-1001",
                "va_timezone": "America/Argentina/Buenos_Aires",
            }],
        )

        result = organizadortg.execute_telegram_plan(
            datetime(2026, 8, 14),
            selected_accounts=["alpha"],
            express_mode=True,
            db_manager=db,
        )

        assert result.startswith("✨ PROCESO TERMINADO")
        assert len(sent_videos) == 1
        usages = VaultLineage(db).usages_for_asset(asset["asset_id"])
        assert [(row["usage_kind"], row["external_ref"]) for row in usages] == [
            ("telegram", entry_id)
        ]
    finally:
        db.close()
