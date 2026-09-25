"""示範模式，以及設定視窗 Claude 那一列的狀態列擷取按鈕。"""
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import claude_hook, config, demo  # noqa: E402
from ai_quota_tray.card import status_message  # noqa: E402
from ai_quota_tray.icon import level_for  # noqa: E402
from ai_quota_tray.model import ERROR, ProviderState  # noqa: E402
from ai_quota_tray.providers import ALL  # noqa: E402

NOW = datetime(2026, 9, 26, 6, 0, tzinfo=timezone.utc)


class SampleTest(unittest.TestCase):
    def test_covers_every_provider_and_every_colour(self):
        states = demo.sample_states(NOW)
        self.assertEqual([n for n, _ in states], list(ALL))
        levels = {level_for(w.remaining_pct) for _, s in states for w in s.windows}
        self.assertEqual(levels, {"green", "yellow", "red"})  # 審核人員一次看到三種顏色
        self.assertTrue(all(w.resets_at > NOW for _, s in states for w in s.windows))

    def test_demo_flag_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            self.assertFalse(config.load_demo(path))  # 預設關
            config.save(path, demo=True, enabled={"claude"})
            self.assertTrue(config.load_demo(path))
            config.save(path, demo=False)
            self.assertFalse(config.load_demo(path))

    def test_claude_without_cache_points_to_settings(self):
        state = ProviderState("claude", [], None, ERROR, {"needs_hook": True}, error="x")
        self.assertIn("安裝 Claude 狀態列擷取", status_message(state))


class TrayDemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def make(self, demo_mode):
        from ai_quota_tray import app
        self.app_mod = app
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cfg = Path(tmp.name) / "config.json"
        for p in (mock.patch.object(app.win32tray, "TrayIcon"),
                  mock.patch.object(app.win32tray, "small_icon_size", return_value=16),
                  mock.patch.object(app.win32tray, "large_icon_size", return_value=32),
                  mock.patch.object(app.Poller, "refresh"),
                  mock.patch.object(app, "AlertStore"),
                  mock.patch.object(app.config, "config_path", return_value=self.cfg),
                  mock.patch.object(app.copilot_provider, "start_prepare")):
            p.start()
            self.addCleanup(p.stop)
        tray_app = app.TrayApp({"claude", "copilot"}, "zh-TW", demo_mode)
        self.addCleanup(tray_app.shutdown)
        return tray_app

    def test_demo_never_queries_and_shows_all_samples(self):
        tray_app = self.make(True)
        tray_app._refresh_on_view()
        tray_app.refresh_all()
        tray_app._poll_local()
        self.app_mod.Poller.refresh.assert_not_called()
        self.app_mod.copilot_provider.start_prepare.assert_not_called()
        self.assertEqual([n for n, _ in tray_app._card_states()], list(ALL))  # 沒勾的也顯示
        self.assertIn("示範模式", tray_app._banner())

    def test_late_result_in_demo_is_kept_but_not_shown_or_alerted(self):
        tray_app = self.make(True)
        tray_app._on_fetched(ProviderState("claude", [], NOW, "ok"))
        self.assertIn("claude", tray_app.states)
        tray_app.alerts.take_due.assert_not_called()

    def test_leaving_demo_resumes_local_polling_and_saves(self):
        tray_app = self.make(True)
        tray_app.apply_settings({"claude"}, "zh-TW", False)
        self.assertFalse(tray_app.demo)
        self.assertFalse(config.load_demo(self.cfg))
        called = [c.args[0] for c in self.app_mod.Poller.refresh.call_args_list]
        self.assertIn("claude", called)
        self.assertIsNone(tray_app._banner())

    def test_card_shows_banner(self):
        from PySide6.QtWidgets import QLabel
        tray_app = self.make(True)
        tray_app.card.set_states(tray_app._card_states(), tray_app._banner())
        texts = [lbl.text() for lbl in tray_app.card.findChildren(QLabel)]
        self.assertTrue(any("示範模式" in t for t in texts))
        self.assertIn("7%", texts)


class SettingsHookButtonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def make(self, status, demo_mode=False):
        from ai_quota_tray.settings import SettingsDialog
        applied = []
        with mock.patch.object(claude_hook, "status", return_value=status):
            dlg = SettingsDialog({"claude"}, "zh-TW", lambda *a: applied.append(a), demo=demo_mode)
        self.addCleanup(dlg.deleteLater)
        return dlg, applied

    def test_button_follows_hook_status(self):
        cases = {claude_hook.NOT_INSTALLED: "安裝", claude_hook.INSTALLED: "移除"}
        for status, text in cases.items():
            dlg, _ = self.make(status)
            self.assertTrue(dlg.hook_button.isVisibleTo(dlg), status)
            self.assertEqual(dlg.hook_button.text(), text)
        for status in (claude_hook.LEGACY, claude_hook.NO_CLAUDE, claude_hook.UNREADABLE):
            dlg, _ = self.make(status)
            self.assertFalse(dlg.hook_button.isVisibleTo(dlg), status)  # 不給按
            self.assertTrue(dlg.claude_desc.text())

    def test_install_needs_confirmation(self):
        dlg, _ = self.make(claude_hook.NOT_INSTALLED)
        with mock.patch.object(dlg, "confirm", return_value=False), \
                mock.patch.object(claude_hook, "install") as install:
            dlg.hook_button.click()
        install.assert_not_called()  # 選否：什麼都不動
        with mock.patch.object(dlg, "confirm", return_value=True), \
                mock.patch.object(claude_hook, "install") as install, \
                mock.patch.object(claude_hook, "status", return_value=claude_hook.INSTALLED):
            dlg.hook_button.click()
        install.assert_called_once()
        self.assertEqual(dlg.hook_button.text(), "移除")

    def test_failed_install_is_reported(self):
        from PySide6.QtWidgets import QMessageBox
        dlg, _ = self.make(claude_hook.NOT_INSTALLED)
        with mock.patch.object(dlg, "confirm", return_value=True), \
                mock.patch.object(claude_hook, "install", side_effect=claude_hook.HookError("壞掉")), \
                mock.patch.object(QMessageBox, "warning") as warning, \
                mock.patch.object(claude_hook, "status", return_value=claude_hook.NOT_INSTALLED):
            dlg.hook_button.click()
        self.assertIn("壞掉", warning.call_args.args[2])

    def test_demo_checkbox_is_saved(self):
        dlg, applied = self.make(claude_hook.NOT_INSTALLED)
        self.assertFalse(dlg.demo_check.isChecked())
        dlg.demo_check.setChecked(True)
        dlg.accept()
        self.assertEqual(applied, [({"claude"}, "zh-TW", True)])
        dlg2, _ = self.make(claude_hook.NOT_INSTALLED, demo_mode=True)
        self.assertTrue(dlg2.demo_check.isChecked())


if __name__ == "__main__":
    unittest.main()
