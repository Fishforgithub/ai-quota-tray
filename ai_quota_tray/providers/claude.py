"""Claude。

首選來源：statusLine hook（D:\\FISH\\tools\\claude-monitor\\statusline-usage.js）寫的
~/.claude/usage-cache.json，格式：
    {"fetchedAt": <ms>, "rate_limits": {"five_hour": {"used_percentage": 9, "resets_at": <s>}, ...}}
不碰 token，上線版唯一來源。

選配：GET https://api.anthropic.com/api/oauth/usage（⚠️ Consumer ToS 風險，見 CLAUDE.md §3）。
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from .. import net
from ..model import (AUTH_EXPIRED, ERROR, OK, AuthExpired, ProviderState, Window,
                     apply_file_freshness, make_window, parse_time, utcnow)

NAME = "claude"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"

# rate_limits 的 key 前綴 → 視窗長度；後綴（例如 seven_day_opus 的 opus）接在 label 後面
_PREFIX_DURATION = {"five_hour": 5 * 3600, "seven_day": 7 * 86400}


def cache_path() -> Path:
    # 與 statusline-usage.js 的 CACHE_PATH 保持一致
    env = os.environ.get("CLAUDE_USAGE_CACHE")
    return Path(env) if env else Path.home() / ".claude" / "usage-cache.json"


def credentials_path() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base) if base else Path.home() / ".claude") / ".credentials.json"


def parse_windows(limits: dict, pct_field: str) -> tuple[list[Window], dict]:
    """把 {five_hour: {...}, seven_day: {...}, seven_day_opus: ...} 轉成視窗。

    認不得的 key 不硬猜，原樣放進 unknown 讓 probe 看得到。
    """
    windows, unknown = [], {}
    for key, value in limits.items():
        prefix = next((p for p in _PREFIX_DURATION if key == p or key.startswith(p + "_")), None)
        if value is None:
            continue
        if prefix is None or not isinstance(value, dict):
            unknown[key] = value
            continue
        duration = _PREFIX_DURATION[prefix]
        window = make_window(value.get(pct_field), value.get("resets_at"), duration)
        suffix = key[len(prefix) + 1:]
        if suffix:
            window.label = f"{window.label}·{suffix}"
        windows.append(window)
    return windows, unknown


def parse_cache(data: dict, now: datetime) -> ProviderState:
    limits = data.get("rate_limits")
    if not isinstance(limits, dict):
        raise ValueError("usage-cache.json 缺 rate_limits")
    windows, unknown = parse_windows(limits, "used_percentage")
    detail = {"unknown_keys": unknown} if unknown else {}
    state = ProviderState(NAME, windows, parse_time(data.get("fetchedAt")), OK,
                          detail, source="statusline-cache", raw=data)
    return apply_file_freshness(state, now)


def parse_oauth_usage(data: dict, now: datetime) -> ProviderState:
    windows, unknown = parse_windows(data, "utilization")
    detail = {"unknown_keys": unknown} if unknown else {}
    return ProviderState(NAME, windows, now, OK, detail, source="oauth-api", raw=data)


def fetch_cache(now: datetime) -> ProviderState:
    path = cache_path()
    if not path.exists():
        raise FileNotFoundError(f"找不到 {path}（statusLine hook 沒裝，或 Claude Code 還沒跑過）")
    return parse_cache(json.loads(path.read_text(encoding="utf-8")), now)


def fetch_oauth(now: datetime) -> ProviderState:
    oauth = json.loads(credentials_path().read_text(encoding="utf-8")).get("claudeAiOauth") or {}
    token = oauth.get("accessToken")
    expires = parse_time(oauth.get("expiresAt"))
    if not token or (expires and expires <= now):
        raise AuthExpired("token 已過期，請開一下 Claude Code")
    data = net.get_json(USAGE_URL, {
        "Authorization": f"Bearer {token}",
        "anthropic-beta": "oauth-2025-04-20",
    })
    return parse_oauth_usage(data, now)


def fetch(use_token: bool = False, now: datetime | None = None) -> ProviderState:
    now = now or utcnow()
    if not use_token:
        return fetch_cache(now)
    try:
        return fetch_oauth(now)
    except (AuthExpired, net.HttpError) as exc:
        # API 不能用時退回 cache；cache 也沒有才回報 API 的錯
        try:
            state = fetch_cache(now)
        except (OSError, ValueError):
            status = AUTH_EXPIRED if isinstance(exc, AuthExpired) else ERROR
            return ProviderState(NAME, [], None, status, source="oauth-api", error=str(exc))
        state.detail["api_error"] = str(exc)
        return state
