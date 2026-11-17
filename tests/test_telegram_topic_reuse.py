"""Regression coverage for stale Telegram thread IDs."""

from datetime import datetime

import pytest

import organizadortg


@pytest.mark.parametrize("express_mode", [False, True])
@pytest.mark.parametrize("delivery_kind", ["trial", "normal"])
def test_stale_thread_is_recreated_once_for_whole_batch(
    monkeypatch, tmp_path, express_mode, delivery_kind,
):
    video = tmp_path / "copy.mp4"
    video.write_bytes(b"video")
    username = "trial-account"
    chat_id = "-1001"
    state_key = organizadortg.topic_state_key(chat_id, username, delivery_kind)
    state = {state_key: {"id": 7, "name": "TRIALS - trial-account MAIN"}}
    valid_threads = set()
    creations = []
    delivered_threads = []

    videos = [
        {
            "path": str(video),
            "filename": f"copy{i}__TANDA_T__ACC1__D1__S{i}.mp4",
            "category": "main",
            "day": "Dia_1",
            "username": username,
            "account_id": 1,
            "delivery_kind": delivery_kind,
        }
        for i in range(207)
    ]
    account = {
        "username": username, "account_type": "MAIN", "trials_active": True,
        "tg_group_id": chat_id, "assigned_va": "VA",
        "va_timezone": "America/Argentina/Buenos_Aires",
    }
    monkeypatch.setattr(organizadortg, "base_dir", str(tmp_path))
    monkeypatch.setattr(organizadortg, "load_tanda_caption_pools", lambda: {})
    monkeypatch.setattr(organizadortg, "load_trial_caption_maps", lambda: {})
    monkeypatch.setattr(organizadortg, "load_normal_individual_caption_maps", lambda: {})
    monkeypatch.setattr(organizadortg, "get_accounts_with_va_info", lambda: [account])
    monkeypatch.setattr(organizadortg, "scan_calendar_structure", lambda: videos)
    monkeypatch.setattr(organizadortg, "_load_delivery_history", lambda _path: {})
    monkeypatch.setattr(organizadortg, "_save_delivery_history", lambda *_args: None)
    monkeypatch.setattr(organizadortg, "_source_sha256", lambda _path: "a" * 64)
    monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object())
    monkeypatch.setattr(organizadortg, "fetch_published_video_publications", lambda _config: (set(), set()))
    monkeypatch.setattr(organizadortg, "load_json", lambda _path: state)
    monkeypatch.setattr(organizadortg, "save_json", lambda *_args: None)
    monkeypatch.setattr(organizadortg, "get_slots_for_set", lambda *_args: ["9:00 AM"])
    monkeypatch.setattr(organizadortg, "convert_et_to_va_tz", lambda slot, _tz: (slot, slot))
    monkeypatch.setattr(organizadortg, "resolve_trial_caption", lambda *_args: None)
    monkeypatch.setattr(organizadortg.time, "sleep", lambda _seconds: None)

    def fake_call_tg(method, data, silent=False):
        if method == "createForumTopic":
            thread_id = 100 + len(creations)
            creations.append((data["name"], thread_id))
            valid_threads.add(thread_id)
            return {"ok": True, "result": {"message_thread_id": thread_id}}
        if method == "sendMessage":
            valid = data["message_thread_id"] in valid_threads
            return {"ok": valid, "description": "message thread not found" if not valid else ""}
        raise AssertionError(method)

    class Response:
        def __init__(self, thread_id):
            self.status_code = 200 if thread_id in valid_threads else 400
            self.text = "" if self.status_code == 200 else "message thread not found"
            if self.status_code == 200:
                delivered_threads.append(thread_id)

    def fake_post(_url, *, data, files):
        return Response(data["message_thread_id"])

    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    monkeypatch.setattr(organizadortg.requests, "post", fake_post)
    result = organizadortg.execute_telegram_plan(
        datetime(2026, 11, 17), selected_accounts=[username], express_mode=express_mode,
        allow_delivered_repeats=delivery_kind == "normal",
    )

    assert "Se enviaron 207 videos" in result
    assert len(creations) == 1
    assert delivered_threads == [creations[0][1]] * 207
    assert state[state_key]["id"] == creations[0][1]
    other_kind = "normal" if delivery_kind == "trial" else "trial"
    assert organizadortg.topic_state_key(chat_id, username, other_kind) not in state
