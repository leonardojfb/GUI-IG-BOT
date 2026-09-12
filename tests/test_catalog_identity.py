import database

from catalog.service import CatalogService


def _temporary_db(tmp_path):
    previous = database.DB_PATH
    database.DB_PATH = str(tmp_path / "organizador.db")
    db = database.DatabaseManager()
    return db, previous


def test_catalog_migration_assigns_stable_identity_and_current_alias(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        db.add_virtual_account("eve_old", "MAIN")
        db.update_account("eve_old", social_network="instagram")

        service = CatalogService(db)
        migrated = service.ensure_identity_catalog()

        [account] = db.get_all_accounts()
        assert migrated == 1
        assert account["identity_id"] == f"legacy-account-{account['id']}"

        identity = service.get_identity(account["identity_id"])
        assert identity["legacy_account_id"] == account["id"]
        assert identity["platform"] == "instagram"
        assert identity["display_name"] == "eve_old"

        aliases = service.get_aliases(account["identity_id"])
        assert aliases == [
            {
                "alias": "eve_old",
                "alias_type": "username",
                "is_current": 1,
                "source": "legacy_migration",
            }
        ]
    finally:
        db.close()
        database.DB_PATH = previous


def test_rename_identity_preserves_identity_id_and_archives_previous_alias(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        db.add_virtual_account("eve_old", "MAIN")
        db.update_account("eve_old", social_network="instagram")
        service = CatalogService(db)
        service.ensure_identity_catalog()
        [before] = db.get_all_accounts()

        service.rename_identity(before["identity_id"], "eve_new")

        [after] = db.get_all_accounts()
        assert after["id"] == before["id"]
        assert after["identity_id"] == before["identity_id"]
        assert after["username"] == "eve_new"
        assert service.get_identity(before["identity_id"])["display_name"] == "eve_new"
        assert service.get_aliases(before["identity_id"]) == [
            {
                "alias": "eve_new",
                "alias_type": "username",
                "is_current": 1,
                "source": "rename",
            },
            {
                "alias": "eve_old",
                "alias_type": "username",
                "is_current": 0,
                "source": "legacy_migration",
            },
        ]
    finally:
        db.close()
        database.DB_PATH = previous


def test_trial_capability_requires_instagram_identity(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        db.add_virtual_account("ig", "MAIN")
        db.update_account("ig", social_network="instagram")
        db.add_virtual_account("fb", "MAIN")
        db.update_account("fb", social_network="facebook")
        service = CatalogService(db)
        service.ensure_identity_catalog()
        accounts = {account["username"]: account for account in db.get_all_accounts()}

        assert service.set_trial_capability(accounts["ig"]["identity_id"], True) is True
        assert db.get_trials_active_accounts()[0]["username"] == "ig"

        try:
            service.set_trial_capability(accounts["fb"]["identity_id"], True)
        except ValueError as exc:
            assert "Instagram" in str(exc)
        else:
            raise AssertionError("facebook identity should not enable Trial")

        refreshed = {account["username"]: account for account in db.get_all_accounts()}
        assert refreshed["fb"]["trials_active"] == 0
    finally:
        db.close()
        database.DB_PATH = previous
