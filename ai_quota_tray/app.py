"""系統匣常駐程式：Qt 主迴圈 + 原生系統匣 + 動態圖示 + 右鍵選單 + hover 卡片。

抓取頻率與畫面更新分離（原則 2）：
- Claude 定期讀本機快取；Codex、Antigravity、Copilot 只在查看卡片或手動刷新時查詢。
- 抓取在背景執行緒，結果用 signal 丟回主執行緒。
- 系統匣一律顯示品牌圖示（業主決定），數字只在卡片；卡片開著時自己每秒重算倒數（card.py）。
- 睡眠喚醒後等 RESUME_DELAY_S 秒重讀 Claude 本機快取。

P4：抓取失敗時保留上一次的數字（model.carry_over）；剩餘 < 10% 跳通知（alerts.py，
每個重置週期只一次）；右鍵選單：立即刷新／設定…（啟用服務，settings.py）／
開機時啟動（startup.py）／關閉。

卡片開關：NIN_POPUPOPEN（hover）或點一下圖示 → 開；之後每 HOVER_CHECK_MS 看一次滑鼠，
離開「圖示＋卡片」超過 HIDE_DELAY_S 才關。不直接靠 NIN_POPUPCLOSE 關，
是因為滑鼠從圖示移到卡片上的途中就會收到 CLOSE，使用者會看不到卡片。
"""
from __future__ import annotations

import logging
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import config, i18n, icon, startup, win32tray
from .alerts import AlertStore
from .i18n import tr
from .card import Card
from .model import ProviderState, carry_over, utcnow
from .providers import ALL, fetch_one
from .settings import SettingsDialog

log = logging.getLogger(__name__)

LOCAL_POLL_INTERVAL_S = 120
VIEW_REFRESH_INTERVAL_S = {"codex": 120, "antigravity": 300, "copilot": 300}
RESUME_DELAY_S = 10
HOVER_CHECK_MS = 150
HIDE_DELAY_S = 0.4
HOVER_SLOP_PX = 6  # 實體像素：卡片邊緣外這麼近仍算在卡片上
MUTEX_NAME = "Local\\AiQuotaTray.SingleInstance"
APP_USER_MODEL_ID = "AiQuotaTray.App"

MENU_REFRESH, MENU_QUIT, MENU_STARTUP, MENU_SETTINGS = 1, 2, 3, 4


class Poller(QObject):
    """背景抓取。同一家還在抓就不重複送出；沒啟用的不抓。"""

    fetched = Signal(object)  # ProviderState

    def __init__(self, enabled: set[str]):
        super().__init__()
        self.enabled = enabled & ALL.keys()
        self._pool = ThreadPoolExecutor(max_workers=len(ALL), thread_name_prefix="poll")
        self._inflight: set[str] = set()

    def refresh(self, name: str) -> None:
        if name in self._inflight or name not in self.enabled or name not in ALL:
            return
        self._inflight.add(name)
        future = self._pool.submit(fetch_one, name, False, utcnow())
        # done callback 在背景執行緒跑；跨執行緒 emit 會自動排進主執行緒
        future.add_done_callback(lambda f, n=name: self.fetched.emit(f.result()))

    def done(self, name: str) -> None:
        self._inflight.discard(name)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


class TrayApp(QObject):
    def __init__(self, enabled: set[str], language: str = i18n.AUTO):
        super().__init__()
        self.language = language  # 設定值（auto／zh-TW／en）；實際語言在 i18n
        self.states: dict[str, ProviderState] = {}
        self.alerts = AlertStore()
        self.tray = win32tray.TrayIcon(self._on_tray_event)
        self.icon_size = win32tray.small_icon_size()
        self.tray.set_balloon_icon(icon.brand_png(win32tray.large_icon_size()),
                                   win32tray.large_icon_size())
        self.poller = Poller(set(enabled))
        self.poller.fetched.connect(self._on_fetched)
        self._last_remote_attempt: dict[str, float] = {}

        self._timers = []
        local_timer = QTimer(self)
        local_timer.setInterval(LOCAL_POLL_INTERVAL_S * 1000)
        local_timer.timeout.connect(lambda: self.poller.refresh("claude"))
        local_timer.start()
        self._timers.append(local_timer)
        freshness_timer = QTimer(self)
        freshness_timer.setInterval(60_000)
        freshness_timer.timeout.connect(self._mark_remote_stale)
        freshness_timer.start()
        self._timers.append(freshness_timer)

        self.card = Card()
        self._settings: SettingsDialog | None = None
        self._card_anchor: tuple[int, int, int, int] | None = None
        self._outside_since: float | None = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(HOVER_CHECK_MS)
        self._hover_timer.timeout.connect(self._check_hover)
        self._resume_timer = QTimer(self)  # 喚醒會連來兩個事件，用同一個計時器合併
        self._resume_timer.setSingleShot(True)
        self._resume_timer.setInterval(RESUME_DELAY_S * 1000)
        self._resume_timer.timeout.connect(lambda: self.poller.refresh("claude"))

        self.tray.set_icon(icon.brand_png(self.icon_size), self.icon_size)
        self.poller.refresh("claude")

    @property
    def enabled(self) -> set[str]:
        return self.poller.enabled

    def refresh_all(self) -> None:
        for name in ALL:
            if name in self.enabled:
                if name in VIEW_REFRESH_INTERVAL_S:
                    self._last_remote_attempt[name] = time.monotonic()
                self.poller.refresh(name)

    def _mark_remote_stale(self) -> None:
        now = utcnow()
        changed = False
        for name, interval in VIEW_REFRESH_INTERVAL_S.items():
            state = self.states.get(name)
            if state is not None and state.status == "ok" and state.fetched_at is not None:
                if (now - state.fetched_at).total_seconds() >= interval:
                    state.status = "stale"
                    changed = True
        if changed:
            self._update_views()

    def _refresh_on_view(self) -> None:
        self._mark_remote_stale()
        now = time.monotonic()
        for name, interval in VIEW_REFRESH_INTERVAL_S.items():
            if name not in self.enabled:
                continue
            last = self._last_remote_attempt.get(name)
            if last is None or now - last >= interval:
                self._last_remote_attempt[name] = now
                self.poller.refresh(name)

    def _on_fetched(self, state: ProviderState) -> None:
        self.poller.done(state.name)
        if state.name not in self.enabled:
            return  # 抓到一半被使用者取消勾選
        now = utcnow()
        state = carry_over(self.states.get(state.name), state, now)
        self.states[state.name] = state
        log.info("%s: %s %s", state.name, state.status,
                 [(w.label, w.remaining_pct) for w in state.windows] or state.error)
        self._update_views()
        due = self.alerts.take_due([state], now)
        if due:
            # 一次只能掛一則，同一家兩個視窗都低時合併
            self.tray.show_balloon(due[0][0], "\n".join(body for _, body in due))

    def _update_views(self) -> None:
        self.tray.set_tooltip(icon.tooltip([s for _, s in self._card_states() if s is not None]))
        if self.card.isVisible():
            self.card.set_states(self._card_states())

    def _card_states(self) -> list[tuple[str, ProviderState | None]]:
        return [(name, self.states.get(name)) for name in ALL if name in self.enabled]

    # ---------- 卡片 ----------

    def show_card(self, x: int, y: int) -> None:
        self._refresh_on_view()
        # 取不到圖示位置（例如收在關著的溢位區）就用事件給的錨點
        self._card_anchor = self.tray.icon_rect() or (x, y, x + 1, y + 1)
        self.card.set_states(self._card_states())
        self.card.show_at(self._card_anchor)
        self._outside_since = None
        self._hover_timer.start()

    def hide_card(self) -> None:
        self._hover_timer.stop()
        self.card.hide()

    def _check_hover(self) -> None:
        x, y = win32tray.cursor_pos()
        l, t, r, b = win32tray.window_rect(int(self.card.winId()))
        on_card = l - HOVER_SLOP_PX <= x < r + HOVER_SLOP_PX and t - HOVER_SLOP_PX <= y < b + HOVER_SLOP_PX
        al, at, ar, ab = self._card_anchor or (0, 0, 0, 0)
        on_icon = al <= x < ar and at <= y < ab
        if on_card or on_icon:
            self._outside_since = None
        elif self._outside_since is None:
            self._outside_since = time.monotonic()
        elif time.monotonic() - self._outside_since >= HIDE_DELAY_S:
            self.hide_card()

    # ---------- 系統匣事件與右鍵選單 ----------

    def _on_tray_event(self, kind: str, x: int, y: int) -> None:
        log.debug("tray event %s (%d, %d)", kind, x, y)
        if kind in ("popup_open", "select", "balloon_click"):
            self.show_card(x, y)
        elif kind == "resume":
            self._resume_timer.start()
        elif kind == "context_menu":
            self.hide_card()
            self._context_menu(x, y)
        elif kind == "quit":
            QApplication.quit()
        # popup_close 不處理，交給 _check_hover（見模組說明）

    def menu_items(self) -> list[win32tray.MenuItem]:
        sep = (None, "", True, False)
        return [(MENU_REFRESH, tr("menu.refresh"), True, False),
                (MENU_SETTINGS, tr("menu.settings"), True, False), sep,
                (MENU_STARTUP, tr("menu.startup"), True, startup.is_enabled()), sep,
                (MENU_QUIT, tr("menu.quit"), True, False)]

    def _context_menu(self, x: int, y: int) -> None:
        self.handle_menu(self.tray.show_menu(self.menu_items(), x, y))

    def handle_menu(self, cmd: int | None) -> None:
        if cmd == MENU_REFRESH:
            self.refresh_all()
        elif cmd == MENU_SETTINGS:
            self.open_settings()
        elif cmd == MENU_STARTUP:
            if startup.is_enabled():
                startup.disable()
                log.info("已關閉開機啟動")
            else:
                log.info("已開啟開機啟動：%s", startup.enable())
        elif cmd == MENU_QUIT:
            QApplication.quit()

    # ---------- 設定 ----------

    def open_settings(self) -> None:
        """非模態，已經開著就拉到前面，不會開第二個。"""
        if self._settings is None or not self._settings.isVisible():
            self._settings = SettingsDialog(self.enabled, self.language, self.apply_settings)
            self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    def apply_settings(self, enabled: set[str], language: str | None = None) -> None:
        """新勾選的服務立即抓取；取消的從卡片移除；語言變更只重畫。"""
        enabled = enabled & ALL.keys()
        changed = enabled - self.enabled
        for name in self.enabled - enabled:
            self.states.pop(name, None)
            self._last_remote_attempt.pop(name, None)
        self.enabled.clear()
        self.enabled.update(enabled)
        if language is not None:
            self.language = language
            log.info("介面語言：%s → %s", language, i18n.set_language(language))
        config.save(enabled=self.enabled, language=self.language)
        log.info("Enabled: %s", sorted(self.enabled))
        self._update_views()
        for name in changed:
            if name == "claude":
                self.poller.refresh(name)
        if self.card.isVisible():
            self._refresh_on_view()

    def shutdown(self) -> None:
        for timer in self._timers + [self._hover_timer, self._resume_timer]:
            timer.stop()
        self.poller.shutdown()
        if self._settings is not None:
            self._settings.close()
        self.card.close()
        self.tray.close()


def run() -> int:
    """Start the tray with saved service and language settings."""
    mutex = win32tray.acquire_single_instance(MUTEX_NAME)
    if mutex is None:
        print("AI Quota Tray 已經在執行了", file=sys.stderr)
        return 1

    enabled = config.load_enabled(set(ALL))
    language = config.load_language()
    i18n.set_language(language)

    win32tray.set_app_id(APP_USER_MODEL_ID)  # 工作列用我們的圖示，不歸到 pythonw.exe
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 沒有任何 Qt 視窗也要常駐
    app.setWindowIcon(QIcon(str(icon.BRAND_PNG)))
    tray_app = TrayApp(enabled, language)
    app.aboutToQuit.connect(tray_app.shutdown)

    # 讓主控台 Ctrl+C 能結束：Qt 迴圈裡 Python 收不到訊號，靠計時器讓直譯器定期醒來
    signal.signal(signal.SIGINT, lambda *_: QApplication.quit())
    wake = QTimer()
    wake.timeout.connect(lambda: None)
    wake.start(500)

    return app.exec()  # mutex 留到行程結束才釋放
