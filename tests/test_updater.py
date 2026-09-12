import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import updater


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def _zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class UpdaterTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app_dir = Path(self.temp_dir.name)
        (self.app_dir / "version.json").write_text(
            json.dumps({"version": "1.0.0"}), encoding="utf-8"
        )
        (self.app_dir / "database.py").write_text("old code", encoding="utf-8")
        (self.app_dir / "organizador.db").write_bytes(b"user database")
        (self.app_dir / "telegram_state_v11.json").write_text(
            '{"session": "user"}', encoding="utf-8"
        )
        for name, content in {
            "dist_accounts_history.json": "history",
            "panel_config.json": "panel",
            "captions.txt": "caption",
            "accounts_demo.txt": "account",
            "update_config.json": '{"manifest_url": "private-client-config"}',
        }.items():
            (self.app_dir / name).write_text(content, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _application_files(self, version="1.0.1", extra=None):
        files = {
            name: f"release content for {name}"
            for name in updater.APPLICATION_REQUIRED_FILES
        }
        files.update(
            {
                "version.json": json.dumps({"version": version}),
                "database.py": "new code",
                "launcher.py": "new launcher",
            }
        )
        files.update(extra or {})
        return files

    def _application_manifest(self, version="1.0.1", files=None, **extra):
        package_files = files or self._application_files(version)
        return {
            "version": version,
            "package_kind": "application",
            "files": sorted(package_files),
            **extra,
        }

    def _package(self, version="1.0.1"):
        return _zip_bytes(self._application_files(version))

    def test_apply_package_preserves_user_data(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(self._package())
        version = updater.apply_package(
            self.app_dir,
            package_path,
            self._application_manifest(),
        )

        self.assertEqual(version, "1.0.1")
        self.assertEqual((self.app_dir / "database.py").read_text(), "new code")
        self.assertEqual(json.loads((self.app_dir / "version.json").read_text())["version"], "1.0.1")
        self.assertEqual((self.app_dir / "organizador.db").read_bytes(), b"user database")
        self.assertEqual(
            (self.app_dir / "telegram_state_v11.json").read_text(),
            '{"session": "user"}',
        )
        for name, expected in {
            "dist_accounts_history.json": "history",
            "panel_config.json": "panel",
            "captions.txt": "caption",
            "accounts_demo.txt": "account",
            "update_config.json": '{"manifest_url": "private-client-config"}',
        }.items():
            self.assertEqual((self.app_dir / name).read_text(), expected)

    def test_apply_package_can_install_airtable_sync_module_without_local_config(self):
        package_path = self.app_dir / "release.zip"
        files = self._application_files(
            extra={"airtable_sync.py": "new airtable sync code"}
        )
        package_path.write_bytes(_zip_bytes(files))

        version = updater.apply_package(
            self.app_dir,
            package_path,
            self._application_manifest(files=files),
        )

        self.assertEqual(version, "1.0.1")
        self.assertEqual((self.app_dir / "airtable_sync.py").read_text(), "new airtable sync code")
        self.assertFalse((self.app_dir / "airtable_config.json").exists())

    def test_apply_package_can_install_default_database_template(self):
        package_path = self.app_dir / "release.zip"
        files = self._application_files(
            extra={"organizador.default.db": b"default database template"}
        )
        package_path.write_bytes(_zip_bytes(files))

        version = updater.apply_package(
            self.app_dir,
            package_path,
            self._application_manifest(files=files),
        )

        self.assertEqual(version, "1.0.1")
        self.assertEqual((self.app_dir / "database.py").read_text(), "new code")
        self.assertEqual((self.app_dir / "organizador.default.db").read_bytes(), b"default database template")
        self.assertEqual((self.app_dir / "dist_accounts_history.json").read_text(), "history")
        self.assertEqual((self.app_dir / "organizador.db").read_bytes(), b"user database")

    def test_apply_package_can_install_bundled_ffmpeg_tools(self):
        package_path = self.app_dir / "release.zip"
        files = self._application_files(
            extra={
                "tools/ffmpeg/bin/ffmpeg.exe": b"ffmpeg binary",
                "tools/ffmpeg/bin/ffprobe.exe": b"ffprobe binary",
            }
        )
        package_path.write_bytes(_zip_bytes(files))

        version = updater.apply_package(
            self.app_dir,
            package_path,
            self._application_manifest(files=files),
        )

        self.assertEqual(version, "1.0.1")
        self.assertEqual((self.app_dir / "tools/ffmpeg/bin/ffmpeg.exe").read_bytes(), b"ffmpeg binary")
        self.assertEqual((self.app_dir / "tools/ffmpeg/bin/ffprobe.exe").read_bytes(), b"ffprobe binary")

    def test_apply_package_rejects_operational_data_even_when_manifest_requests_it(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(
            _zip_bytes(
                {
                    "version.json": json.dumps({"version": "1.0.1"}),
                    "organizador.db": b"release database",
                    "dist_accounts_history.json": "release history",
                }
            )
        )

        with self.assertRaisesRegex(updater.UpdateError, "no permitido"):
            updater.apply_package(
                self.app_dir,
                package_path,
                {
                    "version": "1.0.1",
                    "package_kind": "application",
                    "files": [
                        "version.json",
                        "organizador.db",
                        "dist_accounts_history.json",
                    ],
                },
            )

        self.assertEqual((self.app_dir / "organizador.db").read_bytes(), b"user database")
        self.assertEqual((self.app_dir / "dist_accounts_history.json").read_text(), "history")
        self.assertEqual(updater.read_local_version(self.app_dir), "1.0.0")

    def test_apply_package_requires_explicit_manifest_files(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(self._package())

        with self.assertRaisesRegex(updater.UpdateError, "lista files"):
            updater.apply_package(
                self.app_dir,
                package_path,
                {"version": "1.0.1", "package_kind": "application"},
            )

        self.assertEqual((self.app_dir / "database.py").read_text(), "old code")
        self.assertEqual(updater.read_local_version(self.app_dir), "1.0.0")

    def test_apply_package_rejects_missing_manifest_file_before_writes(self):
        package_path = self.app_dir / "release.zip"
        files = self._application_files()
        files.pop("launcher.py")
        package_path.write_bytes(_zip_bytes(files))

        with self.assertRaisesRegex(updater.UpdateError, "Faltan archivos"):
            updater.apply_package(
                self.app_dir,
                package_path,
                self._application_manifest(),
            )

        self.assertEqual((self.app_dir / "database.py").read_text(), "old code")
        self.assertEqual(updater.read_local_version(self.app_dir), "1.0.0")

    def test_application_package_cannot_advance_version_with_only_version_file(self):
        package_path = self.app_dir / "release.zip"
        files = {"version.json": json.dumps({"version": "1.0.1"})}
        package_path.write_bytes(_zip_bytes(files))

        with self.assertRaisesRegex(updater.UpdateError, "incompleto"):
            updater.apply_package(
                self.app_dir,
                package_path,
                self._application_manifest(files=files),
            )

        self.assertEqual(updater.read_local_version(self.app_dir), "1.0.0")

    def test_bootstrap_package_is_limited_to_updater_and_version(self):
        package_path = self.app_dir / "bridge.zip"
        files = {
            "updater.py": "new updater",
            "version.json": json.dumps(
                {"version": "1.0.1", "update_phase": "bootstrap"}
            ),
        }
        package_path.write_bytes(_zip_bytes(files))

        version = updater.apply_package(
            self.app_dir,
            package_path,
            {
                "version": "1.0.1",
                "package_kind": "bootstrap",
                "files": sorted(files),
            },
        )

        self.assertEqual(version, "1.0.1")
        self.assertEqual((self.app_dir / "updater.py").read_text(), "new updater")

        application_path = self.app_dir / "application.zip"
        application_path.write_bytes(self._package())
        version = updater.apply_package(
            self.app_dir,
            application_path,
            self._application_manifest(),
        )

        self.assertEqual(version, "1.0.1")
        self.assertEqual((self.app_dir / "database.py").read_text(), "new code")
        installed_version = json.loads(
            (self.app_dir / "version.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("update_phase", installed_version)

    def test_hash_mismatch_does_not_change_installation(self):
        package = self._package()
        manifest = json.dumps(
            self._application_manifest(
                url="https://updates.example.test/package.zip",
                sha256="0" * 64,
            )
        ).encode("utf-8")
        (self.app_dir / "update_config.json").write_text(
            json.dumps({"manifest_url": "https://updates.example.test/manifest.json"}), encoding="utf-8"
        )
        responses = {
            "https://updates.example.test/manifest.json": manifest,
            "https://updates.example.test/package.zip": package,
        }

        def opener(request, timeout):
            return _Response(responses[request.full_url])

        self.assertFalse(updater.check_and_apply(self.app_dir, opener=opener))
        self.assertEqual((self.app_dir / "database.py").read_text(), "old code")
        self.assertEqual(updater.read_local_version(self.app_dir), "1.0.0")

    def test_load_config_resolves_manifest_feed_for_selected_channel(self):
        (self.app_dir / "update_config.json").write_text(
            json.dumps(
                {
                    "channel": "bootstrap",
                    "manifest_url": "https://updates.example.test/stable.json",
                    "manifest_feeds": {
                        "stable": "https://updates.example.test/stable.json",
                        "bootstrap": "https://updates.example.test/bootstrap.json",
                    },
                }
            ),
            encoding="utf-8",
        )

        config = updater.load_config(self.app_dir)

        self.assertEqual(config["channel"], "bootstrap")
        self.assertEqual(
            config["manifest_url"],
            "https://updates.example.test/bootstrap.json",
        )

    def test_load_config_keeps_legacy_manifest_url_when_no_feeds_are_configured(self):
        (self.app_dir / "update_config.json").write_text(
            json.dumps(
                {
                    "channel": "stable",
                    "manifest_url": "https://updates.example.test/legacy.json",
                }
            ),
            encoding="utf-8",
        )

        config = updater.load_config(self.app_dir)

        self.assertEqual(config["manifest_url"], "https://updates.example.test/legacy.json")

    def test_load_config_rejects_unknown_channel_feed_before_network(self):
        (self.app_dir / "update_config.json").write_text(
            json.dumps(
                {
                    "channel": "canary",
                    "manifest_feeds": {
                        "stable": "https://updates.example.test/stable.json",
                    },
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(updater.UpdateError, "canal de actualizaciones"):
            updater.load_config(self.app_dir)

    def test_rollback_restores_files_after_copy_failure(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(self._package())
        original_copy = updater._atomic_copy

        def failing_copy(source, destination):
            if destination.name == "launcher.py":
                raise OSError("simulated disk failure")
            original_copy(source, destination)

        with mock.patch.object(updater, "_atomic_copy", side_effect=failing_copy):
            with self.assertRaises(updater.UpdateError):
                updater.apply_package(
                    self.app_dir,
                    package_path,
                    self._application_manifest(),
                )

        self.assertEqual((self.app_dir / "database.py").read_text(), "old code")
        self.assertEqual(updater.read_local_version(self.app_dir), "1.0.0")

    def test_existing_recovery_marker_blocks_update_before_network(self):
        (self.app_dir / ".update_status.json").write_text(
            json.dumps(
                {
                    "error": "RECOVERY_REQUIRED: reparar primero",
                    "recovery_required": True,
                    "backup_dir": "backup-test",
                }
            ),
            encoding="utf-8",
        )
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            raise AssertionError("network must not be used")

        with self.assertRaisesRegex(updater.RecoveryRequiredError, "reparar primero"):
            updater.check_and_apply(self.app_dir, opener=opener)

        self.assertEqual(calls, [])

    def test_incomplete_update_journal_blocks_update_before_network(self):
        (self.app_dir / ".update_journal.json").write_text(
            json.dumps(
                {
                    "phase": "applying",
                    "local_version": "1.0.0",
                    "remote_version": "1.0.1",
                    "backup_dir": str(self.app_dir / ".update_recovery" / "from-1.0.0-test"),
                }
            ),
            encoding="utf-8",
        )
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            raise AssertionError("network must not be used")

        with self.assertRaisesRegex(updater.RecoveryRequiredError, "interrumpida"):
            updater.check_and_apply(self.app_dir, opener=opener)

        self.assertEqual(calls, [])

    def test_apply_package_removes_update_journal_after_success(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(self._package())

        updater.apply_package(
            self.app_dir,
            package_path,
            self._application_manifest(),
        )

        self.assertFalse((self.app_dir / ".update_journal.json").exists())

    def test_rollback_failure_reports_recovery_required(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(self._package())
        original_copy = updater._atomic_copy
        apply_failed = False

        def failing_copy(source, destination):
            nonlocal apply_failed
            if destination.name == "launcher.py" and not apply_failed:
                apply_failed = True
                raise OSError("simulated disk failure")
            if destination.name == "database.py" and apply_failed:
                raise OSError("simulated disk failure")
            original_copy(source, destination)

        with mock.patch.object(updater, "_atomic_copy", side_effect=failing_copy):
            with self.assertRaisesRegex(updater.RecoveryRequiredError, "RECOVERY_REQUIRED"):
                updater.apply_package(
                    self.app_dir,
                    package_path,
                    self._application_manifest(),
                )

        self.assertEqual(updater.read_local_version(self.app_dir), "1.0.0")
        recovery_backups = list((self.app_dir / ".update_recovery").rglob("database.py"))
        self.assertEqual(len(recovery_backups), 1)
        self.assertEqual(recovery_backups[0].read_text(), "old code")

    def test_zip_path_traversal_is_rejected(self):
        package_path = self.app_dir / "unsafe.zip"
        files = self._application_files()
        files["../organizador.db"] = "should not be written"
        package_path.write_bytes(_zip_bytes(files))

        with self.assertRaises(updater.UpdateError):
            updater.apply_package(
                self.app_dir,
                package_path,
                self._application_manifest(),
            )
        self.assertEqual((self.app_dir / "organizador.db").read_bytes(), b"user database")

    def test_check_and_apply_downloads_and_verifies_release(self):
        package = self._package()
        manifest = json.dumps(
            self._application_manifest(
                url="https://updates.example.test/package.zip",
                sha256=hashlib.sha256(package).hexdigest(),
            )
        ).encode("utf-8")
        (self.app_dir / "update_config.json").write_text(
            json.dumps({"manifest_url": "https://updates.example.test/manifest.json"}), encoding="utf-8"
        )
        responses = {
            "https://updates.example.test/manifest.json": manifest,
            "https://updates.example.test/package.zip": package,
        }

        def opener(request, timeout):
            return _Response(responses[request.full_url])

        self.assertTrue(updater.check_and_apply(self.app_dir, opener=opener))
        self.assertEqual(updater.read_local_version(self.app_dir), "1.0.1")
        self.assertEqual((self.app_dir / "database.py").read_text(), "new code")
        self.assertEqual((self.app_dir / "organizador.db").read_bytes(), b"user database")

    def test_check_and_apply_propagates_recovery_required(self):
        package = self._package()
        manifest = json.dumps(
            self._application_manifest(
                url="https://updates.example.test/package.zip",
                sha256=hashlib.sha256(package).hexdigest(),
            )
        ).encode("utf-8")
        (self.app_dir / "update_config.json").write_text(
            json.dumps({"manifest_url": "https://updates.example.test/manifest.json"}),
            encoding="utf-8",
        )
        responses = {
            "https://updates.example.test/manifest.json": manifest,
            "https://updates.example.test/package.zip": package,
        }

        def opener(request, timeout):
            return _Response(responses[request.full_url])

        messages = []
        with mock.patch.object(
            updater,
            "apply_package",
            side_effect=updater.RecoveryRequiredError("RECOVERY_REQUIRED: prueba"),
        ):
            with self.assertRaises(updater.RecoveryRequiredError):
                updater.check_and_apply(
                    self.app_dir,
                    opener=opener,
                    status_callback=messages.append,
                )

        self.assertTrue(any("RECOVERY_REQUIRED" in message for message in messages))

    def test_check_and_apply_uses_github_api_for_private_release(self):
        package = self._package()
        asset_url = "https://api.github.com/repos/acme/metodo/releases/assets/42"
        manifest = json.dumps(
            self._application_manifest(
                url="https://github.com/acme/metodo/releases/download/v1.0.1/MetodoIG-v1.0.1.zip",
                github_repository="acme/metodo",
                github_release_tag="v1.0.1",
                asset_name="MetodoIG-v1.0.1.zip",
                sha256=hashlib.sha256(package).hexdigest(),
            )
        ).encode("utf-8")
        (self.app_dir / "update_config.json").write_text(
            json.dumps(
                {
                    "manifest_url": "https://updates.example.test/manifest.json",
                    "access_token": "test-token",
                }
            ),
            encoding="utf-8",
        )
        responses = {
            "https://updates.example.test/manifest.json": manifest,
            "https://api.github.com/repos/acme/metodo/releases/tags/v1.0.1": json.dumps(
                {"assets": [{"name": "MetodoIG-v1.0.1.zip", "url": asset_url}]}
            ).encode("utf-8"),
            asset_url: package,
        }
        requests = []

        def opener(request, timeout):
            requests.append(request)
            return _Response(responses[request.full_url])

        self.assertTrue(updater.check_and_apply(self.app_dir, opener=opener))
        self.assertEqual(updater.read_local_version(self.app_dir), "1.0.1")
        asset_request = next(request for request in requests if request.full_url == asset_url)
        self.assertEqual(asset_request.get_header("Accept"), "application/octet-stream")
        self.assertEqual(asset_request.get_header("Authorization"), "Bearer test-token")


if __name__ == "__main__":
    unittest.main()
