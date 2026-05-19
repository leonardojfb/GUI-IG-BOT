import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MessageFormatTest(unittest.TestCase):
    def test_meta_message_contains_two_timezones(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("8:00 AM", "America/Argentina/Buenos_Aires")
        tag = "PROMO"
        dia_str = "2026-05-19"
        meta = (
            f"{tag}\n"
            f"Día: {dia_str}\n"
            f"⏰ {et_label}\n"
            f"   → {local_label}\n"
            f"Formato: Reel"
        )
        self.assertIn("PROMO", meta)
        self.assertIn("ET", meta)
        self.assertIn("Nueva York", meta)
        self.assertIn("ART", meta)
        self.assertIn("Buenos Aires", meta)
        self.assertIn("→", meta)
        self.assertEqual(meta.count("\n"), 4)  # 5 líneas → 4 saltos


if __name__ == "__main__":
    unittest.main()
