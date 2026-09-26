"""介面語言：繁中／English 切換。"""
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import alerts, config, i18n  # noqa: E402
from ai_quota_tray.card import header_note, status_message, window_countdown  # noqa: E402
from ai_quota_tray.model import (AUTH_EXPIRED, DISABLED, OK, STALE, ProviderState,  # noqa: E402
                                 format_age, make_window)

NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)


def english(test: unittest.TestCase) -> None:
    i18n.set_language(i18n.EN)
    test.addCleanup(i18n.set_language, i18n.ZH)  # 其他測試都假設是繁中


class StringTableTest(unittest.TestCase):
    def test_both_languages_have_same_placeholders(self):
        for key, (zh, en) in i18n.STRINGS.items():
            self.assertTrue(zh and en, key)
            self.assertEqual(set(re.findall(r"{(\w+)}", zh)), set(re.findall(r"{(\w+)}", en)), key)

    def test_english_strings_have_no_cjk(self):
        for key, (_, en) in i18n.STRINGS.items():
            self.assertIsNone(re.search(r"[一-鿿]", en), key)

    def test_resolve_and_system_language(self):
        self.assertIn(i18n.system_language(), (i18n.ZH, i18n.EN))
        self.assertEqual(i18n.resolve("en"), "en")
        self.assertEqual(i18n.resolve("zh-TW"), "zh-TW")
        self.assertEqual(i18n.resolve("auto"), i18n.system_language())
        self.assertEqual(i18n.resolve("bogus"), i18n.system_language())

    def test_explicit_lang_does_not_touch_global(self):
        self.assertEqual(i18n.tr("settings.save", "en"), "Save")
        self.assertEqual(i18n.current(), i18n.ZH)
        self.assertEqual(i18n.tr("settings.save"), "儲存")


class EnglishTextTest(unittest.TestCase):
    def test_card_texts(self):
        english(self)
        self.assertEqual(status_message(ProviderState("claude", [], None, AUTH_EXPIRED)),
                         "Token expired, please open Claude Code")
        self.assertEqual(status_message(ProviderState("copilot", [], None, AUTH_EXPIRED)),
                         "Copilot sign-in expired, run copilot login")
        self.assertEqual(status_message(ProviderState("copilot", [], None, DISABLED)), "Not enabled")
        self.assertEqual(status_message(ProviderState("copilot", [], NOW, OK,
                                                      {"unlimited": ["Chat", "補全"]})),
                         "Unlimited: Chat, Completions")
        self.assertEqual(format_age(NOW - timedelta(minutes=7), NOW), "7 min ago")
        rolled = ProviderState("codex", [make_window(0, None, 18000)], NOW, STALE,
                               {"rolled_over": ["5h"]})
        self.assertEqual(window_countdown(rolled.windows[0], rolled, NOW), "Reset")
        self.assertEqual(header_note(ProviderState("codex", [], NOW, OK, {"api_error": "x"}), NOW),
                         ("Official source failed; showing local records", True))

    def test_window_labels_translate_only_for_display(self):
        english(self)
        self.assertEqual([i18n.window_label(x) for x in ("5h", "週", "月", "進階", "Pro")],
                         ["5h", "Week", "Month", "Premium", "Pro"])
        # 資料裡的 label 不變，切語言不會讓同一週期再通知一次
        week = make_window(95, NOW + timedelta(days=1, hours=9), 604800)
        self.assertEqual(week.label, "週")
        state = ProviderState("claude", [week], NOW, OK)
        key, title, body = alerts.due_alerts([state], set(), NOW)[0]
        self.assertEqual(key, alerts.alert_key("claude", "週", week.resets_at))
        self.assertEqual(title, "Claude Week quota: 5% left")
        self.assertEqual(body, "Claude Week window has 5% left, resets in 1d09h.")


class LanguageConfigTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            self.assertEqual(config.load_language(path), "auto")  # 沒設定＝跟隨系統
            config.save(path, language="en", enabled={"claude"})
            self.assertEqual(config.load_language(path), "en")
            self.assertEqual(config.load_enabled({"claude", "codex"}, path), {"claude"})
            path.write_text('{"language": "fr"}', encoding="utf-8")
            self.assertEqual(config.load_language(path), "auto")


class SettingsLanguageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def make(self, language="zh-TW"):
        from ai_quota_tray.settings import SettingsDialog
        applied = []
        dlg = SettingsDialog({"claude", "codex"}, language,
                             lambda *args: applied.append(args))
        self.addCleanup(dlg.deleteLater)
        return dlg, applied

    def texts(self, dlg):
        from PySide6.QtWidgets import QLabel, QPushButton
        return {w.text() for w in dlg.findChildren(QLabel) + dlg.findChildren(QPushButton)}

    def test_switch_previews_without_touching_global_and_cancel_discards(self):
        dlg, applied = self.make()
        self.assertEqual(dlg.windowTitle(), "AI Usage Meter · 服務設定")
        self.assertEqual([dlg.language.itemText(i) for i in range(3)],
                         ["跟隨系統", "繁體中文", "English"])
        dlg.language.setCurrentIndex(i18n.LANGUAGES.index("en"))
        self.assertEqual(dlg.windowTitle(), "AI Usage Meter · Services")
        self.assertTrue({"Service", "Save", "Cancel", "Language"} <= self.texts(dlg))
        self.assertEqual(dlg.language.itemText(0), "System default")
        self.assertEqual(i18n.current(), i18n.ZH)  # 還沒儲存
        dlg.reject()
        self.assertEqual(applied, [])

    def test_save_language_only(self):
        dlg, applied = self.make()
        dlg.language.setCurrentIndex(i18n.LANGUAGES.index("en"))
        dlg.accept()
        self.assertEqual(len(applied), 1)
        enabled, language, demo = applied[0]
        self.assertFalse(demo)
        self.assertEqual((enabled, language), ({"claude", "codex"}, "en"))

    def test_opens_in_saved_language(self):
        dlg, _ = self.make("en")
        self.assertEqual(dlg.selected_language(), "en")
        self.assertIn("Choose services to show", self.texts(dlg))

    def test_promo_is_localized_and_opens_only_store_link_on_click(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QPushButton
        from ai_quota_tray import settings
        dlg, _ = self.make()
        button = dlg.findChild(QPushButton, "promoButton")
        self.assertIn("萌寵桌面精靈", self.texts(dlg))
        with mock.patch.object(settings.QDesktopServices, "openUrl") as open_url:
            self.assertEqual(open_url.call_count, 0)
            button.click()
            open_url.assert_called_once_with(QUrl(settings.STORE_URL))
        dlg.language.setCurrentIndex(i18n.LANGUAGES.index("en"))
        self.assertIn("Taskbar Buddy", self.texts(dlg))
        self.assertEqual(button.text(), "Get it from Microsoft →")



class TrayLanguageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def test_apply_language_switches_menu_and_saves(self):
        from ai_quota_tray import app
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cfg = Path(tmp.name) / "config.json"
        for p in (mock.patch.object(app.win32tray, "TrayIcon"),
                  mock.patch.object(app.win32tray, "small_icon_size", return_value=16),
                  mock.patch.object(app.win32tray, "large_icon_size", return_value=32),
                  mock.patch.object(app.Poller, "refresh"),
                  mock.patch.object(app, "AlertStore"),
                  mock.patch.object(app.config, "config_path", return_value=cfg),
                  mock.patch.object(app.startup, "is_enabled", return_value=False)):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(i18n.set_language, i18n.ZH)
        tray_app = app.TrayApp({"claude", "codex"}, "zh-TW")
        self.addCleanup(tray_app.shutdown)
        app.Poller.refresh.reset_mock()
        tray_app.apply_settings({"claude", "codex"}, "en")
        self.assertEqual([t for mid, t, _, _ in tray_app.menu_items() if mid],
                         ["Refresh now", "Settings…", "Start with Windows", "Quit"])
        self.assertEqual(config.load_language(cfg), "en")
        app.Poller.refresh.assert_not_called()  # 只換語言不重抓


if __name__ == "__main__":
    unittest.main()
