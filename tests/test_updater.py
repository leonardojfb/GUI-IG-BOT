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

    def _package(self, version="1.0.1"):
        return _zip_bytes(
            {
                "version.json": json.dumps({"version": version}),
                "database.py": "new code",
                "launcher.py": "new launcher",
            }
        )

    def test_apply_package_preserves_user_data(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(self._package())
        version = updater.apply_package(
            self.app_dir,
            package_path,
            {
                "version": "1.0.1",
                "files": ["version.json", "database.py", "launcher.py"],
            },
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

    def test_image_logistics_upgrade_preserves_calendar_and_photo_batches(self):
        calendar = self.app_dir / "calendar_manifest.json"
        calendar.write_text('{"version":1,"entries":[{"id":"old"}]}', encoding="utf-8")
        batch = self.app_dir / "imagenes_finales" / "existing_batch"
        batch.mkdir(parents=True)
        (batch / "photo_forge_manifest.json").write_text(
            '{"version":1,"entries":[]}', encoding="utf-8")
        (batch / "final.png").write_bytes(b"user photo")
        before = {path: path.read_bytes() for path in (
            calendar, self.app_dir / "organizador.db", batch / "photo_forge_manifest.json",
            batch / "final.png",
        )}
        package = self.app_dir / "release.zip"
        package.write_bytes(_zip_bytes({
            "version.json": json.dumps({"version": "1.0.50"}),
            "gui_premium_v7.py": "new GUI code",
            "photo_forge.py": "new photo forge code",
            "image_logistics.py": "new image logistics code",
        }))

        updater.apply_package(self.app_dir, package, {
            "version": "1.0.50",
            "files": ["version.json", "gui_premium_v7.py", "photo_forge.py", "image_logistics.py"],
        })

        self.assertTrue((self.app_dir / "image_logistics.py").is_file())
        for path, contents in before.items():
            self.assertEqual(path.read_bytes(), contents)

    def test_apply_package_can_install_airtable_sync_module_without_local_config(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(
            _zip_bytes(
                {
                    "version.json": json.dumps({"version": "1.0.1"}),
                    "airtable_sync.py": "new airtable sync code",
                }
            )
        )

        version = updater.apply_package(
            self.app_dir,
            package_path,
            {"version": "1.0.1", "files": ["version.json", "airtable_sync.py"]},
        )

        self.assertEqual(version, "1.0.1")
        self.assertEqual((self.app_dir / "airtable_sync.py").read_text(), "new airtable sync code")
        self.assertFalse((self.app_dir / "airtable_config.json").exists())

    def test_apply_package_can_install_default_database_template_and_history(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(
            _zip_bytes(
                {
                    "version.json": json.dumps({"version": "1.0.1"}),
                    "database.py": "new code",
                    "organizador.default.db": b"default database template",
                    "dist_accounts_history.json": "release history",
                }
            )
        )

        version = updater.apply_package(
            self.app_dir,
            package_path,
            {
                "version": "1.0.1",
                "files": [
                    "version.json",
                    "database.py",
                    "organizador.default.db",
                    "dist_accounts_history.json",
                ],
            },
        )

        self.assertEqual(version, "1.0.1")
        self.assertEqual((self.app_dir / "database.py").read_text(), "new code")
        self.assertEqual((self.app_dir / "organizador.default.db").read_bytes(), b"default database template")
        self.assertEqual((self.app_dir / "dist_accounts_history.json").read_text(), "release history")
        self.assertEqual((self.app_dir / "organizador.db").read_bytes(), b"user database")

    def test_apply_package_can_install_bundled_ffmpeg_tools(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(
            _zip_bytes(
                {
                    "version.json": json.dumps({"version": "1.0.1"}),
                    "tools/ffmpeg/bin/ffmpeg.exe": b"ffmpeg binary",
                    "tools/ffmpeg/bin/ffprobe.exe": b"ffprobe binary",
                }
            )
        )

        version = updater.apply_package(
            self.app_dir,
            package_path,
            {
                "version": "1.0.1",
                "files": [
                    "version.json",
                    "tools/ffmpeg/bin/ffmpeg.exe",
                    "tools/ffmpeg/bin/ffprobe.exe",
                ],
            },
        )

        self.assertEqual(version, "1.0.1")
        self.assertEqual((self.app_dir / "tools/ffmpeg/bin/ffmpeg.exe").read_bytes(), b"ffmpeg binary")
        self.assertEqual((self.app_dir / "tools/ffmpeg/bin/ffprobe.exe").read_bytes(), b"ffprobe binary")

    def test_apply_package_can_replace_database_when_manifest_explicitly_requests_it(self):
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

        version = updater.apply_package(
            self.app_dir,
            package_path,
            {
                "version": "1.0.1",
                "files": ["version.json", "organizador.db", "dist_accounts_history.json"],
            },
        )

        self.assertEqual(version, "1.0.1")
        self.assertEqual((self.app_dir / "organizador.db").read_bytes(), b"release database")
        self.assertEqual((self.app_dir / "dist_accounts_history.json").read_text(), "release history")

    def test_hash_mismatch_does_not_change_installation(self):
        package = self._package()
        manifest = json.dumps(
            {
                "version": "1.0.1",
                "url": "https://updates.example.test/package.zip",
                "sha256": "0" * 64,
            }
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

    def test_rollback_restores_files_after_copy_failure(self):
        package_path = self.app_dir / "release.zip"
        package_path.write_bytes(self._package())
        original_copy = updater._atomic_copy
        calls = 0

        def failing_copy(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            original_copy(source, destination)

        with mock.patch.object(updater, "_atomic_copy", side_effect=failing_copy):
            with self.assertRaises(updater.UpdateError):
                updater.apply_package(
                    self.app_dir,
                    package_path,
                    {"version": "1.0.1", "files": ["version.json", "database.py", "launcher.py"]},
                )

        self.assertEqual((self.app_dir / "database.py").read_text(), "old code")
        self.assertEqual(updater.read_local_version(self.app_dir), "1.0.0")

    def test_zip_path_traversal_is_rejected(self):
        package_path = self.app_dir / "unsafe.zip"
        package_path.write_bytes(
            _zip_bytes(
                {
                    "version.json": json.dumps({"version": "1.0.1"}),
                    "../organizador.db": "should not be written",
                }
            )
        )

        with self.assertRaises(updater.UpdateError):
            updater.apply_package(
                self.app_dir,
                package_path,
                {"version": "1.0.1", "files": ["version.json"]},
            )
        self.assertEqual((self.app_dir / "organizador.db").read_bytes(), b"user database")

    def test_check_and_apply_downloads_and_verifies_release(self):
        package = self._package()
        manifest = json.dumps(
            {
                "version": "1.0.1",
                "url": "https://updates.example.test/package.zip",
                "sha256": hashlib.sha256(package).hexdigest(),
                "files": ["version.json", "database.py", "launcher.py"],
            }
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

    def test_check_and_apply_uses_github_api_for_private_release(self):
        package = self._package()
        asset_url = "https://api.github.com/repos/acme/metodo/releases/assets/42"
        manifest = json.dumps(
            {
                "version": "1.0.1",
                "url": "https://github.com/acme/metodo/releases/download/v1.0.1/MetodoIG-v1.0.1.zip",
                "github_repository": "acme/metodo",
                "github_release_tag": "v1.0.1",
                "asset_name": "MetodoIG-v1.0.1.zip",
                "sha256": hashlib.sha256(package).hexdigest(),
                "files": ["version.json", "database.py", "launcher.py"],
            }
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
