"""設定視窗：每家勾「本機紀錄」或「API」。

版面照業主的設計稿（2026-09-25）：一張三欄表（服務｜本機紀錄｜API），
說明與風險全部收進底下可展開的「各資料來源的說明與限制」，預設收合。
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (QButtonGroup, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QRadioButton, QToolButton, QVBoxLayout,
                               QWidget)

from .config import HAS_LOCAL_SOURCE
from .icon import BRAND_PNG
from .model import DISPLAY_NAME

ORDER = ("claude", "codex", "grok")
LOCAL, API = 0, 1

HEADING = "選擇各服務的用量資料來源"
SUBTITLE = "每個服務只需選一種來源；可隨時回來更改。"
HELP_TOGGLE = "各資料來源的說明與限制"
HELP_TEXT = (
    "・<b>本機紀錄</b>：讀 CLI 留在本機的紀錄，不碰登入憑證；沒在用 CLI 時數字會停住。<br>"
    "・<b>API</b>：用 CLI 的登入 token 向伺服器查，隨時最新。<br>"
    "・⚠️ Claude 用 API 違反 Anthropic 使用條款，可能被封鎖。<br>"
    "・Grok 沒有本機紀錄，只能用 API；token 約 6 小時過期，過期請開一下 Grok CLI。"
)
CLAUDE_CONFIRM = (
    "Claude 改用 API 違反 Anthropic 使用條款（Free／Pro／Max 的登入 token 只能用在 "
    "Claude Code 與 claude.ai），曾經技術封鎖過，可能影響你的帳號。\n\n確定要改用 API 嗎？"
)

PALETTE = {
    "dark": {"bg": "#23262b", "panel": "#1d2025", "line": "#3a3f47", "text": "#e8eaed",
             "dim": "#9aa0a6", "accent": "#3b8fc4", "accent_hover": "#4a9fd4", "button": "#2f333a"},
    "light": {"bg": "#f6f7f9", "panel": "#ffffff", "line": "#d7dbe0", "text": "#1f2328",
              "dim": "#5f6368", "accent": "#1a73e8", "accent_hover": "#3b86ec", "button": "#e9ecef"},
}
CELL_MARGINS = (16, 9, 16, 9)


def _palette() -> dict[str, str]:
    dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return PALETTE["dark" if dark else "light"]


def _style(p: dict[str, str]) -> str:
    return f"""
        QDialog {{ background: {p['bg']}; }}
        QLabel {{ color: {p['text']}; }}
        QLabel#sub, QLabel#head, QLabel#unsupported, QLabel#help {{ color: {p['dim']}; }}
        QLabel#heading {{ font-size: 12pt; }}
        QFrame#table {{ background: {p['panel']}; border: 1px solid {p['line']}; border-radius: 8px; }}
        QFrame#line {{ background: {p['line']}; border: none; }}
        QToolButton#helpToggle {{ color: {p['dim']}; border: none; background: transparent; }}
        QToolButton#helpToggle:hover {{ color: {p['text']}; }}
        QPushButton {{ min-width: 88px; min-height: 30px; border-radius: 6px; padding: 0 14px;
                      color: {p['text']}; background: {p['button']}; border: 1px solid {p['line']}; }}
        QPushButton#save {{ color: white; background: {p['accent']}; border: none; }}
        QPushButton#save:hover {{ background: {p['accent_hover']}; }}
    """


def _cell(*widgets: QWidget, align=Qt.AlignCenter) -> QWidget:
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(*CELL_MARGINS)
    lay.setSpacing(10)
    lay.setAlignment(align)
    for wdg in widgets:
        lay.addWidget(wdg)
    return box


def _line() -> QFrame:
    line = QFrame()
    line.setObjectName("line")
    line.setFixedHeight(1)
    return line


class SettingsDialog(QDialog):
    def __init__(self, token_sources: set[str], on_apply: Callable[[set[str]], None]):
        super().__init__(None, Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("AI Quota Tray · 資料來源")
        self.setWindowIcon(QIcon(str(BRAND_PNG)))
        self.setStyleSheet(_style(_palette()))
        self.setFixedWidth(600)
        self._initial = set(token_sources)
        self._on_apply = on_apply
        self.groups: dict[str, QButtonGroup] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(6)
        heading = QLabel(HEADING)
        heading.setObjectName("heading")
        sub = QLabel(SUBTITLE)
        sub.setObjectName("sub")
        root.addWidget(heading)
        root.addWidget(sub)
        root.addSpacing(10)
        root.addWidget(self._table())

        root.addSpacing(8)
        self.help_toggle = QToolButton()
        self.help_toggle.setObjectName("helpToggle")
        self.help_toggle.setText(HELP_TOGGLE)
        self.help_toggle.setCheckable(True)
        self.help_toggle.setArrowType(Qt.RightArrow)
        self.help_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.help_toggle.toggled.connect(self._toggle_help)
        self.help = QLabel(HELP_TEXT)
        self.help.setObjectName("help")
        self.help.setWordWrap(True)
        self.help.setContentsMargins(18, 0, 0, 0)
        self.help.setVisible(False)
        root.addWidget(self.help_toggle, alignment=Qt.AlignLeft)
        root.addWidget(self.help)

        root.addSpacing(6)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        save = QPushButton("儲存")
        save.setObjectName("save")
        save.setDefault(True)
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        self.select(self._initial)

    def _table(self) -> QFrame:
        table = QFrame()
        table.setObjectName("table")
        grid = QGridLayout(table)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 2)

        for col, text in enumerate(("服務", "本機紀錄", "API")):
            head = QLabel(text)
            head.setObjectName("head")
            grid.addWidget(_cell(head, align=Qt.AlignLeft if col == 0 else Qt.AlignCenter), 0, col)

        row = 1
        for name in ORDER:
            grid.addWidget(_line(), row, 0, 1, 3)
            row += 1
            group = QButtonGroup(self)
            local, api = QRadioButton(), QRadioButton()
            local.setObjectName(f"{name}_local")
            api.setObjectName(f"{name}_api")
            local.setAccessibleName(f"{DISPLAY_NAME[name]} 本機紀錄")
            api.setAccessibleName(f"{DISPLAY_NAME[name]} API")
            group.addButton(local, LOCAL)
            group.addButton(api, API)
            self.groups[name] = group

            local_cell = [local]
            if not HAS_LOCAL_SOURCE[name]:
                local.setEnabled(False)
                note = QLabel("不支援")
                note.setObjectName("unsupported")
                local_cell.append(note)
            grid.addWidget(_cell(QLabel(DISPLAY_NAME[name]), align=Qt.AlignLeft), row, 0)
            grid.addWidget(_cell(*local_cell), row, 1)
            grid.addWidget(_cell(api), row, 2)
            row += 1
        return table

    def _toggle_help(self, shown: bool) -> None:
        self.help_toggle.setArrowType(Qt.DownArrow if shown else Qt.RightArrow)
        self.help.setVisible(shown)
        self.adjustSize()

    def select(self, token_sources: set[str]) -> None:
        for name, group in self.groups.items():
            use_api = name in token_sources or not HAS_LOCAL_SOURCE[name]
            group.button(API if use_api else LOCAL).setChecked(True)

    def selected(self) -> set[str]:
        return {name for name, group in self.groups.items() if group.checkedId() == API}

    def confirm_claude(self) -> bool:
        box = QMessageBox(QMessageBox.Warning, "AI Quota Tray", CLAUDE_CONFIRM,
                          QMessageBox.Yes | QMessageBox.No, self)
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes

    def accept(self) -> None:
        chosen = self.selected()
        if "claude" in chosen and "claude" not in self._initial and not self.confirm_claude():
            self.groups["claude"].button(LOCAL).setChecked(True)
            return  # 留在視窗上
        if chosen != self._initial:
            self._on_apply(chosen)
        super().accept()
