import organizadortg
import database
from Organizador import build_calendar_video_filename
from calendar_manifest import build_entry, replace_entries


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


def test_calendarized_video_name_preserves_tanda_marker_for_caption_routing():
    filename = build_calendar_video_filename(
        "clip__c01.mp4",
        tanda_name="PROMO EVE",
        account_id=42,
        day=3,
        slot=2,
    )

    assert filename == "clip__c01__TANDA_PROMO_EVE__ACC42__D3__S2.mp4"
    assert organizadortg.extract_tanda_tag_from_calendar_filename(filename) == "PROMO_EVE"


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


def test_normal_individual_copies_use_the_same_literal_caption():
    captions = {"vid1": "CAPTION ONE\n#same"}
    first = "vid1__c01__TANDA_NORMAL__ACC1__D1__S1.mp4"
    second = "vid1__c02__TANDA_NORMAL__ACC1__D1__S2.mp4"

    assert organizadortg.caption_for_normal_individual_video(first, captions) == captions["vid1"]
    assert organizadortg.caption_for_normal_individual_video(second, captions) == captions["vid1"]


def test_normal_individual_caption_uses_original_p1_for_edited_video_forge_copies():
    captions = {"Output 14": "CAPTION ORIGINAL OUTPUT 14\n#same"}
    first = "PROMO EVE__Output 14__foto05_editado__c01__TANDA_NORMAL__ACC1__D1__S1.mp4"
    second = "PROMO EVE__Output 14__foto06_editado__c01__TANDA_NORMAL__ACC1__D1__S2.mp4"

    assert organizadortg.caption_for_normal_individual_video(first, captions) == captions["Output 14"]
    assert organizadortg.caption_for_normal_individual_video(second, captions) == captions["Output 14"]


def test_normal_manifest_caption_mode_overrides_saved_individual_captions():
    filename = "clip__SRC01__P2__TANDA_MIXED__ACC1__D1__S1.mp4"
    normal_map = {"SRC01": "individual caption\n#one"}
    pools = {"MIXED": ["general caption\n#two"]}
    indexes = {}

    assert organizadortg.caption_for_normal_calendar_video(
        filename, "general", normal_map, pools, indexes
    ).startswith("general caption")
    assert organizadortg.caption_for_normal_calendar_video(
        filename, "individual", normal_map, pools, indexes
    ) == normal_map["SRC01"]


def test_scan_calendar_structure_uses_manifest_when_present(tmp_path, monkeypatch):
    video = tmp_path / "videos_finales" / "T1" / "clip.mp4"
    legacy = tmp_path / "CALENDARIO_POSTEO" / "Dia_1" / "legacy" / "legacy.mp4"
    video.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    video.write_bytes(b"manifest")
    legacy.write_bytes(b"legacy")
    entry = build_entry(
        "alice",
        1,
        "normal",
        1,
        1,
        "T1",
        str(video),
        "clip__TANDA_T1__ACC1__D1__S1.mp4",
    )
    replace_entries(tmp_path / "calendar_manifest.json", [entry], {"alice"}, "normal")

    monkeypatch.setattr(organizadortg, "base_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(organizadortg, "input_root", str(tmp_path / "CALENDARIO_POSTEO"), raising=False)
    monkeypatch.setattr(organizadortg, "trial_input_root", str(tmp_path / "CALENDARIO_TRIALS"), raising=False)
    monkeypatch.setattr(organizadortg, "get_accounts_with_va_info", lambda: [
        {"username": "alice", "account_type": "promo", "trials_active": False},
        {"username": "legacy", "account_type": "main", "trials_active": False},
    ])

    rows = organizadortg.scan_calendar_structure()

    assert len(rows) == 1
    assert rows[0]["path"] == str(video.resolve())
    assert rows[0]["filename"] == "clip__TANDA_T1__ACC1__D1__S1.mp4"
    assert rows[0]["username"] == "alice"
    assert rows[0]["delivery_kind"] == "normal"
    assert rows[0]["category"] == "promo"
