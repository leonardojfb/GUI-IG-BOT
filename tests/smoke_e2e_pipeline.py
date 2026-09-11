from pathlib import Path

from tests.support.e2e_pipeline import run_e2e_pipeline, run_extracted_release_e2e_pipeline


def _assert_current_json_calendar_result(result):
    assert result["expected"]["processed_outputs"] == 27
    assert result["actual"]["processed_outputs"] == 27
    assert result["expected"]["distributed_files"] == 0
    assert result["actual"]["distributed_files"] == 0
    assert result["expected"]["manifest_entries"] == 9
    assert result["actual"]["manifest_entries"] == 9
    assert result["expected"]["telegram_sends"] == 9
    assert result["actual"]["telegram_sends"] == 9


def test_e2e_multimedia_logistica_telegram_smoke():
    result = run_e2e_pipeline(keep_artifacts=True)

    assert result["run_id"].startswith("e2e-")
    assert Path(result["run_root"]).exists()
    assert Path(result["audit_json"]).exists()
    assert Path(result["audit_md"]).exists()
    assert Path(result["test_report"]).exists()

    _assert_current_json_calendar_result(result)

    assert result["actual"]["categories"] == [
        "PRUEBA_CAT_A",
        "PRUEBA_CAT_B",
        "PRUEBA_CAT_C",
    ]
    assert result["actual"]["vas"] == [
        "PRUEBA_VA_A",
        "PRUEBA_VA_B",
        "PRUEBA_VA_C",
    ]
    assert sorted(result["actual"]["tandas"]) == [
        "ED_A",
        "ED_B",
        "ED_C",
        "FO_A",
        "FO_B",
        "FO_C",
        "TA_A",
        "TA_B",
        "TA_C",
    ]

    bug_codes = {finding["code"] for finding in result["findings"] if finding["status"] == "FAIL"}
    severe_identity_bugs = {
        "TANDA_MIX",
        "CATEGORY_MIX",
        "ACCOUNT_VA_MIX",
        "TELEGRAM_CHAT_TOPIC_MIX",
        "MANIFEST_ACCOUNT_MISSING",
        "MANIFEST_ACCOUNT_UNKNOWN",
        "MANIFEST_DUPLICATE_ACCOUNT",
        "MANIFEST_SOURCE_MISSING",
        "FILE_DUPLICATE",
        "CAPTION_LOST",
        "CAPTION_WRONG_TANDA",
        "CAPTION_UNEXPECTED",
        "CALENDAR_CONTENT_CHANGED",
    }
    assert not (bug_codes & severe_identity_bugs)


def test_extracted_release_launcher_logistica_telegram_smoke():
    result = run_extracted_release_e2e_pipeline(keep_artifacts=True)

    assert result["install_root"].endswith("install")
    assert result["launcher"]["returncode"] == 0
    assert result["launcher"]["opened_gui"]
    assert Path(result["launcher"]["gui_path"]).name == "gui_premium_v7.py"
    assert Path(result["run_root"]).exists()
    assert Path(result["audit_json"]).exists()
    assert Path(result["audit_md"]).exists()

    _assert_current_json_calendar_result(result)
