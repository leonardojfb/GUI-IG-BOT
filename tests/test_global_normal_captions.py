import sqlite3

from database import DatabaseManager
import organizadortg


def _forge(db, tanda, source, identity):
    db.add_tanda(tanda, "p1", "p2", None)
    db.save_forge_video(tanda, source + ".mp4", source + "__c01.mp4", identity)


def test_caption_follows_same_source_across_tandas(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _forge(db, "A", "video", "a" * 64)
        _forge(db, "B", "renamed", "a" * 64)
        db.set_normal_source_caption("A", "video", "global text")
        assert db.get_normal_source_captions("B")["renamed"] == "global text"
        db.set_normal_source_caption("B", "renamed", "updated globally")
        assert db.get_normal_source_captions("A")["video"] == "updated globally"
    finally:
        db.close()


def test_legacy_conflict_stays_as_tanda_exception(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        for tanda, source in (("A", "one"), ("B", "two"), ("C", "three")):
            _forge(db, tanda, source, "b" * 64)
        db.conn.execute("INSERT INTO normal_source_captions(tanda_name, source_key, caption_text) VALUES('A', 'one', 'original')")
        db.conn.execute("INSERT INTO normal_source_captions(tanda_name, source_key, caption_text) VALUES('B', 'two', 'exception')")
        db.conn.commit()
        assert db.get_normal_source_captions("C")["three"] == "original"
        db.set_normal_source_caption("C", "three", "new global")
        assert db.get_normal_source_captions("A")["one"] == "new global"
        assert db.get_normal_source_captions("B")["two"] == "exception"
    finally:
        db.close()


def test_same_filename_with_different_origin_does_not_share(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _forge(db, "A", "video", "a" * 64)
        _forge(db, "B", "video", "b" * 64)
        db.set_normal_source_caption("A", "video", "for A")
        assert "video" not in db.get_normal_source_captions("B")
    finally:
        db.close()


def test_legacy_source_tanda_alias_resolves_under_destination_filename(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _forge(db, "SOURCE", "clip", "c" * 64)
        db.add_tanda("DEST", "p1", "p2", None)
        db.conn.execute(
            "INSERT INTO normal_source_captions(tanda_name, source_key, caption_text) "
            "VALUES('DEST', 'SOURCE::clip', 'saved caption')"
        )
        db.conn.commit()
        assert db.get_normal_source_captions("DEST")["clip"] == "saved caption"
    finally:
        db.close()


def test_telegram_receives_global_caption_in_second_tanda(tmp_path, monkeypatch):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _forge(db, "SOURCE", "clip", "d" * 64)
        _forge(db, "DEST", "renamed", "d" * 64)
        db.set_normal_source_caption("SOURCE", "clip", "literal caption")
        monkeypatch.setattr(organizadortg, "db", db)
        maps = organizadortg.load_normal_individual_caption_maps()
        caption = organizadortg.caption_for_normal_calendar_video(
            "renamed__c01__TANDA_DEST__ACC1__D1__S1.mp4",
            "individual", maps["DEST"], {}, {},
        )
        assert caption == "literal caption"
    finally:
        db.close()


def test_legacy_caption_without_identity_remains_scoped(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        db.add_tanda("A", "p1", "p2", None)
        db.add_tanda("B", "p1", "p2", None)
        db.set_normal_source_caption("A", "same_name", "scoped caption")
        assert db.get_normal_source_captions("A")["same_name"] == "scoped caption"
        assert "same_name" not in db.get_normal_source_captions("B")
    finally:
        db.close()


def test_direct_tanda_caption_wins_over_historical_alias(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _forge(db, "SOURCE", "clip", "e" * 64)
        _forge(db, "DEST", "clip", "e" * 64)
        db.conn.executemany(
            "INSERT INTO normal_source_captions(tanda_name, source_key, caption_text) VALUES(?, ?, ?)",
            [("DEST", "clip", "direct"), ("DEST", "SOURCE::clip", "old alias")],
        )
        db.conn.commit()
        assert db.get_normal_source_captions("DEST")["clip"] == "direct"
    finally:
        db.close()


def test_caption_identity_lookup_reuses_forge_evidence_until_database_changes(tmp_path):
    db = DatabaseManager(str(tmp_path / "captions.db"))
    try:
        _forge(db, "A", "one", "f" * 64)
        queries = []
        db.conn.set_trace_callback(queries.append)
        db.get_normal_source_captions("A")
        db.get_normal_source_captions("A")
        registry_reads = lambda: sum("FROM forge_video_registry" in q for q in queries)
        assert registry_reads() == 1

        db.save_forge_video("A", "two.mp4", "two__c01.mp4", "e" * 64)
        db.get_normal_source_captions("A")
        assert registry_reads() == 2

        with sqlite3.connect(db.db_path) as other:
            other.execute(
                "INSERT INTO forge_video_registry(tanda_name, source_name, output_name, video_hash) "
                "VALUES('A', 'three.mp4', 'three__c01.mp4', ?)",
                ("d" * 64,),
            )
        db.get_normal_source_captions("A")
        assert registry_reads() == 3
    finally:
        db.close()
