from tests.support.e2e_pipeline import run_clean_runtime_smoke


def test_extracted_release_imports_in_clean_runtime():
    result = run_clean_runtime_smoke()

    assert result["venv"]
    assert result["launcher_returncode"] == 0
    assert result["opened_gui"]
    assert result["imported"] == [
        "airtable_sync",
        "calendar_manifest",
        "console_encoding",
        "database",
        "gui_premium_v7",
        "launcher",
        "metadata_pool",
        "Organizador",
        "organizadortg",
        "render_performance",
        "social_publishing",
        "telegram_core",
        "trial_content",
        "updater",
        "video_editor",
        "videos",
    ]
