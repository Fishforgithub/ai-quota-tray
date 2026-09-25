"""系統匣圖示：摘要邏輯與繪製（需要 Pillow）。"""
import io
import unittest
from datetime import datetime, timezone

from PIL import Image

from ai_quota_tray import icon
from ai_quota_tray.model import AUTH_EXPIRED, DISABLED, OK, ProviderState, make_window

NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)


def state(name, *used, status=OK, durations=(18000, 604800)):
    wins = [make_window(u, None, d) for u, d in zip(used, durations)]
    return ProviderState(name, wins, NOW, status)


class SummarizeTest(unittest.TestCase):
    def test_lowest_remaining_across_providers_wins(self):
        spec = icon.summarize([state("claude", 10, 7), state("codex", 0, 5), state("grok", 92, durations=(604800,))])
        self.assertEqual((spec.text, spec.level, spec.source), ("8", "red", "grok 週"))

    def test_thresholds(self):
        self.assertEqual(icon.summarize([state("a", 70.5)]).level, "yellow")  # 剩 29.5
        self.assertEqual(icon.summarize([state("a", 70)]).level, "green")     # 剩 30
        self.assertEqual(icon.summarize([state("a", 90.4)]).text, "9")        # 剩 9.6 → 捨去

    def test_no_data(self):
        self.assertEqual(icon.summarize([]).text, "–")
        spec = icon.summarize([state("grok", status=AUTH_EXPIRED), state("x", status=DISABLED)])
        self.assertEqual((spec.text, spec.level), ("!", "grey"))

    def test_tooltip_fits_szTip(self):
        text = icon.tooltip([state("claude", 10, 7), state("grok", status=AUTH_EXPIRED)])
        self.assertIn("claude 5h 90% 週 93%", text)
        self.assertIn("grok auth_expired", text)
        self.assertLessEqual(len(text), 127)


class RenderTest(unittest.TestCase):
    def test_png_at_requested_size(self):
        for size in (16, 24, 32):
            for text in ("8", "95", "100", "!"):
                png = icon.render(icon.IconSpec(text, "green", None, None), size)
                img = Image.open(io.BytesIO(png))
                self.assertEqual(img.size, (size, size))
                self.assertEqual(img.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
