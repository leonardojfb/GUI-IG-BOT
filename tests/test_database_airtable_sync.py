import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import database
from airtable_sync import AccountSyncPlan


class DatabaseAirtableSyncTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.original_path = database.DB_PATH
        database.DB_PATH = self.path
        self.db = database.DatabaseManager()
        self.db.add_category("OLD")
        self.db.add_virtual_account("one", "OLD")
        self.db.update_account("one", notes="keep local", followers=42, ig_status="alive")
        self.db.add_virtual_account("gone", "OLD")

    def tearDown(self):
        self.db.close()
        database.DB_PATH = self.original_path
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_migrates_and_applies_create_update_delete(self):
        plan = AccountSyncPlan(
            create=[{
                "username": "new", "account_type": "TRIALS", "assigned_va": "Ana",
                "trials_active": True, "two_factor": "x", "account_day": "Lunes",
                "social_network": "Instagram", "vpn_proxy": "p", "account_link": "https://x",
            }],
            update=[{
                "username": "one", "account_type": "PROMO", "assigned_va": "Ana",
                "trials_active": False, "two_factor": "y", "account_day": "Martes",
                "social_network": "TikTok", "vpn_proxy": "q", "account_link": "https://y",
            }],
            delete_usernames=["gone"],
            categories_to_add=["PROMO", "TRIALS"],
        )

        self.assertEqual(
            self.db.apply_airtable_account_plan(plan),
            {"created": 1, "updated": 1, "deleted": 1},
        )
        rows = {row["username"]: row for row in self.db.get_all_accounts()}
        self.assertNotIn("gone", rows)
        self.assertEqual(rows["new"]["account_day"], "Lunes")
        self.assertEqual(rows["one"]["account_type"], "PROMO")
        self.assertEqual(rows["one"]["notes"], "keep local")
        self.assertEqual(rows["one"]["followers"], 42)
        self.assertEqual(rows["one"]["ig_status"], "alive")

    def test_invalid_plan_rolls_back_everything(self):
        plan = AccountSyncPlan(
            create=[{
                "username": "new", "account_type": "PROMO", "assigned_va": "Ana",
                "trials_active": False, "two_factor": "", "account_day": "",
                "social_network": "", "vpn_proxy": "", "account_link": "",
            }],
            update=[],
            delete_usernames=["gone"],
            categories_to_add=["PROMO", ""],
        )

        with self.assertRaises(ValueError):
            self.db.apply_airtable_account_plan(plan)

        self.assertEqual(
            {row["username"] for row in self.db.get_all_accounts()},
            {"one", "gone"},
        )
