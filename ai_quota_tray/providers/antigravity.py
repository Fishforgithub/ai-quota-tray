"""Google Antigravity CLI（agy）。

兩個來源（業主 2026-10-04 定：照 Claude 的做法，擷取優先）：
1. 首選：狀態列擷取（agy_hook.py）寫的 ~/.gemini/antigravity-cli/ai-quota-tray/usage-cache.json：
       {"fetchedAt": <ms>, "quota": {"gemini-weekly": {...}, "3p-weekly": {...}}}
   只讀檔案、不連網（fetch_local，app 背景定時讀）；使用者在用 agy 時它一直在更新。
   跟其他檔案來源一樣照 model.apply_file_freshness 判斷過期與重置歸零。
2. 備援：快取比 CACHE_FRESH_FOR 舊、或沒裝擷取時，跑官方 `agy -p "/usage" --output-format json`
   （非互動模式會展開 slash command，不耗模型 token；登入由 agy 自己處理，不碰 token）。
   2026-10-03 調查（agy log 171 次）：中位數 4 秒，但約 4% 卡在 agy 啟動時的後端請求超過 30 秒——
   不是我們查太勤，官方也沒有寫查詢次數限制。所以：
   - 每次最多等 ATTEMPT_TIMEOUT_S，逾時就重開一支再試一次（卡住的通常只是那一次）；
     逾時當下先看它是不是已經印出答案（有一次 26 秒就印了，是結束時才被砍）。
   - 啟動前先等 STAGGER_S：打開卡片時 Codex、Copilot、Grok 的查詢會一起起來，官方 issue #573
     回報過 agy -p 跟其他 AI CLI 一起跑會卡住（推測，樣本小）。
   - stdin 關掉（官方 issue #508）；cwd 固定在我們的資料夾（不然 Store 版從 System32 起跑，agy 會把它當工作區）。
   - 兩次都逾時 → error，detail.timeout=True：卡片用灰字「查詢逾時，稍後會再試」，不當成紅字錯誤。
   CLI 失敗但手上有擷取的快取（就算舊了）→ 回快取並帶 detail.api_error（跟 Codex 退回本機 rollout 一樣）。

兩個來源的 bucket id 都是「池-視窗」（gemini-weekly、3p-weekly；3p＝第三方模型 Claude／GPT），
標籤一律是 Gemini、Claude/GPT（每週以外的視窗把視窗名接在後面），通知去重的鍵才不會因為換來源而變。
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .. import agy_hook, config
from ..model import (AUTH_EXPIRED, ERROR, OK, AuthExpired, ProviderState, Window,
                     apply_file_freshness, make_window, to_float, utcnow)

NAME = "antigravity"
log = logging.getLogger(__name__)

SOURCE_CACHE, SOURCE_CLI = "agy-statusline", "agy-cli"
ATTEMPT_TIMEOUT_S = 25.0
ATTEMPTS = 2
STAGGER_S = 3.0
CACHE_FRESH_FOR = timedelta(minutes=5)  # 擷取的快取比這新就不跑 CLI
POOL_LABELS = {"gemini": "Gemini", "3p": "Claude/GPT"}
WINDOW_DURATIONS = {"weekly": 7 * 86400, "5h": 5 * 3600}
AUTH_WORDS = ("login", "auth", "credential", "unauthenticated", "登入")


def _group_label(name: str) -> str:
    """/usage 的群組名稱轉成卡片上的簡潔標籤。"""
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


def _label(pool: str, window: str | None) -> str:
    """每週的就叫池名（跟 /usage 一樣），其他視窗把視窗名接在後面。"""
    return pool if not window or window == "weekly" else f"{pool} {window}"


def _used_pct(remaining_fraction: Any) -> float:
    # proto3 會省略 0：沒有 remaining_fraction＝剩 0
    rem = to_float(remaining_fraction)
    return round((1.0 - (rem or 0.0)) * 100.0, 1)


# ---------- 來源 1：狀態列擷取的快取 ----------

def parse_quota(quota: dict) -> list[Window]:
    """{"gemini-weekly": {...}, "3p-weekly": {...}} → 視窗。Gemini 排前面（跟 /usage 的順序一樣）。"""
    windows = []
    for key in sorted(quota, key=lambda k: (not str(k).startswith("gemini"), str(k))):
        value = quota[key]
        if not isinstance(value, dict):
            continue
        pool, _, window = str(key).partition("-")
        label = _label(POOL_LABELS.get(pool, _group_label(pool)), window or None)
        windows.append(make_window(_used_pct(value.get("remaining_fraction")), value.get("reset_time"),
                                   WINDOW_DURATIONS.get(window), label=label))
    return windows


def parse_cache(data: dict, now: datetime) -> ProviderState:
    quota = data.get("quota")
    windows = parse_quota(quota) if isinstance(quota, dict) else []
    if not windows:
        raise ValueError("擷取的快取裡沒有可辨識的 quota")
    ms = to_float(data.get("fetchedAt"))
    fetched_at = datetime.fromtimestamp(ms / 1000, timezone.utc) if ms else None
    state = ProviderState(NAME, windows, fetched_at, OK, {}, source=SOURCE_CACHE, raw=data)
    return apply_file_freshness(state, now)


def fetch_local(now: datetime) -> ProviderState:
    """只讀擷取的快取（沒裝、還沒資料 → 例外，app 會忽略、不蓋掉手上的數字）。"""
    return parse_cache(json.loads(agy_hook.cache_path().read_text(encoding="utf-8-sig")), now)


def _read_cache(now: datetime) -> ProviderState | None:
    try:
        return fetch_local(now)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:  # PowerShell 正在換檔、或內容壞了：當作沒有
        log.info("讀不到 Antigravity 擷取快取：%s", exc)
        return None


# ---------- 來源 2：agy -p /usage ----------

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


def _workdir() -> Path:
    path = config.data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _check(data: dict) -> dict:
    status = data.get("status")
    if status and status != "SUCCESS":
        resp = str(data.get("response") or status)
        if any(w in resp.lower() for w in AUTH_WORDS):
            raise AuthExpired(f"Antigravity CLI 尚未登入：{resp}")
        raise RuntimeError(f"agy CLI 查詢未成功：{resp}")
    return data


def _run_once(agy_bin: str, timeout_s: float) -> dict[str, Any]:
    creationflags = 0
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            [agy_bin, "-p", "/usage", "--output-format", "json"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=_workdir(),
            creationflags=creationflags,
            timeout=timeout_s,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"執行 agy 失敗：{exc}") from exc
    except subprocess.TimeoutExpired as exc:
        # 有時答案已經印出來了，只是結束得慢才被砍
        out = exc.stdout or b""
        out = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
        try:
            return _check(json.loads(out))
        except ValueError:
            pass
        raise TimeoutError(f"查詢 Antigravity 額度逾時（超過 {timeout_s:g} 秒）") from exc

    stdout = proc.stdout.strip()
    if proc.returncode != 0:
        msg = proc.stderr.strip() or stdout or f"exit code {proc.returncode}"
        if any(w in msg.lower() for w in AUTH_WORDS):
            raise AuthExpired(f"Antigravity CLI 尚未登入：{msg}")
        raise RuntimeError(f"agy CLI 執行失敗：{msg}")
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"agy CLI 回傳非 JSON 格式：{stdout[:100]}") from exc
    return _check(data)


def run_agy_usage(timeout_s: float = ATTEMPT_TIMEOUT_S, attempts: int = ATTEMPTS,
                  stagger_s: float = STAGGER_S) -> dict[str, Any]:
    """執行 `agy -p /usage --output-format json`；逾時就重開一支再試（見模組說明）。"""
    agy_bin = find_agy_bin()
    if stagger_s:
        time.sleep(stagger_s)
    for attempt in range(1, attempts + 1):
        try:
            return _run_once(agy_bin, timeout_s)
        except TimeoutError:
            log.info("agy /usage 第 %d 次逾時（%g 秒）", attempt, timeout_s)
            if attempt == attempts:
                raise
    raise AssertionError("unreachable")


def parse_usage(data: dict[str, Any], now: datetime) -> ProviderState:
    """將 agy CLI 回傳的 JSON 轉換成 ProviderState 與各模型群組視窗。"""
    command_data = (data.get("command") or {}).get("data") or {}
    groups = command_data.get("groups")
    windows = []

    if isinstance(groups, list) and groups:
        for g in groups:
            if not isinstance(g, dict):
                continue
            label = _group_label(g.get("name") or "Antigravity")
            for b in g.get("buckets") or []:
                if not isinstance(b, dict):
                    continue
                win_type = b.get("window")
                windows.append(make_window(_used_pct(b.get("remaining_fraction")), b.get("reset_time"),
                                           WINDOW_DURATIONS.get(win_type), label=_label(label, win_type)))
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
                windows.append(make_window(used_pct, reset_str, WINDOW_DURATIONS["weekly"], label=label))

    detail: dict[str, Any] = {}
    if command_data.get("description"):
        detail["description"] = command_data["description"]

    if not windows:
        raise ValueError("agy CLI 回傳中找不到可辨識的額度視窗")
    return ProviderState(NAME, windows, now, OK, detail, source=SOURCE_CLI, raw=data)


def fetch(use_token: bool = False, now: datetime | None = None) -> ProviderState:
    """擷取的快取夠新就用它；否則跑 agy CLI，失敗時退回快取（見模組說明）。
    use_token 是相容舊 provider 介面的參數。"""
    now = now or utcnow()
    cached = _read_cache(now)
    if cached is not None and cached.fetched_at is not None and now - cached.fetched_at <= CACHE_FRESH_FOR:
        return cached
    try:
        return parse_usage(run_agy_usage(), now)
    except AuthExpired as exc:
        return ProviderState(NAME, [], None, AUTH_EXPIRED, source=SOURCE_CLI, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — 手上有快取就退回快取，沒有才照常往上丟
        if cached is not None:
            cached.detail["api_error"] = f"{type(exc).__name__}: {exc}"
            return cached
        if isinstance(exc, TimeoutError):
            return ProviderState(NAME, [], None, ERROR, {"timeout": True}, source=SOURCE_CLI, error=str(exc))
        raise
