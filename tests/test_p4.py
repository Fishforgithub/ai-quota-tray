"""P4：失敗時保留舊數字、低額度通知、開機啟動。"""
import json
import os
import sys
import tempfile
import unittest
import winreg
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import alerts, config, display_version, startup  # noqa: E402
from ai_quota_tray.card import header_note, is_dimmed  # noqa: E402
from ai_quota_tray.model import (AUTH_EXPIRED, DISABLED, ERROR, OK, STALE,  # noqa: E402
                                 ProviderState, carry_over, make_window)

NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)
WEEK_END = NOW + timedelta(days=1, hours=9)


def codex(used=92, status=OK, resets=WEEK_END, fetched=NOW):
    wins = [make_window(used, resets, 604800)] if used is not None else []
    return ProviderState("codex", wins, fetched, status, {"plan_type": "Plus"},
                         source="codex-app-server")


class CarryOverTest(unittest.TestCase):
    def test_failure_keeps_previous_numbers_with_new_status(self):
        prev = codex(fetched=NOW - timedelta(minutes=5))
        new = ProviderState("codex", [], None, AUTH_EXPIRED, error="token 已過期")
        out = carry_over(prev, new, NOW)
        self.assertEqual(out.status, AUTH_EXPIRED)
        self.assertEqual(out.windows[0].used_pct, 92.0)
        self.assertEqual(out.fetched_at, prev.fetched_at)
        self.assertEqual(out.error, "token 已過期")
        self.assertIsNot(out.windows[0], prev.windows[0])  # 不改到上一份

    def test_reset_passed_while_failing_rolls_over(self):
        prev = codex(resets=NOW - timedelta(minutes=1))
        out = carry_over(prev, ProviderState("codex", [], None, ERROR), NOW)
        self.assertEqual(out.windows[0].used_pct, 0.0)
        self.assertEqual(out.detail["rolled_over"], ["週"])

    def test_no_carry_when_success_disabled_or_no_previous(self):
        fresh = codex(50)
        self.assertIs(carry_over(codex(), fresh, NOW), fresh)
        disabled = ProviderState("codex", [], None, DISABLED)
        self.assertIs(carry_over(codex(), disabled, NOW), disabled)
        err = ProviderState("codex", [], None, ERROR)
        self.assertIs(carry_over(None, err, NOW), err)

    def test_card_dims_carried_state_and_shows_age(self):
        out = carry_over(codex(fetched=NOW - timedelta(minutes=7)),
                         ProviderState("codex", [], None, AUTH_EXPIRED), NOW)
        self.assertTrue(is_dimmed(out))
        self.assertEqual(header_note(out, NOW), ("7 分鐘前", False))
        self.assertFalse(is_dimmed(ProviderState("codex", [], None, AUTH_EXPIRED)))


class AlertTest(unittest.TestCase):
    def test_due_only_below_threshold_and_real_numbers(self):
        states = [codex(92), codex(89, status=STALE),
                  ProviderState("claude", [make_window(95, WEEK_END, 18000)], NOW, AUTH_EXPIRED)]
        due = alerts.due_alerts(states, set(), NOW)
        self.assertEqual(len(due), 1)  # 剩 11% 不算；auth_expired 的舊數字不算
        key, title, body = due[0]
        self.assertEqual(title, "Codex 週額度剩 8%")
        self.assertIn("1d09h 後重置", body)

    def test_once_per_reset_cycle_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            store = alerts.AlertStore(path)
            self.assertEqual(len(store.take_due([codex()], NOW)), 1)
            self.assertEqual(store.take_due([codex(95)], NOW), [])  # 同一週期再降也不再跳
            self.assertEqual(alerts.AlertStore(path).take_due([codex()], NOW), [])  # 重開程式
            next_cycle = codex(resets=WEEK_END + timedelta(days=7))
            later = WEEK_END + timedelta(hours=1)
            self.assertEqual(len(alerts.AlertStore(path).take_due([next_cycle], later)), 1)

    def test_prune_drops_passed_resets(self):
        old = alerts.alert_key("codex", "週", NOW - timedelta(seconds=1))
        live = alerts.alert_key("codex", "週", NOW + timedelta(days=1))
        unknown = alerts.alert_key("codex", "週", None)
        self.assertEqual(alerts.prune({old, live, unknown}, NOW), {live, unknown})

    def test_corrupt_state_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{not json", encoding="utf-8")
            store = alerts.AlertStore(path)
            self.assertEqual(store.notified, set())
            store.take_due([codex()], NOW)  # 壞檔要被覆寫，否則下次啟動會重複通知
            self.assertEqual(alerts.AlertStore(path).take_due([codex()], NOW), [])


class StartupTest(unittest.TestCase):
    TEST_KEY = r"Software\AiQuotaTray-unittest"  # 不碰真正的 Run 機碼

    def test_command_uses_pythonw_without_tokens(self):
        # 開機時使用目前版本的 tray 指令。
        cmd = startup.command_line()
        self.assertIn("pythonw.exe", cmd)
        self.assertTrue(cmd.endswith("-m ai_quota_tray tray"))

    def test_frozen_exe(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", r"C:\Apps\AI Usage Meter\AiQuotaTray.exe"):
            self.assertEqual(startup.command_line(), r'"C:\Apps\AI Usage Meter\AiQuotaTray.exe" tray')

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
    KNOWN = {"claude", "codex", "antigravity", "copilot"}
    def test_legacy_source_setting_is_removed_on_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text('{"other": 1, "token_sources": ["claude", "codex"]}', encoding="utf-8")
            config.save(path, enabled={"claude"})
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data, {"other": 1, "enabled": ["claude"]})

    def test_enabled_defaults_to_claude_and_codex_only(self):
        # 業主 2026-09-25：預設只勾 Claude、Codex，其他家要自己到設定勾選
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            self.assertEqual(config.load_enabled(self.KNOWN, path), {"claude", "codex"})
            path.write_text('{"token_sources": ["grok"]}', encoding="utf-8")  # 舊版設定檔
            self.assertEqual(config.load_enabled(self.KNOWN, path), {"claude", "codex"})
            path.write_text('{"enabled": ["grok", "claude"]}', encoding="utf-8")
            self.assertEqual(config.load_enabled(self.KNOWN, path), {"claude"})
            config.save(path, enabled={"copilot", "bogus"})
            self.assertEqual(config.load_enabled(self.KNOWN, path), {"copilot"})
            self.assertNotIn("token_sources", json.loads(path.read_text(encoding="utf-8")))
            config.save(path, enabled=set())  # 全部取消勾選也要記得，不能變回預設
            self.assertEqual(config.load_enabled(self.KNOWN, path), set())


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
            mock.patch.object(app.copilot_provider, "start_prepare"),  # 不能真的去下載 runtime
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.cfg = cfg
        self.tray_app = app.TrayApp({"claude", "codex"})
        self.addCleanup(self.tray_app.shutdown)

    def test_remote_services_fetch_only_when_viewed_and_throttled(self):
        refresh = self.app_mod.Poller.refresh
        # 啟動時只讀本機（Claude 快取、Codex rollout），不連網
        self.assertEqual([(c.args, c.kwargs) for c in refresh.call_args_list],
                         [(("claude",), {}), (("codex",), {"local": True})])
        refresh.reset_mock()
        with mock.patch.object(self.app_mod.time, "monotonic", side_effect=[1000, 1001, 1121]):
            self.tray_app._refresh_on_view()
            self.tray_app._refresh_on_view()
            self.tray_app._refresh_on_view()
        self.assertEqual([call.args[0] for call in refresh.call_args_list], ["codex", "codex"])

    def test_background_local_only_replaces_older_numbers(self):
        now = self.app_mod.utcnow()
        live = ProviderState("codex", [make_window(94, WEEK_END, 18000)], now, OK,
                             source="codex-app-server")
        self.tray_app._on_fetched(live)
        older = ProviderState("codex", [make_window(0, WEEK_END, 18000)], now - timedelta(minutes=30),
                              STALE, source="rollout")
        self.tray_app._on_fetched_local(older)
        self.assertIs(self.tray_app.states["codex"], live)  # 本機紀錄比 App Server 舊，不蓋掉
        self.tray_app._on_fetched_local(ProviderState("codex", [], None, ERROR, error="no rollout"))
        self.assertIs(self.tray_app.states["codex"], live)  # 讀不到本機紀錄也不蓋掉
        newer = ProviderState("codex", [make_window(96, WEEK_END, 18000)], now + timedelta(minutes=1),
                              OK, source="rollout")
        self.tray_app._on_fetched_local(newer)
        self.assertEqual(self.tray_app.states["codex"].windows[0].used_pct, 96.0)

    def test_background_local_triggers_low_quota_alert(self):
        # 不打開卡片、不連網，也要能發低額度通知
        self.tray_app.alerts.take_due.return_value = [("Codex 5h 額度剩 4%", "body")]
        self.tray_app._on_fetched_local(ProviderState(
            "codex", [make_window(96, WEEK_END, 18000)], self.app_mod.utcnow(), OK, source="rollout"))
        self.tray_app.tray.show_balloon.assert_called_once()

    def test_rollout_states_follow_file_freshness_not_remote_interval(self):
        five_min = self.app_mod.utcnow() - timedelta(minutes=5)
        self.tray_app._on_fetched_local(ProviderState(
            "codex", [make_window(50, WEEK_END, 18000)], five_min, OK, source="rollout"))
        self.tray_app._mark_remote_stale()
        self.assertEqual(self.tray_app.states["codex"].status, OK)

    def test_enabling_copilot_prepares_runtime(self):
        self.tray_app.apply_settings({"claude", "codex", "copilot"})
        self.app_mod.copilot_provider.start_prepare.assert_called_once()

    def test_old_remote_numbers_are_marked_stale(self):
        old = self.app_mod.utcnow() - timedelta(seconds=121)
        self.tray_app._on_fetched(ProviderState("codex", [make_window(50, WEEK_END, 604800)], old, OK))
        self.tray_app._mark_remote_stale()
        self.assertEqual(self.tray_app.states["codex"].status, "stale")
        self.assertIn("codex stale", self.tray_app.tray.set_tooltip.call_args.args[0])

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
        self.assertEqual(self.app_mod.Poller.refresh.call_count, 2)

    def test_settings_opens_once_and_applies(self):
        self.tray_app.handle_menu(self.app_mod.MENU_SETTINGS)
        dlg = self.tray_app._settings
        self.assertTrue(dlg.isVisible())
        self.tray_app.handle_menu(self.app_mod.MENU_SETTINGS)
        self.assertIs(self.tray_app._settings, dlg)
        self.app_mod.Poller.refresh.reset_mock()
        dlg.checks["copilot"].setChecked(True)
        dlg.accept()
        self.assertFalse(dlg.isVisible())
        self.assertEqual(config.load_enabled(set(self.app_mod.ALL), self.cfg),
                         {"claude", "codex", "copilot"})
        self.app_mod.Poller.refresh.assert_not_called()

    def test_enable_and_disable_from_settings(self):
        self.tray_app._on_fetched(ProviderState("codex", [make_window(50, WEEK_END, 604800)], NOW, OK))
        self.tray_app.handle_menu(self.app_mod.MENU_SETTINGS)
        dlg = self.tray_app._settings
        self.app_mod.Poller.refresh.reset_mock()
        dlg.checks["codex"].setChecked(False)
        dlg.checks["copilot"].setChecked(True)
        dlg.accept()
        self.assertEqual(self.tray_app.enabled, {"claude", "copilot"})
        self.assertEqual(config.load_enabled(set(self.app_mod.ALL), self.cfg), {"claude", "copilot"})
        self.app_mod.Poller.refresh.assert_not_called()  # 遠端服務等查看卡片才查
        names = [n for n, _ in self.tray_app._card_states()]
        self.assertEqual(names, ["claude", "copilot"])  # 取消勾選的不上卡片
        self.assertNotIn("codex", self.tray_app.states)
        # 取消勾選前已送出的抓取晚到，也不能讓它回到卡片上
        self.tray_app._on_fetched(ProviderState("codex", [make_window(50, WEEK_END, 604800)], NOW, OK))
        self.assertNotIn("codex", self.tray_app.states)

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
        self.tray_app._on_fetched(ProviderState("codex", [make_window(92, WEEK_END, 604800)], NOW, OK))
        tray.set_icon.assert_not_called()
        self.assertIn("codex 週 8%", tray.set_tooltip.call_args.args[0])


class PollerTest(unittest.TestCase):
    def test_fixed_provider_sources(self):
        from ai_quota_tray.app import Poller
        names = {"claude", "codex", "antigravity", "copilot"}
        poller = Poller(names)
        self.addCleanup(poller.shutdown)
        with mock.patch.object(poller, "_pool") as pool:
            for name in names:
                poller.refresh(name)
            routing = {call.args[1]: call.args[2] for call in pool.submit.call_args_list}
        self.assertEqual(routing, {"claude": False, "codex": False,
                                   "antigravity": False, "copilot": False})

    def test_skips_disabled_and_inflight(self):
        from ai_quota_tray.app import Poller
        poller = Poller({"claude", "grok"})
        self.addCleanup(poller.shutdown)
        self.assertEqual(poller.enabled, {"claude"})
        with mock.patch.object(poller, "_pool") as pool:
            poller.refresh("grok")  # 已移除的服務一律不抓
            pool.submit.assert_not_called()
            poller.refresh("claude")
            poller.refresh("claude")  # 還在抓
            self.assertEqual(pool.submit.call_count, 1)


class SettingsDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def make(self, enabled=None, language="zh-TW"):
        from ai_quota_tray.settings import SettingsDialog
        applied = []
        enabled = {"claude", "codex"} if enabled is None else enabled
        dlg = SettingsDialog(enabled, language, lambda *args: applied.append(args))
        self.addCleanup(dlg.deleteLater)
        return dlg, applied

    def test_service_choices_and_source_descriptions(self):
        from PySide6.QtWidgets import QLabel, QRadioButton
        dlg, applied = self.make()
        self.assertEqual(dlg.windowTitle(), f"AI Usage Meter · 服務設定（Ver. {display_version()}）")
        self.assertFalse(dlg.windowIcon().isNull())
        self.assertEqual(dlg.selected_enabled(), {"claude", "codex"})
        self.assertNotIn("grok", dlg.checks)
        self.assertEqual(dlg.findChildren(QRadioButton), [])
        descriptions = [w.text() for w in dlg.findChildren(QLabel) if w.objectName() == "sourceDescription"]
        self.assertEqual(len(descriptions), 4)
        self.assertTrue(any("官方 App Server" in text for text in descriptions))
        self.assertTrue(any("官方 agy CLI" in text for text in descriptions))
        dlg.checks["copilot"].setChecked(True)
        dlg.accept()
        self.assertEqual(applied, [({"claude", "codex", "copilot"}, "zh-TW", False)])

    def test_no_change_no_apply_and_cancel(self):
        dlg, applied = self.make()
        dlg.accept()
        self.assertEqual(applied, [])
        dlg2, applied2 = self.make()
        dlg2.checks["codex"].setChecked(False)
        dlg2.reject()
        self.assertEqual(applied2, [])


if __name__ == "__main__":
    unittest.main()
