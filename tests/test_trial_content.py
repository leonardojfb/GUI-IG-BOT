from trial_content import group_trial_sources, source_key_from_filename


def test_group_trial_sources_returns_one_row_per_source():
    assert group_trial_sources([
        "vid1__c01.mp4", "vid2__c01.mp4", "vid1__c02.mp4"
    ]) == [
        ("vid1", ["vid1__c01.mp4", "vid1__c02.mp4"]),
        ("vid2", ["vid2__c01.mp4"]),
    ]


def test_source_key_removes_only_copy_suffix():
    assert source_key_from_filename("my__source__c03.mov") == "my__source"
    assert source_key_from_filename("normal.mp4") == "normal"

