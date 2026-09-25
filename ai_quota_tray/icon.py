"""圖示與顏色門檻。

系統匣一律顯示品牌圖示（業主 2026-09-25 決定，取代 CLAUDE.md §4 原本「動態畫最低剩餘 %」的設計）：
數字看 hover 卡片，剩餘 < 10% 靠通知。顏色門檻仍給卡片進度條用。
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from .i18n import window_label
from .model import ProviderState

# 剩餘 % 低於門檻就換色；紅色門檻與通知門檻（< 10%）一致
RED_BELOW = 10.0
YELLOW_BELOW = 30.0

COLORS = {
    "green": (46, 160, 67),
    "yellow": (212, 160, 23),
    "red": (207, 34, 46),
    "grey": (110, 118, 129),
}

# 業主設計的 App 圖示（原圖 D:\FISH\Desktop\ai-quota.png，裁掉四周光暈後縮成 512px）
ASSETS = Path(__file__).with_name("assets")
BRAND_PNG = ASSETS / "app.png"
_brand_cache: dict[int, bytes] = {}


def level_for(remaining: float) -> str:
    """剩餘 % → 顏色等級（卡片進度條用）。"""
    return "red" if remaining < RED_BELOW else "yellow" if remaining < YELLOW_BELOW else "green"


def brand_png(size: int) -> bytes:
    """品牌圖示縮到指定尺寸的 PNG（快取，縮圖很慢）。"""
    if size not in _brand_cache:
        out = io.BytesIO()
        with Image.open(BRAND_PNG) as src:
            src.convert("RGBA").resize((size, size), Image.LANCZOS).save(out, "PNG")
        _brand_cache[size] = out.getvalue()
    return _brand_cache[size]


def tooltip(states: list[ProviderState]) -> str:
    """給螢幕閱讀器的純文字摘要（系統匣 szTip 上限 127 字）。"""
    parts = []
    for s in states:
        if s.status == "stale":
            parts.append(f"{s.name} {s.status}")
        elif s.status in ("error", "auth_expired"):
            parts.append(f"{s.name} {s.status}")
        elif s.windows:
            wins = " ".join(f"{window_label(w.label)} {int(w.remaining_pct)}%" for w in s.windows
                            if w.remaining_pct is not None)
            parts.append(f"{s.name} {wins}")
        else:
            parts.append(f"{s.name} {s.status}")
    return ("AI Quota Tray｜" + "；".join(parts))[:127]
