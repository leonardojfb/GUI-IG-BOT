import database
import sqlite3


def _temporary_db(tmp_path):
    previous = database.DB_PATH
    database.DB_PATH = str(tmp_path / "organizador.db")
    db = database.DatabaseManager()
    return db, previous


def test_trials_active_preserves_category(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        db.add_virtual_account("eve", "main")
        assert db.set_account_trials_active("eve", True) is True
        account = db.get_all_accounts()[0]
        assert account["account_type"] == "main"
        assert account["trials_active"] == 1
        assert [row["username"] for row in db.get_trials_active_accounts()] == ["eve"]
    finally:
        db.close()
        database.DB_PATH = previous


def test_trial_captions_are_keyed_by_source(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        db.add_tanda("TRIAL_01", "TRIAL_01", "TRIAL_01", None)
        assert db.set_tanda_trial("TRIAL_01", True) is True
        db.set_trial_source_caption("TRIAL_01", "vid1", "caption 1")
        db.set_trial_source_caption("TRIAL_01", "vid2", "caption 2")
        assert db.get_trial_tandas() == ["TRIAL_01"]
        assert db.get_trial_source_captions("TRIAL_01") == {
            "vid1": "caption 1", "vid2": "caption 2"
        }
    finally:
        db.close()
        database.DB_PATH = previous


def test_trial_tanda_txt_is_independent_of_normal_tandas(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        assert db.set_tanda_trial("TRIAL_ONLY", True)
        assert db.get_tanda_by_name("TRIAL_ONLY") is None
        assert db.set_trial_tanda_captions("TRIAL_ONLY", "C:/trial.txt")
        assert db.get_trial_tanda_captions("TRIAL_ONLY") == "C:/trial.txt"
        db.close()
        db = database.DatabaseManager()
        assert db.get_trial_tanda_captions("TRIAL_ONLY") == "C:/trial.txt"
        assert db.set_trial_tanda_captions("TRIAL_ONLY", None)
        assert db.get_trial_tanda_captions("TRIAL_ONLY") is None
    finally:
        db.close()
        database.DB_PATH = previous


def test_existing_trial_tandas_gain_txt_column_without_losing_rows(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE trial_tandas (tanda_name TEXT PRIMARY KEY, created_at TEXT)")
    conn.execute("INSERT INTO trial_tandas VALUES ('OLD_TRIAL', '2026-01-01')")
    conn.commit()
    conn.close()
    db = database.DatabaseManager(str(path))
    try:
        assert db.get_trial_tandas() == ["OLD_TRIAL"]
        assert db.get_trial_tanda_captions("OLD_TRIAL") is None
        assert db.set_trial_tanda_captions("OLD_TRIAL", "C:/captions.txt")
        assert db.get_trial_tanda_captions("OLD_TRIAL") == "C:/captions.txt"
    finally:
        db.close()

