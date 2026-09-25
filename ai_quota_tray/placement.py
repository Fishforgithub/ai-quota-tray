"""卡片定位：純計算，不依賴 Qt，方便測試。

座標系：
- Win32（Shell_NotifyIconGetRect、GetCursorPos）給的是**實體像素**。
- Qt 的視窗座標是**邏輯像素**。Qt 6 在 Windows 上每個螢幕的邏輯原點＝實體原點，
  螢幕內再除以該螢幕的 devicePixelRatio（QHighDpi::fromNativePixels 的作法）。
矩形一律 (left, top, right, bottom)，right / bottom 不含。
"""
from __future__ import annotations

from dataclasses import dataclass

Rect = tuple[int, int, int, int]

GAP = 8  # 卡片與圖示／螢幕邊緣的距離（邏輯像素）


@dataclass(frozen=True)
class Screen:
    geometry: Rect  # 邏輯像素
    available: Rect  # 邏輯像素，扣掉工作列
    dpr: float

    @property
    def native(self) -> Rect:
        left, top, right, bottom = self.geometry
        return (left, top, left + round((right - left) * self.dpr),
                top + round((bottom - top) * self.dpr))


def _contains(rect: Rect, x: float, y: float) -> bool:
    return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]


def screen_for_physical(x: int, y: int, screens: list[Screen]) -> Screen:
    for s in screens:
        if _contains(s.native, x, y):
            return s
    # 不在任何螢幕上（理論上不會發生）→ 找最近的
    def dist(s: Screen) -> float:
        l, t, r, b = s.native
        dx = max(l - x, 0, x - r + 1)
        dy = max(t - y, 0, y - b + 1)
        return dx * dx + dy * dy
    return min(screens, key=dist)


def physical_to_logical(rect: Rect, screens: list[Screen]) -> tuple[Rect, Screen]:
    """以矩形中心所在的螢幕換算整個矩形。"""
    cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    s = screen_for_physical(cx, cy, screens)
    ox, oy = s.geometry[0], s.geometry[1]

    def conv(x: int, y: int) -> tuple[int, int]:
        return round(ox + (x - ox) / s.dpr), round(oy + (y - oy) / s.dpr)

    l, t = conv(rect[0], rect[1])
    r, b = conv(rect[2], rect[3])
    return (l, t, r, b), s


def taskbar_side(anchor: Rect, available: Rect) -> str:
    """圖示在可用區域的哪一側 → 工作列在哪一邊。inside＝溢位面板或自動隱藏的工作列。"""
    if anchor[1] >= available[3]:
        return "bottom"
    if anchor[3] <= available[1]:
        return "top"
    if anchor[2] <= available[0]:
        return "left"
    if anchor[0] >= available[2]:
        return "right"
    return "inside"


def place(anchor: Rect, size: tuple[int, int], available: Rect) -> tuple[int, int]:
    """回傳卡片左上角（邏輯像素）。貼著圖示、朝螢幕內側，並夾在可用區域內。"""
    w, h = size
    al, at, ar, ab = available
    cx, cy = (anchor[0] + anchor[2]) // 2, (anchor[1] + anchor[3]) // 2
    side = taskbar_side(anchor, available)

    if side == "top":
        x, y = cx - w // 2, max(anchor[3], at) + GAP
    elif side == "left":
        x, y = max(anchor[2], al) + GAP, cy - h // 2
    elif side == "right":
        x, y = min(anchor[0], ar) - w - GAP, cy - h // 2
    elif side == "bottom":
        x, y = cx - w // 2, min(anchor[1], ab) - h - GAP
    else:  # inside：放圖示上方，上面放不下改放下方
        x, y = cx - w // 2, anchor[1] - h - GAP
        if y < at + GAP:
            y = anchor[3] + GAP

    x = min(max(x, al + GAP), ar - w - GAP)
    y = min(max(y, at + GAP), ab - h - GAP)
    return x, y
