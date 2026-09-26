"""系統匣圖示的霓虹外圈動畫：只轉外圈那一環，中間的「Ai」、紅點、底色都不動。

品牌圖示（assets/app.png，512px）外圈是一圈 conic 漸層，轉那一環看起來就是霓虹光在繞圈流動。
做法：把 app.png 轉一個角度，用環形遮罩只取外圈那一段疊回原圖。預先算好 FRAMES 張，
由 app.py 每 PERIOD_S / FRAMES 秒換一張（NIM_MODIFY），跟 RunCat 那類會動的系統匣圖示同一種做法。

環的位置是量出來的（2026-09-26，飽和度高的像素＝霓虹圈）：圓心 (261, 260.5)、霓虹本體半徑約 146～210，
外面還有一層光暈。遮罩範圍踩過兩個坑，改參數要重看預覽：
- 內緣太小（128）會切到紅點外圍的光暈 → 圈內側有一個灰色小光點跟著轉。
- 外緣太大（232）會碰到圓角方形的邊框 → 方形轉起來對不上，外圍一圈深色輪廓。
"""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFilter

from .icon import BRAND_PNG

FRAMES = 60
PERIOD_S = 6.0  # 轉一圈的秒數：「緩慢旋轉」
SOURCE_SIZE = 512
RING_CENTER = (261.0, 260.5)  # 在 512px 原圖上
RING_INNER, RING_OUTER, FEATHER = 140, 222, 5
WORK_SCALE = 4  # 在目標尺寸的 4 倍上旋轉再縮小：比直接在 16～32px 上轉清楚，也比在 512px 上轉快


def frame_interval_ms() -> int:
    return round(PERIOD_S * 1000 / FRAMES)


def _ring_mask(size: int) -> Image.Image:
    k = size / SOURCE_SIZE
    cx, cy = RING_CENTER[0] * k, RING_CENTER[1] * k
    r_in, r_out = RING_INNER * k, RING_OUTER * k
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((cx - r_out, cy - r_out, cx + r_out, cy + r_out), fill=255)
    draw.ellipse((cx - r_in, cy - r_in, cx + r_in, cy + r_in), fill=0)
    return mask.filter(ImageFilter.GaussianBlur(FEATHER * k))


def frame_images(size: int, count: int = FRAMES) -> list[Image.Image]:
    """size×size 的 RGBA 畫格，第 0 張就是沒轉過的樣子。"""
    work = max(size * WORK_SCALE, 64)
    base = Image.open(BRAND_PNG).convert("RGBA").resize((work, work), Image.LANCZOS)
    mask = _ring_mask(work)
    k = work / SOURCE_SIZE
    center = (RING_CENTER[0] * k, RING_CENTER[1] * k)
    frames = []
    for i in range(count):
        rotated = base.rotate(-360 * i / count, resample=Image.BICUBIC, center=center)
        frames.append(Image.composite(rotated, base, mask).resize((size, size), Image.LANCZOS))
    return frames


def frame_pngs(size: int, count: int = FRAMES) -> list[bytes]:
    """給 win32tray.TrayIcon.set_frames 用的 PNG bytes。"""
    out = []
    for img in frame_images(size, count):
        buf = io.BytesIO()
        img.save(buf, "PNG")
        out.append(buf.getvalue())
    return out
