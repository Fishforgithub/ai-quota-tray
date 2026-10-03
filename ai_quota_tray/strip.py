"""工作列長條：釘選的另一種樣子（2026-10-03 業主：貼在工作列、平行一排，用量改成手機電量那樣的小電池）。

    ↻  Claude 5h [62] 週 [81]   Codex 5h [ 7] 週 [44]   …

- 貼著工作列上緣（業主選「緊貼工作列上方」：最穩定、不跟工作列搶 z-order。沒有嵌進 Explorer 的工作列——
  那樣我們一卡住，整條工作列也會跟著卡）。位置由 placement.dock_strip 算；只能左右拖，存右緣
  （內容變長時往左長，不會擠到系統匣那邊），拖到別的螢幕就貼那個螢幕的工作列。
- 每個視窗一顆小電池，剩餘 % 的數字塞在裡面；顏色門檻與卡片進度條共用（icon.level_for），過期變灰。
- 細節（倒數、錯誤原因）不放這裡，看系統匣圖示的 hover 卡片。長條上滑過、點一下都**不會**打開完整卡片
  （業主 2026-10-03：長條貼在工作列上方，滑鼠常經過，一碰就跳很煩），所以也不會因為滑過它就查雲端。
- 最左邊 ↻＝立即刷新（refresh_clicked），查詢中變灰、不能按。
- 浮在最上層、不搶焦點；全螢幕程式在前景時由 app 藏起來（跟桌面卡片一樣）。
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from . import placement
from .card import PROVIDER_NAME_COLOR, _rect, _theme, is_dimmed, is_failure, link_html
from .i18n import tr, window_label
from .icon import COLORS, level_for
from .model import DISPLAY_NAME, ProviderState

STRIP_HEIGHT = 28
BATTERY_W, BATTERY_H = 30, 15  # 電池本體；右邊再接一個小凸點
NUB_W, NUB_H = 2, 6
CLICK_SLOP_PX = 3  # 按下到放開移動不到這麼多＝點一下，不是拖


def text_on(fill: QColor) -> QColor:
    """電池填色上的數字：亮的底（黃、淺灰）用黑字，暗的底（綠、紅）用白字。"""
    luminance = 0.299 * fill.red() + 0.587 * fill.green() + 0.114 * fill.blue()
    return QColor("#202124") if luminance > 150 else QColor("#ffffff")


class Battery(QWidget):
    """手機電量樣式：外框＋右邊小凸點，裡面照剩餘 % 填色，數字塞在中間。
    數字壓在填色上的那段跟壓在空的那段用不同顏色（像手機那樣），哪一段都看得清楚。"""

    def __init__(self, remaining: float | None, fill: str, theme: dict[str, str]):
        super().__init__()
        self.setFixedSize(BATTERY_W + NUB_W, BATTERY_H)
        self.remaining = remaining
        self._fill = QColor(fill)
        self._theme = theme

    def text(self) -> str:
        return "—" if self.remaining is None else str(int(self.remaining))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        outline = QColor(self._theme["dim"])
        body = QRectF(0.5, 0.5, BATTERY_W - 1, BATTERY_H - 1)
        p.setPen(QPen(outline, 1))
        p.setBrush(QColor(self._theme["track"]))
        p.drawRoundedRect(body, 3, 3)
        p.setPen(Qt.NoPen)
        p.setBrush(outline)
        p.drawRoundedRect(QRectF(BATTERY_W, (BATTERY_H - NUB_H) / 2, NUB_W, NUB_H), 1, 1)

        inner = body.adjusted(1.5, 1.5, -1.5, -1.5)
        filled = QRectF(inner.x(), inner.y(), inner.width() * (self.remaining or 0) / 100, inner.height())
        if filled.width() > 0:
            p.setBrush(self._fill)
            p.drawRoundedRect(filled, 1.5, 1.5)

        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(10)
        p.setFont(font)
        split = filled.right() if filled.width() > 0 else 0
        p.setClipRect(QRectF(0, 0, split, self.height()))
        p.setPen(text_on(self._fill))
        p.drawText(body, Qt.AlignCenter, self.text())
        p.setClipRect(QRectF(split, 0, self.width() - split, self.height()))
        p.setPen(QColor(self._theme["text"]))
        p.drawText(body, Qt.AlignCenter, self.text())


class Strip(QWidget):
    refresh_clicked = Signal()  # 最左邊的 ↻
    menu_requested = Signal()  # 右鍵
    moved = Signal()  # 拖完放開（存位置用）

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(STRIP_HEIGHT)
        self._theme = _theme()
        self._right: int | None = None  # 右緣（邏輯像素）；None＝主螢幕靠右
        self._press_x: int | None = None  # 按下時滑鼠的 x（全域）；None＝沒在拖
        self._drag_dx = 0
        self._refreshing = False

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(8, 0, 10, 0)
        self._row.setSpacing(8)
        self._refresh = QLabel()
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 1.1)
        self._refresh.setFont(font)
        self._refresh.setTextFormat(Qt.RichText)
        self._refresh.linkActivated.connect(lambda _href: self.refresh_clicked.emit())
        self._row.addWidget(self._refresh)
        self._content: QWidget | None = None

        self._update_refresh()

    @property
    def right(self) -> int | None:
        return self._right

    # ---------- 內容 ----------

    def set_states(self, states: list[tuple[str, ProviderState | None]],
                   banner: str | None = None) -> None:
        """banner 有東西＝示範模式：最前面標一個紅色「示範」（完整說明在系統匣的 hover 卡片上）。"""
        self._theme = t = _theme()
        self._update_refresh()
        if self._content is not None:
            self._row.removeWidget(self._content)
            self._content.setParent(None)
            self._content.deleteLater()
        content = QWidget()
        row = QHBoxLayout(content)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        def label(text: str, color: str, bold: bool = False) -> QLabel:
            lbl = QLabel(text)
            font = QFont(self.font())
            font.setBold(bold)
            font.setPointSizeF(font.pointSizeF() * 0.9)
            lbl.setFont(font)
            lbl.setStyleSheet(f"color: {color}")
            return lbl

        if banner:
            row.addWidget(label(tr("strip.demo"), t["warn"], bold=True))
            row.addSpacing(6)
        if not states:
            row.addWidget(label("—", t["dim"]))
        for i, (name, state) in enumerate(states):
            if i:
                row.addSpacing(10)
            row.addWidget(label(DISPLAY_NAME.get(name, name), PROVIDER_NAME_COLOR, bold=True))
            failed = is_failure(state)  # 只是逾時（detail.timeout）不打驚嘆號
            if state is None or not state.windows:
                unlimited = state is not None and state.detail.get("unlimited")
                text = "!" if failed else "∞" if unlimited else "—"
                row.addWidget(label(text, t["warn"] if failed else t["dim"], bold=failed))
                continue
            dim = is_dimmed(state)
            for win in state.windows:
                remaining = win.remaining_pct
                fill = t["dim"] if dim or remaining is None else \
                    "#%02x%02x%02x" % COLORS[level_for(remaining)]
                row.addSpacing(2)
                row.addWidget(label(window_label(win.label), t["dim"]))
                row.addWidget(Battery(remaining, fill, t))
            if failed:  # 保留了上一次的數字，但這次沒查到（原因看完整卡片）
                row.addWidget(label("!", t["warn"], bold=True))

        self._content = content
        self._row.addWidget(content)
        if self.isVisible():
            content.show()  # 同 card.py：已顯示的視窗要先 show 新內容，adjustSize 才量得到
            self._dock()

    def set_refreshing(self, refreshing: bool) -> None:
        if refreshing != self._refreshing:
            self._refreshing = refreshing
            self._update_refresh()

    def _update_refresh(self) -> None:
        if self._refreshing:
            self._refresh.setText(f'<span style="color: {self._theme["dim"]}">↻</span>')
        else:
            self._refresh.setText(link_html("↻", self._theme["text"]))
        self._refresh.setToolTip(tr("card.refreshing" if self._refreshing else "menu.refresh"))

    # ---------- 位置 ----------

    def show_docked(self, right: int | None) -> None:
        self._right = right
        self._dock()
        self.show()

    def keep_docked(self) -> None:
        """工作列移動、解析度變了、螢幕拔掉：重新貼齊（app 定期叫，只是算一下位置）。"""
        if self._press_x is None:
            self._dock()

    def _dock(self) -> None:
        self.adjustSize()
        primary = QGuiApplication.primaryScreen()
        screens = [primary] + [s for s in QGuiApplication.screens() if s is not primary]
        x, y = placement.dock_strip(self._right, (self.width(), self.height()),
                                    [(_rect(s.geometry()), _rect(s.availableGeometry())) for s in screens])
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    # ---------- 滑鼠：左右拖、右鍵 ----------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press_x = round(event.globalPosition().x())
            self._drag_dx = self._press_x - self.x()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._press_x is not None and event.buttons() & Qt.LeftButton:
            x = round(event.globalPosition().x())
            if abs(x - self._press_x) >= CLICK_SLOP_PX:
                self.move(x - self._drag_dx, self.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._press_x is not None and event.button() == Qt.LeftButton:
            clicked = abs(round(event.globalPosition().x()) - self._press_x) < CLICK_SLOP_PX
            self._press_x = None
            event.accept()
            if clicked:
                self._dock()  # 只是點一下（晃了一兩個像素）：回原位，不存
                return
            self._right = self.x() + self.width()
            self._dock()  # 換螢幕就貼那個螢幕的工作列，出界就推回來
            self._right = self.x() + self.width()
            self.moved.emit()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        event.accept()
        self.menu_requested.emit()

    def hideEvent(self, event) -> None:
        self._press_x = None
        super().hideEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(self._theme["border"]), 1))
        p.setBrush(QColor(self._theme["bg"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
