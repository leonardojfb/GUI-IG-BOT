import database


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

