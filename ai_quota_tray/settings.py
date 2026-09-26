"""設定視窗：服務啟用勾選、語言、示範模式，以及 Claude 狀態列擷取的安裝／移除。

Claude 那一列右邊的按鈕會「立刻」安裝或移除 hook（claude_hook.py），不等按儲存：
它改的是 Claude Code 的設定檔，不是我們的，按下去時先跳確認視窗說清楚會改什麼。
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QRect, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from . import claude_hook, display_version, i18n, store_update
from .i18n import tr
from .icon import ASSETS, BRAND_PNG
from .model import DISPLAY_NAME
from .providers import ALL

ORDER = tuple(ALL)

PALETTE = {
    "dark": {"bg": "#23262b", "panel": "#1d2025", "line": "#3a3f47", "text": "#e8eaed",
             "dim": "#9aa0a6", "accent": "#3b8fc4", "accent_hover": "#4a9fd4", "button": "#2f333a",
             "chevron": "chevron-down-dark.svg"},
    "light": {"bg": "#f6f7f9", "panel": "#ffffff", "line": "#d7dbe0", "text": "#1f2328",
              "dim": "#5f6368", "accent": "#1a73e8", "accent_hover": "#3b86ec", "button": "#e9ecef",
              "chevron": "chevron-down-light.svg"},
}
STORE_URL = "https://apps.microsoft.com/detail/9MVGRHJJHX0M"
# 設定視窗底部的連結（隱私權政策 §3「其他連線」有列）；英文介面開 /en/ 那一份
SITE_LINKS = {
    "privacy": {i18n.ZH: "https://fish-zero.com/aiusagemeter-privacy",
                i18n.EN: "https://fish-zero.com/en/aiusagemeter-privacy"},
    "website": {i18n.ZH: "https://fish-zero.com/aiusagemeter",
                i18n.EN: "https://fish-zero.com/en/aiusagemeter"},
}
DESKPET_BANNER = ASSETS / "deskpet-banner.webp"


def _palette() -> dict[str, str]:
    dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return PALETTE["dark" if dark else "light"]


def _style(p: dict[str, str]) -> str:
    return f"""
        QDialog {{ background: {p['bg']}; }}
        QLabel, QCheckBox {{ color: {p['text']}; }}
        QCheckBox:disabled {{ color: {p['dim']}; }}
        QLabel#sub, QLabel#head, QLabel#sourceDescription, QLabel#langLabel {{
            color: {p['dim']}; }}
        QLabel#heading {{ font-size: 12pt; }}
        QFrame#table {{ background: {p['panel']}; border: 1px solid {p['line']}; border-radius: 8px; }}
        QFrame#line {{ background: {p['line']}; border: none; }}
        QComboBox {{ min-height: 28px; padding: 0 4px 0 10px; border-radius: 6px; color: {p['text']};
                    background: {p['button']}; border: 1px solid {p['line']}; }}
        QComboBox:hover {{ border-color: {p['dim']}; }}
        /* 只改外框的話，右邊的下拉鈕還是 Windows 原生的方塊，會凸出一截（2026-09-26 業主回報）。
           改成透明、無邊框的區塊，箭頭用自己的 SVG，外觀才會跟 desk-pet 的網頁下拉一樣是一整塊圓角。 */
        QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right;
                               width: 26px; border: none; background: transparent; }}
        QComboBox::down-arrow {{ image: url({(ASSETS / p['chevron']).as_posix()}); width: 12px; height: 12px; }}
        QComboBox QAbstractItemView {{ color: {p['text']}; background: {p['panel']}; outline: 0;
                                      border: 1px solid {p['line']}; padding: 4px;
                                      selection-background-color: {p['accent']}; }}
        QPushButton {{ min-width: 88px; min-height: 30px; border-radius: 6px; padding: 0 14px;
                      color: {p['text']}; background: {p['button']}; border: 1px solid {p['line']}; }}
        QPushButton#cancel, QPushButton#save {{ min-width: 116px; min-height: 38px; }}
        QPushButton#hookButton {{ min-width: 64px; padding: 0 10px; }}  /* 預設 88px 會把說明擠成兩行 */
        QPushButton#save {{ color: white; background: {p['accent']}; border: none; }}
        QPushButton#save:hover {{ background: {p['accent_hover']}; }}
        QFrame#promo {{ background: #1c2948; border: 1px solid #60729b; border-radius: 9px; }}
        QLabel#promoEyebrow {{ color: #b9caec; font-size: 8pt; font-weight: bold; }}
        QLabel#promoTitle {{ color: #ffffff; font-size: 11pt; font-weight: bold; }}
        QLabel#promoBody {{ color: #d8e2f7; font-size: 9pt; }}
        QPushButton#promoButton {{ color: #30220c; background: #ffd77e; border: none;
                                  border-radius: 6px; font-weight: bold; min-width: 0;
                                  min-height: 34px; padding: 0 8px; }}
        QPushButton#promoButton:hover {{ background: #ffe5aa; }}
        QPushButton#updateButton {{ color: white; background: {p['accent']}; border: none;
                                   font-weight: bold; min-width: 0; padding: 0 16px; }}
        QPushButton#updateButton:hover {{ background: {p['accent_hover']}; }}
        QLabel#links, QLabel#disclaimer {{ color: {p['dim']}; font-size: 8pt; }}
    """


def _line() -> QFrame:
    line = QFrame()
    line.setObjectName("line")
    line.setFixedHeight(1)
    return line


class SettingsDialog(QDialog):
    def __init__(self, enabled: set[str], language: str,
                 on_apply: Callable[[set[str], str, bool], None], demo: bool = False,
                 update_available: bool = False):
        super().__init__(None, Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowIcon(QIcon(str(BRAND_PNG)))
        self.setStyleSheet(_style(_palette()))
        # Windows 的標題列約 37px；原本 client 高 653px 對應參考圖的外框約 690px，
        # 2026-09-26 多了底部連結那一行（＋約 30px）。
        self.setFixedSize(590, 683)
        self._initial_enabled = set(enabled)
        self._initial_language = language if language in i18n.LANGUAGES else i18n.AUTO
        self._initial_demo = demo
        self._on_apply = on_apply
        self._hook_status = claude_hook.status()
        self.checks: dict[str, QCheckBox] = {}
        self._texts: list[tuple[QLabel | QPushButton, str]] = []  # (元件, i18n key)

        root = QVBoxLayout(self)
        root.setContentsMargins(31, 27, 31, 24)
        root.setSpacing(0)
        head = QHBoxLayout()
        head.addWidget(self._text(QLabel(), "settings.heading", "heading"))
        head.addStretch(1)
        # Store 查到有新版才出現（store_update.py），按下去開 Store 商品頁讓使用者按更新
        self.update_button = self._text(QPushButton(), "settings.update", "updateButton")
        self.update_button.setCursor(Qt.PointingHandCursor)
        self.update_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(store_update.STORE_PDP_URI)))
        self.update_button.setVisible(update_available)
        head.addWidget(self.update_button)
        root.addLayout(head)
        root.addSpacing(7)

        top = QHBoxLayout()
        top.setSpacing(9)
        top.addWidget(self._text(QLabel(), "settings.subtitle", "sub"))
        top.addStretch(1)
        top.addWidget(self._text(QLabel(), "settings.language", "langLabel"))
        self.language = QComboBox()
        self.language.setObjectName("language")
        # 依最長的選項決定寬度：寫死 108 時英文的「System default」會被切掉
        self.language.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.language.setMinimumWidth(108)
        for code in i18n.LANGUAGES:
            self.language.addItem(i18n.NATIVE_NAMES.get(code, ""), code)
        self.language.setCurrentIndex(i18n.LANGUAGES.index(self._initial_language))
        self.language.currentIndexChanged.connect(self._retranslate)
        top.addWidget(self.language)
        root.addLayout(top)

        root.addSpacing(14)
        root.addWidget(self._table())
        root.addSpacing(28)
        root.addWidget(self._promo())

        root.addSpacing(10)
        # 隱私權政策、官網與無隸屬聲明：畫面上直接出現各家產品名，要說清楚我們不是官方
        footer = QHBoxLayout()
        self.links = QLabel()
        self.links.setObjectName("links")
        self.links.setTextFormat(Qt.RichText)
        self.links.setOpenExternalLinks(True)
        footer.addWidget(self.links)
        footer.addStretch(1)
        footer.addWidget(self._text(QLabel(), "settings.disclaimer", "disclaimer"))
        root.addLayout(footer)

        root.addSpacing(14)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        # 給 Store 審核人員、或還沒裝任何 CLI 的人先看看長什麼樣子（demo.py）
        self.demo_check = self._text(QCheckBox(), "settings.demo", "demoCheck")
        self.demo_check.setChecked(demo)
        buttons.addWidget(self.demo_check)
        buttons.addStretch(1)
        cancel = self._text(QPushButton(), "settings.cancel", "cancel")
        cancel.setFixedWidth(147)
        cancel.clicked.connect(self.reject)
        save = self._text(QPushButton(), "settings.save", "save")
        save.setFixedWidth(145)
        save.setDefault(True)
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        self.select(self._initial_enabled)
        self._retranslate()

    def _text(self, widget, key: str, name: str | None = None):
        """登記一個要跟著語言換字的元件。"""
        if name:
            widget.setObjectName(name)
        self._texts.append((widget, key))
        return widget

    def _table(self) -> QFrame:
        table = QFrame()
        table.setObjectName("table")
        table.setFixedHeight(260)
        rows = QVBoxLayout(table)
        rows.setContentsMargins(1, 1, 1, 1)
        rows.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(43)
        head_layout = QHBoxLayout(header)
        head_layout.setContentsMargins(20, 0, 20, 0)
        head_layout.setSpacing(5)
        service_head = self._text(QLabel(), "settings.col.service", "head")
        service_head.setFixedWidth(125)
        head_layout.addWidget(service_head)
        head_layout.addWidget(self._text(QLabel(), "settings.col.description", "head"), 1)
        rows.addWidget(header)
        rows.addWidget(_line())

        for name in ORDER:
            row = QWidget()
            row.setFixedHeight(53)
            line = QHBoxLayout(row)
            line.setContentsMargins(20, 0, 20, 0)
            line.setSpacing(5)
            check = QCheckBox(DISPLAY_NAME[name])
            check.setObjectName(f"{name}_enabled")
            check.setFixedWidth(125)
            self.checks[name] = check
            line.addWidget(check)
            if name == "claude":  # 說明與按鈕依 hook 狀態變，在 _refresh_hook 填字
                description = QLabel()
                description.setObjectName("sourceDescription")
                self.claude_desc = description
            else:
                description = self._text(QLabel(), f"settings.source.{name}", "sourceDescription")
            description.setWordWrap(True)
            line.addWidget(description, 1)
            if name == "claude":
                self.hook_button = QPushButton()
                self.hook_button.setObjectName("hookButton")
                self.hook_button.clicked.connect(self._on_hook_clicked)
                line.addWidget(self.hook_button)
            rows.addWidget(row)
            if name != ORDER[-1]:
                rows.addWidget(_line())
        return table

    def _promo(self) -> QFrame:
        promo = QFrame()
        promo.setObjectName("promo")
        layout = QHBoxLayout(promo)
        promo.setFixedHeight(187)
        layout.setContentsMargins(10, 10, 12, 10)
        layout.setSpacing(14)

        art = QLabel()
        art.setObjectName("promoArt")
        art.setFixedSize(188, 165)
        source = QPixmap(str(DESKPET_BANNER)).copy(QRect(380, 0, 740, 480))
        scaled = source.scaled(188, 165, Qt.KeepAspectRatioByExpanding,
                               Qt.SmoothTransformation)
        x, y = (scaled.width() - 188) // 2, (scaled.height() - 165) // 2
        art.setPixmap(scaled.copy(x, y, 188, 165))
        layout.addWidget(art)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 1, 0, 1)
        copy.setSpacing(5)
        copy.addWidget(self._text(QLabel(), "settings.promo_eyebrow", "promoEyebrow"))
        copy.addWidget(self._text(QLabel(), "settings.promo_title", "promoTitle"))
        body = self._text(QLabel(), "settings.promo_body", "promoBody")
        body.setWordWrap(True)
        copy.addWidget(body)
        copy.addStretch(1)
        button = self._text(QPushButton(), "settings.promo_cta", "promoButton")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(STORE_URL)))
        copy.addWidget(button)
        layout.addLayout(copy, 1)
        return promo

    def selected_language(self) -> str:
        return self.language.currentData()

    def preview_language(self) -> str:
        """畫面現在用的語言（auto 解析成實際語言）。"""
        return i18n.resolve(self.selected_language())

    def _retranslate(self, *_args) -> None:
        lang = self.preview_language()
        self.setWindowTitle(tr("settings.title", lang) + tr("settings.version", lang, v=display_version()))
        for widget, key in self._texts:
            widget.setText(tr(key, lang))
        self.language.setItemText(0, tr("settings.lang.auto", lang))
        link_color = _palette()["accent_hover"]
        self.links.setText(" · ".join(
            f'<a href="{SITE_LINKS[name][lang]}" style="color:{link_color}; text-decoration:none">'
            f'{tr(f"settings.link.{name}", lang)}</a>' for name in ("privacy", "website")))
        self._refresh_hook()

    def set_update_available(self, available: bool) -> None:
        """設定視窗開著時才查到新版：直接把按鈕叫出來。"""
        self.update_button.setVisible(available)

    # ---------- Claude 狀態列擷取 ----------

    def _refresh_hook(self) -> None:
        lang = self.preview_language()
        self.claude_desc.setText(tr(f"settings.hook.{self._hook_status}", lang))
        actions = {claude_hook.NOT_INSTALLED: "settings.hook.install",
                   claude_hook.INSTALLED: "settings.hook.remove"}
        key = actions.get(self._hook_status)
        self.hook_button.setVisible(key is not None)  # 沒裝 Claude Code、舊版 hook、讀不懂：不給按
        if key:
            self.hook_button.setText(tr(key, lang))

    def confirm(self, text: str) -> bool:
        lang = self.preview_language()
        box = QMessageBox(QMessageBox.Question, "AI Usage Meter", text,
                          QMessageBox.Yes | QMessageBox.No, self)
        # 打包版刪了 Qt 的翻譯檔，按鈕字自己給
        box.button(QMessageBox.Yes).setText(tr("settings.yes", lang))
        box.button(QMessageBox.No).setText(tr("settings.no", lang))
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes

    def _on_hook_clicked(self) -> None:
        lang = self.preview_language()
        installing = self._hook_status == claude_hook.NOT_INSTALLED
        text = tr("settings.hook.confirm_install" if installing else "settings.hook.confirm_remove",
                  lang, path=claude_hook.settings_path())
        if not self.confirm(text):
            return
        try:
            claude_hook.install() if installing else claude_hook.uninstall()
        except (claude_hook.HookError, OSError) as exc:
            QMessageBox.warning(self, "AI Usage Meter", tr("settings.hook.failed", lang, err=exc))
        self._hook_status = claude_hook.status()
        self._refresh_hook()

    # ---------- 服務與儲存 ----------

    def select(self, enabled: set[str]) -> None:
        for name, check in self.checks.items():
            check.setChecked(name in enabled)

    def selected_enabled(self) -> set[str]:
        return {name for name, check in self.checks.items() if check.isChecked()}

    def accept(self) -> None:
        enabled, language = self.selected_enabled(), self.selected_language()
        demo = self.demo_check.isChecked()
        if (enabled != self._initial_enabled or language != self._initial_language
                or demo != self._initial_demo):
            self._on_apply(enabled, language, demo)
        super().accept()
