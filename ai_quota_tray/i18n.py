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
    "startup.blocked_title": ("開機啟動被 Windows 關閉了", "Start with Windows is turned off"),
    "startup.blocked_body": ("請到 Windows 設定 → 應用程式 → 啟動，把 AI Usage Meter 打開。",
                             "Turn on AI Usage Meter in Windows Settings → Apps → Startup."),
    # 第一次啟動的歡迎通知（App 沒有主視窗，不說一聲會以為沒啟動）。標題 ≤63、內文 ≤255 字元
    "welcome.title": ("AI Usage Meter 已在系統匣執行", "AI Usage Meter is running in the notification area"),
    "welcome.body": ("滑鼠移到系統匣圖示上就能看到用量，按右鍵可以開設定。"
                     "工作列上找不到圖示的話，請點 ^ 找找看。點這則通知也能打開。",
                     "Hover the tray icon to see your usage, or right-click it for Settings. "
                     "If you don't see the icon, look under the ^ arrow. You can also click this notification."),
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
    "card.claude_needs_hook": ("還沒有資料：到「設定…」安裝 Claude 狀態列擷取，再用一下 Claude Code",
                               "No data yet: install the Claude status line capture in Settings…, "
                               "then use Claude Code once"),
    "card.demo_banner": ("示範模式・以下為範例資料，不是你的額度",
                         "Demo mode: sample data, not your actual quota"),
    "card.preparing": ("第一次使用，正在下載 Copilot 元件（約 111 MB）…",
                       "First use: downloading Copilot components (about 111 MB)…"),
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
    "settings.title": ("AI Usage Meter · 服務設定", "AI Usage Meter · Services"),
    "settings.heading": ("選擇要顯示的服務", "Choose services to show"),
    "settings.subtitle": ("查看時更新雲端額度；Claude 定期讀取本機資料。", "Cloud quotas refresh on view; Claude reads local files."),
    "settings.col.service": ("服務", "Service"),
    "settings.col.description": ("說明", "Description"),
    # Claude 那一列：說明依 claude_hook.status() 的結果換，按鈕立刻安裝／移除
    "settings.hook.not_installed": ("讀取 Claude Code 狀態列；請先安裝擷取。",
                                    "Reads Claude Code's status line; install the capture first."),
    "settings.hook.installed": ("已安裝狀態列擷取，用 Claude Code 時自動更新。",
                                "Status line capture installed; updates as you use Claude Code."),
    "settings.hook.legacy": ("已偵測到相容的狀態列擷取。",
                             "A compatible status line capture is already set up."),
    "settings.hook.no_claude": ("沒有偵測到 Claude Code。", "Claude Code was not found on this PC."),
    "settings.hook.unreadable": ("Claude Code 的設定檔無法解析，未做任何變更。",
                                 "Couldn't read Claude Code's settings file; nothing was changed."),
    "settings.hook.install": ("安裝", "Install"),
    "settings.hook.remove": ("移除", "Remove"),
    "settings.hook.confirm_install": (
        "要安裝 Claude 狀態列擷取嗎？\n\n"
        "會修改 Claude Code 的設定檔：\n{path}\n\n"
        "・把狀態列指令換成 AI Usage Meter 的小程式（放在同一個資料夾的 ai-quota-tray 底下），"
        "它把 Claude Code 自己已經拿到的額度數字存到本機，不呼叫任何 API、不碰登入憑證。\n"
        "・你原本的狀態列會照常顯示。\n"
        "・改之前會先備份設定檔；之後可以隨時回來按「移除」還原。",
        "Install the Claude status line capture?\n\n"
        "This changes Claude Code's settings file:\n{path}\n\n"
        "• The status line command is replaced with a small AI Usage Meter script (stored in an "
        "ai-quota-tray folder next to it). It saves the quota numbers Claude Code already has to "
        "this PC. No API calls, and your sign-in is never touched.\n"
        "• Your current status line keeps showing as before.\n"
        "• The settings file is backed up first, and you can press Remove here any time to restore it.",
    ),
    "settings.hook.confirm_remove": (
        "要移除 Claude 狀態列擷取嗎？\n\n會把 Claude Code 的狀態列設定還原成安裝前的樣子：\n{path}",
        "Remove the Claude status line capture?\n\n"
        "Claude Code's status line setting will be restored to how it was before:\n{path}",
    ),
    "settings.hook.failed": ("操作失敗，沒有做任何變更：{err}", "That didn't work and nothing was changed: {err}"),
    "settings.demo": ("示範模式", "Demo mode"),
    "settings.yes": ("是", "Yes"),
    "settings.no": ("否", "No"),
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
