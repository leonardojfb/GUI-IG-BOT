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
    monkeypatch.setattr(organizadortg, "input_root", str(tmp_path / "no-normal"))
    monkeypatch.setattr(organizadortg, "trial_input_root", str(trial_root))
    monkeypatch.setattr(organizadortg, "get_accounts_with_va_info", lambda: [
        {"username": "eve", "account_type": "main", "trials_active": True},
        {"username": "spam", "account_type": "SPAM", "trials_active": False},
    ])
    scanned = organizadortg.scan_calendar_structure()
    assert [(row["username"], row["delivery_kind"]) for row in scanned] == [("eve", "trial")]
