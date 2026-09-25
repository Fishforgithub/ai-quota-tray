"""原生系統匣圖示（ctypes 直接呼叫 Win32）。

為什麼不用 QSystemTrayIcon：它會顯示原生 tooltip，也收不到 NIN_POPUPOPEN / NIN_POPUPCLOSE。
為什麼不用 pywin32：它沒包 Shell_NotifyIconGetRect（P3 定位卡片要用），
NOTIFYICON_VERSION_4 的 union 欄位也不好填；ctypes 反而少一個相依。

作法（CLAUDE.md §4）：
- 建一個「隱藏但非 message-only」的頂層視窗收回呼訊息。不用 message-only 是因為
  TaskbarCreated（Explorer 重啟）只廣播給頂層視窗，TrackPopupMenu 也需要能 SetForegroundWindow。
- Qt 的事件迴圈本來就會 DispatchMessage 同執行緒所有視窗 → 不需要第二個迴圈。
- NOTIFYICON_VERSION_4 且不設 NIF_SHOWTIP → hover 收 NIN_POPUPOPEN／離開收 NIN_POPUPCLOSE，沒有原生 tooltip。
"""
from __future__ import annotations

import ctypes
import logging
import traceback
from ctypes import wintypes as w
from typing import Callable

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

WM_NULL, WM_CLOSE, WM_CONTEXTMENU, WM_POWERBROADCAST = 0x0000, 0x0010, 0x007B, 0x0218
PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC = 0x0007, 0x0012
WM_APP = 0x8000
WM_TRAY = WM_APP + 1
NIN_SELECT, NIN_KEYSELECT = 0x0400, 0x0401
NIN_BALLOONUSERCLICK = 0x0405
NIN_POPUPOPEN, NIN_POPUPCLOSE = 0x0406, 0x0407
NIM_ADD, NIM_MODIFY, NIM_DELETE, NIM_SETVERSION = 0, 1, 2, 4
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
NIIF_WARNING, NIIF_USER, NIIF_LARGE_ICON, NIIF_RESPECT_QUIET_TIME = 0x02, 0x04, 0x20, 0x80
NOTIFYICON_VERSION_4 = 4
MF_STRING, MF_GRAYED, MF_CHECKED, MF_SEPARATOR = 0x0000, 0x0001, 0x0008, 0x0800
TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x0002, 0x0080, 0x0100
TPM_BOTTOMALIGN = 0x0020
SM_CXICON, SM_CXSMICON = 11, 49
ERROR_ALREADY_EXISTS = 183
TRAY_ID = 1


class GUID(ctypes.Structure):
    _fields_ = [("Data1", w.DWORD), ("Data2", w.WORD), ("Data3", w.WORD), ("Data4", w.BYTE * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT), ("uFlags", w.UINT),
        ("uCallbackMessage", w.UINT), ("hIcon", w.HICON), ("szTip", w.WCHAR * 128),
        ("dwState", w.DWORD), ("dwStateMask", w.DWORD), ("szInfo", w.WCHAR * 256),
        ("uVersion", w.UINT),  # 與 uTimeout 共用 union
        ("szInfoTitle", w.WCHAR * 64), ("dwInfoFlags", w.DWORD), ("guidItem", GUID),
        ("hBalloonIcon", w.HICON),
    ]


class NOTIFYICONIDENTIFIER(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT), ("guidItem", GUID)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.UINT), ("style", w.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
        ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH), ("lpszMenuName", w.LPCWSTR),
        ("lpszClassName", w.LPCWSTR), ("hIconSm", w.HICON),
    ]


def _sig(fn, restype, *argtypes):
    fn.restype, fn.argtypes = restype, list(argtypes)


# 64 位元下 WPARAM/LPARAM/HANDLE 都要宣告型別，否則會被截成 32 位元
_sig(user32.DefWindowProcW, LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
_sig(user32.RegisterClassExW, w.ATOM, ctypes.POINTER(WNDCLASSEXW))
_sig(user32.UnregisterClassW, w.BOOL, w.LPCWSTR, w.HINSTANCE)
_sig(user32.CreateWindowExW, w.HWND, w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int,
     ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID)
_sig(user32.DestroyWindow, w.BOOL, w.HWND)
_sig(user32.RegisterWindowMessageW, w.UINT, w.LPCWSTR)
_sig(user32.CreateIconFromResourceEx, w.HICON, ctypes.c_void_p, w.DWORD, w.BOOL, w.DWORD,
     ctypes.c_int, ctypes.c_int, w.UINT)
_sig(user32.DestroyIcon, w.BOOL, w.HICON)
_sig(user32.CreatePopupMenu, w.HMENU)
_sig(user32.AppendMenuW, w.BOOL, w.HMENU, w.UINT, ctypes.c_size_t, w.LPCWSTR)
_sig(user32.TrackPopupMenu, w.BOOL, w.HMENU, w.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
     w.HWND, ctypes.c_void_p)
_sig(user32.DestroyMenu, w.BOOL, w.HMENU)
_sig(user32.SetForegroundWindow, w.BOOL, w.HWND)
_sig(user32.PostMessageW, w.BOOL, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
_sig(user32.GetCursorPos, w.BOOL, ctypes.POINTER(w.POINT))
_sig(user32.GetWindowRect, w.BOOL, w.HWND, ctypes.POINTER(w.RECT))
_sig(user32.GetDpiForSystem, w.UINT)
_sig(user32.GetSystemMetricsForDpi, ctypes.c_int, ctypes.c_int, w.UINT)
_sig(shell32.Shell_NotifyIconW, w.BOOL, w.DWORD, ctypes.POINTER(NOTIFYICONDATAW))
_sig(shell32.Shell_NotifyIconGetRect, ctypes.c_long, ctypes.POINTER(NOTIFYICONIDENTIFIER),
     ctypes.POINTER(w.RECT))
_sig(kernel32.GetModuleHandleW, w.HMODULE, w.LPCWSTR)
_sig(kernel32.CreateMutexW, w.HANDLE, w.LPVOID, w.BOOL, w.LPCWSTR)


def _signed_word(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def cursor_pos() -> tuple[int, int]:
    """滑鼠位置（實體像素）。"""
    pt = w.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """視窗在螢幕上的矩形（實體像素）。"""
    rect = w.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def small_icon_size() -> int:
    """系統匣圖示的實際像素（依系統 DPI，100% = 16、150% = 24）。"""
    return user32.GetSystemMetricsForDpi(SM_CXSMICON, user32.GetDpiForSystem())


def large_icon_size() -> int:
    """通知（NIIF_LARGE_ICON）用的大圖示像素（100% = 32）。"""
    return user32.GetSystemMetricsForDpi(SM_CXICON, user32.GetDpiForSystem())


def acquire_single_instance(name: str) -> object | None:
    """拿到回傳 handle（呼叫端要一直留著）；已有另一份在跑回 None。"""
    handle = kernel32.CreateMutexW(None, False, name)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def hicon_from_png(png: bytes, size: int) -> int:
    # Vista 起圖示資源可以直接是 PNG，CreateIconFromResourceEx 看得懂
    buf = (ctypes.c_ubyte * len(png)).from_buffer_copy(png)
    hicon = user32.CreateIconFromResourceEx(buf, len(png), True, 0x00030000, size, size, 0)
    if not hicon:
        raise ctypes.WinError(ctypes.get_last_error())
    return hicon


# (id, 文字, 可否點選, 是否打勾)；id 為 None 表示分隔線
MenuItem = tuple[int | None, str, bool, bool]


class TrayIcon:
    """on_event(kind, x, y)：kind 是 popup_open / popup_close / context_menu / select，
    balloon_click（點了通知）、resume（睡眠喚醒），
    以及 quit（有人對隱藏視窗送 WM_CLOSE，例如安裝程式要關掉我們）。
    座標是實體像素（Qt 6 預設 Per-Monitor DPI aware v2）。"""

    CLASS_NAME = "AiQuotaTrayWindow"

    def __init__(self, on_event: Callable[[str, int, int], None], tooltip: str = "AI Quota Tray"):
        self._on_event = on_event
        self._tooltip = tooltip
        self._hicon = None
        self._balloon_hicon = None
        self._hinst = kernel32.GetModuleHandleW(None)
        self._wndproc = WNDPROC(self._proc)  # 要留參考，不然會被 GC 掉
        self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")

        wc = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=self._wndproc,
                         hInstance=self._hinst, lpszClassName=self.CLASS_NAME)
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            raise ctypes.WinError(ctypes.get_last_error())
        # style=0、不 ShowWindow → 隱藏的頂層視窗
        self.hwnd = user32.CreateWindowExW(0, self.CLASS_NAME, "AI Quota Tray", 0,
                                           0, 0, 0, 0, None, None, self._hinst, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._added = False

    # ---------- Shell_NotifyIcon ----------

    def _data(self, flags: int) -> NOTIFYICONDATAW:
        nid = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self.hwnd,
                              uID=TRAY_ID, uFlags=flags, uCallbackMessage=WM_TRAY)
        nid.hIcon = self._hicon
        nid.szTip = self._tooltip[:127]
        return nid

    def _add(self) -> None:
        # 刻意不設 NIF_SHOWTIP（原則：不要原生 tooltip，要 NIN_POPUPOPEN）
        nid = self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            log.warning("NIM_ADD 失敗（Explorer 可能還沒起來）")
            return
        nid.uVersion = NOTIFYICON_VERSION_4
        shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(nid))
        self._added = True

    def set_icon(self, png: bytes, size: int) -> None:
        old, self._hicon = self._hicon, hicon_from_png(png, size)
        if self._added:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._data(NIF_ICON | NIF_TIP)))
        else:
            self._add()
        if old:
            user32.DestroyIcon(old)

    def set_tooltip(self, text: str) -> None:
        """不會顯示成原生 tooltip，給螢幕閱讀器用。"""
        self._tooltip = text
        if self._added:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._data(NIF_TIP)))

    def set_balloon_icon(self, png: bytes, size: int) -> None:
        """通知用的大圖示（品牌圖示）。沒設就用系統的警告圖示。"""
        old, self._balloon_hicon = self._balloon_hicon, hicon_from_png(png, size)
        if old:
            user32.DestroyIcon(old)

    def show_balloon(self, title: str, text: str) -> None:
        """Windows 10/11 會顯示成 toast 通知；勿擾模式（quiet time）時不打擾。"""
        if not self._added:
            return
        nid = self._data(NIF_INFO)
        nid.szInfoTitle = title[:63]
        nid.szInfo = text[:255]
        if self._balloon_hicon:
            nid.hBalloonIcon = self._balloon_hicon
            nid.dwInfoFlags = NIIF_USER | NIIF_LARGE_ICON | NIIF_RESPECT_QUIET_TIME
        else:
            nid.dwInfoFlags = NIIF_WARNING | NIIF_RESPECT_QUIET_TIME
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def icon_rect(self) -> tuple[int, int, int, int] | None:
        """圖示在螢幕上的矩形（實體像素）。圖示收在溢位區且溢位區關著時會失敗。"""
        ident = NOTIFYICONIDENTIFIER(cbSize=ctypes.sizeof(NOTIFYICONIDENTIFIER),
                                     hWnd=self.hwnd, uID=TRAY_ID)
        rect = w.RECT()
        if shell32.Shell_NotifyIconGetRect(ctypes.byref(ident), ctypes.byref(rect)) != 0:
            return None
        return rect.left, rect.top, rect.right, rect.bottom

    def show_menu(self, items: list[MenuItem], x: int | None = None, y: int | None = None) -> int | None:
        """原生選單，回傳被點的 id（沒點回 None）。"""
        if x is None or y is None:
            x, y = cursor_pos()
        menu = user32.CreatePopupMenu()
        try:
            for item_id, text, enabled, checked in items:
                if item_id is None:
                    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                else:
                    flags = MF_STRING | (0 if enabled else MF_GRAYED) | (MF_CHECKED if checked else 0)
                    user32.AppendMenuW(menu, flags, item_id, text)
            # 不先 SetForegroundWindow 的話，點選單外面選單不會關（KB135788）
            user32.SetForegroundWindow(self.hwnd)
            cmd = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON
                                        | TPM_BOTTOMALIGN, x, y, 0, self.hwnd, None)
            user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        finally:
            user32.DestroyMenu(menu)
        return cmd or None

    def close(self) -> None:
        if self._added:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._data(0)))
            self._added = False
        for attr in ("_hicon", "_balloon_hicon"):
            if getattr(self, attr):
                user32.DestroyIcon(getattr(self, attr))
                setattr(self, attr, None)
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
            user32.UnregisterClassW(self.CLASS_NAME, self._hinst)

    # ---------- 視窗程序 ----------

    def _proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY:
                # VERSION_4：LOWORD(lParam)=事件，wParam=錨點座標
                event = lparam & 0xFFFF
                x, y = _signed_word(wparam), _signed_word(wparam >> 16)
                kind = {NIN_POPUPOPEN: "popup_open", NIN_POPUPCLOSE: "popup_close",
                        WM_CONTEXTMENU: "context_menu", NIN_SELECT: "select",
                        NIN_KEYSELECT: "select", NIN_BALLOONUSERCLICK: "balloon_click"}.get(event)
                if kind:
                    self._on_event(kind, x, y)
                return 0
            if msg == WM_POWERBROADCAST:
                if wparam in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND):
                    self._on_event("resume", 0, 0)
                return 1  # TRUE：允許
            if msg == WM_CLOSE:
                self._on_event("quit", 0, 0)
                return 0  # 不交給 DefWindowProc：視窗由 close() 統一銷毀
            if msg == self._taskbar_created and self._taskbar_created:
                log.info("Explorer 重新啟動，重新登錄系統匣圖示")
                self._added = False
                self._add()
                return 0
        except Exception:  # noqa: BLE001 — 例外穿過 ctypes callback 會直接吞掉，至少印出來
            log.error("系統匣事件處理失敗\n%s", traceback.format_exc())
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
