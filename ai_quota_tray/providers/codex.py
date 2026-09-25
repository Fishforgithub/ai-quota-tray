"""Codex。

首選來源：~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl 最後一筆 token_count 事件的 rate_limits。
實測格式（2026-09-21，team 方案）：
    {"timestamp": "...Z", "type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
        "primary":   {"used_percent": 10.0, "window_minutes": 300,   "resets_at": <s>},
        "secondary": {"used_percent": 1.0,  "window_minutes": 10080, "resets_at": <s>},
        "plan_type": "team", ...}}}
舊版 CLI 用 resets_in_seconds（相對於事件時間），一併支援。

選配：GET https://chatgpt.com/backend-api/wham/usage（token 取自 ~/.codex/auth.json）。
不論哪個來源，label 一律由視窗長度決定，null 視窗略過（Codex 曾拿掉 5h 視窗）。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from .. import net
from ..model import (AUTH_EXPIRED, ERROR, OK, AuthExpired, ProviderState, Window,
                     apply_file_freshness, jwt_exp, make_window, parse_time, to_float, utcnow)

NAME = "codex"
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
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


# ---------- API 來源 ----------

def _api_window(w: dict, now: datetime) -> Window:
    duration = to_float(w.get("limit_window_seconds"))
    resets_at = w.get("reset_at")
    if resets_at is None and w.get("reset_after_seconds") is not None:
        resets_at = now + timedelta(seconds=to_float(w["reset_after_seconds"]) or 0)
    return make_window(w.get("used_percent"), resets_at, int(duration) if duration else None)


def parse_api(data: dict, now: datetime) -> ProviderState:
    rate_limit = data.get("rate_limit") or {}
    windows = [_api_window(rate_limit[k], now)
               for k in ("primary_window", "secondary_window") if isinstance(rate_limit.get(k), dict)]
    detail = {k: data.get(k) for k in ("plan_type", "credits") if data.get(k) is not None}
    if rate_limit.get("limit_reached"):
        detail["limit_reached"] = True
    return ProviderState(NAME, windows, now, OK, detail, source="wham-api", raw=data)


def fetch_api(now: datetime) -> ProviderState:
    auth = json.loads((codex_home() / "auth.json").read_text(encoding="utf-8"))
    tokens = auth.get("tokens") or {}
    token = tokens.get("access_token")
    if not token:
        raise AuthExpired("auth.json 沒有 access_token（是不是用 API key 登入？）")
    exp = jwt_exp(token)
    if exp and exp <= now:
        raise AuthExpired("token 已過期，請開一下 Codex CLI")
    headers = {"Authorization": f"Bearer {token}"}
    if tokens.get("account_id"):
        headers["ChatGPT-Account-Id"] = tokens["account_id"]
    return parse_api(net.get_json(USAGE_URL, headers), now)


def fetch(use_token: bool = False, now: datetime | None = None) -> ProviderState:
    now = now or utcnow()
    if not use_token:
        return fetch_rollout(now)
    try:
        return fetch_api(now)
    except (AuthExpired, net.HttpError) as exc:
        try:
            state = fetch_rollout(now)
        except (OSError, ValueError):
            status = AUTH_EXPIRED if isinstance(exc, AuthExpired) else ERROR
            return ProviderState(NAME, [], None, status, source="wham-api", error=str(exc))
        state.detail["api_error"] = str(exc)
        return state
