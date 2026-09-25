"""系統匣常駐程式（P2 骨架）：Qt 主迴圈 + 原生系統匣 + 動態圖示 + 右鍵選單。

抓取頻率與畫面更新分離（原則 2）：
- 每家各自一個 QTimer 依 POLL_INTERVAL_S 抓；抓取在背景執行緒，結果用 signal 丟回主執行緒。
- 圖示每 ICON_REFRESH_S 秒依已有資料重畫一次，抓到新資料時也立即重畫。
"""
from __future__ import annotations

import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from . import icon, win32tray
from .model import ProviderState, utcnow
from .providers import ALL, fetch_one

log = logging.getLogger(__name__)

POLL_INTERVAL_S = {"claude": 120, "codex": 120, "grok": 300}
ICON_REFRESH_S = 30
MUTEX_NAME = "Local\\AiQuotaTray.SingleInstance"

MENU_REFRESH, MENU_QUIT = 1, 2


class Poller(QObject):
    """背景抓取。同一家還在抓就不重複送出。"""

    fetched = Signal(object)  # ProviderState

    def __init__(self, token_set: set[str]):
        super().__init__()
        self._token_set = token_set
        self._pool = ThreadPoolExecutor(max_workers=len(ALL), thread_name_prefix="poll")
        self._inflight: set[str] = set()

    def refresh(self, name: str) -> None:
        if name in self._inflight:
            return
        self._inflight.add(name)
        future = self._pool.submit(fetch_one, name, name in self._token_set, utcnow())
        # done callback 在背景執行緒跑；跨執行緒 emit 會自動排進主執行緒
        future.add_done_callback(lambda f, n=name: self.fetched.emit(f.result()))

    def done(self, name: str) -> None:
        self._inflight.discard(name)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


class TrayApp(QObject):
    def __init__(self, token_set: set[str]):
        super().__init__()
        self.states: dict[str, ProviderState] = {}
        self.tray = win32tray.TrayIcon(self._on_tray_event)
        self.icon_size = win32tray.small_icon_size()
        self.poller = Poller(token_set)
        self.poller.fetched.connect(self._on_fetched)

        self._timers = []
        for name in ALL:
            timer = QTimer(self)
            timer.setInterval(POLL_INTERVAL_S[name] * 1000)
            timer.timeout.connect(lambda n=name: self.poller.refresh(n))
            timer.start()
            self._timers.append(timer)
        self._icon_timer = QTimer(self)
        self._icon_timer.setInterval(ICON_REFRESH_S * 1000)
        self._icon_timer.timeout.connect(self.redraw)
        self._icon_timer.start()

        self.redraw()  # 先放一個灰色圖示，資料回來再換
        self.refresh_all()

    def refresh_all(self) -> None:
        for name in ALL:
            self.poller.refresh(name)

    def _on_fetched(self, state: ProviderState) -> None:
        self.poller.done(state.name)
        self.states[state.name] = state
        log.info("%s: %s %s", state.name, state.status,
                 [(w.label, w.remaining_pct) for w in state.windows] or state.error)
        self.redraw()

    def redraw(self) -> None:
        states = [self.states[n] for n in ALL if n in self.states]
        spec = icon.summarize(states)
        self.tray.set_icon(icon.render(spec, self.icon_size), self.icon_size)
        self.tray.set_tooltip(icon.tooltip(states))

    def _on_tray_event(self, kind: str, x: int, y: int) -> None:
        log.debug("tray event %s (%d, %d)", kind, x, y)
        if kind == "context_menu":
            cmd = self.tray.show_menu([(MENU_REFRESH, "立即刷新", True), (None, "", True),
                                       (MENU_QUIT, "結束", True)], x, y)
            if cmd == MENU_REFRESH:
                self.refresh_all()
            elif cmd == MENU_QUIT:
                QApplication.quit()
        elif kind == "quit":
            QApplication.quit()
        # popup_open / popup_close：P3 的 hover 卡片接在這裡

    def shutdown(self) -> None:
        for timer in self._timers + [self._icon_timer]:
            timer.stop()
        self.poller.shutdown()
        self.tray.close()


def run(token_set: set[str]) -> int:
    mutex = win32tray.acquire_single_instance(MUTEX_NAME)
    if mutex is None:
        print("AI Quota Tray 已經在執行了", file=sys.stderr)
        return 1

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 沒有任何 Qt 視窗也要常駐
    tray_app = TrayApp(token_set)
    app.aboutToQuit.connect(tray_app.shutdown)

    # 讓主控台 Ctrl+C 能結束：Qt 迴圈裡 Python 收不到訊號，靠計時器讓直譯器定期醒來
    signal.signal(signal.SIGINT, lambda *_: QApplication.quit())
    wake = QTimer()
    wake.timeout.connect(lambda: None)
    wake.start(500)

    return app.exec()  # mutex 留到行程結束才釋放
