from pathlib import Path

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


def test_max_days_uses_all_available_files_without_shortfall():
    files = [f"clip_{index:03d}.mp4" for index in range(125)]
    plan = build_trial_account_plan(
        {"evebloom.xo": "evebloom.xo"},
        {"evebloom.xo": files},
        videos_per_day=3,
        days="MAX",
    )
    assert plan.assigned["evebloom.xo"] == files
    assert plan.shortfalls == {}


def test_max_duplicate_tanda_reports_shortfalls_for_unfilled_accounts():
    files = [f"clip_{index:03d}.mp4" for index in range(5)]
    plan = build_trial_account_plan(
        {"eve": "T1", "luna": "T1", "sol": "T1"},
        {"T1": files},
        videos_per_day=2,
        days="MAX",
    )

    assert plan.assigned["eve"] == files
    assert plan.assigned["luna"] == []
    assert plan.assigned["sol"] == []
    assert plan.shortfalls == {"luna": 5, "sol": 5}
    assert plan.tanda_stats["T1"]["requested"] == 15
    assert plan.tanda_stats["T1"]["shortfall"] == 10
    assert "para 15 requeridos" in reused_trial_tanda_warnings(plan)[0]
    assert "faltan 10" in reused_trial_tanda_warnings(plan)[0]


def test_trial_plan_interleaves_sources_before_repeating_copies():
    plan = build_trial_account_plan(
        {"eve": "T1"},
        {
            "T1": [
                "vid1__c01.mp4",
                "vid1__c02.mp4",
                "vid1__c03.mp4",
                "vid2__c01.mp4",
                "vid2__c02.mp4",
                "vid2__c03.mp4",
                "vid3__c01.mp4",
                "vid3__c02.mp4",
            ],
        },
        videos_per_day=8,
        days=1,
    )
    assert plan.assigned["eve"] == [
        "vid1__c01.mp4",
        "vid2__c01.mp4",
        "vid3__c01.mp4",
        "vid1__c02.mp4",
        "vid2__c02.mp4",
        "vid3__c02.mp4",
        "vid1__c03.mp4",
        "vid2__c03.mp4",
    ]


def test_trial_plan_continues_interleaved_tanda_pool_per_individual_account():
    plan = build_trial_account_plan(
        {"eve": "T1", "luna": "T1"},
        {
            "T1": [
                "vid1__c01.mp4",
                "vid1__c02.mp4",
                "vid2__c01.mp4",
                "vid2__c02.mp4",
                "vid3__c01.mp4",
                "vid3__c02.mp4",
            ],
        },
        videos_per_day=3,
        days=1,
    )
    assert plan.assigned["eve"] == [
        "vid1__c01.mp4",
        "vid2__c01.mp4",
        "vid3__c01.mp4",
    ]
    assert plan.assigned["luna"] == [
        "vid1__c02.mp4",
        "vid2__c02.mp4",
        "vid3__c02.mp4",
    ]


def test_preview_cache_path_is_stable_and_png(tmp_path):
    video = tmp_path / "vid1__c01.mp4"
    video.write_bytes(b"video")
    assert trial_preview_path(video) == trial_preview_path(video)
    assert trial_preview_path(video).suffix == ".png"


def test_trial_distribution_does_not_fall_back_to_all_active_trials():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _trial_dist_run_per_account")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "selected_trial_usernames(" not in body
    assert "Faltan videos: se necesitan" not in body


def test_trial_distribution_confirmation_says_calendarize_not_create():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _trial_dist_run_per_account")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "Crear {sum(map(len, plan.assigned.values()))} videos" not in body
    assert "Calendarizar {sum(map(len, plan.assigned.values()))} videos" in body


def test_trial_distribution_writes_manifest_not_calendar_copies():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _trial_dist_run_per_account")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "_copy_calendar_file(" not in body
    assert "replace_entries(" in body
    assert 'delivery_kind="trial"' in body


def test_trial_distribution_replaces_all_assigned_accounts_even_when_zero_videos():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _trial_dist_run_per_account")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "affected = set(plan.assigned)" in body
    assert "affected.add(user)" not in body


def test_trial_distribution_blocks_incomplete_calendarization():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _trial_dist_run_per_account")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "if plan.shortfalls and not preview_only:" in body
    assert "No se calendariza incompleto" in body


def test_trial_logistica_has_no_global_tanda_selector_and_uses_account_panels():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _build_dist_trials_tab")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "self.trial_dist_tanda" not in body
    assert "Tanda Trial:" not in body
    assert "_trial_toggle_account_panel" in body
    assert "Desplegar panel de trials" in body

