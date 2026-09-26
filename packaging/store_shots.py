"""產生 Microsoft Store 截圖：把真的卡片／設定視窗元件畫出來，放在乾淨的背景上加一句說明。

    .venv\\Scripts\\python packaging\\store_shots.py      → docs\\store\\shots\\<語言>-<n>.png

為什麼不直接截桌面：會拍到業主自己的視窗、系統匣裡別的 App，而且每次重拍都不一樣。
元件是真的（card.Card、settings.SettingsDialog），資料用示範模式的範例（demo.sample_states），
只是不畫示範模式那行紅字——那行是給正在用 App 的人看的，截圖本來就是示意。
⚠️ 每個語言的截圖要是那個語言的介面（desk-pet 經驗：英文清單配中文截圖會被退件）。
規格：PNG、最小 1366×768、最大 3840×2160（docs/store-listing.md §8）。這裡輸出 3840×2160。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_SCALE_FACTOR", "2")  # 元件用 2 倍解析度畫，放大後才不會糊

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ai_quota_tray import card as card_mod, demo, i18n, settings as settings_mod  # noqa: E402
from ai_quota_tray.model import utcnow  # noqa: E402

OUT = ROOT / "docs" / "store" / "shots"
W, H, DPR = 1920, 1080, 2  # 邏輯尺寸 × DPR ＝ 輸出 3840×2160

CAPTIONS = {
    i18n.ZH: [
        ("每個額度還剩多少\n滑鼠移過去就知道", "5 小時、每週、每月的額度，剩餘百分比與重置倒數一次看完。"),
        ("淺色、深色都好讀", "跟著 Windows 的色彩設定切換；快用完的額度會變黃、變紅。"),
        ("選你用的工具\n不用登入、不碰權杖", "查詢交給電腦上已登入的官方工具，不讀你的密碼或權杖。"),
    ],
    i18n.EN: [
        ("Every limit,\none hover away", "5-hour, weekly, and monthly limits: the percentage left and the reset countdown at a glance."),
        ("Easy to read,\nlight or dark", "Follows your Windows color mode. Limits that are running low turn yellow, then red."),
        ("Pick your tools.\nNo sign-in, no tokens.", "Lookups go through the official tools already signed in on your PC. "
                                                    "AI Usage Meter never reads your passwords or tokens."),
    ],
}


def widget_image(widget) -> QImage:
    widget.adjustSize()
    return widget.grab().toImage()  # 不用 show；DPR 跟著 QT_SCALE_FACTOR


def render_card(dark: bool) -> QImage:
    card_mod._theme = lambda: card_mod.THEMES["dark" if dark else "light"]
    card = card_mod.Card()
    card.set_states(demo.sample_states(utcnow()), banner=None)
    return widget_image(card)


def render_settings(dark: bool) -> QImage:
    settings_mod._palette = lambda: settings_mod.PALETTE["dark" if dark else "light"]
    # 畫新使用者看到的樣子（「安裝」按鈕），不是這台電腦剛好已經裝好 hook 的狀態
    settings_mod.claude_hook.status = lambda: settings_mod.claude_hook.NOT_INSTALLED
    dlg = settings_mod.SettingsDialog({"claude", "codex", "copilot"}, i18n.current(), lambda *a, **k: None)
    return widget_image(dlg)


def compose(shot: QImage, title: str, subtitle: str, dark_bg: bool, scale: float) -> QImage:
    img = QImage(W * DPR, H * DPR, QImage.Format_ARGB32)
    img.setDevicePixelRatio(DPR)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    grad = QLinearGradient(0, 0, W, H)
    if dark_bg:
        grad.setColorAt(0, QColor("#0f1424")), grad.setColorAt(1, QColor("#1d2b4a"))
    else:
        grad.setColorAt(0, QColor("#eef2f8")), grad.setColorAt(1, QColor("#d9e3f2"))
    p.fillRect(QRectF(0, 0, W, H), grad)

    # 右邊：元件（邏輯尺寸 × scale），加一層柔和陰影
    sw, sh = shot.width() / shot.devicePixelRatio() * scale, shot.height() / shot.devicePixelRatio() * scale
    x, y = W - sw - 150, (H - sh) / 2
    for i in range(18, 0, -2):  # 簡單的疊層陰影
        path = QPainterPath()
        path.addRoundedRect(QRectF(x - i, y - i + 14, sw + 2 * i, sh + 2 * i), 18 + i, 18 + i)
        p.fillPath(path, QColor(0, 0, 0, 5 if dark_bg else 3))
    p.drawImage(QRectF(x, y, sw, sh), shot)

    # 左邊：一句標題＋一行說明
    text_c, sub_c = (QColor("#f1f4fa"), QColor("#aab4c8")) if dark_bg else (QColor("#172033"), QColor("#4a566e"))
    left, width = 140, x - 140 - 110
    font = QFont("Microsoft JhengHei UI" if i18n.current() == i18n.ZH else "Segoe UI")
    font.setPixelSize(64), font.setBold(True)
    p.setFont(font), p.setPen(text_c)
    title_rect = p.boundingRect(QRectF(left, 0, width, H), Qt.TextWordWrap, title)
    sub_font = QFont(font)
    sub_font.setPixelSize(30), sub_font.setBold(False)
    p.setFont(sub_font)
    sub_rect = p.boundingRect(QRectF(left, 0, width, H), Qt.TextWordWrap, subtitle)
    top = (H - title_rect.height() - 36 - sub_rect.height()) / 2
    p.setFont(font)
    p.drawText(QRectF(left, top, width, title_rect.height()), Qt.TextWordWrap, title)
    p.setFont(sub_font), p.setPen(sub_c)
    p.drawText(QRectF(left, top + title_rect.height() + 36, width, sub_rect.height()), Qt.TextWordWrap, subtitle)
    p.end()
    return img


def main() -> None:
    app = QApplication(sys.argv)  # noqa: F841 — 元件需要 QApplication
    OUT.mkdir(parents=True, exist_ok=True)
    for lang, tag in ((i18n.ZH, "zh-TW"), (i18n.EN, "en")):
        i18n.set_language(lang)
        (t1, s1), (t2, s2), (t3, s3) = CAPTIONS[lang]
        shots = [
            compose(render_card(dark=True), t1, s1, dark_bg=True, scale=1.9),
            compose(render_card(dark=False), t2, s2, dark_bg=False, scale=1.9),
            compose(render_settings(dark=True), t3, s3, dark_bg=True, scale=1.25),
        ]
        for n, img in enumerate(shots, 1):
            path = OUT / f"{tag}-{n}.png"
            img.save(str(path))
            print(f"✅ {path.relative_to(ROOT)}（{img.width()}×{img.height()}）")


if __name__ == "__main__":
    main()
