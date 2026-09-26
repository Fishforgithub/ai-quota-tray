"""v0.1.1：系統匣圖示的霓虹外圈動畫、Store 版「發現新版本」、設定視窗的版號／連結。"""
import os
import sys
import tomllib
import types
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import __version__, display_version, i18n, icon_anim, store_update  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 單獨跑這個檔也找得到 test_launch
from test_launch import TrayAppTestBase  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class VersionTest(unittest.TestCase):
    def test_package_version_matches_pyproject(self):
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(__version__, pyproject["project"]["version"])
        self.assertEqual(display_version(), f"{__version__}.0")  # 與 MSIX／exe 版本資訊同樣四段


class FramesTest(unittest.TestCase):
    def test_only_the_ring_moves(self):
        frames = icon_anim.frame_images(64, count=4)
        self.assertEqual(len(frames), 4)
        self.assertTrue(all(f.size == (64, 64) and f.mode == "RGBA" for f in frames))
        k = 64 / icon_anim.SOURCE_SIZE
        cx, cy = round(icon_anim.RING_CENTER[0] * k), round(icon_anim.RING_CENTER[1] * k)
        ring_y = round(icon_anim.RING_CENTER[1] * k - 178 * k)  # 霓虹圈正上方
        # 中間（「Ai」那一塊）轉了半圈還是一樣；外圈的顏色換了
        self.assertEqual(frames[0].getpixel((cx, cy)), frames[2].getpixel((cx, cy)))
        self.assertNotEqual(frames[0].getpixel((cx, ring_y)), frames[2].getpixel((cx, ring_y)))
        # 四個角（圓角方形外的透明處）不能被轉進來
        self.assertEqual(frames[0].getpixel((0, 0)), frames[2].getpixel((0, 0)))

    def test_png_bytes_and_speed(self):
        pngs = icon_anim.frame_pngs(20)
        self.assertEqual(len(pngs), icon_anim.FRAMES)
        self.assertTrue(all(p.startswith(b"\x89PNG") for p in pngs))
        self.assertEqual(icon_anim.frame_interval_ms(), 100)  # 60 張、6 秒一圈


class AnimationTest(TrayAppTestBase):
    def setUp(self):
        for name, value in (("animations_enabled", True), ("battery_saver_on", False)):
            p = mock.patch.object(self.app_mod_win32(), name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        super().setUp()

    @staticmethod
    def app_mod_win32():
        from ai_quota_tray import app
        return app.win32tray

    def test_runs_by_default_and_frames_were_prepared(self):
        self.assertTrue(self.tray_app._anim_timer.isActive())
        self.tray_app.tray.set_frames.assert_called_once()
        self.tray_app._next_frame()
        self.tray_app.tray.show_frame.assert_called_with(1)

    def test_lock_and_display_off_pause_it(self):
        for off, on in (("lock", "unlock"), ("display_off", "display_on")):
            self.tray_app._on_tray_event(off, 0, 0)
            self.assertFalse(self.tray_app._anim_timer.isActive(), off)
            self.tray_app.tray.show_static.assert_called()  # 停下來回到靜態品牌圖示
            self.tray_app._on_tray_event(on, 0, 0)
            self.assertTrue(self.tray_app._anim_timer.isActive(), on)

    def test_respects_windows_animation_setting_and_battery_saver(self):
        win32 = self.app_mod_win32()
        with mock.patch.object(win32, "animations_enabled", return_value=False):
            self.tray_app._update_animation()
            self.assertFalse(self.tray_app._anim_timer.isActive())
        self.tray_app._update_animation()
        self.assertTrue(self.tray_app._anim_timer.isActive())
        with mock.patch.object(win32, "battery_saver_on", return_value=True):
            self.tray_app._update_animation()
            self.assertFalse(self.tray_app._anim_timer.isActive())

class StoreUpdateCheckTest(unittest.TestCase):
    def fake_winrt(self, size=None, error=None):
        class Updates:
            pass

        async def query():
            if error:
                raise error
            updates = Updates()
            updates.size = size
            return updates

        context = mock.Mock()
        context.get_app_and_optional_store_package_updates_async = lambda: query()
        module = types.ModuleType("winrt.windows.services.store")
        module.StoreContext = mock.Mock(get_default=lambda: context)
        return mock.patch.dict(sys.modules, {"winrt.windows.services.store": module})

    def test_personal_build_does_not_ask(self):
        with mock.patch.object(store_update.startup, "is_packaged", return_value=False):
            self.assertIsNone(store_update.check())

    def test_packaged_results(self):
        with mock.patch.object(store_update.startup, "is_packaged", return_value=True):
            with self.fake_winrt(size=1):
                self.assertTrue(store_update.check())
            with self.fake_winrt(size=0):
                self.assertFalse(store_update.check())
            with self.fake_winrt(error=OSError("no store")):
                self.assertIsNone(store_update.check())  # 查不到就當不知道

    def test_store_link_points_to_our_product(self):
        self.assertEqual(store_update.STORE_PDP_URI, "ms-windows-store://pdp/?productid=9PLDWKRFDGDC")


class UpdateNoticeTest(TrayAppTestBase):
    def test_notifies_once_and_click_opens_settings(self):
        with mock.patch.object(self.tray_app, "open_settings") as open_settings:
            self.tray_app._on_update_checked(True)
            self.tray_app._on_update_checked(True)
            self.assertTrue(self.tray_app.update_available)
            self.tray_app.tray.show_balloon.assert_called_once_with(
                i18n.tr("update.title"), i18n.tr("update.body"), respect_quiet_time=True)
            self.tray_app._on_tray_event("balloon_click", 0, 0)
            open_settings.assert_called_once_with()

    def test_unknown_result_changes_nothing(self):
        self.tray_app._on_update_checked(None)
        self.assertFalse(self.tray_app.update_available)
        self.tray_app.tray.show_balloon.assert_not_called()

    def test_alert_click_still_opens_card(self):
        self.tray_app._notify("alert", "t", "b")
        with mock.patch.object(self.tray_app, "show_card") as show_card, \
                mock.patch.object(self.tray_app, "open_settings") as open_settings:
            self.tray_app._on_tray_event("balloon_click", 1, 2)
        show_card.assert_called_once_with(1, 2, hold=True)
        open_settings.assert_not_called()


class SettingsAdditionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def make(self, language="zh-TW", **kwargs):
        from ai_quota_tray.settings import SettingsDialog
        applied = []
        dlg = SettingsDialog({"claude"}, language, lambda *a: applied.append(a), **kwargs)
        self.addCleanup(dlg.deleteLater)
        return dlg, applied

    def test_update_button_only_when_available(self):
        dlg, _ = self.make()
        self.assertFalse(dlg.update_button.isVisibleTo(dlg))
        dlg.set_update_available(True)
        self.assertTrue(dlg.update_button.isVisibleTo(dlg))
        dlg2, _ = self.make(update_available=True)
        self.assertTrue(dlg2.update_button.isVisibleTo(dlg2))
        self.assertEqual(dlg2.update_button.text(), "版本可更新")

    def test_links_follow_preview_language(self):
        dlg, _ = self.make()
        self.assertIn('href="https://fish-zero.com/aiusagemeter-privacy"', dlg.links.text())
        self.assertIn('href="https://fish-zero.com/aiusagemeter"', dlg.links.text())
        dlg.language.setCurrentIndex(i18n.LANGUAGES.index("en"))
        self.assertIn('href="https://fish-zero.com/en/aiusagemeter-privacy"', dlg.links.text())
        self.assertIn("Privacy policy", dlg.links.text())

    def test_disclaimer_and_no_animation_toggle(self):
        from PySide6.QtWidgets import QCheckBox, QLabel
        dlg, applied = self.make()
        texts = [w.text() for w in dlg.findChildren(QLabel)]
        self.assertIn("非 Anthropic、OpenAI、GitHub、Google 官方產品", texts)
        # 業主 2026-09-26 定：動畫一律開著，設定裡不放開關（只有服務勾選與示範模式）
        self.assertEqual({c.objectName() for c in dlg.findChildren(QCheckBox)},
                         {"claude_enabled", "codex_enabled", "antigravity_enabled", "copilot_enabled", "demoCheck"})
        dlg.demo_check.setChecked(True)
        dlg.accept()
        self.assertEqual(applied, [({"claude"}, "zh-TW", True)])

if __name__ == "__main__":
    unittest.main()
