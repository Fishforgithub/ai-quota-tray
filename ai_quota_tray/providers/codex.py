"""Codex。

首選來源：官方 Codex App Server 的 account/rateLimits/read。
失敗時讀取 ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl 的 rate_limits。
實測格式（2026-09-21，team 方案）：
    {"timestamp": "...Z", "type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
        "primary":   {"used_percent": 10.0, "window_minutes": 300,   "resets_at": <s>},
        "secondary": {"used_percent": 1.0,  "window_minutes": 10080, "resets_at": <s>},
        "plan_type": "team", ...}}}
舊版 CLI 用 resets_in_seconds（相對於事件時間），一併支援。

不論哪個來源，label 一律由視窗長度決定，null 視窗略過（Codex 曾拿掉 5h 視窗）。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from ..codex_app_server import AppServerError, client
from ..model import (ERROR, OK, ProviderState, Window, apply_file_freshness,
                     make_window, parse_time, to_float, utcnow)

NAME = "codex"
SCAN_DAY_DIRS = 14  # 長時間的 session 會繼續寫在開始那天的目錄，所以往回多看幾天
SCAN_FILES = 20


def codex_home() -> Path:
    env = os.environ.get("CODEX_HOME")
    return Path(env) if env else Path.home() / ".codex"


# ---------- 檔案來源 ----------

def recent_rollouts(sessions_dir: Path) -> list[Path]:
    """最近幾天目錄內的 rollout 檔，依修改時間新到舊。"""
    day_dirs = sorted(sessions_dir.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]"), reverse=True)
    files = [f for d in day_dirs[:SCAN_DAY_DIRS] for f in d.glob("rollout-*.jsonl")]
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)[:SCAN_FILES]


def last_rate_limit_event(path: Path) -> dict | None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        if '"token_count"' not in line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # 正在寫入的最後一行可能不完整
        payload = event.get("payload") or {}
        if payload.get("type") == "token_count" and isinstance(payload.get("rate_limits"), dict):
            return event
    return None


def _event_window(w: dict, event_time: datetime | None) -> Window:
    minutes = to_float(w.get("window_minutes"))
    duration = int(minutes * 60) if minutes else None
    resets_at = w.get("resets_at")
    if resets_at is None and w.get("resets_in_seconds") is not None and event_time:
        resets_at = event_time + timedelta(seconds=to_float(w["resets_in_seconds"]) or 0)
    return make_window(w.get("used_percent"), resets_at, duration)


def parse_event(event: dict, now: datetime) -> ProviderState:
    limits = event["payload"]["rate_limits"]
    event_time = parse_time(event.get("timestamp"))
    windows = [_event_window(limits[k], event_time)
               for k in ("primary", "secondary") if isinstance(limits.get(k), dict)]
    detail = {k: limits.get(k) for k in ("plan_type", "limit_id", "credits",
                                         "rate_limit_reached_type") if limits.get(k) is not None}
    state = ProviderState(NAME, windows, event_time, OK, detail, source="rollout", raw=event)
    return apply_file_freshness(state, now)


def fetch_rollout(now: datetime) -> ProviderState:
    sessions = codex_home() / "sessions"
    for path in recent_rollouts(sessions):
        event = last_rate_limit_event(path)
        if event:
            state = parse_event(event, now)
            state.detail["file"] = path.name
            return state
    raise FileNotFoundError(f"{sessions} 最近 {SCAN_DAY_DIRS} 天內找不到含 rate_limits 的 token_count 事件")


# ---------- 官方 App Server 來源 ----------

def _server_window(w: dict) -> Window:
    minutes = to_float(w.get("windowDurationMins"))
    duration = int(minutes * 60) if minutes else None
    return make_window(w.get("usedPercent"), w.get("resetsAt"), duration)


def parse_app_server(data: dict, now: datetime) -> ProviderState:
    by_id = data.get("rateLimitsByLimitId")
    if isinstance(by_id, dict) and by_id:
        limits = by_id.get("codex")
    else:
        limits = data.get("rateLimits")
        if isinstance(limits, dict) and limits.get("limitId") not in (None, "codex"):
            limits = None
    if not isinstance(limits, dict):
        raise ValueError("Codex App Server 沒有 Codex 額度資料")
    windows = [_server_window(limits[k]) for k in ("primary", "secondary")
               if isinstance(limits.get(k), dict)]
    if not windows:
        raise ValueError("Codex App Server 沒有額度視窗")
    detail = {k: limits[k] for k in ("planType", "credits", "rateLimitReachedType")
              if limits.get(k) is not None}
    if "planType" in detail:
        detail["plan_type"] = detail.pop("planType")
    return ProviderState(NAME, windows, now, OK, detail, source="codex-app-server", raw=limits)


def fetch_app_server(now: datetime) -> ProviderState:
    return parse_app_server(client.rate_limits(), now)


def fetch(use_token: bool = False, now: datetime | None = None) -> ProviderState:
    now = now or utcnow()
    try:
        return fetch_app_server(now)
    except (AppServerError, OSError, ValueError) as exc:
        try:
            state = fetch_rollout(now)
        except (OSError, ValueError):
            return ProviderState(NAME, [], None, ERROR, source="codex-app-server", error=str(exc))
        state.detail["api_error"] = str(exc)
        return state
