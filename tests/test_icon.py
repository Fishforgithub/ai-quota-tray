"""圖示：顏色門檻、品牌圖示、tooltip（需要 Pillow）。"""
import io
import unittest
from datetime import datetime, timezone

from PIL import Image

from ai_quota_tray import icon
from ai_quota_tray.model import AUTH_EXPIRED, OK, ProviderState, make_window

NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)


def state(name, *used, status=OK, durations=(18000, 604800)):
    wins = [make_window(u, None, d) for u, d in zip(used, durations)]
    return ProviderState(name, wins, NOW, status)


class LevelTest(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(icon.level_for(9.9), "red")
        self.assertEqual(icon.level_for(10), "yellow")
        self.assertEqual(icon.level_for(29.5), "yellow")
        self.assertEqual(icon.level_for(30), "green")


class BrandTest(unittest.TestCase):
    def test_brand_png_at_requested_size(self):
        for size in (16, 24, 32, 48):
            img = Image.open(io.BytesIO(icon.brand_png(size)))
            self.assertEqual((img.size, img.mode), ((size, size), "RGBA"))
            self.assertLess(img.getpixel((0, 0))[3], 16)  # 四角幾乎透明（只剩一點光暈）

    def test_ico_has_small_sizes(self):
        with Image.open(icon.ASSETS / "app.ico") as ico:
            sizes = ico.info["sizes"]
        for s in (16, 24, 32, 48, 256):
            self.assertIn((s, s), sizes)


class TooltipTest(unittest.TestCase):
    def test_tooltip_fits_szTip(self):
        text = icon.tooltip([state("claude", 10, 7), state("codex", status=AUTH_EXPIRED)])
        self.assertIn("claude 5h 90% 週 93%", text)
        self.assertIn("codex auth_expired", text)
        self.assertLessEqual(len(text), 127)


if __name__ == "__main__":
    unittest.main()
