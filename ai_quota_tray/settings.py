"""設定視窗：每家選「API」或「本機紀錄」，並說明預設值與改用 API 的風險。

右鍵選單只留「設定…」一個入口，保持乾淨（業主 2026-09-25 要求）。
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QDialog, QDialogButtonBox, QGroupBox, QLabel,
                               QMessageBox, QPushButton, QRadioButton, QVBoxLayout)

from .config import DEFAULT_TOKEN_SOURCES, HAS_LOCAL_SOURCE
from .model import DISPLAY_NAME

ORDER = ("claude", "codex", "grok")
LOCAL, API = 0, 1

INTRO = (
    "<b>本機紀錄</b>：讀各家 CLI 自己留在這台電腦上的紀錄，<b>不碰你的登入憑證</b>。<br>"
    "<b>API</b>：讀 CLI 登入後存下的 token，直接向該服務的伺服器查額度，數字隨時最新。"
    "本程式只讀取 token，不會更新它，也只送到該服務自己的伺服器。"
)

# (本機紀錄說明, API 說明, API 是否特別危險)
SOURCE_INFO = {
    "claude": (
        "Claude Code 開著時即時更新；沒開時停在最後一次，卡片會顯示「n 分鐘前」。"
        "需要 Claude Code 的 statusLine hook。",
        "隨時最新。⚠️ Anthropic 自 2026-02 起明文規定：Free／Pro／Max 的登入 token 用在 "
        "Claude Code、claude.ai 以外的工具即違反使用條款，而且曾經技術封鎖過，可能影響你的帳號。",
        True,
    ),
    "codex": (
        "只有在使用 Codex 時才會更新；閒置幾天的話數字會落後。",
        "隨時最新。使用 Codex CLI 的登入 token 查詢 ChatGPT 的非公開額度 API；"
        "OpenAI 對第三方工具這樣使用沒有明文說明。token 過期時請開一下 Codex CLI。",
        False,
    ),
    "grok": (
        "🚫 無法使用：Grok CLI 不在本機留下額度紀錄。",
        "唯一的取得方式。使用 Grok CLI 的登入 token 查詢額度；xAI 對第三方工具這樣使用沒有明文說明。"
        "token 效期約 6 小時，過期時卡片會提示「請開一下 Grok CLI」。",
        False,
    ),
}

CLAUDE_CONFIRM = (
    "你選了讓 Claude 使用 API。\n\n"
    "Anthropic 自 2026-02 起明文規定：Free／Pro／Max 的 OAuth token 用在 Claude Code、"
    "claude.ai 以外的任何工具都違反 Consumer ToS，而且曾經技術封鎖過。\n\n"
    "不開也能用：Claude 的數字會從 Claude Code 的 statusLine 取得。\n\n確定要改用 API 嗎？"
)


def default_label(name: str) -> str:
    return "API" if name in DEFAULT_TOKEN_SOURCES or not HAS_LOCAL_SOURCE[name] else "本機紀錄"


class SettingsDialog(QDialog):
    def __init__(self, token_sources: set[str], on_apply: Callable[[set[str]], None]):
        super().__init__(None, Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("AI Quota Tray 設定")
        self.setMinimumWidth(540)
        self._initial = set(token_sources)
        self._on_apply = on_apply
        self.groups: dict[str, QButtonGroup] = {}

        root = QVBoxLayout(self)
        title = QLabel("<b>資料來源</b>")
        root.addWidget(title)
        intro = QLabel(INTRO)
        intro.setWordWrap(True)
        root.addWidget(intro)

        for name in ORDER:
            local_text, api_text, dangerous = SOURCE_INFO[name]
            box = QGroupBox(f"{DISPLAY_NAME[name]}　（預設：{default_label(name)}）")
            lay = QVBoxLayout(box)
            group = QButtonGroup(self)
            for choice, label, text, warn in ((LOCAL, "本機紀錄", local_text, False),
                                              (API, "API", api_text, dangerous)):
                radio = QRadioButton(label)
                radio.setObjectName(f"{name}_{'api' if choice == API else 'local'}")
                group.addButton(radio, choice)
                desc = QLabel(text)
                desc.setWordWrap(True)
                desc.setContentsMargins(22, 0, 0, 6)  # 對齊單選按鈕的文字
                if warn:
                    desc.setStyleSheet("color: #d93025")
                if choice == LOCAL and not HAS_LOCAL_SOURCE[name]:
                    radio.setEnabled(False)
                    desc.setEnabled(False)
                lay.addWidget(radio)
                lay.addWidget(desc)
            self.groups[name] = group
            root.addWidget(box)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("確定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        reset = QPushButton("還原預設")
        buttons.addButton(reset, QDialogButtonBox.ResetRole)
        reset.clicked.connect(lambda: self.select(set(DEFAULT_TOKEN_SOURCES)))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.select(self._initial)

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
            return  # 留在視窗上讓使用者再看一次
        if chosen != self._initial:
            self._on_apply(chosen)
        super().accept()
