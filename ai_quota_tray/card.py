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

from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from . import placement
from .icon import COLORS, level_for
from .model import (AUTH_EXPIRED, DISABLED, ERROR, STALE, ProviderState, Window,
                    format_age, format_countdown, utcnow)

DISPLAY_NAME = {"claude": "Claude", "codex": "Codex", "grok": "Grok"}
CLI_NAME = {"claude": "Claude Code", "codex": "Codex CLI", "grok": "Grok CLI"}

THEMES = {
    "dark": {"bg": "#202124", "border": "#3c4043", "text": "#e8eaed", "dim": "#9aa0a6",
             "track": "#3c4043", "warn": "#f28b82"},
    "light": {"bg": "#ffffff", "border": "#d0d4d9", "text": "#202124", "dim": "#5f6368",
              "track": "#e3e6ea", "warn": "#c5221f"},
}
CARD_WIDTH = 300
ERROR_TEXT_MAX = 60


def _theme() -> dict[str, str]:
    dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return THEMES["dark" if dark else "light"]


def _rect(r: QRect) -> placement.Rect:
    return r.x(), r.y(), r.x() + r.width(), r.y() + r.height()


def window_countdown(win: Window, state: ProviderState, now: datetime) -> str:
    if win.resets_at is None and win.label in state.detail.get("rolled_over", []):
        return "已重置"
    return format_countdown(win.resets_at, now)


def header_note(state: ProviderState, now: datetime) -> tuple[str, bool]:
    """區塊右上角的小字：(文字, 是否警示色)。"""
    if state.detail.get("api_error"):
        return "API 失敗，顯示本機紀錄", True
    if state.status == STALE:
        return format_age(state.fetched_at, now), False
    plan = state.detail.get("subscription_tier") or state.detail.get("plan_type")
    return (str(plan) if plan else ""), False


def status_message(state: ProviderState) -> str:
    if state.status == AUTH_EXPIRED:
        return f"Token 過期，請開一下 {CLI_NAME.get(state.name, 'CLI')}"
    if state.status == DISABLED:
        return "未啟用"
    if state.status == ERROR:
        err = state.error or "未知錯誤"
        return "抓取失敗：" + (err if len(err) <= ERROR_TEXT_MAX else err[:ERROR_TEXT_MAX] + "…")
    return "沒有額度資料"


class Bar(QWidget):
    """剩餘額度條：滿格＝剩 100%。"""

    def __init__(self, remaining: float | None, color: str, track: str):
        super().__init__()
        self.setFixedSize(110, 6)
        self._remaining, self._color, self._track = remaining, QColor(color), QColor(track)

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
        for i, (name, state) in enumerate(states):
            if i:
                grid.setRowMinimumHeight(row, 6)
                row += 1
            dim = state is not None and state.status == STALE
            text_c = t["dim"] if dim else t["text"]
            grid.addWidget(label(DISPLAY_NAME.get(name, name), text_c, bold=True), row, 0, 1, 2)
            note_lbl = label("", t["dim"], small=True, align=right)
            grid.addWidget(note_lbl, row, 2, 1, 2)
            row += 1

            if state is None:
                grid.addWidget(label("讀取中…", t["dim"], small=True), row, 0, 1, 4)
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
                grid.addWidget(label(win.label, text_c), row, 0)
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

            products = state.detail.get("products") or []
            if products:
                text = "、".join(f"{p['product']} {int(p['usage_pct'])}%" for p in products)
                grid.addWidget(label(f"已用佔比：{text}", t["dim"], small=True), row, 0, 1, 4)
                row += 1

        self._body = body
        self._outer.addWidget(body)
        if self.isVisible():
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
