import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class GetSlotsForSetTest(unittest.TestCase):
    def setUp(self):
        self.tmp_db_fd, self.tmp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_db_fd)
        import database
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_db_path
        from database import DatabaseManager
        self.db = DatabaseManager()

    def tearDown(self):
        self.db.close()
        import database
        database.DB_PATH = self._original_db_path
        if os.path.exists(self.tmp_db_path):
            try:
                os.unlink(self.tmp_db_path)
            except PermissionError:
                pass  # Windows: SQLite may still hold a handle; file will be cleaned up by OS

    def test_falls_back_to_default_schedule_when_no_config(self):
        from organizadortg import get_slots_for_set, DEFAULT_SCHEDULE
        slots = get_slots_for_set("VA1", "promo", 0, self.db)
        self.assertEqual(slots, DEFAULT_SCHEDULE[0])

    def test_returns_custom_slots_when_config_exists(self):
        from organizadortg import get_slots_for_set
        self.db.set_schedule_config("VA1", "promo", 2, ["11:00 AM", "5:00 PM"])
        slots = get_slots_for_set("VA1", "promo", 2, self.db)
        self.assertEqual(slots, ["11:00 AM", "5:00 PM"])

    def test_default_schedule_has_all_seven_days(self):
        from organizadortg import DEFAULT_SCHEDULE
        for d in range(7):
            self.assertIn(d, DEFAULT_SCHEDULE)
            self.assertGreater(len(DEFAULT_SCHEDULE[d]), 0)


if __name__ == "__main__":
    unittest.main()