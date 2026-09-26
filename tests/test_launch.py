"""App 沒有主視窗：第一次啟動的歡迎通知、再啟動一次就打開卡片、非 hover 打開的卡片先停留。

2026-09-26 為了 Store 審核加的：從開始功能表啟動後畫面上什麼都沒出現，已在執行時再點一次也什麼都沒發生，
審核人員會以為 App 沒啟動。
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import config, i18n, win32tray  # noqa: E402

FAR_AWAY = (5000, 5000)


class TrayAppTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def setUp(self):
        from ai_quota_tray import app
        self.app_mod = app
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patches = [
            mock.patch.object(app.win32tray, "TrayIcon"),
            mock.patch.object(app.win32tray, "small_icon_size", return_value=16),
            mock.patch.object(app.win32tray, "large_icon_size", return_value=32),
            mock.patch.object(app.Poller, "refresh"),
            mock.patch.object(app, "AlertStore"),
            mock.patch.object(app.config, "config_path", return_value=Path(tmp.name) / "config.json"),
            mock.patch.object(app.copilot_provider, "start_prepare"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.tray_app = app.TrayApp({"claude"}, "zh-TW")
        self.tray_app.tray.icon_rect.return_value = (100, 100, 120, 120)
        self.addCleanup(self.tray_app.shutdown)

    def check_hover_at(self, pos, now):
        """在 monotonic＝now、滑鼠在 pos 時跑一次 _check_hover。卡片固定在 (200,200)-(400,400)。"""
        with mock.patch.object(self.app_mod.win32tray, "cursor_pos", return_value=pos), \
                mock.patch.object(self.app_mod.win32tray, "window_rect", return_value=(200, 200, 400, 400)), \
                mock.patch.object(self.app_mod.time, "monotonic", return_value=now):
            self.tray_app._check_hover()


class HoldOpenTest(TrayAppTestBase):
    def open_via(self, kind, now=1000.0):
        with mock.patch.object(self.app_mod.time, "monotonic", return_value=now):
            self.tray_app._on_tray_event(kind, 0, 0)
        self.assertTrue(self.tray_app.card.isVisible())

    def test_activate_keeps_card_open_while_mouse_is_elsewhere(self):
        self.open_via("activate")
        hold = self.app_mod.HOLD_OPEN_S
        self.check_hover_at(FAR_AWAY, 1001.0)
        self.check_hover_at(FAR_AWAY, 1000.0 + hold - 0.1)
        self.assertTrue(self.tray_app.card.isVisible(), "停留時間內不能關")
        # 停留時間過了才開始算一般的 0.4 秒
        self.check_hover_at(FAR_AWAY, 1000.0 + hold + 0.1)
        self.check_hover_at(FAR_AWAY, 1000.0 + hold + 0.6)
        self.assertFalse(self.tray_app.card.isVisible())

    def test_balloon_click_also_holds(self):
        self.open_via("balloon_click")
        self.check_hover_at(FAR_AWAY, 1001.0)
        self.check_hover_at(FAR_AWAY, 1002.0)
        self.assertTrue(self.tray_app.card.isVisible())

    def test_mouse_visiting_the_card_ends_the_hold(self):
        self.open_via("activate")
        self.check_hover_at((300, 300), 1001.0)  # 移進卡片
        self.check_hover_at(FAR_AWAY, 1001.5)
        self.check_hover_at(FAR_AWAY, 1002.0)
        self.assertFalse(self.tray_app.card.isVisible(), "滑鼠來過之後照一般規則 0.4 秒就關")

    def test_hover_open_does_not_hold(self):
        self.open_via("popup_open")
        self.check_hover_at(FAR_AWAY, 1001.0)
        self.check_hover_at(FAR_AWAY, 1001.5)
        self.assertFalse(self.tray_app.card.isVisible())


class WelcomeTest(TrayAppTestBase):
    def test_welcome_ignores_quiet_time(self):
        self.tray_app.show_welcome()
        self.tray_app.tray.show_balloon.assert_called_once_with(
            i18n.tr("welcome.title"), i18n.tr("welcome.body"), respect_quiet_time=False)

    def test_welcome_text_fits_notification_limits(self):
        for lang in (i18n.ZH, i18n.EN):
            self.assertLessEqual(len(i18n.tr("welcome.title", lang)), 63)  # szInfoTitle
            self.assertLessEqual(len(i18n.tr("welcome.body", lang)), 255)  # szInfo

    def test_welcomed_flag_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            self.assertFalse(config.load_welcomed(path))
            config.save(path, language="en")
            self.assertFalse(config.load_welcomed(path))
            config.save(path, welcomed=True)
            self.assertTrue(config.load_welcomed(path))
            self.assertEqual(config.load_language(path), "en")  # 其他欄位保留


class SecondLaunchTest(unittest.TestCase):
    def test_second_launch_asks_running_instance_to_open_card(self):
        from ai_quota_tray import app
        with mock.patch.object(app.win32tray, "acquire_single_instance", return_value=None), \
                mock.patch.object(app.win32tray, "activate_running_instance", return_value=True) as act:
            self.assertEqual(app.run(), 0)
        act.assert_called_once_with()

    def test_second_launch_when_first_is_not_ready(self):
        from ai_quota_tray import app
        with mock.patch.object(app.win32tray, "acquire_single_instance", return_value=None), \
                mock.patch.object(app.win32tray, "activate_running_instance", return_value=False):
            self.assertEqual(app.run(), 1)


class ActivateMessageTest(unittest.TestCase):
    """真的建一個隱藏視窗、真的 PostMessage，確認 wndproc 收到後回報 activate。"""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def test_post_and_receive(self):
        # 換一個測試專用的類別名稱：本機若正在跑真的 AI Usage Meter，不能把訊息送到它那裡
        with mock.patch.object(win32tray.TrayIcon, "CLASS_NAME", "AiQuotaTrayWindow-unittest"):
            self.assertFalse(win32tray.activate_running_instance())  # 還沒有視窗
            events = []
            # 註冊螢幕狀態通知時 Windows 會立刻送一次目前狀態（display_on），這裡只看 activate
            tray = win32tray.TrayIcon(lambda kind, x, y: kind == "activate" and events.append(kind))
            try:
                self.assertTrue(win32tray.activate_running_instance())
                for _ in range(20):
                    self.qapp.processEvents()  # Qt 的迴圈也會分派到我們的 Win32 視窗
                    if events:
                        break
            finally:
                tray.close()
        self.assertEqual(events, ["activate"])


if __name__ == "__main__":
    unittest.main()
