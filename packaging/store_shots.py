"""產生 Microsoft Store 截圖：把真的卡片／設定視窗元件畫出來，放在乾淨的背景上加一句說明。

    .venv\\Scripts\\python packaging\\store_shots.py      → docs\\store\\shots\\<語言>-<n>.png

為什麼不直接截桌面：會拍到業主自己的視窗、系統匣裡別的 App，而且每次重拍都不一樣。
元件是真的（card.Card、strip.Strip、settings.SettingsDialog），資料用示範模式的範例（demo.sample_states），
只是不畫示範模式那行紅字——那行是給正在用 App 的人看的，截圖本來就是示意。
⚠️ 每個語言的截圖要是那個語言的介面（desk-pet 經驗：英文清單配中文截圖會被退件）。
規格：PNG、最小 1366×768、最大 3840×2160（docs/store-listing.md §8）。這裡輸出 3840×2160。
第 4 張（0.1.5 起）是釘選：釘在桌面的卡片＋貼在工作列上方的長條。底下那條「工作列」是畫出來的示意，
不截真的工作列（會拍到業主釘在工作列上的 App）。
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

from ai_quota_tray import card as card_mod, demo, i18n, settings as settings_mod, strip as strip_mod  # noqa: E402
from ai_quota_tray.model import utcnow  # noqa: E402

OUT = ROOT / "docs" / "store" / "shots"
W, H, DPR = 1920, 1080, 2  # 邏輯尺寸 × DPR ＝ 輸出 3840×2160

CAPTIONS = {
    i18n.ZH: [
        ("每個額度還剩多少\n滑鼠移過去就知道", "5 小時、每週、每月的額度，剩餘百分比與重置倒數一次看完。"),
        ("淺色、深色都好讀", "跟著 Windows 的色彩設定切換；快用完的額度會變黃、變紅。"),
        ("選你用的工具\n不用登入、不碰權杖", "查詢交給電腦上已登入的官方工具，不讀你的密碼或權杖。"),
        ("釘在桌面\n或貼在工作列上方", "不想每次都滑過圖示？把卡片留在桌面上，或縮成一排小電池貼著工作列。"),
    ],
    i18n.EN: [
        ("Every limit,\none hover away", "5-hour, weekly, and monthly limits: the percentage left and the reset countdown at a glance."),
        ("Easy to read,\nlight or dark", "Follows your Windows color mode. Limits that are running low turn yellow, then red."),
        ("Pick your tools.\nNo sign-in, no tokens.", "Lookups go through the official tools already signed in on your PC. "
                                                    "AI Usage Meter never reads your passwords or tokens."),
        ("Pin it to your desktop\nor above the taskbar", "Keep the card on your desktop, or shrink it into a row of "
                                                          "tiny batteries right above the taskbar."),
    ],
    i18n.JA: [
        ("利用枠をまとめて確認", "残量とリセットまでの時間を、通知領域からすばやく確認。"),
        ("明るい画面でも暗い画面でも", "Windows の表示モードに合わせて見やすく表示します。"),
        ("使うツールを選択", "サインイン済みの公式ツールを利用し、パスワードやトークンは読み取りません。"),
        ("デスクトップや\nタスクバーの上に固定", "カードをデスクトップに表示したままにしたり、小さなバッテリー表示にしてタスクバーの上に並べたりできます。"),
    ],
    i18n.DE: [
        ("Alle Limits im Blick", "Restkontingent und Rücksetzzeit direkt im Windows-Infobereich sehen."),
        ("Hell oder dunkel", "Die Anzeige folgt dem Windows-Farbmodus und kennzeichnet knappe Limits."),
        ("Deine Tools wählen", "Die Abfrage nutzt angemeldete offizielle Tools – ohne Passwörter oder Token zu lesen."),
        ("Auf dem Desktop\noder über der Taskleiste", "Lass die Karte auf dem Desktop oder als Reihe kleiner Akkus direkt über der Taskleiste."),
    ],
    i18n.ZH_CN: [
        ("各项额度 一眼看清", "悬停系统托盘图标，查看剩余用量和重置倒计时。"),
        ("浅色、深色都清晰", "跟随 Windows 显示模式，额度不足时颜色也会变化。"),
        ("选择要查看的工具", "通过已登录的官方工具查询，不读取密码或令牌。"),
        ("固定在桌面\n或贴在任务栏上方", "把卡片留在桌面上，或缩成一排小电池贴在任务栏上方。"),
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
    settings_mod.agy_hook.status = lambda: settings_mod.agy_hook.NOT_INSTALLED
    dlg = settings_mod.SettingsDialog({"claude", "codex", "copilot"}, i18n.current(), lambda *a, **k: None)
    return widget_image(dlg)


def render_pinned() -> tuple[QImage, QImage]:
    """釘在桌面的卡片（左下角有「立即刷新」）與工作列長條，都用深色。"""
    dark = lambda: card_mod.THEMES["dark"]  # noqa: E731
    card_mod._theme = strip_mod._theme = dark
    states = demo.sample_states(utcnow())
    desk = card_mod.Card(pinned=True)
    desk.set_states(states[:3], banner=None)
    bar = strip_mod.Strip()
    bar.set_states(states, banner=None)
    return widget_image(desk), widget_image(bar)


TASKBAR_H = 64


def compose_pinned(desk: QImage, bar: QImage, title: str, subtitle: str) -> QImage:
    """右上：釘在桌面的卡片；底下：示意的工作列，長條貼在它上緣、靠右。左邊照樣是標題與說明。"""
    img = compose(None, title, subtitle, dark_bg=True, scale=1.0, text_right=W - 760)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    p.fillRect(QRectF(0, H - TASKBAR_H, W, TASKBAR_H), QColor("#161a22"))
    p.fillRect(QRectF(0, H - TASKBAR_H, W, 1), QColor("#2c3240"))
    bw, bh = bar.width() / bar.devicePixelRatio() * 1.45, bar.height() / bar.devicePixelRatio() * 1.45
    p.drawImage(QRectF(W - bw - 70, H - TASKBAR_H - bh, bw, bh), bar)
    dw, dh = desk.width() / desk.devicePixelRatio() * 1.45, desk.height() / desk.devicePixelRatio() * 1.45
    x, y = W - dw - 150, (H - TASKBAR_H - bh - dh) / 2
    for i in range(18, 0, -2):
        path = QPainterPath()
        path.addRoundedRect(QRectF(x - i, y - i + 14, dw + 2 * i, dh + 2 * i), 18 + i, 18 + i)
        p.fillPath(path, QColor(0, 0, 0, 5))
    p.drawImage(QRectF(x, y, dw, dh), desk)
    p.end()
    return img


def compose(shot: QImage | None, title: str, subtitle: str, dark_bg: bool, scale: float,
            text_right: float | None = None) -> QImage:
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

    # 右邊：元件（邏輯尺寸 × scale），加一層柔和陰影；shot=None 時由呼叫端自己畫（compose_pinned）
    if shot is not None:
        sw, sh = shot.width() / shot.devicePixelRatio() * scale, shot.height() / shot.devicePixelRatio() * scale
        x, y = W - sw - 150, (H - sh) / 2
        for i in range(18, 0, -2):  # 簡單的疊層陰影
            path = QPainterPath()
            path.addRoundedRect(QRectF(x - i, y - i + 14, sw + 2 * i, sh + 2 * i), 18 + i, 18 + i)
            p.fillPath(path, QColor(0, 0, 0, 5 if dark_bg else 3))
        p.drawImage(QRectF(x, y, sw, sh), shot)
    else:
        x = text_right

    # 左邊：一句標題＋一行說明
    text_c, sub_c = (QColor("#f1f4fa"), QColor("#aab4c8")) if dark_bg else (QColor("#172033"), QColor("#4a566e"))
    left, width = 140, x - 140 - 110
    font_family = {i18n.ZH: "Microsoft JhengHei UI", i18n.JA: "Yu Gothic UI",
                   i18n.ZH_CN: "Microsoft YaHei UI"}.get(i18n.current(), "Segoe UI")
    font = QFont(font_family)
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
    for lang, tag in ((lang, lang) for lang in i18n.LANGUAGES):
        i18n.set_language(lang)
        (t1, s1), (t2, s2), (t3, s3), (t4, s4) = CAPTIONS[lang]
        shots = [
            compose(render_card(dark=True), t1, s1, dark_bg=True, scale=1.9),
            compose(render_card(dark=False), t2, s2, dark_bg=False, scale=1.9),
            compose(render_settings(dark=True), t3, s3, dark_bg=True, scale=1.25),
            compose_pinned(*render_pinned(), t4, s4),
        ]
        for n, img in enumerate(shots, 1):
            path = OUT / f"{tag}-{n}.png"
            img.save(str(path))
            print(f"✅ {path.relative_to(ROOT)}（{img.width()}×{img.height()}）")


if __name__ == "__main__":
    main()
