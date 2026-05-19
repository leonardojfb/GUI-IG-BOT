# tests/test_database_schedule.py
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TimezoneColumnTest(unittest.TestCase):
    def setUp(self):
        self.tmp_db_fd, self.tmp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_db_fd)
        import database
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_db_path

    def tearDown(self):
        import database
        database.DB_PATH = self._original_db_path
        if os.path.exists(self.tmp_db_path):
            try:
                os.unlink(self.tmp_db_path)
            except PermissionError:
                pass  # Windows file lock — will be cleaned by temp dir cleanup

    def test_timezone_column_exists_after_init(self):
        from database import DatabaseManager
        db = DatabaseManager()
        try:
            cur = db.conn.cursor()
            cur.execute("PRAGMA table_info(virtual_assistants)")
            cols = [row["name"] for row in cur.fetchall()]
            self.assertIn("timezone", cols)
        finally:
            db.close()

    def test_timezone_default_is_buenos_aires(self):
        from database import DatabaseManager
        db = DatabaseManager()
        try:
            db.add_va("TestVA")
            cur = db.conn.cursor()
            cur.execute("SELECT timezone FROM virtual_assistants WHERE name = ?", ("TestVA",))
            row = cur.fetchone()
            self.assertEqual(row["timezone"], "America/Argentina/Buenos_Aires")
        finally:
            db.close()


class ScheduleConfigTableTest(unittest.TestCase):
    def setUp(self):
        self.tmp_db_fd, self.tmp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_db_fd)
        import database
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_db_path

    def tearDown(self):
        import database
        database.DB_PATH = self._original_db_path
        if os.path.exists(self.tmp_db_path):
            try:
                os.unlink(self.tmp_db_path)
            except PermissionError:
                pass  # Windows file lock — will be cleaned by temp dir cleanup

    def test_schedule_config_table_exists(self):
        from database import DatabaseManager
        db = DatabaseManager()
        cur = db.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedule_config'")
        row = cur.fetchone()
        self.assertIsNotNone(row)
        db.close()

    def test_schedule_config_primary_key_composite(self):
        from database import DatabaseManager
        db = DatabaseManager()
        cur = db.conn.cursor()
        cur.execute("PRAGMA table_info(schedule_config)")
        pk_cols = [row["name"] for row in cur.fetchall() if row["pk"] > 0]
        self.assertEqual(set(pk_cols), {"va_name", "category", "day_of_week"})
        db.close()


if __name__ == "__main__":
    unittest.main()