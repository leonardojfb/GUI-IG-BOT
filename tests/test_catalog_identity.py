import database

from calendar_manifest import build_entry, replace_entries
from catalog.service import CLEAR, SET, UNSET, CatalogService


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


def test_bulk_preview_and_apply_distinguishes_unset_clear_and_set(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        db.add_virtual_account("one", "MAIN")
        db.update_account("one", assigned_va="Laura", trials_active=1)
        db.add_virtual_account("two", "MAIN")
        db.update_account("two", assigned_va="Leo")
        db.add_virtual_account("three", "SPAM")
        db.update_account("three", assigned_va="Maria")
        service = CatalogService(db)
        service.ensure_identity_catalog()
        accounts = {account["username"]: account for account in db.get_all_accounts()}

        preview = service.preview_bulk_update(
            [accounts["one"]["id"], accounts["two"]["id"]],
            {
                "account_type": SET("TRIALS"),
                "assigned_va": CLEAR,
                "trials_active": UNSET,
            },
        )

        assert [row["id"] for row in preview["rows"]] == [
            accounts["one"]["id"],
            accounts["two"]["id"],
        ]
        assert preview["rows"][0]["before"]["assigned_va"] == "Laura"
        assert preview["rows"][0]["after"]["assigned_va"] == "Sin Asignar"
        assert preview["rows"][0]["after"]["trials_active"] == 1
        assert preview["rows"][1]["after"]["account_type"] == "TRIALS"

        changed = service.apply_bulk_update(preview)

        assert changed == 2
        refreshed = {account["username"]: account for account in db.get_all_accounts()}
        assert refreshed["one"]["account_type"] == "TRIALS"
        assert refreshed["one"]["assigned_va"] == "Sin Asignar"
        assert refreshed["one"]["trials_active"] == 1
        assert refreshed["two"]["account_type"] == "TRIALS"
        assert refreshed["three"]["account_type"] == "SPAM"
        assert refreshed["three"]["assigned_va"] == "Maria"
    finally:
        db.close()
        database.DB_PATH = previous


def test_bulk_apply_rejects_stale_preview_revision(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        db.add_virtual_account("one", "MAIN")
        db.update_account("one", assigned_va="Laura")
        service = CatalogService(db)
        service.ensure_identity_catalog()
        [account] = db.get_all_accounts()

        preview = service.preview_bulk_update(
            [account["id"]],
            {"assigned_va": SET("Leo")},
        )
        db.update_account("one", assigned_va="Maria")

        try:
            service.apply_bulk_update(preview)
        except ValueError as exc:
            assert "revision" in str(exc)
        else:
            raise AssertionError("stale preview should be rejected")

        [refreshed] = db.get_all_accounts()
        assert refreshed["assigned_va"] == "Maria"
    finally:
        db.close()
        database.DB_PATH = previous


def test_category_remains_unique_while_tags_are_many_to_many(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        db.add_virtual_account("one", "MAIN")
        service = CatalogService(db)
        service.ensure_identity_catalog()
        [account] = db.get_all_accounts()

        assert service.set_account_category(account["id"], "SPAM") is True
        assert service.add_account_tag(account["id"], "hot") is True
        assert service.add_account_tag(account["id"], "trial-ready") is True
        assert service.add_account_tag(account["id"], "hot") is False

        [refreshed] = db.get_all_accounts()
        assert refreshed["account_type"] == "SPAM"
        assert service.tags_for_account(account["id"]) == ["hot", "trial-ready"]

        assert service.remove_account_tag(account["id"], "hot") is True
        assert service.tags_for_account(account["id"]) == ["trial-ready"]
        assert refreshed["account_type"] not in service.tags_for_account(account["id"])
    finally:
        db.close()
        database.DB_PATH = previous


def test_tag_schema_is_additive_for_existing_databases(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        service = CatalogService(db)
        service.ensure_identity_catalog()

        cur = db.conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (?, ?)",
            ("account_tags", "virtual_account_tags"),
        )

        assert {row["name"] for row in cur.fetchall()} == {
            "account_tags",
            "virtual_account_tags",
        }
    finally:
        db.close()
        database.DB_PATH = previous


def test_bulk_preview_blocks_apply_when_selected_account_has_confirmed_calendar(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        db.add_virtual_account("one", "MAIN")
        service = CatalogService(db)
        service.ensure_identity_catalog()
        [account] = db.get_all_accounts()
        source = tmp_path / "video.mp4"
        source.write_bytes(b"video")
        manifest = tmp_path / "calendar_manifest.json"
        replace_entries(
            manifest,
            [
                build_entry(
                    "one",
                    account["id"],
                    "normal",
                    1,
                    2,
                    "TANDA_A",
                    str(source),
                    "one__TANDA_TANDA_A.mp4",
                    manual_status="confirmed",
                )
            ],
            {"one"},
            "normal",
        )

        preview = service.preview_bulk_update(
            [account["id"]],
            {"account_type": SET("SPAM")},
            manifest_file=manifest,
        )

        assert preview["calendar_conflicts"][0]["username"] == "one"
        assert preview["calendar_conflicts"][0]["manual_status"] == "confirmed"
        try:
            service.apply_bulk_update(preview)
        except ValueError as exc:
            assert "calendario" in str(exc)
        else:
            raise AssertionError("calendar conflict should require explicit override")

        assert service.apply_bulk_update(
            preview,
            allow_confirmed_calendar_changes=True,
        ) == 1
    finally:
        db.close()
        database.DB_PATH = previous


def test_category_change_validates_confirmed_calendar_conflicts(tmp_path):
    db, previous = _temporary_db(tmp_path)
    try:
        db.add_virtual_account("one", "MAIN")
        service = CatalogService(db)
        service.ensure_identity_catalog()
        [account] = db.get_all_accounts()
        source = tmp_path / "video.mp4"
        source.write_bytes(b"video")
        manifest = tmp_path / "calendar_manifest.json"
        replace_entries(
            manifest,
            [
                build_entry(
                    "one",
                    account["id"],
                    "normal",
                    1,
                    1,
                    "TANDA_A",
                    str(source),
                    "one__TANDA_TANDA_A.mp4",
                    manual_status="planned",
                )
            ],
            {"one"},
            "normal",
        )

        try:
            service.set_account_category(account["id"], "SPAM", manifest_file=manifest)
        except ValueError as exc:
            assert "calendario" in str(exc)
        else:
            raise AssertionError("category change should require calendar override")

        assert service.set_account_category(
            account["id"],
            "SPAM",
            manifest_file=manifest,
            allow_confirmed_calendar_changes=True,
        ) is True
    finally:
        db.close()
        database.DB_PATH = previous
