"""P4：失敗時保留舊數字、低額度通知、開機啟動。"""
import os
import sys
import tempfile
import unittest
import winreg
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import alerts, config, startup  # noqa: E402
from ai_quota_tray.card import header_note, is_dimmed  # noqa: E402
from ai_quota_tray.model import (AUTH_EXPIRED, DISABLED, ERROR, OK, STALE,  # noqa: E402
                                 ProviderState, carry_over, make_window)

NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)
WEEK_END = NOW + timedelta(days=1, hours=9)


def grok(used=92, status=OK, resets=WEEK_END, fetched=NOW):
    wins = [make_window(used, resets, 604800)] if used is not None else []
    return ProviderState("grok", wins, fetched, status, {"subscription_tier": "GrokPro"},
                         source="billing-api")


class CarryOverTest(unittest.TestCase):
    def test_failure_keeps_previous_numbers_with_new_status(self):
        prev = grok(fetched=NOW - timedelta(minutes=5))
        new = ProviderState("grok", [], None, AUTH_EXPIRED, error="token 已過期")
        out = carry_over(prev, new, NOW)
        self.assertEqual(out.status, AUTH_EXPIRED)
        self.assertEqual(out.windows[0].used_pct, 92.0)
        self.assertEqual(out.fetched_at, prev.fetched_at)
        self.assertEqual(out.error, "token 已過期")
        self.assertIsNot(out.windows[0], prev.windows[0])  # 不改到上一份

    def test_reset_passed_while_failing_rolls_over(self):
        prev = grok(resets=NOW - timedelta(minutes=1))
        out = carry_over(prev, ProviderState("grok", [], None, ERROR), NOW)
        self.assertEqual(out.windows[0].used_pct, 0.0)
        self.assertEqual(out.detail["rolled_over"], ["週"])

    def test_no_carry_when_success_disabled_or_no_previous(self):
        fresh = grok(50)
        self.assertIs(carry_over(grok(), fresh, NOW), fresh)
        disabled = ProviderState("grok", [], None, DISABLED)
        self.assertIs(carry_over(grok(), disabled, NOW), disabled)
        err = ProviderState("grok", [], None, ERROR)
        self.assertIs(carry_over(None, err, NOW), err)

    def test_card_dims_carried_state_and_shows_age(self):
        out = carry_over(grok(fetched=NOW - timedelta(minutes=7)),
                         ProviderState("grok", [], None, AUTH_EXPIRED), NOW)
        self.assertTrue(is_dimmed(out))
        self.assertEqual(header_note(out, NOW), ("7 分鐘前", False))
        self.assertFalse(is_dimmed(ProviderState("grok", [], None, AUTH_EXPIRED)))


class AlertTest(unittest.TestCase):
    def test_due_only_below_threshold_and_real_numbers(self):
        states = [grok(92), grok(89, status=STALE),
                  ProviderState("claude", [make_window(95, WEEK_END, 18000)], NOW, AUTH_EXPIRED)]
        due = alerts.due_alerts(states, set(), NOW)
        self.assertEqual(len(due), 1)  # 剩 11% 不算；auth_expired 的舊數字不算
        key, title, body = due[0]
        self.assertEqual(title, "Grok 週額度剩 8%")
        self.assertIn("1d09h 後重置", body)

    def test_once_per_reset_cycle_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            store = alerts.AlertStore(path)
            self.assertEqual(len(store.take_due([grok()], NOW)), 1)
            self.assertEqual(store.take_due([grok(95)], NOW), [])  # 同一週期再降也不再跳
            self.assertEqual(alerts.AlertStore(path).take_due([grok()], NOW), [])  # 重開程式
            next_cycle = grok(resets=WEEK_END + timedelta(days=7))
            later = WEEK_END + timedelta(hours=1)
            self.assertEqual(len(alerts.AlertStore(path).take_due([next_cycle], later)), 1)

    def test_prune_drops_passed_resets(self):
        old = alerts.alert_key("grok", "週", NOW - timedelta(seconds=1))
        live = alerts.alert_key("grok", "週", NOW + timedelta(days=1))
        unknown = alerts.alert_key("grok", "週", None)
        self.assertEqual(alerts.prune({old, live, unknown}, NOW), {live, unknown})

    def test_corrupt_state_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{not json", encoding="utf-8")
            store = alerts.AlertStore(path)
            self.assertEqual(store.notified, set())
            store.take_due([grok()], NOW)  # 壞檔要被覆寫，否則下次啟動會重複通知
            self.assertEqual(alerts.AlertStore(path).take_due([grok()], NOW), [])


class StartupTest(unittest.TestCase):
    TEST_KEY = r"Software\AiQuotaTray-unittest"  # 不碰真正的 Run 機碼

    def test_command_uses_pythonw_without_tokens(self):
        # token 來源在 config.json；帶 --token 會在每次開機蓋掉選單的選擇
        cmd = startup.command_line()
        self.assertIn("pythonw.exe", cmd)
        self.assertTrue(cmd.endswith("-m ai_quota_tray tray"))

    def test_frozen_exe(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", r"C:\Apps\AI Quota Tray\AiQuotaTray.exe"):
            self.assertEqual(startup.command_line(), r'"C:\Apps\AI Quota Tray\AiQuotaTray.exe" tray')

    def test_registry_roundtrip(self):
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.TEST_KEY).Close()
        try:
            with mock.patch.object(startup, "RUN_KEY", self.TEST_KEY):
                self.assertFalse(startup.is_enabled())
                cmd = startup.enable()
                self.assertEqual(startup.registered_command(), cmd)
                startup.disable()
                self.assertFalse(startup.is_enabled())
                startup.disable()  # 重複關閉不報錯
        finally:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.TEST_KEY)


class ConfigTest(unittest.TestCase):
    def test_roundtrip_ignores_unknown_and_keeps_other_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "config.json"
            known = {"claude", "codex", "grok"}
            self.assertEqual(config.load_token_sources(known, path), {"grok"})  # 沒檔案＝預設
            path.parent.mkdir()
            path.write_text('{"other": 1, "token_sources": ["codex", "bogus"]}', encoding="utf-8")
            # grok 沒有本機紀錄，就算設定檔沒寫也一定用 API
            self.assertEqual(config.load_token_sources(known, path), {"codex", "grok"})
            config.save_token_sources({"claude", "grok"}, path)
            self.assertEqual(config.load_token_sources(known, path), {"claude", "grok"})
            self.assertIn('"other": 1', path.read_text(encoding="utf-8"))
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(config.load_token_sources(known, path), {"grok"})
            config.save_token_sources({"codex", "grok"}, path)  # 壞檔直接覆寫
            self.assertEqual(config.load_token_sources(known, path), {"codex", "grok"})


class MenuTest(unittest.TestCase):
    """右鍵選單：真的走一次 TrayApp 的事件處理（2026-09-25 曾因方法插錯類別，右鍵直接 AttributeError）。"""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def setUp(self):
        from ai_quota_tray import app
        self.app_mod = app
        self.tmp = tempfile.TemporaryDirectory()
        cfg = Path(self.tmp.name) / "config.json"
        patches = [
            mock.patch.object(app.win32tray, "TrayIcon"),
            mock.patch.object(app.win32tray, "small_icon_size", return_value=16),
            mock.patch.object(app.win32tray, "large_icon_size", return_value=32),
            mock.patch.object(app.Poller, "refresh"),
            mock.patch.object(app, "AlertStore"),
            mock.patch.object(app.config, "config_path", return_value=cfg),
            mock.patch.object(app.startup, "is_enabled", return_value=False),
            mock.patch.object(app.startup, "enable", return_value="cmd"),
            mock.patch.object(app.startup, "disable"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.cfg = cfg
        self.tray_app = app.TrayApp({"grok"})
        self.addCleanup(self.tray_app.shutdown)

    def labels(self):
        return [(text, checked) for mid, text, _, checked in self.tray_app.menu_items() if mid]

    def test_menu_is_clean(self):
        # 業主要求：右鍵選單保持乾淨，資料來源放到「設定…」
        self.assertEqual([t for t, _ in self.labels()], ["立即刷新", "設定…", "開機時啟動", "關閉"])

    def test_right_click_opens_menu_and_runs_choice(self):
        tray = self.tray_app.tray
        tray.show_menu.return_value = self.app_mod.MENU_REFRESH
        self.app_mod.Poller.refresh.reset_mock()
        self.tray_app._on_tray_event("context_menu", 10, 20)
        tray.show_menu.assert_called_once()
        self.assertEqual(self.app_mod.Poller.refresh.call_count, 3)

    def test_settings_opens_once_and_applies(self):
        self.tray_app.handle_menu(self.app_mod.MENU_SETTINGS)
        dlg = self.tray_app._settings
        self.assertTrue(dlg.isVisible())
        self.tray_app.handle_menu(self.app_mod.MENU_SETTINGS)
        self.assertIs(self.tray_app._settings, dlg)  # 不會開第二個
        self.app_mod.Poller.refresh.reset_mock()
        dlg.groups["codex"].button(1).setChecked(True)  # Codex → API
        dlg.accept()
        self.assertFalse(dlg.isVisible())
        self.assertEqual(self.tray_app.token_set, {"codex", "grok"})
        self.assertEqual(config.load_token_sources({"codex", "grok", "claude"}, self.cfg), {"codex", "grok"})
        self.app_mod.Poller.refresh.assert_called_once_with("codex")  # 只重抓有變的那家

    def test_startup_and_quit(self):
        self.tray_app.handle_menu(self.app_mod.MENU_STARTUP)
        self.app_mod.startup.enable.assert_called_once_with()
        with mock.patch.object(self.app_mod.QApplication, "quit") as quit_:
            self.tray_app.handle_menu(self.app_mod.MENU_QUIT)
        quit_.assert_called_once()

    def test_tray_always_shows_brand_icon(self):
        # 業主決定：系統匣一律品牌圖示，資料進來只更新 tooltip，不換圖
        from ai_quota_tray import icon
        tray = self.tray_app.tray
        self.assertEqual(tray.set_icon.call_args_list[0].args[0], icon.brand_png(16))
        tray.set_icon.reset_mock()
        self.tray_app._on_fetched(ProviderState("grok", [make_window(92, WEEK_END, 604800)], NOW, OK))
        tray.set_icon.assert_not_called()
        self.assertIn("grok 週 8%", tray.set_tooltip.call_args.args[0])


class SettingsDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def make(self, sources):
        from ai_quota_tray.settings import SettingsDialog
        applied = []
        dlg = SettingsDialog(sources, applied.append)
        self.addCleanup(dlg.deleteLater)
        return dlg, applied

    def test_reflects_current_and_grok_local_is_disabled(self):
        from ai_quota_tray.settings import API, LOCAL
        dlg, _ = self.make({"grok"})
        self.assertEqual(dlg.groups["claude"].checkedId(), LOCAL)
        self.assertEqual(dlg.groups["codex"].checkedId(), LOCAL)
        self.assertEqual(dlg.groups["grok"].checkedId(), API)
        self.assertFalse(dlg.groups["grok"].button(LOCAL).isEnabled())

    def test_texts_explain_default_and_risk(self):
        from PySide6.QtWidgets import QGroupBox, QLabel
        dlg, _ = self.make({"grok"})
        titles = [b.title() for b in dlg.findChildren(QGroupBox)]
        self.assertIn("Claude　（預設：本機紀錄）", titles)
        self.assertIn("Grok　（預設：API）", titles)
        text = " ".join(lbl.text() for lbl in dlg.findChildren(QLabel))
        self.assertIn("違反使用條款", text)
        self.assertIn("不碰你的登入憑證", text)

    def test_claude_api_needs_confirmation(self):
        from ai_quota_tray.settings import API, LOCAL
        dlg, applied = self.make({"grok"})
        dlg.groups["claude"].button(API).setChecked(True)
        with mock.patch.object(dlg, "confirm_claude", return_value=False):
            dlg.accept()
        self.assertEqual(applied, [])  # 沒套用
        self.assertEqual(dlg.groups["claude"].checkedId(), LOCAL)  # 退回本機紀錄
        dlg.groups["claude"].button(API).setChecked(True)
        with mock.patch.object(dlg, "confirm_claude", return_value=True):
            dlg.accept()
        self.assertEqual(applied, [{"claude", "grok"}])

    def test_reset_to_default_and_no_change_no_apply(self):
        from PySide6.QtWidgets import QPushButton

        from ai_quota_tray.settings import LOCAL
        dlg, _ = self.make({"codex", "grok"})
        [b for b in dlg.findChildren(QPushButton) if b.text() == "還原預設"][0].click()
        self.assertEqual(dlg.groups["codex"].checkedId(), LOCAL)
        self.assertEqual(dlg.selected(), {"grok"})
        dlg2, applied2 = self.make({"grok"})
        dlg2.accept()
        self.assertEqual(applied2, [])  # 沒改就不套用、不重抓


if __name__ == "__main__":
    unittest.main()
