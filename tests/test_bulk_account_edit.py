import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import DatabaseManager
from gui_premium_v7 import build_bulk_account_updates, resolve_selected_account_ids


class BulkAccountEditTest(unittest.TestCase):
    def test_builds_only_selected_fields(self):
        self.assertEqual(
            build_bulk_account_updates("PROMO", "Sin cambios"),
            {"account_type": "PROMO"},
        )
        self.assertEqual(
            build_bulk_account_updates("Sin cambios", "Laura"),
            {"assigned_va": "Laura"},
        )
        self.assertEqual(
            build_bulk_account_updates("SUICIDE", "Laura"),
            {"account_type": "SUICIDE", "assigned_va": "Laura"},
        )

    def test_rejects_empty_bulk_update(self):
        self.assertEqual(build_bulk_account_updates("Sin cambios", "Sin cambios"), {})

    def test_updates_only_selected_accounts_and_preserves_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager()
            db.close()
            db.db_path = os.path.join(tmp, "accounts.db")
            db.conn = __import__("sqlite3").connect(db.db_path)
            db.conn.row_factory = __import__("sqlite3").Row
            db.initialize()
            db.add_virtual_account("one", "PROMO")
            db.add_virtual_account("two", "PROMO")
            db.add_virtual_account("three", "SUICIDE")
            selected = db.get_all_accounts()[:2]
            db.bulk_update_accounts(
                [account["id"] for account in selected],
                account_type="SUICIDE",
                assigned_va="Laura",
            )
            values = {a["username"]: a for a in db.get_all_accounts()}
            self.assertEqual(values["one"]["account_type"], "SUICIDE")
            self.assertEqual(values["one"]["assigned_va"], "Laura")
            self.assertEqual(values["two"]["account_type"], "SUICIDE")
            self.assertEqual(values["three"]["account_type"], "SUICIDE")
            self.assertEqual(values["three"]["assigned_va"], "Sin Asignar")
            db.close()


class BulkAccountHandlerTest(unittest.TestCase):
    def test_selected_usernames_resolve_to_database_ids(self):
        rows = [
            {"id": 10, "username": "one"},
            {"id": 11, "username": "two"},
            {"id": 12, "username": "three"},
        ]
        self.assertEqual(
            resolve_selected_account_ids(rows, ["one", "three"]),
            [10, 12],
        )


if __name__ == "__main__":
    unittest.main()
