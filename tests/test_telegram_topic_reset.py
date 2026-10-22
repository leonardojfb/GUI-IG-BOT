from datetime import datetime

import organizadortg


def test_call_tg_prints_clear_message_for_missing_forum_topic(monkeypatch, capsys):
    class FakeResponse:
        def json(self):
            return {
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: TOPIC_ID_INVALID",
            }

    def fake_post(url, json):
        return FakeResponse()

    monkeypatch.setattr(organizadortg.requests, "post", fake_post)

    res = organizadortg.call_tg(
        "deleteForumTopic",
        {"chat_id": "-1001", "message_thread_id": 11},
    )

    out = capsys.readouterr().out
    assert res["description"] == "Bad Request: TOPIC_ID_INVALID"
    assert "se intento borrar un topic que ya no existe" in out.lower()
    assert "Error en Telegram API" not in out


def test_delete_known_topics_for_chats_deletes_topics_and_clears_state(monkeypatch):
    calls = []

    def fake_call_tg(method, data, silent=False):
        calls.append((method, dict(data), silent))
        return {"ok": True, "result": True}

    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    state = {
        "-1001_alpha": 11,
        "-1001_beta": {"id": 22, "name": "beta"},
        "-1002_gamma": 33,
    }

    summary = organizadortg.delete_known_topics_for_chats({"-1001"}, state)

    assert summary["deleted"] == 2
    assert summary["failed"] == 0
    assert state == {"-1002_gamma": 33}
    assert calls == [
        ("deleteForumTopic", {"chat_id": "-1001", "message_thread_id": 11}, False),
        ("deleteForumTopic", {"chat_id": "-1001", "message_thread_id": 22}, False),
    ]


def test_delete_known_topics_for_accounts_only_deletes_matching_account_names(monkeypatch):
    calls = []

    def fake_call_tg(method, data, silent=False):
        calls.append((method, dict(data), silent))
        return {"ok": True, "result": True}

    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    state = {
        "-1001_alpha": 11,
        "-1001_beta": 22,
        "-1001_TRIALS Cuentas - Franco": 33,
        "-1002_alpha": 44,
    }

    summary = organizadortg.delete_known_topics_for_accounts({"alpha"}, state)

    assert summary["deleted"] == 2
    assert summary["failed"] == 0
    assert state == {
        "-1001_beta": 22,
        "-1001_TRIALS Cuentas - Franco": 33,
    }
    assert calls == [
        ("deleteForumTopic", {"chat_id": "-1001", "message_thread_id": 11}, False),
        ("deleteForumTopic", {"chat_id": "-1002", "message_thread_id": 44}, False),
    ]


def test_delete_known_topics_for_accounts_does_not_delete_prefixed_trial_topics(monkeypatch):
    calls = []

    def fake_call_tg(method, data, silent=False):
        calls.append((method, dict(data), silent))
        return {"ok": True, "result": True}

    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    state = {
        "-1001_evestarryh": 11,
        "-1001_evestarryh trials": 22,
        "-1001_evestarryh trials main": 33,
        "-1001_evestarryh main trial": 44,
        "-1001_evestarryhmain": 55,
    }

    summary = organizadortg.delete_known_topics_for_accounts({"evestarryh"}, state)

    assert summary["deleted"] == 1
    assert summary["failed"] == 0
    assert state == {
        "-1001_evestarryh trials": 22,
        "-1001_evestarryh trials main": 33,
        "-1001_evestarryh main trial": 44,
        "-1001_evestarryhmain": 55,
    }
    assert calls == [
        ("deleteForumTopic", {"chat_id": "-1001", "message_thread_id": 11}, False),
    ]


def test_delete_known_topics_for_accounts_preserves_trials_prefixed_topic_for_base_account(monkeypatch):
    calls = []

    def fake_call_tg(method, data, silent=False):
        calls.append((method, dict(data), silent))
        return {"ok": True, "result": True}

    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    state = {
        "-1001_evestarryh": {"id": 11, "name": "TRIALS - evestarryh TRIALS"},
        "-1002_evestarryh": {"id": 22, "name": "evestarryh MAIN"},
    }

    summary = organizadortg.delete_known_topics_for_accounts({"evestarryh"}, state)

    assert summary["deleted"] == 1
    assert summary["failed"] == 0
    assert state == {
        "-1001_evestarryh": {"id": 11, "name": "TRIALS - evestarryh TRIALS"},
    }
    assert calls == [
        ("deleteForumTopic", {"chat_id": "-1002", "message_thread_id": 22}, False),
    ]


def test_delete_known_topics_for_accounts_deletes_modern_trial_topic_for_selected_account(monkeypatch):
    calls = []

    def fake_call_tg(method, data, silent=False):
        calls.append((method, dict(data), silent))
        return {"ok": True, "result": True}

    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    state = {
        "-1001_evestarryh": {"id": 11, "name": "evestarryh MAIN"},
        "-1001_evestarryh_trials": {"id": 22, "name": "TRIALS - evestarryh MAIN"},
        "-1001_evestarryhmain_trials": {"id": 33, "name": "TRIALS - evestarryhmain MAIN"},
        "-1001_TRIALS Cuentas - Rafa": 44,
    }

    summary = organizadortg.delete_known_topics_for_accounts({"evestarryh"}, state)

    assert summary["deleted"] == 2
    assert summary["failed"] == 0
    assert state == {
        "-1001_evestarryhmain_trials": {"id": 33, "name": "TRIALS - evestarryhmain MAIN"},
        "-1001_TRIALS Cuentas - Rafa": 44,
    }
    assert calls == [
        ("deleteForumTopic", {"chat_id": "-1001", "message_thread_id": 11}, False),
        ("deleteForumTopic", {"chat_id": "-1001", "message_thread_id": 22}, False),
    ]


def test_trial_scoped_reset_preserves_normal_topic_and_other_accounts(monkeypatch):
    deleted = []

    def fake_call_tg(method, data, silent=False):
        deleted.append(data["message_thread_id"])
        return {"ok": True, "result": True}

    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    state = {
        "-1001_alpha": {"id": 11, "name": "alpha MAIN"},
        "-1001_alpha_trials": {"id": 22, "name": "TRIALS - alpha MAIN"},
        "-1002_alpha": {"id": 33, "name": "TRIALS - alpha MAIN"},
        "-1001_beta_trials": {"id": 44, "name": "TRIALS - beta MAIN"},
    }

    summary = organizadortg.delete_known_topics_for_accounts(
        {"alpha"}, state, delivery_kinds={"alpha": {"trial"}},
    )

    assert summary["deleted"] == 2
    assert deleted == [22, 33]
    assert set(state) == {"-1001_alpha", "-1001_beta_trials"}


def test_trial_subaccount_topics_are_named_with_trials_prefix(monkeypatch):
    calls = []

    def fake_call_tg(method, data, silent=False):
        calls.append((method, dict(data), silent))
        return {"ok": True, "result": {"message_thread_id": 77}}

    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    state = {}

    topic_id = organizadortg.get_or_create_topic("-1001", "evestarryh", "TRIALS", state)

    assert topic_id == 77
    assert state == {
        "-1001_evestarryh": {"id": 77, "name": "TRIALS - evestarryh TRIALS"},
    }
    assert calls == [
        (
            "createForumTopic",
            {"chat_id": "-1001", "name": "TRIALS - evestarryh TRIALS"},
            False,
        ),
    ]


def test_topic_id_invalid_is_treated_as_stale_state(monkeypatch):
    calls = []

    def fake_call_tg(method, data, silent=False):
        calls.append((method, dict(data), silent))
        return {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: TOPIC_ID_INVALID",
        }

    monkeypatch.setattr(organizadortg, "call_tg", fake_call_tg)
    state = {"-1001_alpha": 11}

    summary = organizadortg.delete_known_topics_for_accounts({"alpha"}, state)

    assert summary["deleted"] == 0
    assert summary["missing"] == 1
    assert summary["failed"] == 0
    assert state == {}


def test_execute_plan_resets_selected_account_topics_before_recreating(monkeypatch, tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake")
    monkeypatch.setattr(organizadortg, "base_dir", str(tmp_path))
    state = {"-1001_alpha": 11, "-1001_old": 99, "-1002_beta": 22}
    order = []

    monkeypatch.setattr(organizadortg, "load_tanda_caption_pools", lambda: {})
    monkeypatch.setattr(
        organizadortg,
        "get_accounts_with_va_info",
        lambda: [
            {
                "id": 1,
                "username": "alpha",
                "account_type": "promo",
                "assigned_va": "VA1",
                "tg_group_id": "-1001",
                "va_timezone": "America/Argentina/Buenos_Aires",
            },
            {
                "id": 2,
                "username": "beta",
                "account_type": "promo",
                "assigned_va": "VA2",
                "tg_group_id": "-1002",
                "va_timezone": "America/Argentina/Buenos_Aires",
            },
        ],
    )
    monkeypatch.setattr(
        organizadortg,
        "scan_calendar_structure",
        lambda: [
            {
                "path": str(video_path),
                "filename": "ALPHA__TANDA_NEW__ACC1__D1__S1.mp4",
                "category": "promo",
                "day": "Dia_1",
                "username": "alpha",
                "account_id": 1,
            },
            {
                "path": str(video_path),
                "filename": "BETA__TANDA_OLD__ACC2__D1__S1.mp4",
                "category": "promo",
                "day": "Dia_1",
                "username": "beta",
                "account_id": 2,
            },
        ],
    )
    monkeypatch.setattr(organizadortg, "load_json", lambda _path: state)
    monkeypatch.setattr(organizadortg, "save_json", lambda _path, _data: None)
    monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object())
    monkeypatch.setattr(organizadortg, "fetch_published_video_publications", lambda _config: (set(), set()))
    monkeypatch.setattr(organizadortg, "time", type("TimeStub", (), {"sleep": staticmethod(lambda _seconds: None)}))

    def fake_delete(account_names, topics_state, delivery_kinds=None):
        assert delivery_kinds == {"alpha": {"normal"}}
        order.append(("delete", tuple(sorted(account_names)), dict(topics_state)))
        topics_state.pop("-1001_alpha", None)
        return {"deleted": 1, "missing": 0, "failed": 0, "failures": []}

    def fake_get_or_create(chat_id, username, tag, topics_state, is_admin=False, force_recreate=False):
        order.append(("create", chat_id, username, dict(topics_state)))
        topics_state[f"{chat_id}_{username}"] = 500 + len(order)
        return topics_state[f"{chat_id}_{username}"]

    monkeypatch.setattr(organizadortg, "delete_known_topics_for_accounts", fake_delete)
    monkeypatch.setattr(organizadortg, "get_or_create_topic", fake_get_or_create)
    monkeypatch.setattr(organizadortg, "call_tg", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(organizadortg, "_send_video_to_topic", lambda *args, **_kwargs: (True, args[1]))

    result = organizadortg.execute_telegram_plan(
        datetime(2026, 7, 27),
        selected_accounts=["alpha"],
        reset_topics=True,
    )

    assert result.startswith("✨ PROCESO TERMINADO")
    assert order[0] == ("delete", ("alpha",), {"-1001_alpha": 11, "-1001_old": 99, "-1002_beta": 22})
    assert order[1][0:3] == ("create", "-1001", "alpha")
    assert "-1001_alpha" not in order[1][3]
    assert "-1001_old" in order[1][3]
    assert "-1002_beta" in order[1][3]


def test_controller_passes_reset_topics_to_execute_plan(monkeypatch):
    captured = {}

    def fake_execute(start_date, selected_accounts=None, controller=None, reset_topics=False, express_mode=False, allow_published_repeats=False, allow_delivered_repeats=False):
        captured["start_date"] = start_date
        captured["selected_accounts"] = selected_accounts
        captured["controller"] = controller
        captured["reset_topics"] = reset_topics
        captured["express_mode"] = express_mode
        captured["allow_published_repeats"] = allow_published_repeats
        captured["allow_delivered_repeats"] = allow_delivered_repeats
        return "done"

    monkeypatch.setattr(organizadortg, "execute_telegram_plan", fake_execute)

    controller = organizadortg.TelegramBotController(
        "2026-07-27",
        selected_accounts=["alpha"],
        reset_topics=True,
        express_mode=True,
    )
    controller.start()

    assert captured["start_date"] == datetime(2026, 7, 27)
    assert captured["selected_accounts"] == ["alpha"]
    assert captured["controller"] is controller
    assert captured["reset_topics"] is True
    assert captured["express_mode"] is True
    assert captured["allow_published_repeats"] is False
    assert captured["allow_delivered_repeats"] is False
