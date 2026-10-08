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
    build_legacy_column_repair_plan,
    build_positional_column_repair_plan,
    build_account_sync_plan,
    build_airtable_mirror_plan,
    apply_airtable_mirror_plan,
    fetch_airtable_records,
    fetch_airtable_accounts,
    fetch_published_video_hashes,
    load_airtable_config,
    prepare_airtable_account_table,
    save_airtable_config,
)
from gui_premium_v7 import (
    airtable_schema_preparation_text,
    airtable_sync_review_text,
    airtable_mirror_review_text,
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
    def test_fetch_published_hashes_uses_dedicated_table_and_all_pages(self):
        calls = []

        def fake_get(url, *, headers, params, timeout):
            calls.append((url, params.copy()))
            if params.get("offset"):
                return FakeResponse({
                    "records": [{"id": "rec2", "fields": {"SHA-256": "b" * 64}}]
                })
            return FakeResponse({
                "records": [{"id": "rec1", "fields": {"SHA-256": "a" * 64}}],
                "offset": "next",
            })

        hashes = fetch_published_video_hashes(
            AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get
        )

        self.assertEqual(hashes, {"a" * 64, "b" * 64})
        self.assertEqual(
            calls[0][0], "https://api.airtable.com/v0/app123/Videos%20publicados"
        )
        self.assertEqual(calls[1][1]["offset"], "next")

    def test_fetch_published_hashes_rejects_invalid_hash(self):
        def fake_get(_url, *, headers, params, timeout):
            return FakeResponse({
                "records": [{"id": "rec1", "fields": {"SHA-256": "wrong"}}]
            })

        with self.assertRaisesRegex(AirtableSyncError, "videos publicados"):
            fetch_published_video_hashes(
                AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get
            )

    def test_fetch_airtable_records_keeps_record_ids_across_pages(self):
        calls = []

        def fake_get(_url, *, headers, params, timeout):
            calls.append(params.copy())
            if params.get("offset"):
                return FakeResponse({"records": [{"id": "rec2", "fields": {"Username": "two"}}]})
            return FakeResponse({"records": [{"id": "rec1", "fields": {"Username": "one"}}], "offset": "next"})

        records = fetch_airtable_records(AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get)
        self.assertEqual([record["id"] for record in records], ["rec1", "rec2"])
        self.assertEqual(calls[1]["offset"], "next")

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
    def test_repairs_first_nine_columns_by_position_without_name_detection(self):
        table = {
            "id": "tblAccounts",
            "name": "Cuentas",
            "fields": [
                {"id": f"fld{i}", "name": name, "type": "singleLineText"}
                for i, name in enumerate(
                    ("Name", "Field 1", "Field 2", "Field 3", "Field 4", "Field 5", "Field 6", "Field 7", "Field 8"),
                    start=1,
                )
            ] + [
                {"id": "fldDuplicate", "name": "Categoria", "type": "singleLineText"},
            ],
        }

        plan = build_positional_column_repair_plan(table)

        self.assertEqual(
            plan.source_renames,
            tuple((f"fld{i}", target) for i, target in enumerate(
                ("Username", "2FA", "VA", "Categoria", "Trials desbloqueados", "Dia", "Red social", "VPN / Proxy", "Link"),
                start=1,
            )),
        )
        self.assertEqual(plan.backup_renames, (("fldDuplicate", "__backup__Categoria"),))

    def test_repairs_first_columns_and_moves_existing_duplicates_to_backup_names(self):
        schema = {
            "id": "tblAccounts",
            "name": "Cuentas",
            "fields": [
                {"id": "fldUsername", "name": "Username", "type": "multilineText"},
                *[
                    {"id": f"fld{i}", "name": f"Field {i}", "type": "singleSelect"}
                    for i in range(1, 9)
                ],
                {"id": "fld2fa", "name": "2FA", "type": "multilineText"},
                {"id": "fldCategoria", "name": "Categoria", "type": "singleLineText"},
                {"id": "fldTrials", "name": "Trials desbloqueados", "type": "checkbox"},
            ],
        }

        plan = build_legacy_column_repair_plan(schema)

        self.assertEqual(
            plan.source_renames,
            (
                ("fld1", "2FA"), ("fld2", "VA"), ("fld3", "Categoria"),
                ("fld4", "Trials desbloqueados"), ("fld5", "Dia"),
                ("fld6", "Red social"), ("fld7", "VPN / Proxy"), ("fld8", "Link"),
            ),
        )
        self.assertEqual(
            plan.backup_renames,
            (
                ("fld2fa", "__backup__2FA"),
                ("fldCategoria", "__backup__Categoria"),
                ("fldTrials", "__backup__Trials desbloqueados"),
            ),
        )

    def test_preparation_renames_existing_first_columns_in_place(self):
        schema = {"tables": [{
            "id": "tblAccounts", "name": "Cuentas", "fields": [
                {"id": "fldUsername", "name": "Username", "type": "multilineText"},
                *[
                    {"id": f"fld{i}", "name": f"Field {i}", "type": "singleSelect"}
                    for i in range(1, 9)
                ],
                {"id": "fld2fa", "name": "2FA", "type": "multilineText"},
            ],
        }]}
        calls = []

        def fake_get(_url, *, headers, timeout):
            return FakeResponse(schema)

        def fake_patch(url, *, headers, json, timeout):
            calls.append((url, json))
            return FakeResponse({"id": "field"})

        result = prepare_airtable_account_table(
            AirtableConfig("pat_secret", "app123", "Cuentas"),
            fake_get,
            requests_patch=fake_patch,
        )

        self.assertEqual(result.added_fields, ())
        self.assertEqual(calls[0][1], {"name": "__backup__2FA"})
        self.assertEqual(calls[1][1], {"name": "2FA"})
        self.assertEqual(calls[-1][1], {"name": "Link"})

    def test_renames_first_nine_columns_without_creating_fields(self):
        calls = []
        post_calls = []

        def fake_get(url, *, headers, timeout):
            self.assertEqual(url, "https://api.airtable.com/v0/meta/bases/app123/tables")
            self.assertEqual(headers, {"Authorization": "Bearer pat_secret"})
            return FakeResponse({"tables": [{
                "id": "tblAccounts",
                "name": "Cuentas",
                "fields": [
                    {"id": f"fld{i}", "name": f"Whatever {i}", "type": "singleLineText"}
                    for i in range(1, 10)
                ],
            }]})

        def fake_post(url, *, headers, json, timeout):
            post_calls.append((url, headers, json, timeout))
            return FakeResponse({"id": "unexpected"})

        def fake_patch(url, *, headers, json, timeout):
            calls.append((url, headers, json, timeout))
            return FakeResponse({"id": "updated"})

        result = prepare_airtable_account_table(
            AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get, fake_post, fake_patch
        )

        self.assertEqual(
            result.added_fields,
            (),
        )
        self.assertEqual(result.incompatible_fields, ())
        self.assertEqual([call[2] for call in calls], [
            {"name": name}
            for name in ("Username", "2FA", "VA", "Categoria", "Trials desbloqueados", "Dia", "Red social", "VPN / Proxy", "Link")
        ])
        self.assertEqual(post_calls, [])

    def test_rejects_table_with_fewer_than_nine_columns(self):
        def fake_get(_url, *, headers, timeout):
            return FakeResponse({"tables": [{
                "id": "tblWrong", "name": "CUENTAS EVE", "fields": [
                    {"id": "fldName", "name": "Name", "type": "singleLineText"},
                    {"id": "fldStatus", "name": "Status", "type": "singleSelect"},
                ],
            }]})

        with self.assertRaisesRegex(AirtableSyncError, "al menos 9 columnas"):
            prepare_airtable_account_table(
                AirtableConfig("pat_secret", "app123", "CUENTAS EVE"), fake_get
            )

    def test_requires_at_least_nine_columns_and_existing_table(self):
        def fake_get(_url, *, headers, timeout):
            return FakeResponse({"tables": [{
                "id": "tblAccounts",
                "name": "Cuentas",
                "fields": [
                    {"id": "fldUsername", "name": "Username", "type": "singleLineText"},
                    {"id": "fldCategory", "name": "Categoria", "type": "singleSelect"},
                ],
            }]})

        with self.assertRaisesRegex(AirtableSyncError, "al menos 9 columnas"):
            prepare_airtable_account_table(
                AirtableConfig("pat_secret", "app123", "Cuentas"), fake_get
            )

        with self.assertRaisesRegex(AirtableSyncError, "no existe"):
            prepare_airtable_account_table(
                AirtableConfig("pat_secret", "app123", "Ausente"),
                lambda _url, **_kwargs: FakeResponse({"tables": []}),
            )

    def test_reports_schema_write_permission_without_exposing_the_token(self):
        def fake_get(_url, *, headers, timeout):
            return FakeResponse({"tables": [{
                "id": "tblAccounts",
                "name": "Cuentas",
                "fields": [
                    {"id": f"fld{i}", "name": f"Whatever {i}", "type": "singleLineText"}
                    for i in range(1, 10)
                ],
            }]})

        def fake_patch(_url, *, headers, json, timeout):
            return FakeResponse({
                "error": {"type": "INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND"}
            }, status_code=403)

        with self.assertRaisesRegex(AirtableSyncError, "HTTP 403") as exc:
            prepare_airtable_account_table(
                AirtableConfig("pat_secret", "app123", "Cuentas"),
                fake_get,
                requests_patch=fake_patch,
            )
        message = str(exc.exception)
        self.assertIn("HTTP 403", message)
        self.assertIn("INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND", message)
        self.assertIn("Username", message)
        self.assertNotIn("pat_secret", message)


class AirtableMirrorTest(unittest.TestCase):
    def test_builds_complete_local_mirror_plan(self):
        local = [
            {
                "username": "keep",
                "two_factor": "new-secret",
                "assigned_va": "Ana",
                "account_type": "MAIN",
                "trials_active": True,
                "account_day": "Dia 2",
                "social_network": "IG",
                "vpn_proxy": "proxy",
                "account_link": "https://example.com/keep",
            },
            {
                "username": "new",
                "account_type": "TRIALS",
            },
        ]
        remote = [
            {"id": "recKeep", "fields": {"Username": "keep", "2FA": "old", "Categoria": "MAIN"}},
            {"id": "recGone", "fields": {"Username": "gone", "Categoria": "SPAM"}},
        ]

        plan = build_airtable_mirror_plan(local, remote)

        self.assertEqual([row["Username"] for row in plan.create], ["new"])
        self.assertEqual(plan.update[0]["record_id"], "recKeep")
        self.assertEqual(plan.update[0]["fields"]["2FA"], "new-secret")
        self.assertEqual(plan.delete, [{"record_id": "recGone", "username": "gone"}])

    def test_applies_create_update_and_delete_without_extra_fields(self):
        calls = []

        def fake_post(url, *, headers, json, timeout):
            calls.append(("POST", url, json))
            return FakeResponse({"records": [{"id": "recNew"}]})

        def fake_patch(url, *, headers, json, timeout):
            calls.append(("PATCH", url, json))
            return FakeResponse({"records": [{"id": "recKeep"}]})

        def fake_delete(url, *, headers, timeout):
            calls.append(("DELETE", url, None))
            return FakeResponse({}, status_code=200)

        plan = build_airtable_mirror_plan(
            [{"username": "new", "account_type": "TRIALS"}],
            [{"id": "recGone", "fields": {"Username": "gone", "Categoria": "SPAM"}}],
        )
        counts = apply_airtable_mirror_plan(
            AirtableConfig("pat_secret", "app123", "Cuentas"),
            plan,
            fake_post,
            fake_patch,
            fake_delete,
        )

        self.assertEqual(counts, {"created": 1, "updated": 0, "deleted": 1})
        self.assertEqual([call[0] for call in calls], ["POST", "DELETE"])
        self.assertNotIn("pat_secret", repr(calls))


class AirtableGuiConnectionTest(unittest.TestCase):
    def test_mirror_review_mentions_deletions_and_source(self):
        text = airtable_mirror_review_text(
            type("Plan", (), {
                "create": [{"Username": "new"}],
                "update": [{"username": "keep"}],
                "delete": [{"username": "gone"}],
            })()
        )
        self.assertIn("GUI → Airtable", text)
        self.assertIn("1 creadas", text)
        self.assertIn("1 actualizadas", text)
        self.assertIn("1 eliminadas", text)
        self.assertIn("@gone", text)

    def test_gui_exposes_separate_gui_to_airtable_button(self):
        source = open(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "gui_premium_v7.py"),
            encoding="utf-8",
        ).read()
        self.assertIn('text="Sincronizar GUI → Airtable"', source)
        self.assertIn("apply_airtable_mirror_plan", source)

    def test_connection_feedback_reports_reused_first_columns(self):
        text = airtable_schema_preparation_text(AirtableSchemaPreparation(
            added_fields=(),
            incompatible_fields=(),
            source_renames=(("fld1", "2FA"), ("fld8", "Link")),
            backup_renames=(("fldOld", "__backup__2FA"),),
        ))

        self.assertIn("primeras 9 columnas por posición", text)
        self.assertIn("2FA", text)
        self.assertIn("respaldo", text)

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
