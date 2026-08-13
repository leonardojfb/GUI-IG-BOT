from trial_content import build_trial_account_plan, reused_trial_tanda_warnings, trial_preview_path


def test_duplicate_tanda_uses_each_output_only_once():
    plan = build_trial_account_plan(
        {"eve": "T1", "luna": "T1"},
        {"T1": ["a.mp4", "b.mp4", "c.mp4"]},
        videos_per_day=2,
        days=1,
    )
    assert plan.assigned["eve"] == ["a.mp4", "b.mp4"]
    assert plan.assigned["luna"] == ["c.mp4"]
    assert plan.shortfalls == {"luna": 1}
    assert "T1" in reused_trial_tanda_warnings(plan)[0]


def test_preview_cache_path_is_stable_and_png(tmp_path):
    video = tmp_path / "vid1__c01.mp4"
    video.write_bytes(b"video")
    assert trial_preview_path(video) == trial_preview_path(video)
    assert trial_preview_path(video).suffix == ".png"

