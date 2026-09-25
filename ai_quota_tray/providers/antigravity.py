"""Google Antigravity CLI（agy）。

透過 agy CLI 原生非互動指令查詢額度：
    agy -p "/usage" --output-format json

回傳資料結構包含 command.data.groups：
- Gemini Models（共用每週額度池）
- Claude and GPT models（共用每週額度池）

好處：
1. 不碰 OAuth Token、不需掃描內部 RPC 連線，完全由 agy 處理驗證與刷新。
2. 不消耗任何 LLM Token（total_tokens: 0）。
3. 支援 Windows 背景無黑窗執行（creationflags=CREATE_NO_WINDOW）。
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from ..model import (AUTH_EXPIRED, OK, AuthExpired, ProviderState,
                     make_window, to_float, utcnow)

NAME = "antigravity"
log = logging.getLogger(__name__)

TIMEOUT_S = 30.0


def _group_label(name: str) -> str:
    """群組名稱轉成卡片上的簡潔標籤。"""
    lower = name.lower()
    if "gemini" in lower:
        return "Gemini"
    if "claude" in lower and "gpt" in lower:
        return "Claude/GPT"
    if "claude" in lower:
        return "Claude"
    if "gpt" in lower:
        return "GPT"
    cleaned = re.sub(r"\s+models?", "", name, flags=re.IGNORECASE).strip()
    return cleaned or name


def find_agy_bin() -> str:
    """尋找 agy 執行檔位置（PATH -> %LOCALAPPDATA%\\agy\\bin -> ~/.gemini/antigravity-cli/bin）。"""
    path = shutil.which("agy") or shutil.which("agy.exe")
    if path:
        return path
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data) / "agy" / "bin" / "agy.exe"
        if candidate.is_file():
            return str(candidate)
    gemini_bin = Path.home() / ".gemini" / "antigravity-cli" / "bin" / "agy.exe"
    if gemini_bin.is_file():
        return str(gemini_bin)
    raise FileNotFoundError("找不到 agy 執行檔，請確認已安裝 Antigravity CLI 並加入 PATH")


def run_agy_usage(timeout_s: float = TIMEOUT_S) -> dict[str, Any]:
    """執行 `agy -p /usage --output-format json` 並解析標準輸出。"""
    agy_bin = find_agy_bin()
    creationflags = 0
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.run(
            [agy_bin, "-p", "/usage", "--output-format", "json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            timeout=timeout_s,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"執行 agy 失敗：{exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"查詢 Antigravity 額度逾時（超過 {timeout_s} 秒）") from exc

    stdout = proc.stdout.strip()
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        msg = stderr or stdout or f"exit code {proc.returncode}"
        if any(w in msg.lower() for w in ("login", "auth", "credential", "unauthenticated", "登入")):
            raise AuthExpired(f"Antigravity CLI 尚未登入：{msg}")
        raise RuntimeError(f"agy CLI 執行失敗：{msg}")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"agy CLI 回傳非 JSON 格式：{stdout[:100]}") from exc

    status = data.get("status")
    if status and status != "SUCCESS":
        resp = str(data.get("response") or status)
        if any(w in resp.lower() for w in ("login", "auth", "credential", "unauthenticated", "登入")):
            raise AuthExpired(f"Antigravity CLI 尚未登入：{resp}")
        raise RuntimeError(f"agy CLI 查詢未成功：{resp}")

    return data


def parse_usage(data: dict[str, Any], now: datetime) -> ProviderState:
    """將 agy CLI 回傳的 JSON 轉換成 ProviderState 與各模型群組視窗。"""
    command_data = (data.get("command") or {}).get("data") or {}
    groups = command_data.get("groups")
    windows = []

    if isinstance(groups, list) and groups:
        for g in groups:
            if not isinstance(g, dict):
                continue
            name = g.get("name") or "Antigravity"
            label = _group_label(name)
            buckets = g.get("buckets") or []
            for b in buckets:
                if not isinstance(b, dict):
                    continue
                rem = to_float(b.get("remaining_fraction"))
                if rem is None:
                    rem = 0.0
                used_pct = round((1.0 - rem) * 100.0, 1)
                resets_at = b.get("reset_time")
                win_type = b.get("window")
                duration_s = 7 * 86400 if win_type == "weekly" else None
                windows.append(make_window(used_pct, resets_at, duration_s, label=label))
    else:
        # Fallback: 若無 command.data.groups 結構，嘗試解析 response 中的 TSV 格式
        resp = data.get("response") or ""
        for line in resp.splitlines():
            parts = line.strip().split("\t")
            if len(parts) >= 4:
                gname, _, pct_str, reset_str = parts[0], parts[1], parts[2], parts[3]
                label = _group_label(gname)
                rem_pct = to_float(pct_str.rstrip("%"))
                used_pct = round(100.0 - rem_pct, 1) if rem_pct is not None else None
                windows.append(make_window(used_pct, reset_str, 7 * 86400, label=label))

    detail: dict[str, Any] = {}
    if command_data.get("description"):
        detail["description"] = command_data["description"]

    if not windows:
        raise ValueError("agy CLI 回傳中找不到可辨識的額度視窗")
    return ProviderState(NAME, windows, now, OK, detail, source="agy-cli", raw=data)


def fetch(use_token: bool = False, now: datetime | None = None) -> ProviderState:
    """透過官方 agy CLI 抓取額度；use_token 是相容舊 provider 介面的參數。"""
    now = now or utcnow()
    try:
        data = run_agy_usage()
        return parse_usage(data, now)
    except AuthExpired as exc:
        return ProviderState(NAME, [], None, AUTH_EXPIRED, source="agy-cli", error=str(exc))
