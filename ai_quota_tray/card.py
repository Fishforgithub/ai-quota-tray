"""Hover 卡片（CLAUDE.md §4）。

每家一個區塊，每個視窗一列：label｜進度條（剩餘）｜剩餘 %｜重置倒數。
- 資料過期（stale）→ 區塊變灰，右上顯示「n 分鐘前」。
- auth_expired / error / disabled 且沒有視窗 → 一行說明文字。
- 卡片開著時每秒重算倒數（原則 2：只存 resets_at，倒數本地算）。
- 用量速度（進階設定，model.pace）：只在「照目前速度會在重置前用完」的那一列才出現
  （業主 2026-09-28 定：安全的不列）——進度條上畫一條刻度＝平均使用時這時候應剩多少，
  下面多一行「約 n 後用完」。
- 倒數欄靠左：↻ 要排成一直線（靠右時 04:20 與 2d01h 寬度不同，↻ 會錯開）。
- 頁尾右邊「釘選…／取消釘選」連結（pin_clicked；釘成卡片或工作列長條由 app 跳選單問）。
不搶焦點：Qt.Tool + WindowDoesNotAcceptFocus + WA_ShowWithoutActivating。

釘在桌面上的那一張（pinned=True，app.TrayApp.desk）用同一個類別，差在：不自動關、
可以用滑鼠拖（放開時 moved）、滑鼠移進來發 hovered（app 這時才查雲端）、右鍵發 menu_requested；
頁尾左邊多一個一直顯示的「立即刷新」（refresh_clicked，業主要的：不用再按右鍵），查詢中變「更新中…」；
右邊的「取消釘選」平常藏著（保留位置，不會一 hover 就變高），滑鼠移進來才出現。
一樣浮在最上層（業主 2026-10-03 定），全螢幕程式在前景時由 app 藏起來。
另一種釘選樣子（工作列長條）在 strip.py。
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import placement
from .i18n import join, tr, window_label
from .icon import COLORS, level_for
from .model import (AUTH_EXPIRED, DISABLED, DISPLAY_NAME, ERROR, OK, PREPARING, STALE, Pace,
                    ProviderState, Window, format_age, format_countdown, pace, parse_time, utcnow)

CLI_NAME = {"claude": "Claude Code", "codex": "Codex CLI",
            "antigravity": "Antigravity CLI", "grok": "Grok Build CLI"}
# token 不會自己過期、「開一下 CLI」也沒用的，另外寫提示（i18n key）
AUTH_HINT = {"antigravity": "card.auth_antigravity", "copilot": "card.auth_copilot",
             "grok": "card.auth_grok"}

THEMES = {
    "dark": {"bg": "#202124", "border": "#3c4043", "text": "#e8eaed", "dim": "#9aa0a6",
             "track": "#3c4043", "warn": "#f28b82"},
    "light": {"bg": "#ffffff", "border": "#d0d4d9", "text": "#202124", "dim": "#5f6368",
              "track": "#e3e6ea", "warn": "#c5221f"},
}
CARD_WIDTH = 300
PROVIDER_NAME_COLOR = "#00BFFF"
BAR_WIDTH, BAR_MIN_WIDTH = 110, 60
BAR_HEIGHT, TICK_HEIGHT = 6, 10  # 刻度比條高一點，條在中間
ERROR_TEXT_MAX = 60


def _theme() -> dict[str, str]:
    dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return THEMES["dark" if dark else "light"]


def _rect(r: QRect) -> placement.Rect:
    return r.x(), r.y(), r.x() + r.width(), r.y() + r.height()


def window_countdown(win: Window, state: ProviderState, now: datetime) -> str:
    if win.resets_at is None and win.label in state.detail.get("rolled_over", []):
        return tr("card.rolled_over")
    countdown = format_countdown(win.resets_at, now)
    if win.label in state.detail.get("estimated_resets", []):
        return tr("card.estimated_reset", countdown=countdown)
    return countdown


def header_note(state: ProviderState, now: datetime) -> tuple[str, bool]:
    """區塊右上角的小字：(文字, 是否警示色)。"""
    if state.detail.get("api_error"):
        return tr("card.api_failed"), True
    if is_dimmed(state):
        return format_age(state.fetched_at, now), False
    plan = state.detail.get("subscription_tier") or state.detail.get("plan_type")
    return (str(plan) if plan else ""), False


def is_dimmed(state: ProviderState | None) -> bool:
    """資料不是剛抓到的：檔案來源過期，或這次失敗、顯示的是上一次的數字（model.carry_over）。"""
    if state is None:
        return False
    return state.status == STALE or (state.status in (AUTH_EXPIRED, ERROR) and bool(state.windows))


def is_failure(state: ProviderState | None) -> bool:
    """要用紅字提醒的失敗。只是查詢逾時（detail.timeout，例如 agy 偶爾卡住）不算：灰字說稍後再試就好。"""
    return state is not None and state.status in (AUTH_EXPIRED, ERROR) and not state.detail.get("timeout")


def status_message(state: ProviderState) -> str:
    if state.status == AUTH_EXPIRED:
        if state.name in AUTH_HINT:
            return tr(AUTH_HINT[state.name])
        return tr("card.auth_expired", cli=CLI_NAME.get(state.name, "CLI"))
    if state.status == DISABLED:
        return tr("card.disabled")
    if state.status == PREPARING:
        return tr("card.preparing")
    if state.status == ERROR and state.detail.get("needs_hook"):
        return tr("card.claude_needs_hook")
    if state.status == ERROR and state.detail.get("timeout"):
        return tr("card.timeout")
    if state.status == ERROR:
        err = state.error or tr("card.unknown_error")
        return tr("card.error", err=err if len(err) <= ERROR_TEXT_MAX else err[:ERROR_TEXT_MAX] + "…")
    if state.detail.get("unlimited"):  # 例如 Copilot 付費方案的 Chat／補全
        return unlimited_text(state.detail["unlimited"])
    return tr("card.no_data")


def window_pace(win: Window, state: ProviderState) -> Pace | None:
    """只估確定是真數字的（ok / stale）；失敗後保留的舊數字不估。以數字量到的時間為準。"""
    if state.status not in (OK, STALE):
        return None
    return pace(win, state.fetched_at or utcnow())


def unlimited_text(labels: list[str]) -> str:
    return tr("card.unlimited", items=join(window_label(x) for x in labels))


class Bar(QWidget):
    """剩餘額度條：滿格＝剩 100%。expected（用量速度）給了就在那個位置畫一條刻度。"""

    def __init__(self, remaining: float | None, color: str, track: str,
                 expected: float | None = None, tick: str | None = None):
        super().__init__()
        # 平常 110 寬；label 比較長（英文的 Completions）時縮，否則右邊的 % 會壓到條上
        self.setFixedHeight(TICK_HEIGHT if expected is not None else BAR_HEIGHT)
        self.setMinimumWidth(BAR_MIN_WIDTH)
        self.setMaximumWidth(BAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._remaining, self._color, self._track = remaining, QColor(color), QColor(track)
        self.expected = expected
        self._tick = QColor(tick or color)

    def sizeHint(self) -> QSize:
        return QSize(BAR_WIDTH, self.height())

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        w, h = self.width(), self.height()
        r = QRectF(0, (h - BAR_HEIGHT) / 2, w, BAR_HEIGHT)
        p.setBrush(self._track)
        p.drawRoundedRect(r, 3, 3)
        if self._remaining:
            p.setBrush(self._color)
            p.drawRoundedRect(QRectF(0, r.y(), w * self._remaining / 100, BAR_HEIGHT), 3, 3)
        if self.expected is not None:
            x = min(max(w * self.expected / 100, 1), w - 1)
            p.setBrush(self._tick)
            p.drawRoundedRect(QRectF(x - 1, 0, 2, h), 1, 1)


def link_html(text: str, color: str) -> str:
    return f'<a href="#" style="color: {color}; text-decoration: none">{text}</a>'


def footer_label(font: QFont, align: Qt.AlignmentFlag, on_click: Callable[[], None]) -> QLabel:
    """頁尾的小字連結。藏起來時保留位置，卡片才不會一 hover 就變高。"""
    lbl = QLabel()
    small = QFont(font)
    small.setPointSizeF(small.pointSizeF() * 0.9)
    lbl.setFont(small)
    lbl.setAlignment(align | Qt.AlignVCenter)
    lbl.setTextFormat(Qt.RichText)
    lbl.linkActivated.connect(lambda _href: on_click())
    policy = lbl.sizePolicy()
    policy.setRetainSizeWhenHidden(True)
    lbl.setSizePolicy(policy)
    return lbl


class Card(QWidget):
    pin_clicked = Signal()  # 頁尾右邊的「釘選…／取消釘選」
    refresh_clicked = Signal()  # 以下只有 pinned：頁尾左邊的「立即刷新」
    hovered = Signal()  # 滑鼠移進卡片
    menu_requested = Signal()  # 在卡片上按右鍵
    moved = Signal()  # 拖完放開（存位置用）

    def __init__(self, pinned: bool = False):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(CARD_WIDTH)
        self.pinned = pinned
        self._theme = _theme()
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(14, 12, 14, 12)
        self._body: QWidget | None = None
        self._tickers: list[Callable[[datetime], None]] = []
        self._anchor: placement.Rect | None = None
        self._drag_offset: QPoint | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        # 頁尾：左「立即刷新」（只有釘著的那張，一直顯示——不用再按右鍵）、右「釘選…／取消釘選」
        self._pin_on = pinned  # True＝右邊顯示「取消釘選」
        self._refreshing = False  # True＝左邊顯示「更新中…」（不能按）
        footer = QWidget()
        row = QHBoxLayout(footer)
        row.setContentsMargins(0, 0, 0, 0)
        self._refresh_link = footer_label(self.font(), Qt.AlignLeft, self.refresh_clicked.emit)
        self._pin_link = footer_label(self.font(), Qt.AlignRight, self.pin_clicked.emit)
        row.addWidget(self._refresh_link)
        row.addStretch(1)
        row.addWidget(self._pin_link)
        self._outer.addWidget(footer)
        if pinned:
            self._pin_link.hide()  # 滑鼠移進來才出現
        else:
            self._refresh_link.hide()  # hover 卡片一打開就會查，不需要
        self._update_footer()

    # ---------- 內容 ----------

    def set_states(self, states: list[tuple[str, ProviderState | None]],
                   banner: str | None = None, show_pace: bool = False,
                   waiting: set[str] | frozenset[str] = frozenset()) -> None:
        """banner：卡片最上方的一行提示（示範模式用，標明這些不是真的數字）。
        show_pace：進階設定的「顯示用量速度」。
        waiting：還沒有資料、也沒在查的服務（釘在桌面時，雲端來源要滑鼠移進來才查）。"""
        now = utcnow()
        self._theme = t = _theme()
        self._update_footer()  # 語言、深淺色可能換了
        if self._body is not None:
            self._outer.removeWidget(self._body)
            self._body.setParent(None)  # 立即脫離，不等 deleteLater 才消失
            self._body.deleteLater()
        self._tickers = []
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(1, 1)

        def label(text: str, color: str, *, bold=False, small=False,
                  align=Qt.AlignLeft | Qt.AlignVCenter) -> QLabel:
            lbl = QLabel(text)
            font = QFont(self.font())
            font.setBold(bold)
            if small:
                font.setPointSizeF(font.pointSizeF() * 0.9)
            lbl.setFont(font)
            lbl.setStyleSheet(f"color: {color}")
            lbl.setAlignment(align)
            return lbl

        right = Qt.AlignRight | Qt.AlignVCenter
        row = 0
        if banner:
            note = label(banner, t["warn"], bold=True, small=True)
            note.setWordWrap(True)
            grid.addWidget(note, row, 0, 1, 4)
            row += 1
            grid.setRowMinimumHeight(row, 4)
            row += 1
        if not states:
            msg = label(tr("card.nothing_enabled"), t["dim"], small=True)
            msg.setWordWrap(True)
            grid.addWidget(msg, row, 0, 1, 4)
        for i, (name, state) in enumerate(states):
            if i:
                grid.setRowMinimumHeight(row, 6)
                row += 1
            dim = is_dimmed(state)
            text_c = t["dim"] if dim else t["text"]
            grid.addWidget(label(DISPLAY_NAME.get(name, name), PROVIDER_NAME_COLOR, bold=True),
                           row, 0, 1, 2)
            note_lbl = label("", t["dim"], small=True, align=right)
            grid.addWidget(note_lbl, row, 2, 1, 2)
            row += 1

            if state is None:
                text = tr("card.hover_to_load" if name in waiting else "card.loading")
                grid.addWidget(label(text, t["dim"], small=True), row, 0, 1, 4)
                row += 1
                continue

            def update_note(now, s=state, lbl=note_lbl):
                text, warn = header_note(s, now)
                lbl.setText(text)
                lbl.setStyleSheet(f"color: {t['warn'] if warn else t['dim']}")
            update_note(now)
            self._tickers.append(update_note)

            if not state.windows:
                msg = label(status_message(state), t["warn"] if is_failure(state) else t["dim"], small=True)
                msg.setWordWrap(True)
                grid.addWidget(msg, row, 0, 1, 4)
                row += 1
                continue

            for win in state.windows:
                remaining = win.remaining_pct
                color = t["dim"] if dim or remaining is None else \
                    "#%02x%02x%02x" % COLORS[level_for(remaining)]
                speed = window_pace(win, state) if show_pace else None
                if speed is not None and speed.runs_out_at is None:
                    speed = None  # 撐得到重置：不畫刻度也不提醒
                grid.addWidget(label(window_label(win.label), text_c), row, 0)
                grid.addWidget(Bar(remaining, color, t["track"],
                                   speed.expected_remaining_pct if speed else None, text_c),
                               row, 1, Qt.AlignVCenter)
                pct = "—" if remaining is None else f"{int(remaining)}%"
                grid.addWidget(label(pct, text_c, bold=True, align=right), row, 2)
                cd = label("", t["dim"])
                grid.addWidget(cd, row, 3)

                def update_cd(now, w=win, s=state, lbl=cd):
                    lbl.setText("↻ " + window_countdown(w, s, now))
                update_cd(now)
                self._tickers.append(update_cd)
                row += 1

                if speed and speed.runs_out_at and speed.runs_out_at > now:
                    runs = label("", t["dim"] if dim else t["warn"], small=True)
                    grid.addWidget(runs, row, 0, 1, 4)

                    def update_runs(now, at=speed.runs_out_at, lbl=runs):
                        lbl.setText(tr("card.pace_runs_out", countdown=format_countdown(at, now)))
                    update_runs(now)
                    self._tickers.append(update_runs)
                    row += 1

            count = state.detail.get("reset_credits_count") if name == "codex" else None
            if isinstance(count, int) and count >= 0:
                grid.addWidget(label(tr("card.reset_credits", count=count), text_c, small=True),
                               row, 0, 1, 4)
                row += 1
                if count:
                    expiry = parse_time(state.detail.get("reset_credits_next_expiry"))
                    expiry_text = (tr("card.reset_credits_expiry",
                                      date=expiry.astimezone().strftime("%Y/%m/%d %H:%M"))
                                   if expiry else tr("card.reset_credits_expiry_unknown"))
                    grid.addWidget(label(expiry_text, text_c, small=True), row, 0, 1, 4)
                    row += 1

            unlimited = state.detail.get("unlimited") or []
            if unlimited:
                grid.addWidget(label(unlimited_text(unlimited), t["dim"], small=True),
                               row, 0, 1, 4)
                row += 1

            if state.status in (AUTH_EXPIRED, ERROR):  # 保留了上一次的數字，但要說明為什麼沒更新
                msg = label(status_message(state), t["warn"] if is_failure(state) else t["dim"], small=True)
                msg.setWordWrap(True)
                grid.addWidget(msg, row, 0, 1, 4)
                row += 1

        self._body = body
        self._outer.insertWidget(0, body)  # 頁尾連結固定在最下面
        if self.isVisible():
            # 加進已顯示的視窗時 Qt 是「排隊」才顯示新內容，不先 show 的話 adjustSize 只量到
            # 24px 高 → 卡片照小尺寸貼著工作列定位，內容長出來後下半截跑到螢幕外（2026-09-25 業主截圖）
            body.show()
            self._reposition()

    def _tick(self) -> None:
        now = utcnow()
        for tick in self._tickers:
            tick(now)

    def set_pin_state(self, pinned: bool) -> None:
        """hover 卡片的頁尾：已經釘著（卡片或長條）就顯示「取消釘選」，否則「釘選…」。"""
        self._pin_on = pinned
        self._update_footer()

    def set_refreshing(self, refreshing: bool) -> None:
        """還有服務在查：「立即刷新」換成「更新中…」，查完換回來。"""
        if refreshing != self._refreshing:
            self._refreshing = refreshing
            self._update_footer()

    def _update_footer(self) -> None:
        dim = self._theme["dim"]
        self._pin_link.setText(link_html(tr("card.unpin" if self._pin_on else "card.pin"), dim))
        if self._refreshing:
            self._refresh_link.setText(f'<span style="color: {dim}">{tr("card.refreshing")}</span>')
        else:
            self._refresh_link.setText(link_html("↻ " + tr("menu.refresh"), dim))

    # ---------- 顯示／定位 ----------

    def show_at(self, anchor_physical: placement.Rect) -> None:
        self._anchor = anchor_physical
        self._reposition()
        self._tick()
        self.show()
        self.raise_()
        self._timer.start()

    def show_pinned(self, pos: tuple[int, int] | None) -> None:
        """釘在桌面：pos＝左上角（邏輯像素），None＝主螢幕右下角；放不進螢幕的會拉回來。"""
        self._place_pinned(pos)
        self._tick()
        self.show()
        self._timer.start()

    def keep_on_screen(self) -> None:
        """螢幕拔掉、內容變高之後：整張拉回螢幕裡。"""
        self._place_pinned((self.x(), self.y()))

    def _place_pinned(self, pos: tuple[int, int] | None) -> None:
        self.adjustSize()
        primary = QGuiApplication.primaryScreen()
        x, y = placement.keep_on_screen(
            pos, (self.width(), self.height()),
            [_rect(s.availableGeometry()) for s in QGuiApplication.screens()],
            _rect(primary.availableGeometry()))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def _reposition(self) -> None:
        if self.pinned:
            self.keep_on_screen()
            return
        if self._anchor is None:
            return
        screens = [placement.Screen(_rect(s.geometry()), _rect(s.availableGeometry()),
                                    s.devicePixelRatio()) for s in QGuiApplication.screens()]
        anchor, screen = placement.physical_to_logical(self._anchor, screens)
        self.adjustSize()
        x, y = placement.place(anchor, (self.width(), self.height()), screen.available)
        self.move(x, y)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        self._drag_offset = None
        super().hideEvent(event)

    # ---------- 釘在桌面：拖曳、右鍵、滑鼠移入 ----------
    # 自己算位移而不用 startSystemMove：無邊框的 Tool 視窗沒有系統選單，Qt 那條路可能直接回 False

    def mousePressEvent(self, event) -> None:
        if self.pinned and event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_offset is not None and event.button() == Qt.LeftButton:
            self._drag_offset = None
            self.keep_on_screen()  # 拖到螢幕外就推回來
            self.moved.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        if self.pinned:
            event.accept()
            self.menu_requested.emit()
            return
        super().contextMenuEvent(event)

    def enterEvent(self, event) -> None:
        if self.pinned:
            self._pin_link.show()
            self.hovered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self.pinned:
            self._pin_link.hide()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(self._theme["border"]), 1))
        p.setBrush(QColor(self._theme["bg"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
