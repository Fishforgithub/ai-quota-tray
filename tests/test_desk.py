"""釘在桌面的卡片（2026-10-03 使用者回饋：想像桌面小工具一樣常駐）。

app.TrayApp.desk＝card.Card(pinned=True)；位置存 config 的 desk；跑出螢幕由 placement.keep_on_screen 拉回。
它照背景規則走：啟動、釘選都不查雲端，滑鼠移進來才查（業主 2026-09-26 定：不要一直去打對方的服務）。
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import config, i18n, placement, win32tray  # noqa: E402

SCREEN = (0, 0, 1920, 1040)  # 主螢幕可用區域（扣掉工作列）
RIGHT = (1920, 0, 3840, 1080)
SIZE = (300, 400)


class KeepOnScreenTest(unittest.TestCase):
    def test_inside_stays_put(self):
        self.assertEqual(placement.keep_on_screen((100, 200), SIZE, [SCREEN], SCREEN), (100, 200))

    def test_pushed_back_from_edges(self):
        self.assertEqual(placement.keep_on_screen((1800, 900), SIZE, [SCREEN], SCREEN), (1620, 640))
        self.assertEqual(placement.keep_on_screen((-50, -10), SIZE, [SCREEN], SCREEN), (0, 0))

    def test_picks_screen_with_most_overlap(self):
        self.assertEqual(placement.keep_on_screen((1800, 100), SIZE, [SCREEN, RIGHT], SCREEN), (1920, 100))
        self.assertEqual(placement.keep_on_screen((1700, 100), SIZE, [SCREEN, RIGHT], SCREEN), (1620, 100))

    def test_unplugged_screen_or_no_position_goes_to_primary_corner(self):
        corner = (1920 - 300 - placement.GAP, 1040 - 400 - placement.GAP)
        self.assertEqual(placement.keep_on_screen((2500, 100), SIZE, [SCREEN], SCREEN), corner)
        self.assertEqual(placement.keep_on_screen(None, SIZE, [SCREEN], SCREEN), corner)


class DeskConfigTest(unittest.TestCase):
    def test_round_trip_and_bad_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            self.assertEqual(config.load_desk(path), config.Desk())
            config.save(path, language="en")
            config.save(path, desk=config.Desk(True, 120, -30))  # 左邊有螢幕時座標可以是負的
            self.assertEqual(config.load_desk(path), config.Desk(True, 120, -30))
            self.assertEqual(config.load_desk(path).pos, (120, -30))
            self.assertEqual(config.load_language(path), "en")  # 其他欄位保留
            path.write_text(json.dumps({"desk": {"pinned": "yes", "x": True, "y": 1.5}}), encoding="utf-8")
            self.assertEqual(config.load_desk(path), config.Desk())
            self.assertIsNone(config.load_desk(path).pos)
            path.write_text(json.dumps({"desk": [1, 2]}), encoding="utf-8")
            self.assertEqual(config.load_desk(path), config.Desk())


class FullscreenProbeTest(unittest.TestCase):
    def test_real_call_returns_bool(self):
        self.assertIsInstance(win32tray.fullscreen_app_on(0), bool)


def texts(widget):
    from PySide6.QtWidgets import QLabel
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


class DeskCardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def test_link_shows_only_while_hovered(self):
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QEnterEvent
        from PySide6.QtWidgets import QApplication
        from ai_quota_tray.card import Card
        desk = Card(pinned=True)
        self.addCleanup(desk.close)
        hovered = []
        desk.hovered.connect(lambda: hovered.append(True))
        desk.set_states([("claude", None)])
        desk.show_pinned((10, 10))
        height = desk.height()
        self.assertTrue(desk._pin_link.isHidden())
        self.assertIn(i18n.tr("card.unpin"), desk._pin_link.text())
        QApplication.sendEvent(desk, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(15, 15)))
        self.assertFalse(desk._pin_link.isHidden())
        self.assertEqual(hovered, [True])
        self.assertEqual(desk.height(), height, "連結出現不能讓卡片變高")
        QApplication.sendEvent(desk, QEvent(QEvent.Leave))
        self.assertTrue(desk._pin_link.isHidden())

    def test_clicking_the_link_emits_pin_clicked(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from ai_quota_tray.card import Card
        card = Card()
        self.addCleanup(card.close)
        clicked = []
        card.pin_clicked.connect(lambda: clicked.append(True))
        card.set_states([("claude", None)])
        card.show()
        link = card._pin_link
        QTest.mouseClick(link, Qt.LeftButton, Qt.NoModifier, QPoint(link.width() - 5, link.height() // 2))
        self.assertEqual(clicked, [True])

    def test_hover_card_is_not_draggable(self):
        from ai_quota_tray.card import Card
        card = Card()
        self.addCleanup(card.close)
        card.set_states([("claude", None)])
        card.move(100, 100)
        card.show()
        send_mouse(card, "press", (110, 110))
        send_mouse(card, "move", (300, 300))
        send_mouse(card, "release", (300, 300))
        self.assertEqual((card.x(), card.y()), (100, 100))
        self.assertIn(i18n.tr("card.pin"), card._pin_link.text())


def send_mouse(widget, kind, global_pos):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    event_type = {"press": QEvent.MouseButtonPress, "move": QEvent.MouseMove,
                  "release": QEvent.MouseButtonRelease}[kind]
    button = Qt.NoButton if kind == "move" else Qt.LeftButton
    buttons = Qt.NoButton if kind == "release" else Qt.LeftButton
    local = QPointF(global_pos[0] - widget.x(), global_pos[1] - widget.y())
    QApplication.sendEvent(widget, QMouseEvent(event_type, local, QPointF(*global_pos), button,
                                               buttons, Qt.NoModifier))


class DeskAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def setUp(self):
        from ai_quota_tray import app
        self.app_mod = app
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cfg = Path(tmp.name) / "config.json"
        patches = [
            mock.patch.object(app.win32tray, "TrayIcon"),
            mock.patch.object(app.win32tray, "small_icon_size", return_value=16),
            mock.patch.object(app.win32tray, "large_icon_size", return_value=32),
            mock.patch.object(app.Poller, "refresh"),
            mock.patch.object(app, "AlertStore"),
            mock.patch.object(app.config, "config_path", return_value=self.cfg),
            mock.patch.object(app.copilot_provider, "start_prepare"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.tray_app = self.make({"claude", "codex", "antigravity"})

    def make(self, enabled, desk=None):
        tray_app = self.app_mod.TrayApp(enabled, "zh-TW", desk=desk)
        tray_app.tray.icon_rect.return_value = (700, 780, 720, 800)
        self.addCleanup(tray_app.shutdown)
        return tray_app

    def remote_refreshes(self):
        return [c.args[0] for c in self.app_mod.Poller.refresh.call_args_list if not c.kwargs.get("local")
                and c.args[0] != "claude"]  # Claude 只讀本機快取


    def pin_card(self, ta, pos=(40, 50)):
        ta._card_pos = pos
        ta.pin("card")

    def right_click(self, widget, cmd):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QContextMenuEvent
        from PySide6.QtWidgets import QApplication
        self.tray_app.tray.show_menu.return_value = cmd
        QApplication.sendEvent(widget, QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(10, 10),
                                                         QPoint(widget.x() + 10, widget.y() + 10)))
        return self.tray_app.tray.show_menu.call_args.args[0]

    def test_pin_card_from_hover_card_then_unpin(self):
        ta = self.tray_app
        ta.show_card(0, 0)
        ta.card.move(50, 60)
        ta.tray.show_menu.return_value = self.app_mod.MENU_PIN_CARD
        ta.card.pin_clicked.emit()  # 使用者按 hover 卡片頁尾的「釘選…」→ 選「卡片」
        self.assertEqual([item[0] for item in ta.tray.show_menu.call_args.args[0]],
                         [self.app_mod.MENU_PIN_CARD, self.app_mod.MENU_PIN_STRIP])
        self.assertTrue(ta.pinned)
        self.assertTrue(ta.desk.isVisible())
        self.assertFalse(ta.strip.isVisible())
        self.assertFalse(ta.card.isVisible())
        self.assertEqual((ta.desk.x(), ta.desk.y()), (50, 60), "留在 hover 卡片原本的位置")
        self.assertEqual(config.load_desk(self.cfg), config.Desk(True, 50, 60, "card"))

        ta.show_card(0, 0)
        self.assertIn(i18n.tr("card.unpin"), ta.card._pin_link.text())
        ta.tray.show_menu.reset_mock()
        ta.card.pin_clicked.emit()
        ta.tray.show_menu.assert_not_called()  # 取消不用問
        self.assertFalse(ta.pinned)
        self.assertFalse(ta.desk.isVisible())
        self.assertTrue(ta.card.isVisible(), "從 hover 卡片取消釘選，hover 卡片留著")
        self.assertIn(i18n.tr("card.pin"), ta.card._pin_link.text())
        self.assertFalse(config.load_desk(self.cfg).pinned)

    def test_dismissing_the_pin_menu_does_nothing(self):
        ta = self.tray_app
        ta.show_card(0, 0)
        ta.tray.show_menu.return_value = None
        ta.card.pin_clicked.emit()
        self.assertFalse(ta.pinned)
        self.assertTrue(ta.card.isVisible())

    def test_pin_strip_docks_above_taskbar(self):
        ta = self.tray_app
        ta.show_card(0, 0)
        ta.tray.show_menu.return_value = self.app_mod.MENU_PIN_STRIP
        ta.card.pin_clicked.emit()
        self.assertTrue(ta.strip.isVisible())
        self.assertFalse(ta.desk.isVisible())
        self.assertFalse(ta.card.isVisible())
        screen = self.qapp.primaryScreen().availableGeometry()  # offscreen：800x800、沒有工作列
        self.assertEqual(ta.strip.y() + ta.strip.height(), screen.bottom() + 1, "貼著可用區域底邊")
        self.assertEqual(ta.strip.x() + ta.strip.width(), screen.right() + 1 - placement.GAP, "預設靠右")
        self.assertEqual(config.load_desk(self.cfg).style, "strip")

    def test_switch_style_from_right_click_keeps_each_position(self):
        ta = self.tray_app
        self.pin_card(ta, (40, 50))
        items = self.right_click(ta.desk, self.app_mod.MENU_PIN_STRIP)
        self.assertIn((self.app_mod.MENU_PIN_CARD, i18n.tr("pin.card"), True, True), items, "目前那一種打勾")
        self.assertTrue(ta.strip.isVisible())
        self.assertFalse(ta.desk.isVisible())
        self.assertEqual(config.load_desk(self.cfg), config.Desk(True, 40, 50, "strip"))
        self.right_click(ta.strip, self.app_mod.MENU_PIN_CARD)
        self.assertTrue(ta.desk.isVisible())
        self.assertFalse(ta.strip.isVisible())
        self.assertEqual((ta.desk.x(), ta.desk.y()), (40, 50), "換回卡片回到卡片原本的位置")

    def test_starts_pinned_without_querying_remote_and_hover_queries(self):
        self.app_mod.Poller.refresh.reset_mock()
        ta = self.make({"claude", "codex", "antigravity"}, config.Desk(True, 40, 50))
        self.assertTrue(ta.desk.isVisible())
        self.assertEqual((ta.desk.x(), ta.desk.y()), (40, 50))
        self.assertEqual(self.remote_refreshes(), [], "啟動時只讀本機")
        self.assertIn(i18n.tr("card.hover_to_load"), texts(ta.desk))

        with mock.patch.object(self.app_mod.time, "monotonic", return_value=1000.0):
            ta.desk.hovered.emit()
        self.assertCountEqual(self.remote_refreshes(), ["codex", "antigravity"])
        with mock.patch.object(self.app_mod.time, "monotonic", return_value=1010.0):
            ta.desk.hovered.emit()
        self.assertCountEqual(self.remote_refreshes(), ["codex", "antigravity"], "有最短間隔，不會每次移進來都查")

    def test_starts_as_strip_where_it_was(self):
        self.app_mod.Poller.refresh.reset_mock()
        ta = self.make({"claude", "codex"}, config.Desk(True, style="strip", strip_right=600))
        self.assertTrue(ta.strip.isVisible())
        self.assertFalse(ta.desk.isVisible())
        self.assertEqual(ta.strip.x() + ta.strip.width(), 600)
        self.assertEqual(self.remote_refreshes(), [], "啟動時只讀本機")

    def test_waiting_text_only_while_nothing_is_fetching(self):
        ta = self.tray_app
        self.pin_card(ta)
        self.assertIn(i18n.tr("card.hover_to_load"), texts(ta.desk))
        ta.poller._inflight.update({"claude", "codex:local", "antigravity"})
        ta._update_views()
        self.assertNotIn(i18n.tr("card.hover_to_load"), texts(ta.desk))
        self.assertIn(i18n.tr("card.loading"), texts(ta.desk))
        ta.poller._inflight.clear()
        ta.show_card(0, 0)
        self.assertNotIn(i18n.tr("card.hover_to_load"), texts(ta.card), "hover 卡片打開就會查，照舊寫讀取中")

    def test_refresh_link_bottom_left_refreshes_everything(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        ta = self.tray_app
        self.pin_card(ta)
        link = ta.desk._refresh_link
        self.assertFalse(link.isHidden(), "一直顯示，不用先移進去")
        self.assertIn(i18n.tr("menu.refresh"), link.text())
        self.assertTrue(ta.card._refresh_link.isHidden(), "hover 卡片沒有")
        with mock.patch.object(self.app_mod.time, "monotonic", return_value=1000.0):
            ta.desk.hovered.emit()  # 移進去先查過一次
        self.app_mod.Poller.refresh.reset_mock()
        QTest.mouseClick(link, Qt.LeftButton, Qt.NoModifier, QPoint(5, link.height() // 2))
        self.assertCountEqual([c.args[0] for c in self.app_mod.Poller.refresh.call_args_list],
                              ["claude", "codex", "antigravity"], "立即刷新不管最短間隔")
        ta.poller._inflight.add("antigravity")
        ta._update_busy()
        self.assertIn(i18n.tr("card.refreshing"), link.text())
        ta.poller._inflight.clear()
        ta._update_busy()
        self.assertIn(i18n.tr("menu.refresh"), link.text())

    def test_fullscreen_hides_and_restores(self):
        ta = self.tray_app
        self.pin_card(ta)
        with mock.patch.object(self.app_mod.win32tray, "fullscreen_app_on", return_value=True):
            ta._check_fullscreen()
        self.assertFalse(ta.desk.isVisible())
        self.assertTrue(ta.pinned, "只是暫時藏起來，還是釘著")
        self.assertTrue(config.load_desk(self.cfg).pinned)
        with mock.patch.object(self.app_mod.win32tray, "fullscreen_app_on", return_value=False):
            ta._check_fullscreen()
        self.assertTrue(ta.desk.isVisible())
        self.assertEqual((ta.desk.x(), ta.desk.y()), (40, 50))

        ta.pin("strip")
        with mock.patch.object(self.app_mod.win32tray, "fullscreen_app_on", return_value=True):
            ta._check_fullscreen()
        self.assertFalse(ta.strip.isVisible())
        self.assertFalse(ta.desk.isVisible(), "藏長條時不會把卡片叫出來")
        with mock.patch.object(self.app_mod.win32tray, "fullscreen_app_on", return_value=False):
            ta._check_fullscreen()
        self.assertTrue(ta.strip.isVisible())

        ta.unpin()
        with mock.patch.object(self.app_mod.win32tray, "fullscreen_app_on", return_value=False) as probe:
            ta._check_fullscreen()
        probe.assert_not_called()
        self.assertFalse(ta.desk.isVisible() or ta.strip.isVisible(), "取消釘選後不會被全螢幕檢查叫回來")

    def test_right_click_menu_unpins(self):
        ta = self.tray_app
        self.pin_card(ta)
        items = self.right_click(ta.desk, self.app_mod.MENU_UNPIN)
        self.assertIn((self.app_mod.MENU_UNPIN, i18n.tr("card.unpin"), True, False), items)
        self.assertNotIn(self.app_mod.MENU_QUIT, [item[0] for item in items])
        self.assertFalse(ta.pinned)
        self.assertFalse(ta.desk.isVisible())

    def test_drag_moves_and_saves_and_stays_on_screen(self):
        ta = self.tray_app
        self.pin_card(ta)
        send_mouse(ta.desk, "press", (60, 70))
        send_mouse(ta.desk, "move", (160, 170))
        self.assertEqual((ta.desk.x(), ta.desk.y()), (140, 150))
        send_mouse(ta.desk, "release", (160, 170))
        self.assertEqual(config.load_desk(self.cfg), config.Desk(True, 140, 150))

        send_mouse(ta.desk, "press", (160, 170))
        send_mouse(ta.desk, "move", (5000, 5000))
        send_mouse(ta.desk, "release", (5000, 5000))
        x, y = config.load_desk(self.cfg).pos
        screen = self.qapp.primaryScreen().availableGeometry()  # offscreen 平台是 800x800
        self.assertLessEqual(x + ta.desk.width(), screen.right() + 1)
        self.assertLessEqual(y + ta.desk.height(), screen.bottom() + 1)
        self.assertEqual((ta.desk.x(), ta.desk.y()), (x, y))

    def test_strip_drags_sideways_only_and_saves_right_edge(self):
        ta = self.tray_app
        ta.pin("strip")
        y0 = ta.strip.y()
        start = (ta.strip.x() + 10, y0 + 10)
        send_mouse(ta.strip, "press", start)
        send_mouse(ta.strip, "move", (start[0] - 200, start[1] - 300))
        self.assertEqual(ta.strip.y(), y0, "只能左右拖")
        send_mouse(ta.strip, "release", (start[0] - 200, start[1] - 300))
        self.assertEqual(ta.strip.y(), y0)
        self.assertEqual(config.load_desk(self.cfg).strip_right, ta.strip.x() + ta.strip.width())
        self.assertFalse(ta.card.isVisible(), "拖完不打開卡片")

    def test_strip_hover_or_click_does_not_open_full_card_or_query(self):
        """業主 2026-10-03：長條滑過去就跳出完整卡片很煩 → 滑過、點一下都不開，也就不會因此查雲端。"""
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QEnterEvent
        from PySide6.QtWidgets import QApplication
        ta = self.tray_app
        ta.pin("strip")
        self.app_mod.Poller.refresh.reset_mock()
        x0 = ta.strip.x()
        QApplication.sendEvent(ta.strip, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(x0 + 5, 790)))
        point = (x0 + 20, ta.strip.y() + 10)
        send_mouse(ta.strip, "press", point)
        send_mouse(ta.strip, "release", (point[0] + 1, point[1]))  # 手抖一個像素也算點一下
        QApplication.sendEvent(ta.strip, QEvent(QEvent.Leave))
        self.qapp.processEvents()
        self.assertFalse(ta.card.isVisible())
        self.assertEqual(ta.strip.x(), x0, "點一下不會移動")
        self.assertIsNone(config.load_desk(self.cfg).strip_right, "點一下不存位置")
        self.assertEqual(self.remote_refreshes(), [])

    def test_language_switch_relabels_link(self):
        ta = self.tray_app
        self.addCleanup(i18n.set_language, "zh-TW")
        ta.show_card(0, 0)
        ta.apply_settings(set(ta.enabled), language="en")
        self.assertIn("Pin…", ta.card._pin_link.text())


class DockStripTest(unittest.TestCase):
    BOTTOM = ((0, 0, 1920, 1080), (0, 0, 1920, 1032))  # 工作列在下面，48px
    TOP = ((0, 0, 1920, 1080), (0, 48, 1920, 1080))
    SECOND = ((1920, 0, 3840, 1080), (1920, 0, 3840, 1040))

    def test_default_sits_on_taskbar_right(self):
        self.assertEqual(placement.dock_strip(None, (400, 28), [self.BOTTOM]),
                         (1920 - placement.GAP - 400, 1032 - 28))

    def test_taskbar_on_top_docks_below_it(self):
        self.assertEqual(placement.dock_strip(1000, (400, 28), [self.TOP]), (600, 48))

    def test_dragged_to_second_screen_docks_to_its_taskbar(self):
        self.assertEqual(placement.dock_strip(2600, (400, 28), [self.BOTTOM, self.SECOND]), (2200, 1012))

    def test_pushed_back_inside_and_unplugged_screen_falls_back(self):
        self.assertEqual(placement.dock_strip(300, (400, 28), [self.BOTTOM]), (0, 1004))
        self.assertEqual(placement.dock_strip(5000, (400, 28), [self.BOTTOM]),
                         (1920 - placement.GAP - 400, 1004))


class StripContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def test_batteries_show_numbers_and_readable_text(self):
        from PySide6.QtGui import QColor
        from ai_quota_tray import demo, strip
        from ai_quota_tray.model import utcnow
        bar = strip.Strip()
        self.addCleanup(bar.close)
        states = demo.sample_states(utcnow())
        bar.set_states(states, banner="demo")
        batteries = bar.findChildren(strip.Battery)
        self.assertEqual(len(batteries), sum(len(s.windows) for _, s in states))
        self.assertIn("62", [b.text() for b in batteries])  # Claude 5h 用了 38%
        self.assertIn(i18n.tr("strip.demo"), texts(bar))
        self.assertEqual(strip.Battery(None, "#000000", {}).text(), "—")
        self.assertEqual(strip.text_on(QColor(46, 160, 67)).name(), "#ffffff")  # 綠底白字
        self.assertEqual(strip.text_on(QColor(212, 160, 23)).name(), "#202124")  # 黃底黑字
        self.assertEqual(strip.text_on(QColor(207, 34, 46)).name(), "#ffffff")  # 紅底白字

    def test_failed_and_empty_providers(self):
        from ai_quota_tray import strip
        from ai_quota_tray.model import AUTH_EXPIRED, ProviderState
        bar = strip.Strip()
        self.addCleanup(bar.close)
        bar.set_states([("claude", None),
                        ("grok", ProviderState("grok", [], None, AUTH_EXPIRED)),
                        ("copilot", ProviderState("copilot", [], None, "ok", {"unlimited": ["Chat"]}))])
        self.assertEqual(bar.findChildren(strip.Battery), [])
        self.assertEqual([t for t in texts(bar) if t in ("—", "!", "∞")], ["—", "!", "∞"])


if __name__ == "__main__":
    unittest.main()
