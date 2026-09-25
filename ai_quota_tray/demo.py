"""示範模式的範例資料（給 Microsoft Store 審核人員，以及還沒裝任何 CLI 的人先看看長什麼樣子）。

審核人員的電腦上不會有 Claude Code／Codex／agy／Copilot，正常模式下卡片只會是一排「沒有資料」，
容易被判成 App 沒有功能。示範模式不查詢任何服務、不發通知，只顯示這裡的固定數字；
重置時間相對於「現在」算，倒數看起來是活的。數字刻意涵蓋綠／黃／紅三種顏色與「約」（推算的重置）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .model import OK, ProviderState, make_window

_H, _D = 3600, 86400


def sample_states(now: datetime) -> list[tuple[str, ProviderState]]:
    def at(seconds: float) -> datetime:
        return now + timedelta(seconds=seconds)

    return [
        ("claude", ProviderState("claude", [
            make_window(38, at(2 * _H + 13 * 60), 5 * _H),
            make_window(19, at(4 * _D + 6 * _H), 7 * _D),
        ], now, OK, source="demo")),
        ("codex", ProviderState("codex", [
            make_window(93, at(47 * 60), 5 * _H),       # 剩 7%：紅色
            make_window(56, at(2 * _D + 9 * _H), 7 * _D),
        ], now, OK, {"plan_type": "plus"}, source="demo")),
        ("antigravity", ProviderState("antigravity", [
            make_window(77, at(5 * _D + 20 * _H), 7 * _D, label="Gemini"),   # 剩 23%：黃色
            make_window(0, at(6 * _D + 2 * _H), 7 * _D, label="Claude/GPT"),
        ], now, OK, source="demo")),
        ("copilot", ProviderState("copilot", [
            make_window(8, at(5 * _D + 4 * _H), None, label="Chat"),
            make_window(37, at(5 * _D + 4 * _H), None, label="補全"),
        ], now, OK, {"plan_type": "Free", "estimated_resets": ["Chat", "補全"]}, source="demo")),
    ]
