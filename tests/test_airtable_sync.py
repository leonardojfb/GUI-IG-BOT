import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from airtable_sync import (
    AirtableConfig,
    AirtableSyncError,
    build_account_sync_plan,
    fetch_airtable_accounts,
    load_airtable_config,
    save_airtable_config,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class AirtableConfigTest(unittest.TestCase):
    def test_round_trip_and_missing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "airtable_config.json")
            config = AirtableConfig("pat_secret", "app123", "Cuentas")
            save_airtable_config(config, path)
            self.assertEqual(load_airtable_config(path), config)
            with open(path, "w", encoding="utf-8") as stream:
                json.dump({"base_id": "app123"}, stream)
            with self.assertRaisesRegex(AirtableSyncError, "configuraci"):
                load_airtable_config(path)


class AirtableFetchTest(unittest.TestCase):
    def test_fetches_every_page_and_normalizes_username(self):
        calls = []

        def fake_get(url, *, headers, params, timeout):
            calls.append(params.copy())
            if params.get("offset"):
                return FakeResponse({"records": [
                    {"id": "rec2", "fields": {"Username": "two", "Categoría": "PROMO"}}
                ]})
            return FakeResponse({"records": [
                {"id": "rec1", "fields": {"Username": "@One", "Categoría": "PROMO"}}
            ], "offset": "next"})

        rows = fetch_airtable_accounts(
            AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get
        )
        self.assertEqual([row.username for row in rows], ["One", "two"])
        self.assertEqual(calls[1]["offset"], "next")
        self.assertNotIn("pat_secret", repr(rows))

    def test_rejects_duplicate_username(self):
        def fake_get(_url, *, headers, params, timeout):
            return FakeResponse({"records": [
                {"id": "rec1", "fields": {"Username": "@One", "Categoría": "PROMO"}},
                {"id": "rec2", "fields": {"Username": "one", "Categoría": "PROMO"}},
            ]})

        with self.assertRaisesRegex(AirtableSyncError, "duplicado"):
            fetch_airtable_accounts(
                AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get
            )


class ReconciliationTest(unittest.TestCase):
    def test_plans_create_update_delete_without_unmanaged_values(self):
        remote = [
            {
                "username": "one", "account_type": "PROMO", "assigned_va": "Ana",
                "trials_active": True, "two_factor": "secret", "account_day": "Lunes",
                "social_network": "Instagram", "vpn_proxy": "proxy", "account_link": "https://x",
            },
            {
                "username": "new", "account_type": "TRIALS", "assigned_va": "Sin Asignar",
                "trials_active": False, "two_factor": "", "account_day": "",
                "social_network": "", "vpn_proxy": "", "account_link": "",
            },
        ]
        local = [
            {
                "id": 1, "username": "ONE", "account_type": "OLD", "assigned_va": "Leo",
                "trials_active": 0, "ig_status": "alive", "notes": "local",
            },
            {"id": 2, "username": "gone", "account_type": "PROMO", "assigned_va": "Leo"},
        ]

        plan = build_account_sync_plan(remote, local)

        self.assertEqual([row["username"] for row in plan.create], ["new"])
        self.assertEqual([row["username"] for row in plan.update], ["one"])
        self.assertEqual(plan.delete_usernames, ["gone"])
        self.assertEqual(plan.categories_to_add, ["PROMO", "TRIALS"])
        self.assertNotIn("notes", plan.update[0])
