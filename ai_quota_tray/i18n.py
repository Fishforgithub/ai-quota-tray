"""介面語言：繁體中文／English。

設定視窗可選「跟隨系統／繁體中文／English」，存在 config.json 的 language
（auto / zh-TW / en）。auto：Windows 介面語言是中文 → 繁中，其他 → English。

所有畫面上的字都經過 tr(key)。視窗 label（週、月、進階…）在資料裡一律維持中文
（通知去重的鍵含 label，切語言不能讓同一週期再通知一次），只在顯示時用 window_label 翻。
provider 回傳的錯誤細節（state.error）是除錯用，不翻。

模組預設是繁中，run() 啟動時才依設定切換；測試因此不受本機語言影響。
"""
from __future__ import annotations

import ctypes
import locale
import sys

ZH, EN, AUTO = "zh-TW", "en", "auto"
LANGUAGES = (AUTO, ZH, EN)

_current = ZH

STRINGS: dict[str, tuple[str, str]] = {
    # 右鍵選單
    "menu.refresh": ("立即刷新", "Refresh now"),
    "menu.settings": ("設定…", "Settings…"),
    "menu.startup": ("開機時啟動", "Start with Windows"),
    "menu.quit": ("關閉", "Quit"),
    # 卡片
    "card.loading": ("讀取中…", "Loading…"),
    "card.nothing_enabled": ("沒有啟用任何服務，請在右鍵選單「設定…」勾選",
                             "No services enabled. Right-click → Settings… to pick some."),
    "card.api_failed": ("官方介面失敗，顯示本機紀錄", "Official source failed; showing local records"),
    "card.auth_expired": ("Token 過期，請開一下 {cli}", "Token expired, please open {cli}"),
    "card.auth_antigravity": ("Antigravity CLI 尚未登入，請先執行 agy 登入",
                              "Antigravity CLI is not signed in, run agy to sign in"),
    "card.auth_copilot": ("Copilot 登入失效，請執行 copilot login",
                          "Copilot sign-in expired, run copilot login"),
    "card.disabled": ("未啟用", "Not enabled"),
    "card.error": ("抓取失敗：{err}", "Fetch failed: {err}"),
    "card.unknown_error": ("未知錯誤", "unknown error"),
    "card.no_data": ("沒有額度資料", "No quota data"),
    "card.unlimited": ("無上限：{items}", "Unlimited: {items}"),
    "card.rolled_over": ("已重置", "Reset"),
    "card.estimated_reset": ("約 {countdown}", "~{countdown}"),
    "list.sep": ("、", ", "),
    # 時間
    "age.unknown": ("時間不明", "unknown time"),
    "age.now": ("剛剛", "just now"),
    "age.minutes": ("{n} 分鐘前", "{n} min ago"),
    "age.hours": ("{n} 小時前", "{n} h ago"),
    "age.days": ("{n} 天前", "{n} d ago"),
    # 通知
    "alert.title": ("{name} {label}額度剩 {pct}%", "{name} {label} quota: {pct}% left"),
    "alert.body": ("{name} 的{label}視窗只剩 {pct}%{reset}。",
                   "{name} {label} window has {pct}% left{reset}."),
    "alert.reset": ("，{countdown} 後重置", ", resets in {countdown}"),
    # 設定視窗
    "settings.title": ("AI Quota Tray · 服務設定", "AI Quota Tray · Services"),
    "settings.heading": ("選擇要顯示的服務", "Choose services to show"),
    "settings.subtitle": ("查看時更新雲端額度；Claude 定期讀取本機資料。", "Cloud quotas refresh on view; Claude reads local files."),
    "settings.col.service": ("服務", "Service"),
    "settings.col.description": ("說明", "Description"),
    "settings.source.claude": ("讀取本機紀錄。", "Reads local records."),
    "settings.source.codex": ("透過官方 App Server 查詢；失敗時退回本機紀錄。",
                              "Uses the official App Server; falls back to local records."),
    "settings.source.antigravity": ("透過官方 agy CLI 查詢；未登入請先執行 agy。",
                                    "Uses the official agy CLI; sign in with agy first."),
    "settings.source.copilot": ("透過官方 SDK 查詢；請先執行 copilot login 登入。",
                                "Uses the official SDK; sign in with copilot login first."),
    "settings.language": ("語言", "Language"),
    "settings.lang.auto": ("跟隨系統", "System default"),
    "settings.cancel": ("取消", "Cancel"),
    "settings.save": ("儲存", "Save"),
    "settings.promo_eyebrow": ("廣告 · FISH-ZERO 自家 App", "Ad · A FISH-ZERO app"),
    "settings.promo_title": ("萌寵桌面精靈", "Taskbar Buddy"),
    "settings.promo_body": ("住在 Windows 桌面上的小寵物，陪你工作與休息。",
                            "A tiny pet for your Windows desktop, keeping you company as you work."),
    "settings.promo_cta": ("從 Microsoft Store 下載 →", "Get it from Microsoft →"),

}

# 資料裡的視窗 label（中文）→ English。沒列到的（5h、3d、Chat、Pro…）兩種語言都一樣
WINDOW_LABELS_EN = {"日": "Day", "週": "Week", "月": "Month", "進階": "Premium",
                    "補全": "Completions"}

# 語言選單上的名稱，永遠用各自的語言寫（切錯了也找得回來）
NATIVE_NAMES = {ZH: "繁體中文", EN: "English"}


def system_language() -> str:
    """Windows 介面語言是中文（任何地區）→ 繁中，其他 → English。"""
    primary = None
    if sys.platform == "win32":
        try:
            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        except (AttributeError, OSError):
            primary = None
    if primary is not None:
        return ZH if primary == 0x04 else EN  # LANG_CHINESE
    lang = (locale.getlocale()[0] or "").lower()
    return ZH if lang.startswith("zh") or lang.startswith("chinese") else EN


def resolve(setting: str | None) -> str:
    return setting if setting in (ZH, EN) else system_language()


def set_language(setting: str | None) -> str:
    """setting 是 config 的值（auto / zh-TW / en）；回傳實際套用的語言。"""
    global _current
    _current = resolve(setting)
    return _current


def current() -> str:
    return _current


def tr(key: str, lang: str | None = None, **kwargs) -> str:
    """lang 不給＝目前語言。設定視窗預覽別的語言時才會給（還沒按儲存，不能動到全域）。"""
    zh, en = STRINGS[key]
    text = en if (lang or _current) == EN else zh
    return text.format(**kwargs) if kwargs else text


def window_label(label: str) -> str:
    return WINDOW_LABELS_EN.get(label, label) if _current == EN else label


def join(items) -> str:
    return tr("list.sep").join(items)
