# tests/test_tanda_sync.py
"""Sincronización del desplegable de logística con las carpetas de videos_finales.

Cubre el bug de tandas con nombre repetido / carpeta renombrada:
la lista de logística salía solo de la DB (batch_tandas) y nunca reflejaba
lo que había en disco. Ahora escanea videos_finales/, registra carpetas
nuevas y oculta tandas Forge huérfanas (carpeta borrada/renombrada).
"""
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TandaSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp_db_fd, self.tmp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_db_fd)
        import database
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_db_path

        self.vf_root = tempfile.mkdtemp(prefix="videos_finales_")

    def tearDown(self):
        import database
        database.DB_PATH = self._original_db_path
        for path in (self.tmp_db_path,):
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except PermissionError:
                    pass
        shutil.rmtree(self.vf_root, ignore_errors=True)

    def _make_folder(self, name, n_videos=1):
        folder = os.path.join(self.vf_root, name)
        os.makedirs(folder, exist_ok=True)
        for i in range(n_videos):
            open(os.path.join(folder, f"vid_{i:02d}.mp4"), "w").close()
        return folder

    def _db(self):
        from database import DatabaseManager
        return DatabaseManager()

    def test_folder_with_videos_gets_registered_and_listed(self):
        self._make_folder("NUMEROS L", n_videos=3)
        db = self._db()
        try:
            names = db.list_and_sync_tandas(self.vf_root)
            self.assertIn("NUMEROS L", names)
            # Quedó persistido en la DB
            self.assertIsNotNone(db.get_tanda_by_name("NUMEROS L"))
        finally:
            db.close()

    def test_empty_folder_is_ignored(self):
        self._make_folder("VACIA", n_videos=0)
        db = self._db()
        try:
            names = db.list_and_sync_tandas(self.vf_root)
            self.assertNotIn("VACIA", names)
            self.assertIsNone(db.get_tanda_by_name("VACIA"))
        finally:
            db.close()

    def test_orphan_forge_tanda_is_hidden(self):
        # Tanda Forge en DB (p1==p2==nombre) pero SIN carpeta en disco.
        db = self._db()
        try:
            db.add_tanda("NUMEROS", "NUMEROS", "NUMEROS", "")
            names = db.list_and_sync_tandas(self.vf_root)
            self.assertNotIn("NUMEROS", names)
            # No se borra de la DB, solo se oculta del desplegable
            self.assertIsNotNone(db.get_tanda_by_name("NUMEROS"))
        finally:
            db.close()

    def test_legacy_p1p2_tanda_always_shown(self):
        # Tanda legacy: p1 != p2, videos viven en carpetas de origen, no en videos_finales.
        db = self._db()
        try:
            db.add_tanda("LEGACY", "CategoriaA", "CategoriaB", "caps.txt")
            names = db.list_and_sync_tandas(self.vf_root)
            self.assertIn("LEGACY", names)
        finally:
            db.close()

    def test_rename_scenario_ghost_hidden_new_shown(self):
        # Reproduce el bug del usuario: DB tiene "NUMEROS", carpeta renombrada a "NUMEROS L".
        self._make_folder("NUMEROS L", n_videos=5)
        db = self._db()
        try:
            db.add_tanda("NUMEROS", "NUMEROS", "NUMEROS", "")
            names = db.list_and_sync_tandas(self.vf_root)
            self.assertIn("NUMEROS L", names)
            self.assertNotIn("NUMEROS", names)
        finally:
            db.close()

    def test_idempotent_does_not_duplicate_or_overwrite(self):
        self._make_folder("TANDA X", n_videos=2)
        db = self._db()
        try:
            db.list_and_sync_tandas(self.vf_root)
            db.list_and_sync_tandas(self.vf_root)
            rows = [t for t in db.get_all_tandas() if t["tanda_name"] == "TANDA X"]
            self.assertEqual(len(rows), 1)
        finally:
            db.close()

    def test_no_videos_finales_dir_does_not_crash(self):
        db = self._db()
        try:
            names = db.list_and_sync_tandas(os.path.join(self.vf_root, "no_existe"))
            self.assertEqual(names, [])
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
