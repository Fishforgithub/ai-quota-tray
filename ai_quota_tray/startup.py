"""開機啟動，兩條路：

- 一般安裝（venv、PyInstaller 打包版）：HKCU\\...\\Run 機碼。
- MSIX 套件（Store 版）：manifest 的 windows.startupTask，用 WinRT 的 StartupTask API 開關。
  MSIX 裡 HKCU 寫入會被虛擬化，Run 機碼無效（CLAUDE.md §5）。StartupTask 只能由「帶套件身分的
  程式本身」呼叫，所以一定要在 App 裡做，不能叫外部工具幫忙。TaskId 必須與
  packaging/msix/AppxManifest.xml 的 StartupTask TaskId 完全一致。
  使用者在工作管理員／Windows 設定裡關掉過（DisabledByUser），App 就不能自己再打開，
  只能請使用者去 Windows 設定開 → enable() 丟 StartupBlocked，由呼叫端提示。
"""
from __future__ import annotations

import asyncio
import ctypes
import subprocess
import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "AiQuotaTray"
TASK_ID = "AiQuotaTrayStartup"
APPMODEL_ERROR_NO_PACKAGE = 15700


class StartupBlocked(Exception):
    """使用者或群組原則把開機啟動關了，App 不能自己打開。"""


def is_packaged() -> bool:
    """這個行程有沒有 MSIX 套件身分（從開始功能表啟動的 Store 版才有；直接跑 exe 沒有）。"""
    if sys.platform != "win32":
        return False
    length = ctypes.c_uint32(0)
    try:
        rc = ctypes.windll.kernel32.GetCurrentPackageFullName(ctypes.byref(length), None)
    except AttributeError:  # Windows 7：沒有這個 API
        return False
    return rc != APPMODEL_ERROR_NO_PACKAGE


# ---------- MSIX：StartupTask ----------

def _task():
    from winrt.windows.applicationmodel import StartupTask

    async def get():
        return await StartupTask.get_async(TASK_ID)
    return asyncio.run(get())


def _task_state() -> str:
    from winrt.windows.applicationmodel import StartupTaskState
    return StartupTaskState(_task().state).name


# ---------- 一般安裝：Run 機碼 ----------

def command_line() -> str:
    """重現目前這份程式的啟動方式，但一律不開主控台（pythonw）。"""
    if getattr(sys, "frozen", False):  # PyInstaller 打包版
        args = [sys.executable, "tray"]
    else:
        exe = Path(sys.executable)
        pythonw = exe.with_name("pythonw.exe")
        args = [str(pythonw if pythonw.exists() else exe), "-m", "ai_quota_tray", "tray"]
    return subprocess.list2cmdline(args)


def registered_command() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return value
    except FileNotFoundError:
        return None


# ---------- 對外介面 ----------

def is_enabled() -> bool:
    if is_packaged():
        return _task_state() in ("ENABLED", "ENABLED_BY_POLICY")
    return registered_command() is not None


def enable() -> str:
    """打開開機啟動，回傳給 log 看的說明。MSIX 版被使用者／原則擋住時丟 StartupBlocked。"""
    if is_packaged():
        task = _task()

        async def request():
            return await task.request_enable_async()
        from winrt.windows.applicationmodel import StartupTaskState
        state = StartupTaskState(asyncio.run(request())).name
        if state not in ("ENABLED", "ENABLED_BY_POLICY"):
            raise StartupBlocked(state)
        return f"StartupTask {TASK_ID}: {state}"
    cmd = command_line()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, cmd)
    return cmd


def disable() -> None:
    if is_packaged():
        _task().disable()
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass


def describe() -> str:
    """目前的開機啟動狀態（給 `startup` 子命令與除錯用）。"""
    if is_packaged():
        return f"MSIX StartupTask {TASK_ID}: {_task_state()}"
    cmd = registered_command()
    return f"Run 機碼：{cmd}" if cmd else "Run 機碼：未設定"
