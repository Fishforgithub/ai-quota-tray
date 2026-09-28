"""進階設定：通知門檻、重置通知、用量速度、Claude 花費上限。"""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import alerts, config  # noqa: E402
from ai_quota_tray.config import Advanced  # noqa: E402
from ai_quota_tray.model import OK, ProviderState, make_window, pace, utcnow  # noqa: E402
from ai_quota_tray.providers import claude  # noqa: E402

NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)
H, D = 3600, 86400


def codex(used, resets, duration=5 * H, fetched=NOW, status=OK):
    return ProviderState("codex", [make_window(used, resets, duration)], fetched, status)


class PaceTest(unittest.TestCase):
    def test_on_track_has_tick_but_no_warning(self):
        # 5h 視窗過了一半（剩 2.5h）、用了 30%：平均的話應剩 50%，照目前速度撐得到重置
        p = pace(make_window(30, NOW + timedelta(hours=2.5), 5 * H), NOW)
        self.assertAlmostEqual(p.expected_remaining_pct, 50.0)
        self.assertIsNone(p.runs_out_at)

    def test_too_fast_predicts_run_out(self):
        # 用了 80%、過了 4h（每小時 20%）→ 剩 20% 再 1h 用完，重置還有 1h 以上
        p = pace(make_window(80, NOW + timedelta(hours=1, minutes=30), 5.5 * H), NOW)
        self.assertEqual(p.runs_out_at, NOW + timedelta(hours=1))

    def test_not_estimated_early_or_without_length(self):
        early = make_window(20, NOW + timedelta(hours=4, minutes=45), 5 * H)  # 才過 15 分鐘
        self.assertIsNone(pace(early, NOW))
        self.assertIsNone(pace(make_window(20, NOW + timedelta(days=3), None, label="Chat"), NOW))
        self.assertIsNone(pace(make_window(20, None, 5 * H), NOW))
        self.assertIsNone(pace(make_window(20, NOW - timedelta(minutes=1), 5 * H), NOW))

    def test_used_up_or_unused_has_no_warning(self):
        self.assertIsNone(pace(make_window(100, NOW + timedelta(hours=1), 5 * H), NOW).runs_out_at)
        self.assertIsNone(pace(make_window(0, NOW + timedelta(hours=1), 5 * H), NOW).runs_out_at)


class SpendLimitTest(unittest.TestCase):
    def test_parsed_as_its_own_window(self):
        resets = int((NOW + timedelta(days=20)).timestamp())
        state = claude.parse_cache({"fetchedAt": int(NOW.timestamp() * 1000), "rate_limits": {
            "five_hour": {"used_percentage": 10, "resets_at": resets - 19 * D},
            "spend_limit": {"used_percentage": 112.5, "resets_at": resets},
        }}, NOW)
        spend = [w for w in state.windows if w.label == claude.SPEND_LIMIT_LABEL]
        self.assertEqual(len(spend), 1)
        self.assertEqual(spend[0].used_pct, 100.0)  # 超過上限：夾到 100，剩 0%
        self.assertIsNone(spend[0].duration_s)
        self.assertNotIn("unknown_keys", state.detail)


class AdvancedConfigTest(unittest.TestCase):
    def test_defaults_roundtrip_and_bad_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            self.assertEqual(config.load_advanced(path), Advanced())  # 沒有設定檔
            value = Advanced(alert_threshold=30, reset_alert=False, pace=False, spend_limit=False)
            config.save(path, language="en", advanced=value)
            self.assertEqual(config.load_advanced(path), value)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["language"], "en")
            path.write_text(json.dumps({"advanced": {"alert_threshold": 15, "pace": "yes",
                                                     "reset_alert": False}}), encoding="utf-8")
            self.assertEqual(config.load_advanced(path), Advanced(reset_alert=False))
            path.write_text(json.dumps({"advanced": {"alert_threshold": True}}), encoding="utf-8")
            self.assertEqual(config.load_advanced(path).alert_threshold, 10)


class ThresholdTest(unittest.TestCase):
    def test_threshold_is_configurable(self):
        state = codex(75, NOW + timedelta(hours=2))  # 剩 25%
        self.assertEqual(alerts.due_alerts([state], set(), NOW), [])  # 預設 10%
        self.assertEqual(len(alerts.due_alerts([state], set(), NOW, 30)), 1)
        self.assertEqual(alerts.due_alerts([codex(99, NOW + timedelta(hours=2))], set(), NOW, 0), [])


class ResetAlertTest(unittest.TestCase):
    def store(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return alerts.AlertStore(Path(tmp.name) / "state.json")

    def test_alerted_window_reset_is_announced_once(self):
        store = self.store()
        resets = NOW + timedelta(hours=1)
        self.assertEqual(len(store.take_due([codex(95, resets)], NOW)), 1)
        self.assertEqual(store.take_resets(NOW + timedelta(minutes=30)), [])  # 還沒重置
        due = store.take_resets(resets + timedelta(minutes=1))
        self.assertEqual(due, [("Codex 5h額度已重置", "Codex 的5h視窗重置了，額度回來了。")])
        self.assertEqual(store.take_resets(resets + timedelta(minutes=2)), [])  # 只說一次
        self.assertEqual(store.notified, set())

    def test_reset_found_by_fetch_is_still_announced(self):
        # 抓取時（take_due）先清掉了過期的鍵，每分鐘的重置檢查仍要拿得到
        store = self.store()
        resets = NOW + timedelta(hours=1)
        store.take_due([codex(95, resets)], NOW)
        store.take_due([codex(3, resets + timedelta(hours=5))], resets + timedelta(seconds=30))
        self.assertEqual(len(store.take_resets(resets + timedelta(minutes=1))), 1)

    def test_old_resets_and_disabled_services_are_dropped(self):
        store = self.store()
        resets = NOW + timedelta(hours=1)
        store.take_due([codex(95, resets)], NOW)
        self.assertEqual(store.take_resets(resets + timedelta(hours=2)), [])  # 電腦睡太久
        store.take_due([codex(95, resets + timedelta(hours=5))], NOW)
        self.assertEqual(store.take_resets(resets + timedelta(hours=5, minutes=1), {"claude"}), [])

    def test_never_alerted_windows_are_silent(self):
        store = self.store()
        store.take_due([codex(50, NOW + timedelta(hours=1))], NOW)
        self.assertEqual(store.take_resets(NOW + timedelta(hours=1, minutes=1)), [])


class TrayAppAdvancedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def make(self, advanced=None):
        from ai_quota_tray import app
        self.app_mod = app
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cfg = Path(tmp.name) / "config.json"
        self.store = alerts.AlertStore(Path(tmp.name) / "state.json")
        for p in (mock.patch.object(app.win32tray, "TrayIcon"),
                  mock.patch.object(app.win32tray, "small_icon_size", return_value=16),
                  mock.patch.object(app.win32tray, "large_icon_size", return_value=32),
                  mock.patch.object(app.Poller, "refresh"),
                  mock.patch.object(app, "AlertStore", return_value=self.store),
                  mock.patch.object(app.config, "config_path", return_value=self.cfg),
                  mock.patch.object(app.copilot_provider, "start_prepare")):
            p.start()
            self.addCleanup(p.stop)
        tray_app = app.TrayApp({"claude", "codex"}, "zh-TW", False, advanced)
        self.addCleanup(tray_app.shutdown)
        return tray_app

    def claude_with_spend(self, now):
        return ProviderState("claude", [
            make_window(10, now + timedelta(hours=3), 5 * H),
            make_window(96, now + timedelta(days=9), None, label=claude.SPEND_LIMIT_LABEL),
        ], now, OK, source="statusline-cache")

    def test_spend_limit_toggle_hides_row_and_alert(self):
        now = utcnow()
        tray_app = self.make(Advanced(spend_limit=False))
        tray_app._on_fetched(self.claude_with_spend(now))
        shown = dict(tray_app._card_states())["claude"]
        self.assertEqual([w.label for w in shown.windows], ["5h"])
        tray_app.tray.show_balloon.assert_not_called()  # 花費上限剩 4%，但關掉了不通知
        self.assertEqual(len(tray_app.states["claude"].windows), 2)  # 資料本身照存

        tray_app = self.make()
        tray_app._on_fetched(self.claude_with_spend(now))
        self.assertEqual(len(dict(tray_app._card_states())["claude"].windows), 2)
        self.assertIn("花費上限", tray_app.tray.show_balloon.call_args.args[0])

    def test_threshold_from_settings(self):
        now = utcnow()
        tray_app = self.make(Advanced(alert_threshold=30))
        tray_app._on_fetched(codex(75, now + timedelta(hours=2), fetched=now))
        tray_app.tray.show_balloon.assert_called_once()

    def test_reset_notification_follows_setting(self):
        now = utcnow()
        for advanced, expected in ((Advanced(), 1), (Advanced(reset_alert=False), 0)):
            tray_app = self.make(advanced)
            # 發過低額度通知、重置時間剛過的視窗
            self.store.notified.add(alerts.alert_key("codex", "5h", now - timedelta(seconds=5)))
            tray_app._check_resets()
            self.assertEqual(tray_app.tray.show_balloon.call_count, expected, advanced)
            self.assertEqual(self.store.notified, set())  # 關著也要清掉

    def test_apply_settings_saves_advanced(self):
        tray_app = self.make()
        value = Advanced(alert_threshold=20, pace=True)
        tray_app.apply_settings({"claude", "codex"}, "zh-TW", False, value)
        self.assertEqual(tray_app.advanced, value)
        self.assertEqual(config.load_advanced(self.cfg), value)


class CardPaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def texts_and_bars(self, show_pace, used=80):
        from PySide6.QtWidgets import QLabel
        from ai_quota_tray.card import Bar, Card
        now = utcnow()
        # 過了 4h 用掉 80%：剩 20% 約 1h 用完，重置還有 1.5h
        state = ProviderState("codex", [make_window(used, now + timedelta(hours=1.5), 5.5 * H)],
                              now, OK)
        card = Card()
        self.addCleanup(card.deleteLater)
        card.set_states([("codex", state)], show_pace=show_pace)
        return [lbl.text() for lbl in card.findChildren(QLabel)], card.findChildren(Bar)

    def test_pace_tick_and_warning(self):
        texts, bars = self.texts_and_bars(True)
        self.assertTrue(any(t.startswith("照目前速度，約 0") for t in texts), texts)
        self.assertAlmostEqual(bars[0].expected, 100 * 1.5 / 5.5, places=1)

    def test_safe_window_shows_nothing(self):
        texts, bars = self.texts_and_bars(True, used=50)  # 用得比平均慢
        self.assertFalse(any("照目前速度" in t for t in texts))
        self.assertIsNone(bars[0].expected)

    def test_off_by_setting(self):
        texts, bars = self.texts_and_bars(False)
        self.assertFalse(any("照目前速度" in t for t in texts))
        self.assertIsNone(bars[0].expected)


class AdvancedDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def test_dialog_edits_and_reset_follows_threshold(self):
        from ai_quota_tray.settings import AdvancedDialog
        dlg = AdvancedDialog(Advanced(), "zh-TW")
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.windowTitle(), "AI Usage Meter · 進階設定")
        self.assertEqual([dlg.threshold.itemText(i) for i in range(dlg.threshold.count())],
                         ["不通知", "剩 10% 以下", "剩 20% 以下", "剩 30% 以下"])
        self.assertEqual(dlg.value(), Advanced())
        dlg.threshold.setCurrentIndex(0)
        self.assertFalse(dlg.checks["reset_alert"].isEnabled())  # 不發低額度通知就沒有重置通知
        self.assertFalse(dlg.checks["pace"].isChecked())  # 預設不勾
        dlg.checks["pace"].setChecked(True)
        self.assertEqual(dlg.value(), Advanced(alert_threshold=0, pace=True))
        en = AdvancedDialog(Advanced(), "de")
        self.addCleanup(en.deleteLater)
        self.assertEqual(en.windowTitle(), "AI Usage Meter · Erweitert")

    def test_settings_saves_advanced_only_on_save(self):
        from ai_quota_tray import settings
        applied = []
        dlg = settings.SettingsDialog({"claude"}, "zh-TW", lambda *a: applied.append(a),
                                      advanced=Advanced())
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.advanced_button.text(), "進階設定…")
        chosen = Advanced(alert_threshold=20)
        with mock.patch.object(settings.AdvancedDialog, "exec", return_value=settings.QDialog.Accepted), \
                mock.patch.object(settings.AdvancedDialog, "value", return_value=chosen):
            dlg.open_advanced()
        self.assertEqual(applied, [])  # 還沒按儲存
        dlg.accept()
        self.assertEqual(applied, [({"claude"}, "zh-TW", False, chosen)])

        cancelled = []
        dlg2 = settings.SettingsDialog({"claude"}, "zh-TW", lambda *a: cancelled.append(a))
        self.addCleanup(dlg2.deleteLater)
        with mock.patch.object(settings.AdvancedDialog, "exec", return_value=settings.QDialog.Rejected):
            dlg2.open_advanced()
        dlg2.accept()
        self.assertEqual(cancelled, [])  # 進階設定按了取消＝沒改


if __name__ == "__main__":
    unittest.main()
