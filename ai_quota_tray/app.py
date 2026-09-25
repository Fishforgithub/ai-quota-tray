"""系統匣常駐程式：Qt 主迴圈 + 原生系統匣 + 動態圖示 + 右鍵選單 + hover 卡片。

抓取頻率與畫面更新分離（原則 2）：
- 每家各自一個 QTimer 依 POLL_INTERVAL_S 抓；抓取在背景執行緒，結果用 signal 丟回主執行緒。
- 系統匣一律顯示品牌圖示（業主決定），數字只在卡片；卡片開著時自己每秒重算倒數（card.py）。
- 睡眠喚醒後等 RESUME_DELAY_S 秒（網路通常還沒好）全部重抓。

P4：抓取失敗時保留上一次的數字（model.carry_over）；剩餘 < 10% 跳通知（alerts.py，
每個重置週期只一次）；右鍵選單切換各家 token 來源（config.py）與開機啟動（startup.py）。

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
from PySide6.QtWidgets import QApplication, QMessageBox

from . import config, icon, startup, win32tray
from .alerts import AlertStore
from .card import Card
from .model import ProviderState, carry_over, utcnow
from .providers import ALL, fetch_one

log = logging.getLogger(__name__)

POLL_INTERVAL_S = {"claude": 120, "codex": 120, "grok": 300}
RESUME_DELAY_S = 10
HOVER_CHECK_MS = 150
HIDE_DELAY_S = 0.4
HOVER_SLOP_PX = 6  # 實體像素：卡片邊緣外這麼近仍算在卡片上
MUTEX_NAME = "Local\\AiQuotaTray.SingleInstance"

MENU_REFRESH, MENU_QUIT, MENU_STARTUP = 1, 2, 3
# 「使用 API」選項：選單 id → provider
MENU_TOKEN = {11: "codex", 12: "grok", 13: "claude"}
TOKEN_LABEL = {
    "codex": "Codex 使用 API（較即時）",
    "grok": "Grok 使用 API（必要）",
    "claude": "Claude 使用 API（⚠️ 違反使用條款風險）",
}
CLAUDE_WARNING = (
    "Anthropic 自 2026-02 起明文規定：Free／Pro／Max 的 OAuth token 用在 Claude Code、"
    "claude.ai 以外的任何工具都違反 Consumer ToS，而且曾經技術封鎖過。\n\n"
    "不開也能用：Claude 的數字會從 Claude Code 的 statusLine 取得。\n\n確定要開啟嗎？"
)


class Poller(QObject):
    """背景抓取。同一家還在抓就不重複送出。"""

    fetched = Signal(object)  # ProviderState

    def __init__(self, token_set: set[str]):
        super().__init__()
        self.token_set = token_set
        self._pool = ThreadPoolExecutor(max_workers=len(ALL), thread_name_prefix="poll")
        self._inflight: set[str] = set()

    def refresh(self, name: str) -> None:
        if name in self._inflight:
            return
        self._inflight.add(name)
        future = self._pool.submit(fetch_one, name, name in self.token_set, utcnow())
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
        self.alerts = AlertStore()
        self.tray = win32tray.TrayIcon(self._on_tray_event)
        self.icon_size = win32tray.small_icon_size()
        self.tray.set_balloon_icon(icon.brand_png(win32tray.large_icon_size()),
                                   win32tray.large_icon_size())
        self.poller = Poller(set(token_set))
        self.poller.fetched.connect(self._on_fetched)

        self._timers = []
        for name in ALL:
            timer = QTimer(self)
            timer.setInterval(POLL_INTERVAL_S[name] * 1000)
            timer.timeout.connect(lambda n=name: self.poller.refresh(n))
            timer.start()
            self._timers.append(timer)

        self.card = Card()
        self._card_anchor: tuple[int, int, int, int] | None = None
        self._outside_since: float | None = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(HOVER_CHECK_MS)
        self._hover_timer.timeout.connect(self._check_hover)
        self._resume_timer = QTimer(self)  # 喚醒會連來兩個事件，用同一個計時器合併
        self._resume_timer.setSingleShot(True)
        self._resume_timer.setInterval(RESUME_DELAY_S * 1000)
        self._resume_timer.timeout.connect(self.refresh_all)

        self.tray.set_icon(icon.brand_png(self.icon_size), self.icon_size)
        self.refresh_all()

    @property
    def token_set(self) -> set[str]:
        return self.poller.token_set

    def refresh_all(self) -> None:
        for name in ALL:
            self.poller.refresh(name)

    def _on_fetched(self, state: ProviderState) -> None:
        self.poller.done(state.name)
        now = utcnow()
        state = carry_over(self.states.get(state.name), state, now)
        self.states[state.name] = state
        log.info("%s: %s %s", state.name, state.status,
                 [(w.label, w.remaining_pct) for w in state.windows] or state.error)
        self.tray.set_tooltip(icon.tooltip([self.states[n] for n in ALL if n in self.states]))
        if self.card.isVisible():
            self.card.set_states(self._card_states())
        due = self.alerts.take_due([state], now)
        if due:
            # 一次只能掛一則，同一家兩個視窗都低時合併
            self.tray.show_balloon(due[0][0], "\n".join(body for _, body in due))

    def _card_states(self) -> list[tuple[str, ProviderState | None]]:
        return [(name, self.states.get(name)) for name in ALL]

    # ---------- 卡片 ----------

    def show_card(self, x: int, y: int) -> None:
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
        tokens = [(mid, TOKEN_LABEL[name], True, name in self.token_set)
                  for mid, name in MENU_TOKEN.items()]
        return [(MENU_REFRESH, "立即刷新", True, False), sep, *tokens, sep,
                (MENU_STARTUP, "開機時啟動", True, startup.is_enabled()), sep,
                (MENU_QUIT, "關閉", True, False)]

    def _context_menu(self, x: int, y: int) -> None:
        self.handle_menu(self.tray.show_menu(self.menu_items(), x, y))

    def handle_menu(self, cmd: int | None) -> None:
        if cmd == MENU_REFRESH:
            self.refresh_all()
        elif cmd in MENU_TOKEN:
            self.toggle_token(MENU_TOKEN[cmd])
        elif cmd == MENU_STARTUP:
            if startup.is_enabled():
                startup.disable()
                log.info("已關閉開機啟動")
            else:
                log.info("已開啟開機啟動：%s", startup.enable())
        elif cmd == MENU_QUIT:
            QApplication.quit()

    def toggle_token(self, name: str) -> None:
        enabling = name not in self.token_set
        if enabling and name == "claude" and not self.confirm_claude_token():
            return
        self.token_set.symmetric_difference_update({name})
        config.save_token_sources(self.token_set)
        log.info("token 來源：%s", sorted(self.token_set) or "（全部不用）")
        self.poller.refresh(name)

    def confirm_claude_token(self) -> bool:
        box = QMessageBox(QMessageBox.Warning, "AI Quota Tray", CLAUDE_WARNING,
                          QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes

    def shutdown(self) -> None:
        for timer in self._timers + [self._hover_timer, self._resume_timer]:
            timer.stop()
        self.poller.shutdown()
        self.card.close()
        self.tray.close()


def run(cli_tokens: set[str] | None) -> int:
    """cli_tokens：命令列有給 --token 就用它並存進設定；沒給（None）就讀設定。"""
    mutex = win32tray.acquire_single_instance(MUTEX_NAME)
    if mutex is None:
        print("AI Quota Tray 已經在執行了", file=sys.stderr)
        return 1

    if cli_tokens is not None:
        config.save_token_sources(cli_tokens)
    token_set = config.load_token_sources(set(ALL))

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 沒有任何 Qt 視窗也要常駐
    app.setWindowIcon(QIcon(str(icon.BRAND_PNG)))
    tray_app = TrayApp(token_set)
    app.aboutToQuit.connect(tray_app.shutdown)

    # 讓主控台 Ctrl+C 能結束：Qt 迴圈裡 Python 收不到訊號，靠計時器讓直譯器定期醒來
    signal.signal(signal.SIGINT, lambda *_: QApplication.quit())
    wake = QTimer()
    wake.timeout.connect(lambda: None)
    wake.start(500)

    return app.exec()  # mutex 留到行程結束才釋放
