"""系統匣圖示：三家所有視窗中「最低剩餘 %」，綠／黃／紅（CLAUDE.md §4）。"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .model import AUTH_EXPIRED, ERROR, ProviderState

# 剩餘 % 低於門檻就換色；紅色門檻與 P4 的 toast 門檻（< 10%）一致
RED_BELOW = 10.0
YELLOW_BELOW = 30.0

COLORS = {
    "green": (46, 160, 67),
    "yellow": (212, 160, 23),
    "red": (207, 34, 46),
    "grey": (110, 118, 129),
}
_FONT_DIR = Path(r"C:\Windows\Fonts")
_SUPERSAMPLE = 4


@dataclass(frozen=True)
class IconSpec:
    text: str
    level: str  # green / yellow / red / grey
    remaining: float | None  # 最低剩餘 %
    source: str | None  # 例如 "grok 週"，給 tooltip 用


def summarize(states: list[ProviderState]) -> IconSpec:
    lowest: tuple[float, str] | None = None
    for s in states:
        for win in s.windows:
            r = win.remaining_pct
            if r is not None and (lowest is None or r < lowest[0]):
                lowest = (r, f"{s.name} {win.label}")
    if lowest is None:
        broken = any(s.status in (ERROR, AUTH_EXPIRED) for s in states)
        return IconSpec("!" if broken else "–", "grey", None, None)
    remaining, source = lowest
    # 無條件捨去：剩 9.6% 顯示 9 而不是 10，避免看起來比實際寬裕
    return IconSpec(str(int(remaining)), level_for(remaining), remaining, source)


def level_for(remaining: float) -> str:
    """剩餘 % → 顏色等級。圖示與卡片進度條共用。"""
    return "red" if remaining < RED_BELOW else "yellow" if remaining < YELLOW_BELOW else "green"


def _font(px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("segoeuib.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(str(_FONT_DIR / name), px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def render(spec: IconSpec, size: int) -> bytes:
    """回傳 PNG bytes。先畫 4 倍大再縮小，16px 也不會鋸齒。"""
    big = size * _SUPERSAMPLE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=big // 5, fill=COLORS[spec.level])

    # 字級依字數縮放：1–2 字吃滿，「100」要再小一點才放得下
    font_px = int(big * (0.78 if len(spec.text) <= 2 else 0.56))
    font = _font(font_px)
    box = draw.textbbox((0, 0), spec.text, font=font)
    x = (big - (box[2] - box[0])) / 2 - box[0]
    y = (big - (box[3] - box[1])) / 2 - box[1]
    draw.text((x, y), spec.text, font=font, fill=(255, 255, 255, 255))

    out = io.BytesIO()
    img.resize((size, size), Image.LANCZOS).save(out, format="PNG")
    return out.getvalue()


def tooltip(states: list[ProviderState]) -> str:
    """給螢幕閱讀器的純文字摘要（系統匣 szTip 上限 127 字）。"""
    parts = []
    for s in states:
        if s.windows:
            wins = " ".join(f"{w.label} {int(w.remaining_pct)}%" for w in s.windows
                            if w.remaining_pct is not None)
            parts.append(f"{s.name} {wins}")
        else:
            parts.append(f"{s.name} {s.status}")
    return ("AI Quota Tray｜" + "；".join(parts))[:127]
