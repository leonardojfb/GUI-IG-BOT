import organizadortg
import database


def test_caption_routing_uses_the_caption_assigned_to_each_tanda(tmp_path):
    ed_caption = tmp_path / "ed.txt"
    ta_caption = tmp_path / "ta.txt"
    fo_caption = tmp_path / "fo.txt"
    ed_caption.write_text("CAPTION_ED_A_UNIQUE\n#ed\n", encoding="utf-8")
    ta_caption.write_text("CAPTION_TA_B_UNIQUE\n#ta\n", encoding="utf-8")
    fo_caption.write_text("CAPTION_FO_C_UNIQUE\n#fo\n", encoding="utf-8")

    pools = organizadortg.load_tanda_caption_pools(
        [
            {"tanda_name": "ED_A", "captions_file_path": str(ed_caption)},
            {"tanda_name": "TA_B", "captions_file_path": str(ta_caption)},
            {"tanda_name": "FO_C", "captions_file_path": str(fo_caption)},
            {"tanda_name": "ED_B", "captions_file_path": None},
        ]
    )
    indexes = {}

    assert organizadortg.caption_for_calendar_video(
        "ED_A__P1__P2__TANDA_ED_A__ACC1__D1__S1.mp4", pools, indexes
    ).startswith("CAPTION_ED_A_UNIQUE")
    assert organizadortg.caption_for_calendar_video(
        "TA_B__P1__P2__TANDA_TA_B__ACC1__D1__S2.mp4", pools, indexes
    ).startswith("CAPTION_TA_B_UNIQUE")
    assert organizadortg.caption_for_calendar_video(
        "FO_C__c01__TANDA_FO_C__ACC1__D1__S3.mp4", pools, indexes
    ).startswith("CAPTION_FO_C_UNIQUE")
    assert organizadortg.caption_for_calendar_video(
        "ED_B__P1__P2__TANDA_ED_B__ACC1__D1__S4.mp4", pools, indexes
    ) is None


def test_caption_routing_accepts_tanda_names_with_spaces():
    assert organizadortg.extract_tanda_tag_from_calendar_filename(
        "clip__TANDA_PROMO_EVE__ACC2__D1__S1.mp4"
    ) == "PROMO_EVE"


def test_logistica_caption_assignment_persists_on_the_tanda(tmp_path):
    previous_db_path = database.DB_PATH
    database.DB_PATH = str(tmp_path / "organizador.db")
    db = database.DatabaseManager()
    try:
        db.add_tanda("ED_A", "p1", "p2", None)
        assert db.set_tanda_captions("ED_A", "C:/captions/ed_a.txt") == 1
        assert db.get_tanda_by_name("ED_A")["captions_file_path"] == "C:/captions/ed_a.txt"
        assert db.set_tanda_captions("ED_A", None) == 1
        assert db.get_tanda_by_name("ED_A")["captions_file_path"] is None
    finally:
        db.close()
        database.DB_PATH = previous_db_path
