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


def test_source_key_uses_p1_for_forge_copies_from_edited_video_names():
    assert (
        source_key_from_filename("PROMO EVE__Output 14__foto05_editado__c01.mp4")
        == "Output 14"
    )


def test_group_trial_sources_collapses_edited_video_variants_under_original_p1():
    assert group_trial_sources([
        "PROMO EVE__Output 14__foto05_editado__c01.mp4",
        "PROMO EVE__Output 14__foto06_editado__c01.mp4",
        "PROMO EVE__Output 99__foto01_editado__c01.mp4",
    ]) == [
        ("Output 14", [
            "PROMO EVE__Output 14__foto05_editado__c01.mp4",
            "PROMO EVE__Output 14__foto06_editado__c01.mp4",
        ]),
        ("Output 99", ["PROMO EVE__Output 99__foto01_editado__c01.mp4"]),
    ]


def test_source_key_removes_calendar_marker_after_resolving_edited_forge_copy():
    assert (
        source_key_from_filename(
            "PROMO EVE__Output 14__foto05_editado__c01__TANDA_NORMAL__ACC1__D1__S1.mp4"
        )
        == "Output 14"
    )


def test_forge_trial_logs_trial_process_kind(tmp_path):
    import gui_premium_v7
    from database import DatabaseManager

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    src = tmp_path / "src.mp4"
    out = tmp_path / "videos_finales" / "TRIAL" / "src__c17.mp4"
    src.write_bytes(b"src")
    out.parent.mkdir(parents=True)
    out.write_bytes(b"out")

    gui_premium_v7._save_forge_transform_log(
        db,
        process_kind="forge_trial",
        source_path=str(src),
        output_path=str(out),
        tanda_name="TRIAL",
        source_identity="hash",
        params={"rotate_deg": 0.8, "crop_px": 2, "speed": 1.003},
        meta={"device": "iphone"},
    )

    row = db.list_video_transform_logs()[0]
    assert row["process_kind"] == "forge_trial"
    assert row["tanda_name"] == "TRIAL"
    db.close()

