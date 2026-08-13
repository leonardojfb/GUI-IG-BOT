import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from airtable_sync import (
    AirtableConfig,
    AirtableSchemaPreparation,
    AirtableSyncError,
    build_legacy_field_migration_plan,
    build_account_sync_plan,
    fetch_airtable_accounts,
    load_airtable_config,
    prepare_airtable_account_table,
    save_airtable_config,
)
from gui_premium_v7 import airtable_schema_preparation_text, airtable_sync_review_text


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
                    {"id": "rec2", "fields": {"Username": "two", "Categoria": "PROMO"}}
                ]})
            return FakeResponse({"records": [
                {"id": "rec1", "fields": {"Username": "@One", "Categoria": "PROMO"}}
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
                {"id": "rec1", "fields": {"Username": "@One", "Categoria": "PROMO"}},
                {"id": "rec2", "fields": {"Username": "one", "Categoria": "PROMO"}},
            ]})

        with self.assertRaisesRegex(AirtableSyncError, "duplicado"):
            fetch_airtable_accounts(
                AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get
            )

    def test_ignores_completely_empty_airtable_rows(self):
        def fake_get(_url, *, headers, params, timeout):
            return FakeResponse({"records": [
                {"id": "recEmpty", "fields": {}},
                {"id": "recOne", "fields": {"Username": "one", "Categoria": "PROMO"}},
            ]})

        rows = fetch_airtable_accounts(
            AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get
        )

        self.assertEqual([row.username for row in rows], ["one"])


class AirtableSchemaPreparationTest(unittest.TestCase):
    def test_adds_only_missing_required_fields_to_existing_table(self):
        calls = []

        def fake_get(url, *, headers, timeout):
            self.assertEqual(url, "https://api.airtable.com/v0/meta/bases/app123/tables")
            self.assertEqual(headers, {"Authorization": "Bearer pat_secret"})
            return FakeResponse({"tables": [{
                "id": "tblAccounts",
                "name": "Cuentas",
                "fields": [{"id": "fldUsername", "name": "Username", "type": "singleLineText"}],
            }]})

        def fake_post(url, *, headers, json, timeout):
            calls.append((url, headers, json, timeout))
            return FakeResponse({"id": f"fld{len(calls)}"})

        result = prepare_airtable_account_table(
            AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get, fake_post
        )

        self.assertEqual(
            result.added_fields,
            ("2FA", "VA", "Categoria", "Trials desbloqueados", "Dia", "Red social", "VPN / Proxy", "Link"),
        )
        self.assertEqual(result.incompatible_fields, ())
        self.assertEqual([call[2] for call in calls], [
            {"name": "2FA", "type": "multilineText"},
            {"name": "VA", "type": "singleLineText"},
            {"name": "Categoria", "type": "singleLineText"},
            {
                "name": "Trials desbloqueados",
                "type": "checkbox",
                "options": {"icon": "check", "color": "greenBright"},
            },
            {"name": "Dia", "type": "singleLineText"},
            {"name": "Red social", "type": "singleLineText"},
            {"name": "VPN / Proxy", "type": "multilineText"},
            {"name": "Link", "type": "url"},
        ])
        self.assertTrue(all(call[0].endswith("/tblAccounts/fields") for call in calls))

    def test_keeps_incompatible_field_and_requires_existing_table(self):
        def fake_get(_url, *, headers, timeout):
            return FakeResponse({"tables": [{
                "id": "tblAccounts",
                "name": "Cuentas",
                "fields": [{"id": "fldCategory", "name": "Categoria", "type": "singleSelect"}],
            }]})

        calls = []

        def fake_post(_url, *, headers, json, timeout):
            calls.append(json)
            return FakeResponse({"id": f"fld{len(calls)}"})

        result = prepare_airtable_account_table(
            AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get, fake_post
        )

        self.assertEqual(result.incompatible_fields, (("Categoria", "singleSelect", "singleLineText"),))
        self.assertNotIn({"name": "Categoria", "type": "singleLineText"}, calls)

        with self.assertRaisesRegex(AirtableSyncError, "no existe"):
            prepare_airtable_account_table(
                AirtableConfig("pat_secret", "app123", "Ausente"),
                lambda _url, **_kwargs: FakeResponse({"tables": []}),
                fake_post,
            )

    def test_reports_schema_write_permission_without_exposing_the_token(self):
        def fake_get(_url, *, headers, timeout):
            return FakeResponse({"tables": [{
                "id": "tblAccounts",
                "name": "Cuentas",
                "fields": [],
            }]})

        def fake_post(_url, *, headers, json, timeout):
            return FakeResponse({
                "error": {"type": "INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND"}
            }, status_code=403)

        with self.assertRaisesRegex(AirtableSyncError, "permiso.*schema.bases:write") as exc:
            prepare_airtable_account_table(
                AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get, fake_post
            )
        message = str(exc.exception)
        self.assertIn("HTTP 403", message)
        self.assertIn("INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND", message)
        self.assertIn("Username", message)
        self.assertNotIn("pat_secret", message)


class AirtableGuiConnectionTest(unittest.TestCase):
    def test_connection_feedback_reports_added_and_untouched_fields(self):
        text = airtable_schema_preparation_text(AirtableSchemaPreparation(
            added_fields=("Username", "Link"),
            incompatible_fields=(("Categoria", "singleSelect", "singleLineText"),),
        ))

        self.assertIn("Columnas agregadas: Username, Link.", text)
        self.assertIn("Categoria", text)
        self.assertIn("no se modificó", text)

    def test_gui_prepares_schema_before_saving_connection(self):
        source = open(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "gui_premium_v7.py"),
            encoding="utf-8",
        ).read()
        configure_source = source[source.index("    def configure_airtable(self):"):source.index("    def sync_airtable_accounts(self):")]

        self.assertIn('text="Conectar y preparar Airtable"', source)
        self.assertIn("prepare_airtable_account_table(config)", configure_source)
        self.assertLess(
            configure_source.index("prepare_airtable_account_table(config)"),
            configure_source.index("save_airtable_config(config)"),
        )


class AirtableLegacyMigrationTest(unittest.TestCase):
    def test_copies_generic_fields_without_overwriting_and_converts_trials(self):
        plan = build_legacy_field_migration_plan([
            {
                "id": "recOne",
                "fields": {
                    "Field 1": "secret", "Field 2": "Ana", "Field 3": "PROMO",
                    "Field 4": "Sí", "Field 5": "Lunes", "Field 6": "Instagram",
                    "Field 7": "proxy", "Field 8": "instagram.com/one",
                    "VA": "No sobreescribir",
                },
            },
            {
                "id": "recTwo",
                "fields": {"Field 3": "TRIALS", "Field 4": "No"},
            },
        ])

        self.assertEqual(plan.records_to_update, 2)
        self.assertEqual(plan.field_counts["Categoria"], 2)
        first = next(row for row in plan.updates if row["id"] == "recOne")["fields"]
        second = next(row for row in plan.updates if row["id"] == "recTwo")["fields"]
        self.assertEqual(first["2FA"], "secret")
        self.assertNotIn("VA", first)
        self.assertEqual(first["Categoria"], "PROMO")
        self.assertTrue(first["Trials desbloqueados"])
        self.assertEqual(first["Dia"], "Lunes")
        self.assertEqual(first["Link"], "https://instagram.com/one")
        self.assertNotIn("Trials desbloqueados", second)


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


class ReviewTextTest(unittest.TestCase):
    def test_review_contains_counts_and_usernames_only(self):
        plan = build_account_sync_plan(
            [{
                "username": "one", "account_type": "PROMO", "assigned_va": "Ana",
                "trials_active": False, "two_factor": "never-show", "account_day": "",
                "social_network": "", "vpn_proxy": "never-show", "account_link": "",
            }],
            [{"id": 1, "username": "gone", "account_type": "PROMO", "assigned_va": "Ana"}],
        )

        text = airtable_sync_review_text(plan)

        self.assertIn("1 creadas", text)
        self.assertIn("1 eliminadas", text)
        self.assertIn("@one", text)
        self.assertIn("@gone", text)
        self.assertNotIn("never-show", text)
