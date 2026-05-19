import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TimezoneConversionTest(unittest.TestCase):
    def test_et_to_art_basic(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("8:00 AM", "America/Argentina/Buenos_Aires")
        self.assertIn("ET", et_label)
        self.assertIn("Nueva York", et_label)
        self.assertIn("ART", local_label)
        self.assertIn("Buenos Aires", local_label)
        # Diferencia ART vs ET es +1h (con DST puede ser +2h)
        self.assertTrue(
            local_label.startswith("9:00 AM") or local_label.startswith("10:00 AM"),
            f"Expected 9 or 10 AM, got {local_label}",
        )

    def test_et_to_et_same_time(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("8:00 AM", "America/New_York")
        self.assertTrue(local_label.startswith("8:00 AM"))

    def test_pm_time(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("7:00 PM", "America/Argentina/Buenos_Aires")
        self.assertIn("7:00 PM", et_label)

    def test_unknown_timezone_falls_back_to_art(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("8:00 AM", "Invalid/Timezone")
        # Fallback debe devolver al menos algo parseable y no crashear
        self.assertIn("ET", et_label)
        self.assertIn("Buenos Aires", local_label)

    def test_madrid_timezone(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("8:00 AM", "Europe/Madrid")
        self.assertIn("Madrid", local_label)


if __name__ == "__main__":
    unittest.main()
