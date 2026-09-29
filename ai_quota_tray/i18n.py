"""介面語言：繁體中文、English、日本語、Deutsch、简体中文。

設定視窗可選五種語言，存在 config.json 的 language。
舊設定的 auto 會在讀取時依系統語言轉成其中一種。

所有畫面上的字都經過 tr(key)。視窗 label（週、月、進階…）在資料裡一律維持中文
（通知去重的鍵含 label，切語言不能讓同一週期再通知一次），只在顯示時用 window_label 翻。
provider 回傳的錯誤細節（state.error）是除錯用，不翻。

模組預設是繁中，run() 啟動時才依設定切換；測試因此不受本機語言影響。
"""
from __future__ import annotations

import ctypes
import locale
import sys

from .locales.de import STRINGS as STRINGS_DE
from .locales.ja import STRINGS_JA
from .locales.zh_cn import STRINGS as STRINGS_ZH_CN

ZH, EN, JA, DE, ZH_CN, AUTO = "zh-TW", "en", "ja", "de", "zh-CN", "auto"
LANGUAGES = (ZH, EN, JA, DE, ZH_CN)

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
    # Store 版查到有新版（store_update.py）。拿不到新版版號，所以不寫版號
    "update.title": ("發現新版本", "New version available"),
    "update.body": ("AI Usage Meter 有新版本了。點這則通知，或到「設定…」按「版本可更新」，前往 Microsoft Store 更新。",
                    "A new version of AI Usage Meter is available. Click this notification, or open Settings… "
                    "and choose Update available, to update it in the Microsoft Store."),
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
    "card.reset_credits": ("重置券：{count} 張", "Banked resets: {count}"),
    "card.reset_credits_expiry": ("最近到期：{date}", "Earliest expiry: {date}"),
    "card.reset_credits_expiry_unknown": ("最近到期：未提供", "Earliest expiry: unavailable"),
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
    "alert.reset_title": ("{name} {label}額度已重置", "{name} {label} quota has reset"),
    "alert.reset_body": ("{name} 的{label}視窗重置了，額度回來了。",
                         "{name} {label} window has reset. Your quota is back."),
    # 卡片：用量速度（進階設定，model.pace）
    "card.pace_runs_out": ("照目前速度，約 {countdown} 後用完", "At this pace, runs out in ~{countdown}"),
    # 進階設定（settings.AdvancedDialog）
    "settings.advanced": ("進階設定…", "Advanced…"),
    "advanced.title": ("AI Usage Meter · 進階設定", "AI Usage Meter · Advanced"),
    "advanced.threshold": ("低額度通知", "Low quota alert"),
    "advanced.threshold_off": ("不通知", "Off"),
    "advanced.threshold_pct": ("剩 {pct}% 以下", "Below {pct}% left"),
    "advanced.threshold_note": ("剩餘額度低於這個值時發通知，每個視窗每個重置週期只通知一次。",
                                "Notifies when a window drops below this, once per reset cycle."),
    "advanced.reset_alert": ("額度重置時通知", "Notify when quota resets"),
    "advanced.reset_alert_note": ("只限發過低額度通知的視窗，不會每次重置都跳。",
                                  "Only for windows that triggered a low quota alert."),
    "advanced.pace": ("顯示用量速度", "Show usage pace"),
    "advanced.pace_note": ("照目前速度會在重置前用完時才提醒，並在進度條上標出平均使用時這時候應剩的位置。",
                           "Warns only when your current pace would run out before the reset, "
                           "and marks where an even pace would be on the bar."),
    "advanced.spend_limit": ("顯示 Claude 花費上限", "Show Claude spend limit"),
    "advanced.spend_limit_note": ("公司透過 Claude apps gateway 設定花費上限時才會出現。",
                                  "Only appears when your organization sets a spend limit through "
                                  "a Claude apps gateway."),
    "advanced.ok": ("確定", "OK"),
    # 設定視窗
    "settings.title": ("AI Usage Meter · 服務設定", "AI Usage Meter · Services"),
    "settings.heading": ("選擇要顯示的服務", "Choose services to show"),
    "settings.subtitle": ("查看時更新雲端額度", "Cloud updates on view"),
    "settings.col.service": ("服務", "Service"),
    "settings.col.description": ("說明", "Description"),
    # Claude 那一列：說明依 claude_hook.status() 的結果換，按鈕立刻安裝／移除
    "settings.hook.not_installed": ("安裝用量擷取後才能顯示 Claude 額度；不會安裝 Claude Code。",
                                    "Install usage capture to show Claude limits. This does not install Claude Code."),
    "settings.hook.installed": ("已安裝用量擷取；移除擷取不會移除 Claude Code。",
                                "Usage capture is installed. Removing it does not remove Claude Code."),
    "settings.hook.legacy": ("已偵測到相容的狀態列擷取。",
                             "A compatible status line capture is already set up."),
    "settings.hook.no_claude": ("沒有偵測到 Claude Code。", "Claude Code was not found on this PC."),
    "settings.hook.unreadable": ("Claude Code 的設定檔無法解析，未做任何變更。",
                                 "Couldn't read Claude Code's settings file; nothing was changed."),
    "settings.hook.install": ("安裝擷取", "Install capture"),
    "settings.hook.remove": ("移除擷取", "Remove capture"),
    "settings.reset_credits_note": ("重置券數量與最近到期日目前僅支援 Codex。",
                                    "Reset vouchers: count/expiry for Codex only."),
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
    "settings.version": ("（Ver. {v}）", " (Ver. {v})"),
    "settings.update": ("版本可更新", "Update available"),
    "settings.link.privacy": ("隱私權政策", "Privacy policy"),
    "settings.link.website": ("官網", "Website"),
    "settings.disclaimer": ("非 Anthropic、OpenAI、GitHub、Google 官方產品",
                            "Not affiliated with Anthropic, OpenAI, GitHub, or Google"),
    "settings.yes": ("是", "Yes"),
    "settings.no": ("否", "No"),
    "settings.source.codex": ("透過官方 App Server 查詢；失敗時退回本機紀錄。",
                              "Uses the official App Server; falls back to local records."),
    "settings.source.antigravity": ("透過官方 agy CLI 查詢；未登入請先執行 agy。",
                                    "Uses the official agy CLI; sign in with agy first."),
    "settings.source.copilot": ("透過官方 SDK 查詢；請先執行 copilot login 登入。",
                                "Uses the official SDK; sign in with copilot login first."),
    "settings.source.grok": ("僅個人版：讀取 Grok Build CLI 的本機登入資料查詢；登入約 6 小時過期，會請 Grok CLI 自己續期。",
                             "Personal build only: reads the local Grok Build CLI sign-in; when it expires (about 6 hours) the Grok CLI is asked to renew it."),
    "settings.language": ("語言", "Language"),
    "settings.cancel": ("取消", "Cancel"),
    "settings.save": ("儲存", "Save"),
    "settings.promo_eyebrow": ("廣告 · FISH-ZERO 自家 App", "Ad · A FISH-ZERO app"),
    "settings.promo_title": ("萌寵桌面精靈", "Taskbar Buddy"),
    "settings.promo_body": ("住在 Windows 桌面上的小寵物，陪你工作與休息。",
                            "A tiny pet for your Windows desktop, keeping you company as you work."),
    "settings.promo_cta": ("從 Microsoft Store 下載 →", "Get it from Microsoft →"),

}

# 資料裡的視窗 label 固定繁中；只在顯示時翻譯，不改通知去重用的值。
WINDOW_LABELS = {
    EN: {"日": "Day", "週": "Week", "月": "Month", "進階": "Premium",
         "補全": "Completions", "花費上限": "Spend limit"},
    JA: {"日": "日", "週": "週", "月": "月", "進階": "プレミアム", "補全": "補完",
         "花費上限": "利用額上限"},
    DE: {"日": "Tag", "週": "Woche", "月": "Monat", "進階": "Premium", "補全": "Vervollst.",
         "花費上限": "Ausgabenlimit"},
    ZH_CN: {"日": "日", "週": "周", "月": "月", "進階": "高级", "補全": "补全", "花費上限": "花费上限"},
}

# 語言選單上的名稱，永遠用各自的語言寫（切錯了也找得回來）
NATIVE_NAMES = {ZH: "繁體中文", EN: "English", JA: "日本語", DE: "Deutsch", ZH_CN: "简体中文"}

TRANSLATIONS = {JA: STRINGS_JA, DE: STRINGS_DE, ZH_CN: STRINGS_ZH_CN}


def _locale_language(tag: str | None) -> str:
    tag = (tag or "").replace("_", "-").lower()
    if tag.startswith("zh"):
        return ZH_CN if any(x in tag for x in ("-cn", "-sg", "-hans")) else ZH
    if tag.startswith("ja"):
        return JA
    if tag.startswith("de"):
        return DE
    return EN


def system_language() -> str:
    """依 Windows 介面語言選擇已支援語系；其他語言回退英文。"""
    langid = None
    if sys.platform == "win32":
        try:
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        except (AttributeError, OSError):
            langid = None
    if langid is not None:
        tag = locale.windows_locale.get(langid)
        if tag:
            return _locale_language(tag)
    return _locale_language(locale.getlocale()[0])


def resolve(setting: str | None) -> str:
    return setting if setting in LANGUAGES else system_language()


def set_language(setting: str | None) -> str:
    """回傳實際套用的語言；舊版 auto 依系統語言選擇。"""
    global _current
    _current = resolve(setting)
    return _current


def current() -> str:
    return _current


def tr(key: str, lang: str | None = None, **kwargs) -> str:
    """lang 不給＝目前語言。設定視窗預覽別的語言時才會給（還沒按儲存，不能動到全域）。"""
    zh, en = STRINGS[key]
    chosen = resolve(lang) if lang is not None else _current
    if key.startswith("settings.promo_") and chosen in TRANSLATIONS:
        text = en  # 自家寵物 App 只支援繁中／英文；廣告不暗示它支援其他語言。
        if key == "settings.promo_body":
            text += "\nAvailable in English and Traditional Chinese."
    elif chosen == ZH:
        text = zh
    elif chosen == EN:
        text = en
    else:
        text = TRANSLATIONS[chosen][key]
    return text.format(**kwargs) if kwargs else text


def window_label(label: str) -> str:
    return WINDOW_LABELS.get(_current, {}).get(label, label)


def join(items) -> str:
    return tr("list.sep").join(items)
