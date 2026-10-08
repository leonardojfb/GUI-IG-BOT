from datetime import datetime
import hashlib

import organizadortg
from airtable_sync import AirtableSyncError


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
    monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object())
    monkeypatch.setattr(organizadortg, "fetch_published_video_hashes", lambda _config: set())

    def fake_get_or_create(chat_id, username, tag, topics_state, is_admin=False, force_recreate=False, delivery_kind="normal"):
        state_key = organizadortg.topic_state_key(chat_id, username, delivery_kind)
        if state_key not in topics_state or force_recreate:
            topics_state[state_key] = 700 + len(topics_state)
        return topics_state[state_key]

    def fake_call_tg(method, data, silent=False):
        calls.append((method, dict(data), silent))
        return {"ok": True}

    def fake_send_video(chat_id, topic_id, caption, video_path, topics_state, username, tag, source_hash=None):
        sent_videos.append((chat_id, topic_id, username, video_path))
        return True, topic_id

    monkeypatch.setattr(organizadortg, "get_or_create_topic", fake_get_or_create)
    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    monkeypatch.setattr(organizadortg, "_send_video_to_topic", fake_send_video)
    return calls, sent_videos


def _account(username, chat_id):
    return {
        "username": username,
        "account_type": "promo",
        "assigned_va": "VA1",
        "tg_group_id": chat_id,
        "va_timezone": "America/Argentina/Buenos_Aires",
    }


def _video(path, username, filename=None):
    return {
        "path": str(path),
        "filename": filename or path.name,
        "category": "promo",
        "day": "Dia_1",
        "username": username,
    }


def test_plan_omits_identical_published_bytes_for_every_account(monkeypatch, tmp_path):
    old = tmp_path / "old.mp4"
    new = tmp_path / "new.mp4"
    old.write_bytes(b"same")
    new.write_bytes(b"different")
    _calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch,
        [
            _video(old, "alpha"),
            _video(old, "beta", "renamed.mp4"),
            _video(new, "beta"),
        ],
        [_account("alpha", "-1001"), _account("beta", "-1002")],
    )
    published_hash = hashlib.sha256(old.read_bytes()).hexdigest()
    monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object(), raising=False)
    monkeypatch.setattr(
        organizadortg,
        "fetch_published_video_hashes",
        lambda _config: {published_hash},
        raising=False,
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 8, 14))

    assert [video[3] for video in sent_videos] == [str(new)]
    assert "Omitidos publicados: 2" in result


def test_plan_fails_closed_before_topic_creation_on_airtable_error(monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"test")
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [_video(video, "alpha")], [_account("alpha", "-1001")]
    )
    monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object(), raising=False)

    def unavailable(_config):
        raise AirtableSyncError("down")

    monkeypatch.setattr(
        organizadortg, "fetch_published_video_hashes", unavailable, raising=False
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 8, 14))

    assert result == "❌ No se pudo verificar Airtable; no se enviaron videos."
    assert calls == []
    assert sent_videos == []


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
