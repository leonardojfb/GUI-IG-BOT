from database import DatabaseManager
import organizadortg


def _trial_forge(db, tanda, source, identity):
    db.add_tanda(tanda, "p1", "p2", None)
    db.set_tanda_trial(tanda, True)
    db.save_forge_video(tanda, source + ".mp4", source + "__c01.mp4", identity)


def _normal_forge(db, tanda, source, identity):
    db.add_tanda(tanda, "p1", "p2", None)
    db.save_forge_video(tanda, source + ".mp4", source + "__c01.mp4", identity)


def test_normal_caption_reaches_trial_forge_of_same_origin(tmp_path, monkeypatch):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _normal_forge(db, "NORMAL", "original", "e" * 64)
        _trial_forge(db, "TRIAL", "trial_copy", "e" * 64)
        db.set_normal_source_caption("NORMAL", "original", "normal caption")
        assert db.get_trial_source_captions("TRIAL")["trial_copy"] == "normal caption"
        monkeypatch.setattr(organizadortg, "db", db)
        maps = organizadortg.load_trial_caption_maps()
        assert organizadortg.caption_for_trial_calendar_video(
            "trial_copy__c01__TANDA_TRIAL__ACC1__D1__S1.mp4", maps["TRIAL"]
        ) == "normal caption"
    finally:
        db.close()


def test_trial_caption_reaches_normal_forge_of_same_origin(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _trial_forge(db, "TRIAL", "trial_copy", "f" * 64)
        _normal_forge(db, "NORMAL", "original", "f" * 64)
        db.set_trial_source_caption("TRIAL", "trial_copy", "trial caption")
        assert db.get_normal_source_captions("NORMAL")["original"] == "trial caption"
    finally:
        db.close()


def test_historical_trial_difference_stays_exception_to_normal_caption(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _normal_forge(db, "NORMAL", "original", "1" * 64)
        _trial_forge(db, "OLD_TRIAL", "trial_copy", "1" * 64)
        _trial_forge(db, "NEW_TRIAL", "another_copy", "1" * 64)
        db.conn.execute(
            "INSERT INTO normal_source_captions(tanda_name,source_key,caption_text) VALUES('NORMAL','original','normal old')"
        )
        db.conn.execute(
            "INSERT INTO trial_source_captions(tanda_name,source_key,caption_text) VALUES('OLD_TRIAL','trial_copy','trial exception')"
        )
        db.conn.commit()
        assert db.get_trial_source_captions("OLD_TRIAL")["trial_copy"] == "trial exception"
        assert db.get_trial_source_captions("NEW_TRIAL")["another_copy"] == "normal old"
        db.set_normal_source_caption("NORMAL", "original", "normal updated")
        assert db.get_trial_source_captions("OLD_TRIAL")["trial_copy"] == "trial exception"
        assert db.get_trial_source_captions("NEW_TRIAL")["another_copy"] == "normal updated"
    finally:
        db.close()


def test_trial_caption_follows_origin_into_new_tanda_and_telegram(tmp_path, monkeypatch):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _trial_forge(db, "OLD", "original", "a" * 64)
        _trial_forge(db, "NEW", "renamed", "a" * 64)
        db.set_trial_source_caption("OLD", "original", "trial caption")
        assert db.get_trial_source_captions("NEW")["renamed"] == "trial caption"
        monkeypatch.setattr(organizadortg, "db", db)
        maps = organizadortg.load_trial_caption_maps()
        assert organizadortg.caption_for_trial_calendar_video(
            "renamed__c01__TANDA_NEW__ACC1__D1__S1.mp4", maps["NEW"]
        ) == "trial caption"
        db.set_trial_source_caption("NEW", "renamed", "updated trial")
        assert db.get_trial_source_captions("OLD")["original"] == "updated trial"
    finally:
        db.close()


def test_conflicting_historical_trial_caption_remains_tanda_exception(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        for tanda, source in (("A", "one"), ("B", "two"), ("C", "three")):
            _trial_forge(db, tanda, source, "b" * 64)
        db.conn.executemany(
            "INSERT INTO trial_source_captions(tanda_name, source_key, caption_text) VALUES(?, ?, ?)",
            [("A", "one", "original"), ("B", "two", "exception")],
        )
        db.conn.commit()
        assert db.get_trial_source_captions("C")["three"] == "original"
        db.set_trial_source_caption("C", "three", "new global")
        assert db.get_trial_source_captions("A")["one"] == "new global"
        assert db.get_trial_source_captions("B")["two"] == "exception"
    finally:
        db.close()


def test_trial_caption_does_not_cross_different_origin(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _trial_forge(db, "A", "same", "c" * 64)
        _trial_forge(db, "B", "same", "d" * 64)
        _normal_forge(db, "C", "same", "d" * 64)
        db.set_trial_source_caption("A", "same", "trial only")
        assert "same" not in db.get_trial_source_captions("B")
        assert "same" not in db.get_normal_source_captions("C")
    finally:
        db.close()


def test_trial_caption_without_verified_origin_stays_in_tanda(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        for tanda in ("A", "B"):
            db.add_tanda(tanda, "p1", "p2", None)
            db.set_tanda_trial(tanda, True)
        db.set_trial_source_caption("A", "same", "local")
        assert db.get_trial_source_captions("A")["same"] == "local"
        assert "same" not in db.get_trial_source_captions("B")
    finally:
        db.close()
