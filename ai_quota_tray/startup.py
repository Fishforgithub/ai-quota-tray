"""開機啟動：個人版用 HKCU\\...\\Run 機碼。

⚠️ MSIX 裡 HKCU 寫入會被虛擬化，Run 機碼無效 → 上線版要改用 manifest 的
windows.startupTask（CLAUDE.md §5）。
"""
from __future__ import annotations

import subprocess
import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "AiQuotaTray"


def command_line(token_set: set[str]) -> str:
    """重現目前這份程式的啟動方式，但一律不開主控台（pythonw）。"""
    if getattr(sys, "frozen", False):  # PyInstaller 打包版
        args = [sys.executable, "tray"]
    else:
        exe = Path(sys.executable)
        pythonw = exe.with_name("pythonw.exe")
        args = [str(pythonw if pythonw.exists() else exe), "-m", "ai_quota_tray", "tray"]
    if token_set:
        args += ["--token", ",".join(sorted(token_set))]
    return subprocess.list2cmdline(args)


def registered_command() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return value
    except FileNotFoundError:
        return None


def is_enabled() -> bool:
    return registered_command() is not None


def enable(token_set: set[str]) -> str:
    cmd = command_line(token_set)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, cmd)
    return cmd


def disable() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
