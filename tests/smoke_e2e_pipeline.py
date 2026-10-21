from pathlib import Path

from tests.support.e2e_pipeline import run_e2e_pipeline


def test_e2e_multimedia_logistica_telegram_smoke():
    result = run_e2e_pipeline(keep_artifacts=True)

    assert result["run_id"].startswith("e2e-")
    assert Path(result["run_root"]).exists()
    assert Path(result["audit_json"]).exists()
    assert Path(result["audit_md"]).exists()
    assert Path(result["test_report"]).exists()

    assert result["expected"]["processed_outputs"] == 27
    assert result["actual"]["processed_outputs"] == 27
    assert result["expected"]["distributed_files"] == 63
    assert result["actual"]["distributed_files"] == 63
    assert result["expected"]["telegram_sends"] == 63
    assert result["actual"]["telegram_sends"] == 63

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
        "FILE_MISSING",
        "FILE_DUPLICATE",
        "CAPTION_LOST",
        "CAPTION_WRONG_TANDA",
        "CAPTION_UNEXPECTED",
        "CALENDAR_CONTENT_CHANGED",
    }
    assert not (bug_codes & severe_identity_bugs)
