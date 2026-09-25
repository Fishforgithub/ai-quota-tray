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

from ai_quota_tray import alerts, startup  # noqa: E402
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

    def test_command_uses_pythonw_and_tokens(self):
        cmd = startup.command_line({"grok", "codex"})
        self.assertIn("pythonw.exe", cmd)
        self.assertTrue(cmd.endswith("-m ai_quota_tray tray --token codex,grok"))
        self.assertTrue(startup.command_line(set()).endswith("tray"))

    def test_frozen_exe(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", r"C:\Apps\AI Quota Tray\AiQuotaTray.exe"):
            self.assertEqual(startup.command_line({"grok"}),
                             r'"C:\Apps\AI Quota Tray\AiQuotaTray.exe" tray --token grok')

    def test_registry_roundtrip(self):
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.TEST_KEY).Close()
        try:
            with mock.patch.object(startup, "RUN_KEY", self.TEST_KEY):
                self.assertFalse(startup.is_enabled())
                cmd = startup.enable({"grok"})
                self.assertEqual(startup.registered_command(), cmd)
                startup.disable()
                self.assertFalse(startup.is_enabled())
                startup.disable()  # 重複關閉不報錯
        finally:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.TEST_KEY)


if __name__ == "__main__":
    unittest.main()
