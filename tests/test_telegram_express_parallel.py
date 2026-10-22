from datetime import datetime
import hashlib
import json
from pathlib import Path

import organizadortg
from airtable_sync import AirtableSyncError
from calendar_manifest import build_entry, replace_entries
from database import DatabaseManager


def test_manifest_origin_identity_falls_back_to_persisted_transform_log(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    source = tmp_path / "source.mp4"
    output = tmp_path / "variation.mp4"
    source.write_bytes(b"source")
    output.write_bytes(b"variation")
    log_id = db.save_video_transform_log(
        "forge",
        str(source),
        str(output),
        {},
        tanda_name="TANDA",
        source_identity="origin-persisted",
    )

    identity = organizadortg._manifest_origin_identity(
        {"source_path": str(output), "transform_log_id": log_id},
        db,
    )

    assert identity == "origin-persisted"
    db.close()


def _stub_common_telegram_plan(monkeypatch, videos, accounts):
    state = {}
    sent_videos = []
    calls = []
    monkeypatch.setattr(organizadortg, "base_dir", str(Path(videos[0]["path"]).parent))

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
    monkeypatch.setattr(organizadortg, "fetch_published_video_origins", lambda _config: set())
    monkeypatch.setattr(
        organizadortg,
        "fetch_published_video_publications",
        lambda _config: (set(), set()),
        raising=False,
    )

    def fake_get_or_create(chat_id, username, tag, topics_state, is_admin=False, force_recreate=False, delivery_kind="normal"):
        state_key = organizadortg.topic_state_key(chat_id, username, delivery_kind)
        if state_key not in topics_state or force_recreate:
            topics_state[state_key] = 700 + len(topics_state)
        return topics_state[state_key]

    def fake_call_tg(method, data, silent=False):
        calls.append((method, dict(data), silent))
        return {"ok": True}

    def fake_send_video(chat_id, topic_id, caption, video_path, topics_state, username, tag, source_hash=None, origin_token=None, upload_filename=None, delivery_kind="normal"):
        sent_videos.append((chat_id, topic_id, username, video_path, delivery_kind))
        return True, topic_id

    monkeypatch.setattr(organizadortg, "get_or_create_topic", fake_get_or_create)
    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    monkeypatch.setattr(organizadortg, "_send_video_to_topic", fake_send_video)
    return calls, sent_videos


def _account(username, chat_id, account_id=None):
    return {
        "id": account_id or {"alpha": 1, "beta": 2}.get(username, 99),
        "username": username,
        "account_type": "promo",
        "assigned_va": "VA1",
        "tg_group_id": chat_id,
        "va_timezone": "America/Argentina/Buenos_Aires",
    }


def _video(path, username, filename=None, origin_identity=None, account_id=None):
    resolved_account_id = account_id or {"alpha": 1, "beta": 2}.get(username, 99)
    video = {
        "path": str(path),
        "filename": filename or f"{path.stem}__ACC{resolved_account_id}__D1__S1{path.suffix}",
        "category": "promo",
        "day": "Dia_1",
        "username": username,
        "account_id": resolved_account_id,
    }
    if origin_identity:
        video["origin_identity"] = origin_identity
    return video


def test_send_video_uses_calendar_filename_with_account_id(monkeypatch, tmp_path):
    video = tmp_path / "physical-copy.mov"
    video.write_bytes(b"fake")
    captured = {}

    class Response:
        status_code = 200
        text = ""

    def fake_post(_url, *, data, files):
        captured["upload_name"] = files["video"][0]
        captured["callback"] = json.loads(data["reply_markup"])["inline_keyboard"][0][0]["callback_data"]
        return Response()

    monkeypatch.setattr(organizadortg.requests, "post", fake_post)

    ok, _topic = organizadortg._send_video_to_topic(
        "-1001", 7, "caption", str(video), {}, "alpha", "PROMO",
        source_hash="a" * 64,
        origin_token="b" * 16,
        upload_filename="clip__ACC149__D1__S1.mov",
    )

    assert ok is True
    assert captured["upload_name"] == "clip__ACC149__D1__S1.mov"
    assert len(captured["callback"]) == 64
    assert captured["callback"].startswith("v1")


def test_trial_video_publish_button_is_visual_only(monkeypatch, tmp_path):
    video = tmp_path / "trial-copy.mov"
    video.write_bytes(b"trial")
    captured = {}

    class Response:
        status_code = 200
        text = ""

    def fake_post(_url, *, data, files):
        captured["callback"] = json.loads(data["reply_markup"])["inline_keyboard"][0][0]["callback_data"]
        return Response()

    monkeypatch.setattr(organizadortg.requests, "post", fake_post)

    ok, _topic = organizadortg._send_video_to_topic(
        "-1001", 7, "caption", str(video), {}, "alpha", "PROMO",
        source_hash="a" * 64,
        origin_token="b" * 16,
        upload_filename="clip__ACC149__D1__S1.mov",
        delivery_kind="trial",
    )

    assert ok is True
    assert captured["callback"] == "pub"


def test_plan_fails_closed_when_manifest_account_id_is_missing(monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"test")
    item = _video(video, "alpha")
    item["account_id"] = None
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [item], [_account("alpha", "-1001")]
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 8, 14))

    assert result == "❌ El calendario tiene identidad de cuenta inválida; no se enviaron videos."
    assert calls == []
    assert sent_videos == []


def test_plan_fails_closed_when_manifest_account_disagrees_with_filename(monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"test")
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch,
        [_video(video, "alpha", filename="video__ACC2__D1__S1.mp4", account_id=1)],
        [_account("alpha", "-1001")],
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 8, 14))

    assert result == "❌ El calendario tiene identidad de cuenta inválida; no se enviaron videos."
    assert calls == []
    assert sent_videos == []


def test_plan_omits_identical_published_bytes_only_for_matching_account(monkeypatch, tmp_path):
    old = tmp_path / "old.mp4"
    new = tmp_path / "new.mp4"
    old.write_bytes(b"same")
    new.write_bytes(b"different")
    _calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch,
        [
            _video(old, "alpha"),
            _video(old, "beta", "renamed__ACC2__D1__S1.mp4"),
            _video(new, "beta"),
        ],
        [_account("alpha", "-1001"), _account("beta", "-1002")],
    )
    published_hash = hashlib.sha256(old.read_bytes()).hexdigest()
    monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object(), raising=False)
    monkeypatch.setattr(
        organizadortg,
        "fetch_published_video_publications",
        lambda _config: ({("1", published_hash)}, set()),
        raising=False,
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 8, 14))

    assert [video[3] for video in sent_videos] == [str(old), str(new)]
    assert [video[2] for video in sent_videos] == ["beta", "beta"]
    assert "Omitidos publicados: 1" in result


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
        organizadortg, "fetch_published_video_publications", unavailable, raising=False
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 8, 14))

    assert result == "❌ No se pudo verificar Airtable; no se enviaron videos."
    assert calls == []
    assert sent_videos == []

    opted_in_result = organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14), allow_published_repeats=True,
    )
    assert opted_in_result == result
    assert calls == []
    assert sent_videos == []


def test_plan_omits_published_origin_only_for_matching_account(monkeypatch, tmp_path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    other = tmp_path / "other.mp4"
    first.write_bytes(b"variation-one")
    second.write_bytes(b"variation-two")
    other.write_bytes(b"different-origin")
    _calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch,
        [
            _video(first, "alpha", origin_identity="origin-A"),
            _video(second, "beta", origin_identity="origin-A"),
            _video(other, "beta", origin_identity="origin-B"),
        ],
        [_account("alpha", "-1001"), _account("beta", "-1002")],
    )
    monkeypatch.setattr(
        organizadortg,
        "fetch_published_video_publications",
        lambda _config: (
            set(),
            {("1", organizadortg.origin_token_from_identity("origin-A"))},
        ),
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 8, 14))

    assert [video[3] for video in sent_videos] == [str(second), str(other)]
    assert [video[2] for video in sent_videos] == ["beta", "beta"]
    assert "Omitidos publicados: 1" in result


def test_opt_in_repeats_published_origin_only_for_its_account(monkeypatch, tmp_path):
    alpha = tmp_path / "alpha.mp4"
    alpha_copy = tmp_path / "alpha-copy.mp4"
    beta = tmp_path / "beta.mp4"
    for path in (alpha, alpha_copy, beta):
        path.write_bytes(path.name.encode())
    videos = [
        _video(alpha, "alpha", origin_identity="shared-origin"),
        _video(alpha_copy, "alpha", origin_identity="shared-origin"),
        _video(beta, "beta", origin_identity="shared-origin"),
    ]
    _calls, sent = _stub_common_telegram_plan(
        monkeypatch, videos,
        [_account("alpha", "-1001"), _account("beta", "-1002")],
    )
    token = organizadortg.origin_token_from_identity("shared-origin")
    organizadortg._save_delivery_history(
        tmp_path / organizadortg.DELIVERY_HISTORY_FILE,
        {"1": {token}, "2": {token}},
    )
    monkeypatch.setattr(
        organizadortg, "fetch_published_video_publications",
        lambda _config: (set(), {("1", token)}),
    )

    result = organizadortg.execute_telegram_plan(
        datetime(2026, 10, 14), allow_published_repeats=True,
    )

    assert [(video[2], video[3]) for video in sent] == [("alpha", str(alpha))]
    assert "Omitidos publicados: 0" in result
    assert "Omitidos por origin duplicado en la cuenta: 1" in result
    assert "Omitidos por origin ya enviado a la cuenta: 1" in result


def test_plan_sends_each_origin_once_per_account_across_tandas_and_days(monkeypatch, tmp_path):
    first = tmp_path / "tjp-copy.mp4"
    second = tmp_path / "talking-copy.mp4"
    third = tmp_path / "other-account-copy.mp4"
    for path in (first, second, third):
        path.write_bytes(path.name.encode())
    first_video = _video(first, "alpha", origin_identity="shared-origin")
    second_video = _video(second, "alpha", origin_identity="shared-origin")
    second_video["day"] = "Dia_6"
    third_video = _video(third, "beta", origin_identity="shared-origin")
    _calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch,
        [first_video, second_video, third_video],
        [_account("alpha", "-1001"), _account("beta", "-1002")],
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 10, 12))

    assert [(video[2], video[3]) for video in sent_videos] == [
        ("alpha", str(first)), ("beta", str(third)),
    ]
    assert "Omitidos por origin duplicado en la cuenta: 1" in result


def test_saved_cross_tanda_duplicate_is_skipped_by_telegram(monkeypatch, tmp_path):
    first = tmp_path / "tjp-copy.mp4"
    second = tmp_path / "talking-copy.mp4"
    first.write_bytes(b"variation-one")
    second.write_bytes(b"variation-two")
    manifest = tmp_path / "calendar_manifest.json"
    for path, tanda, day in ((first, "TJP OCT", 1), (second, "Talking", 6)):
        entry = build_entry(
            "alpha", 1, "normal", day, 1, tanda, str(path),
            f"{path.stem}__ACC1__D{day}__S1.mp4",
            origin_identity="shared-origin",
        )
        replace_entries(manifest, [entry], {"alpha"}, "normal", tanda_names={tanda})

    _calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [_video(first, "alpha")], [_account("alpha", "-1001")],
    )
    monkeypatch.setattr(
        organizadortg, "scan_calendar_structure",
        lambda: organizadortg._scan_manifest_calendar_structure(manifest),
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 10, 12))

    assert [video[3] for video in sent_videos] == [str(first)]
    assert "Omitidos por origin duplicado en la cuenta: 1" in result


def test_successful_send_blocks_same_origin_in_later_run(monkeypatch, tmp_path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"variation-one")
    second.write_bytes(b"variation-two")
    monkeypatch.setattr(organizadortg, "base_dir", str(tmp_path))
    _calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [_video(first, "alpha", origin_identity="shared-origin")],
        [_account("alpha", "-1001")],
    )
    organizadortg.execute_telegram_plan(datetime(2026, 10, 12))
    monkeypatch.setattr(
        organizadortg, "scan_calendar_structure",
        lambda: [_video(second, "alpha", origin_identity="shared-origin")],
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 10, 13))

    assert [video[3] for video in sent_videos] == [str(first)]
    assert "Omitidos por origin ya enviado a la cuenta: 1" in result


def test_opt_in_resends_delivered_origin_without_erasing_history(monkeypatch, tmp_path):
    alpha = tmp_path / "alpha.mp4"
    alpha_copy = tmp_path / "alpha-copy.mp4"
    beta = tmp_path / "beta.mp4"
    for path in (alpha, alpha_copy, beta):
        path.write_bytes(path.name.encode())
    videos = [
        _video(alpha, "alpha", origin_identity="shared-origin"),
        _video(alpha_copy, "alpha", origin_identity="shared-origin"),
        _video(beta, "beta", origin_identity="shared-origin"),
    ]
    _calls, sent = _stub_common_telegram_plan(
        monkeypatch, videos,
        [_account("alpha", "-1001"), _account("beta", "-1002")],
    )
    token = organizadortg.origin_token_from_identity("shared-origin")
    history_path = tmp_path / organizadortg.DELIVERY_HISTORY_FILE
    organizadortg._save_delivery_history(history_path, {"1": {token}, "2": {token}})
    monkeypatch.setattr(
        organizadortg, "fetch_published_video_publications",
        lambda _config: (set(), {("2", token)}),
    )

    result = organizadortg.execute_telegram_plan(
        datetime(2026, 10, 14), allow_delivered_repeats=True,
    )

    assert [(video[2], video[3]) for video in sent] == [("alpha", str(alpha))]
    assert "Omitidos por origin duplicado en la cuenta: 1" in result
    assert "Omitidos publicados: 1" in result
    assert organizadortg._load_delivery_history(history_path) == {"1": {token}, "2": {token}}


def test_corrupt_delivery_history_stops_before_telegram_calls(monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(organizadortg, "base_dir", str(tmp_path))
    (tmp_path / organizadortg.DELIVERY_HISTORY_FILE).write_text("{broken", encoding="utf-8")
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [_video(video, "alpha", origin_identity="origin-A")],
        [_account("alpha", "-1001")],
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 10, 12))

    assert result == "❌ No se pudo leer el historial de envíos; no se enviaron videos."
    assert calls == []
    assert sent_videos == []


def test_publication_without_account_does_not_omit_origin_for_any_account(monkeypatch, tmp_path):
    video = tmp_path / "another-copy.mp4"
    video.write_bytes(b"another variation")
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [_video(video, "alpha", origin_identity="origin-A")],
        [_account("alpha", "-1001")],
    )
    token = organizadortg.origin_token_from_identity("origin-A")
    monkeypatch.setattr(
        organizadortg, "fetch_published_video_publications",
        lambda _config: (set(), {("*", token)}),
    )
    result = organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14), selected_accounts=["alpha"],
        reset_topics=True, express_mode=True,
    )
    assert "Omitidos publicados: 0" in result
    assert [video[3] for video in sent_videos] == [str(video)]
    assert calls == []


def test_unscoped_wavespeed_publication_does_not_block_another_account(monkeypatch, tmp_path):
    source_name = "wavespeed_" + "f" * 32
    video = tmp_path / f"{source_name}__c17.mov"
    video.write_bytes(b"new Forge copy")
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [_video(video, "alpha", origin_identity="real-origin")],
        [_account("alpha", "-1001")],
    )
    monkeypatch.setattr(
        organizadortg, "fetch_published_video_publications",
        lambda _config: (set(), {("*", "source-family:" + source_name)}),
    )
    result = organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14), selected_accounts=["alpha"],
        reset_topics=True, express_mode=True,
    )
    assert "Omitidos publicados: 0" in result
    assert calls == []
    assert [video[3] for video in sent_videos] == [str(video)]


def test_unscoped_published_hash_does_not_block_other_accounts(monkeypatch, tmp_path):
    video = tmp_path / "same-bytes.mp4"
    video.write_bytes(b"same bytes")
    _calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [_video(video, "alpha", origin_identity="origin-A")],
        [_account("alpha", "-1001")],
    )
    published_hash = hashlib.sha256(video.read_bytes()).hexdigest()
    monkeypatch.setattr(
        organizadortg, "fetch_published_video_publications",
        lambda _config: ({("*", published_hash)}, set()),
    )

    result = organizadortg.execute_telegram_plan(datetime(2026, 8, 14))

    assert "Omitidos publicados: 0" in result
    assert [item[3] for item in sent_videos] == [str(video)]


def test_manifest_video_without_provable_origin_is_sent_when_hash_is_unpublished(monkeypatch, tmp_path):
    video = tmp_path / "edited-photo.mp4"
    video.write_bytes(b"variation")
    item = _video(video, "alpha")
    item["origin_required"] = True
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [item], [_account("alpha", "-1001")],
    )
    result = organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14), selected_accounts=["alpha"],
        reset_topics=True, express_mode=True,
    )
    assert "Videos sin origin (comparados por SHA-256): 1" in result
    assert calls == []
    assert [video[3] for video in sent_videos] == [str(video)]


def test_express_with_topic_reset_deletes_topic_without_metadata(monkeypatch, tmp_path):
    video = tmp_path / "fresh.mp4"
    video.write_bytes(b"fresh")
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [_video(video, "alpha", origin_identity="new-origin")],
        [_account("alpha", "-1001")],
    )
    state = {organizadortg.topic_state_key("-1001", "alpha", "normal"): 123}
    monkeypatch.setattr(organizadortg, "load_json", lambda _path: state)
    result = organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14), selected_accounts=["alpha"],
        reset_topics=True, express_mode=True,
    )
    assert result.startswith("✨ PROCESO TERMINADO")
    assert [method for method, _data, _silent in calls] == ["deleteForumTopic"]
    assert len(sent_videos) == 1


def test_topic_reset_preserves_topic_when_all_normal_videos_are_published(monkeypatch, tmp_path):
    video = tmp_path / "published.mp4"
    video.write_bytes(b"already published")
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [_video(video, "alpha", origin_identity="old-origin")],
        [_account("alpha", "-1001")],
    )
    state = {organizadortg.topic_state_key("-1001", "alpha", "normal"): 123}
    monkeypatch.setattr(organizadortg, "load_json", lambda _path: state)
    token = organizadortg.origin_token_from_identity("old-origin")
    monkeypatch.setattr(
        organizadortg, "fetch_published_video_publications",
        lambda _config: (set(), {("1", token)}),
    )
    result = organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14), selected_accounts=["alpha"],
        reset_topics=True, express_mode=True,
    )
    assert "Se enviaron 0 videos" in result
    assert calls == []
    assert sent_videos == []
    assert state == {organizadortg.topic_state_key("-1001", "alpha", "normal"): 123}


def test_trial_video_reuses_published_origin_and_resets_only_trial_topic(monkeypatch, tmp_path):
    video = tmp_path / "successful-source.mp4"
    video.write_bytes(b"successful source")
    normal = _video(video, "alpha", origin_identity="successful-origin")
    trial = dict(normal, delivery_kind="trial")
    calls, sent_videos = _stub_common_telegram_plan(
        monkeypatch, [normal, trial], [_account("alpha", "-1001")],
    )
    state = {
        organizadortg.topic_state_key("-1001", "alpha", "normal"): 123,
        organizadortg.topic_state_key("-1001", "alpha", "trial"): 456,
    }
    monkeypatch.setattr(organizadortg, "load_json", lambda _path: state)
    token = organizadortg.origin_token_from_identity("successful-origin")
    source_hash = hashlib.sha256(video.read_bytes()).hexdigest()
    monkeypatch.setattr(
        organizadortg, "fetch_published_video_publications",
        lambda _config: ({("1", source_hash)}, {("1", token)}),
    )

    result = organizadortg.execute_telegram_plan(
        datetime(2026, 8, 14), selected_accounts=["alpha"],
        reset_topics=True, express_mode=True,
    )

    assert "Se enviaron 1 videos" in result
    assert "Omitidos publicados: 1" in result
    assert [item[3] for item in sent_videos] == [str(video)]
    assert [item[4] for item in sent_videos] == ["trial"]
    assert [data["message_thread_id"] for method, data, _ in calls if method == "deleteForumTopic"] == [456]
    assert state[organizadortg.topic_state_key("-1001", "alpha", "normal")] == 123


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
            "account_id": 1,
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
    assert sent_videos == [("-1001", 700, "alpha", str(video), "normal")]


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
                "account_id": index,
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
