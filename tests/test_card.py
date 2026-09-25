"""P3：卡片定位、倒數格式、卡片內容（Qt 用 offscreen 平台，不會真的開視窗）。"""
import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from ai_quota_tray import placement  # noqa: E402
from ai_quota_tray.card import Card, header_note, status_message, window_countdown  # noqa: E402
from ai_quota_tray.model import (AUTH_EXPIRED, DISABLED, ERROR, OK, STALE,  # noqa: E402
                                 ProviderState, format_age, format_countdown, make_window)

NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)


class FormatTest(unittest.TestCase):
    def test_countdown(self):
        self.assertEqual(format_countdown(NOW + timedelta(hours=2, minutes=59, seconds=59), NOW), "02:59")
        self.assertEqual(format_countdown(NOW + timedelta(hours=23, minutes=59), NOW), "23:59")
        self.assertEqual(format_countdown(NOW + timedelta(days=3, hours=4, minutes=30), NOW), "3d04h")
        self.assertEqual(format_countdown(NOW + timedelta(hours=24), NOW), "1d00h")
        self.assertEqual(format_countdown(NOW - timedelta(minutes=1), NOW), "00:00")
        self.assertEqual(format_countdown(None, NOW), "—")

    def test_age(self):
        self.assertEqual(format_age(NOW - timedelta(seconds=30), NOW), "剛剛")
        self.assertEqual(format_age(NOW - timedelta(minutes=12), NOW), "12 分鐘前")
        self.assertEqual(format_age(NOW - timedelta(hours=5), NOW), "5 小時前")
        self.assertEqual(format_age(NOW - timedelta(days=4, hours=1), NOW), "4 天前")
        self.assertEqual(format_age(None, NOW), "時間不明")


# 1920x1200、125%、工作列在底部 48 邏輯像素（實測機器的形狀）
MAIN = placement.Screen((0, 0, 1536, 960), (0, 0, 1536, 912), 1.25)
# 右邊一台 100% 的 1920x1080，工作列在頂端
SECOND = placement.Screen((1920, 0, 3840, 1080), (1920, 40, 3840, 1080), 1.0)


class PlacementTest(unittest.TestCase):
    def test_physical_to_logical_per_screen(self):
        rect, screen = placement.physical_to_logical((1550, 1140, 1590, 1200), [MAIN, SECOND])
        self.assertIs(screen, MAIN)
        self.assertEqual(rect, (1240, 912, 1272, 960))
        rect, screen = placement.physical_to_logical((2000, 0, 2040, 40), [MAIN, SECOND])
        self.assertIs(screen, SECOND)
        self.assertEqual(rect, (2000, 0, 2040, 40))

    def test_taskbar_bottom_places_above_and_clamps_right_edge(self):
        x, y = placement.place((1500, 912, 1532, 960), (300, 200), MAIN.available)
        self.assertEqual(y, 912 - 200 - placement.GAP)
        self.assertEqual(x, 1536 - 300 - placement.GAP)  # 靠右邊界夾回來

    def test_taskbar_top_places_below(self):
        x, y = placement.place((2000, 0, 2040, 40), (300, 200), SECOND.available)
        self.assertEqual((x, y), (1920 + placement.GAP, 40 + placement.GAP))

    def test_taskbar_left_and_right(self):
        avail = (48, 0, 1536, 960)
        x, y = placement.place((0, 800, 48, 840), (300, 200), avail)
        self.assertEqual((x, y), (48 + placement.GAP, 720))
        avail = (0, 0, 1488, 960)
        x, _ = placement.place((1488, 800, 1536, 840), (300, 200), avail)
        self.assertEqual(x, 1488 - 300 - placement.GAP)

    def test_inside_overflow_flyout_goes_above_or_below(self):
        x, y = placement.place((1300, 700, 1332, 732), (300, 200), MAIN.available)
        self.assertEqual(y, 700 - 200 - placement.GAP)
        _, y = placement.place((1300, 50, 1332, 82), (300, 200), MAIN.available)
        self.assertEqual(y, 82 + placement.GAP)


def st(name, status=OK, windows=(), **kw):
    return ProviderState(name, list(windows), kw.pop("fetched_at", NOW), status, kw.pop("detail", {}),
                         error=kw.pop("error", None))


class CardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_helpers(self):
        rolled = st("codex", STALE, [make_window(0, None, 18000)], detail={"rolled_over": ["5h"]},
                    fetched_at=NOW - timedelta(minutes=20))
        self.assertEqual(window_countdown(rolled.windows[0], rolled, NOW), "已重置")
        self.assertEqual(header_note(rolled, NOW), ("20 分鐘前", False))
        self.assertEqual(header_note(st("grok", detail={"subscription_tier": "GrokPro"}), NOW),
                         ("GrokPro", False))
        self.assertTrue(header_note(st("codex", detail={"api_error": "HTTP 500"}), NOW)[1])
        self.assertIn("Grok CLI", status_message(st("grok", AUTH_EXPIRED)))
        self.assertEqual(status_message(st("grok", DISABLED)), "未啟用")
        self.assertTrue(status_message(st("grok", ERROR, error="x" * 200)).endswith("…"))

    def test_builds_every_state_and_rebuilds(self):
        card = Card()
        now = datetime.now(timezone.utc)  # 卡片內部用真實時間算「n 小時前」
        states = [
            ("claude", st("claude", windows=[make_window(10, now + timedelta(hours=3), 18000),
                                             make_window(7, now + timedelta(days=5), 604800)])),
            ("codex", st("codex", STALE, [make_window(0, None, 18000)],
                         detail={"rolled_over": ["5h"]}, fetched_at=now - timedelta(hours=2))),
            ("grok", st("grok", windows=[make_window(92, now + timedelta(days=1), 604800)],
                        detail={"products": [{"product": "GrokBuild", "usage_pct": 92.0}]})),
        ]
        card.set_states(states)
        texts = [lbl.text() for lbl in card.findChildren(QLabel)]
        self.assertIn("8%", texts)
        self.assertIn("↻ 已重置", texts)
        self.assertIn("2 小時前", texts)
        card.set_states([("claude", None), ("grok", st("grok", AUTH_EXPIRED))])
        card.adjustSize()
        texts = [lbl.text() for lbl in card.findChildren(QLabel)]
        self.assertIn("讀取中…", texts)
        self.assertNotIn("8%", texts)
        card.deleteLater()


if __name__ == "__main__":
    unittest.main()
