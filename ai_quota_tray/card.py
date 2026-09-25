"""Hover 卡片（CLAUDE.md §4）。

每家一個區塊，每個視窗一列：label｜進度條（剩餘）｜剩餘 %｜重置倒數。
- 資料過期（stale）→ 區塊變灰，右上顯示「n 分鐘前」。
- auth_expired / error / disabled 且沒有視窗 → 一行說明文字。
- 卡片開著時每秒重算倒數（原則 2：只存 resets_at，倒數本地算）。
不搶焦點：Qt.Tool + WindowDoesNotAcceptFocus + WA_ShowWithoutActivating。
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import placement
from .i18n import join, tr, window_label
from .icon import COLORS, level_for
from .model import (AUTH_EXPIRED, DISABLED, DISPLAY_NAME, ERROR, STALE, ProviderState, Window,
                    format_age, format_countdown, utcnow)

CLI_NAME = {"claude": "Claude Code", "codex": "Codex CLI",
            "antigravity": "Antigravity CLI"}
# token 不會自己過期、「開一下 CLI」也沒用的，另外寫提示（i18n key）
AUTH_HINT = {"antigravity": "card.auth_antigravity", "copilot": "card.auth_copilot"}

THEMES = {
    "dark": {"bg": "#202124", "border": "#3c4043", "text": "#e8eaed", "dim": "#9aa0a6",
             "track": "#3c4043", "warn": "#f28b82"},
    "light": {"bg": "#ffffff", "border": "#d0d4d9", "text": "#202124", "dim": "#5f6368",
              "track": "#e3e6ea", "warn": "#c5221f"},
}
CARD_WIDTH = 300
BAR_WIDTH, BAR_MIN_WIDTH = 110, 60
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


def status_message(state: ProviderState) -> str:
    if state.status == AUTH_EXPIRED:
        if state.name in AUTH_HINT:
            return tr(AUTH_HINT[state.name])
        return tr("card.auth_expired", cli=CLI_NAME.get(state.name, "CLI"))
    if state.status == DISABLED:
        return tr("card.disabled")
    if state.status == ERROR:
        err = state.error or tr("card.unknown_error")
        return tr("card.error", err=err if len(err) <= ERROR_TEXT_MAX else err[:ERROR_TEXT_MAX] + "…")
    if state.detail.get("unlimited"):  # 例如 Copilot 付費方案的 Chat／補全
        return unlimited_text(state.detail["unlimited"])
    return tr("card.no_data")


def unlimited_text(labels: list[str]) -> str:
    return tr("card.unlimited", items=join(window_label(x) for x in labels))


class Bar(QWidget):
    """剩餘額度條：滿格＝剩 100%。"""

    def __init__(self, remaining: float | None, color: str, track: str):
        super().__init__()
        # 平常 110 寬；label 比較長（英文的 Completions）時縮，否則右邊的 % 會壓到條上
        self.setFixedHeight(6)
        self.setMinimumWidth(BAR_MIN_WIDTH)
        self.setMaximumWidth(BAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._remaining, self._color, self._track = remaining, QColor(color), QColor(track)

    def sizeHint(self) -> QSize:
        return QSize(BAR_WIDTH, 6)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = QRectF(self.rect())
        p.setBrush(self._track)
        p.drawRoundedRect(r, 3, 3)
        if self._remaining:
            p.setBrush(self._color)
            p.drawRoundedRect(QRectF(0, 0, r.width() * self._remaining / 100, r.height()), 3, 3)


class Card(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(CARD_WIDTH)
        self._theme = _theme()
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(14, 12, 14, 12)
        self._body: QWidget | None = None
        self._tickers: list[Callable[[datetime], None]] = []
        self._anchor: placement.Rect | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    # ---------- 內容 ----------

    def set_states(self, states: list[tuple[str, ProviderState | None]]) -> None:
        now = utcnow()
        self._theme = t = _theme()
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
            grid.addWidget(label(DISPLAY_NAME.get(name, name), text_c, bold=True), row, 0, 1, 2)
            note_lbl = label("", t["dim"], small=True, align=right)
            grid.addWidget(note_lbl, row, 2, 1, 2)
            row += 1

            if state is None:
                grid.addWidget(label(tr("card.loading"), t["dim"], small=True), row, 0, 1, 4)
                row += 1
                continue

            def update_note(now, s=state, lbl=note_lbl):
                text, warn = header_note(s, now)
                lbl.setText(text)
                lbl.setStyleSheet(f"color: {t['warn'] if warn else t['dim']}")
            update_note(now)
            self._tickers.append(update_note)

            if not state.windows:
                warn = state.status in (AUTH_EXPIRED, ERROR)
                msg = label(status_message(state), t["warn"] if warn else t["dim"], small=True)
                msg.setWordWrap(True)
                grid.addWidget(msg, row, 0, 1, 4)
                row += 1
                continue

            for win in state.windows:
                remaining = win.remaining_pct
                color = t["dim"] if dim or remaining is None else \
                    "#%02x%02x%02x" % COLORS[level_for(remaining)]
                grid.addWidget(label(window_label(win.label), text_c), row, 0)
                grid.addWidget(Bar(remaining, color, t["track"]), row, 1, Qt.AlignVCenter)
                pct = "—" if remaining is None else f"{int(remaining)}%"
                grid.addWidget(label(pct, text_c, bold=True, align=right), row, 2)
                cd = label("", t["dim"], align=right)
                grid.addWidget(cd, row, 3)

                def update_cd(now, w=win, s=state, lbl=cd):
                    lbl.setText("↻ " + window_countdown(w, s, now))
                update_cd(now)
                self._tickers.append(update_cd)
                row += 1

            unlimited = state.detail.get("unlimited") or []
            if unlimited:
                grid.addWidget(label(unlimited_text(unlimited), t["dim"], small=True),
                               row, 0, 1, 4)
                row += 1

            if state.status in (AUTH_EXPIRED, ERROR):  # 保留了上一次的數字，但要說明為什麼沒更新
                msg = label(status_message(state), t["warn"], small=True)
                msg.setWordWrap(True)
                grid.addWidget(msg, row, 0, 1, 4)
                row += 1

        self._body = body
        self._outer.addWidget(body)
        if self.isVisible():
            # 加進已顯示的視窗時 Qt 是「排隊」才顯示新內容，不先 show 的話 adjustSize 只量到
            # 24px 高 → 卡片照小尺寸貼著工作列定位，內容長出來後下半截跑到螢幕外（2026-09-25 業主截圖）
            body.show()
            self._reposition()

    def _tick(self) -> None:
        now = utcnow()
        for tick in self._tickers:
            tick(now)

    # ---------- 顯示／定位 ----------

    def show_at(self, anchor_physical: placement.Rect) -> None:
        self._anchor = anchor_physical
        self._reposition()
        self._tick()
        self.show()
        self.raise_()
        self._timer.start()

    def _reposition(self) -> None:
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
        super().hideEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(self._theme["border"]), 1))
        p.setBrush(QColor(self._theme["bg"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
