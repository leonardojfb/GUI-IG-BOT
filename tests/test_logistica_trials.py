from trial_content import (
    missing_trial_caption_sources,
    selected_trial_usernames,
    trial_calendar_root,
)


def test_missing_trial_caption_lists_one_missing_source():
    assert missing_trial_caption_sources(
        ["vid1__c01.mp4", "vid1__c02.mp4", "vid2__c01.mp4"],
        {"vid1": "caption 1"},
    ) == ["vid2"]


def test_trial_output_is_separate_and_only_active_accounts(tmp_path):
    accounts = [
        {"username": "main_active", "trials_active": 1, "account_type": "main"},
        {"username": "spam_inactive", "trials_active": 0, "account_type": "SPAM"},
    ]
    assert selected_trial_usernames(accounts) == ["main_active"]
    assert trial_calendar_root(tmp_path).name == "CALENDARIO_TRIALS"

