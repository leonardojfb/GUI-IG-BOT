from trial_content import (
    TrialPlan,
    assign_trial_general_captions,
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


def test_general_captions_cycle_across_accounts_by_file():
    plan = TrialPlan(
        assigned={"a": ["clip__c01.mp4", "other__c01.mp4"],
                  "b": ["clip__c02.mp4", "third__c01.mp4"]},
        shortfalls={}, tanda_stats={},
    )
    assigned = assign_trial_general_captions(
        plan, {"a": "T", "b": "T"},
        {"a": "general", "b": "general"}, {"T": ["A", "B", "C"]}, 2,
    )
    assert assigned == {
        ("a", "clip__c01.mp4"): "A",
        ("b", "clip__c02.mp4"): "B",
        ("a", "other__c01.mp4"): "C",
        ("b", "third__c01.mp4"): "A",
    }


def test_general_captions_ignore_individual_accounts_and_separate_tandas():
    plan = TrialPlan(assigned={"a": ["a.mp4"], "b": ["b.mp4"], "c": ["c.mp4"]},
                     shortfalls={}, tanda_stats={})
    assert assign_trial_general_captions(
        plan, {"a": "T", "b": "T", "c": "U"},
        {"a": "general", "b": "individual", "c": "general"},
        {"T": ["A", "B"], "U": ["X"]}, 1,
    ) == {("a", "a.mp4"): "A", ("c", "c.mp4"): "X"}


def test_general_captions_use_distinct_txt_texts_before_repeating():
    plan = TrialPlan(assigned={"a": ["one.mp4", "two.mp4", "three.mp4"]},
                     shortfalls={}, tanda_stats={})
    assert assign_trial_general_captions(
        plan, {"a": "T"}, {"a": "general"}, {"T": ["A", "A", "B"]}, 1,
    ) == {("a", "one.mp4"): "A", ("a", "two.mp4"): "B",
          ("a", "three.mp4"): "A"}

