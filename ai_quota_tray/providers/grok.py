"""Grok（最脆弱的一家）。

只有 token 來源：~/.grok/auth.json（Grok Build CLI 登入後產生），沒有不碰 token 的做法。
2026-06 改制後是「每週共用運算額度池」，沒有 5h 視窗；部分方案另有月額度。

    週：GET {BASE}/billing?format=credits  → currentPeriod / creditUsagePercent / productUsage[]
    月：GET {BASE}/billing                 → monthlyLimit / used / billingPeriodEnd
    方案：GET {BASE}/user?include=subscription → subscriptionTier

⚠️ proto3：值為 0 的欄位會被省略；數值可能包成 {"val": ...}。
參考：PyPI quse（quse/grok_quota.py，MIT）。與 quse 不同的是主數字用整池的
creditUsagePercent（真正會擋人的是整池），GrokBuild 佔比只放 detail。
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import net
from ..model import (AUTH_EXPIRED, DISABLED, OK, AuthExpired, ProviderState, Window,
                     make_window, parse_time, to_float, utcnow)

NAME = "grok"
BASE_URL = "https://cli-chat-proxy.grok.com/v1"
WEEKLY = "USAGE_PERIOD_TYPE_WEEKLY"
_PERIOD_DURATION = {"USAGE_PERIOD_TYPE_DAILY": 86400, WEEKLY: 7 * 86400}


def auth_path() -> Path:
    env = os.environ.get("GROK_HOME")
    return (Path(env) if env else Path.home() / ".grok") / "auth.json"


def _config(data: dict | None) -> dict:
    if not isinstance(data, dict):
        return {}
    inner = data.get("config")
    return inner if isinstance(inner, dict) else data


def _ts(value: Any) -> datetime | None:
    # proto Timestamp 可能是 ISO 字串，也可能是 {"seconds": ...}
    if isinstance(value, dict) and "seconds" in value:
        value = value["seconds"]
    return parse_time(value)


def _duration(start: datetime | None, end: datetime | None, fallback: int | None) -> int | None:
    if start and end and end > start:
        return int((end - start).total_seconds())
    return fallback


def weekly_window(cfg: dict) -> Window | None:
    period = cfg.get("currentPeriod") if isinstance(cfg.get("currentPeriod"), dict) else {}
    period_type = period.get("type")
    used = to_float(cfg.get("creditUsagePercent"))
    if used is None:
        cap, spent = to_float(cfg.get("onDemandCap")), to_float(cfg.get("onDemandUsed"))
        if cap and cap > 0:
            used = (spent or 0.0) / cap * 100
    if used is None:
        if period_type != WEEKLY:
            return None
        used = 0.0  # proto3 省略了 0，不是「無資料」
    end = _ts(period.get("end")) or _ts(cfg.get("billingPeriodEnd"))
    start = _ts(period.get("start"))
    return make_window(used, end, _duration(start, end, _PERIOD_DURATION.get(period_type)))


def monthly_window(cfg: dict) -> Window | None:
    limit = to_float(cfg.get("monthlyLimit"))
    if not limit or limit <= 0:
        return None
    used = to_float(cfg.get("used")) or 0.0
    end = _ts(cfg.get("billingPeriodEnd"))
    start = _ts(cfg.get("billingPeriodStart"))
    return make_window(used / limit * 100, end, _duration(start, end, None), label="月")


def parse_billing(credits: dict, monthly: dict | None, user: dict | None,
                  now: datetime) -> ProviderState:
    cfg = _config(credits)
    windows = [w for w in (weekly_window(cfg), monthly_window(_config(monthly))) if w]
    detail: dict[str, Any] = {}
    period = cfg.get("currentPeriod")
    if isinstance(period, dict) and period.get("type"):
        detail["period_type"] = period["type"]
    products = [
        {"product": p.get("product"), "usage_pct": to_float(p.get("usagePercent")) or 0.0}
        for p in cfg.get("productUsage") or [] if isinstance(p, dict) and p.get("product")
    ]
    if products:
        detail["products"] = products
    for src, dst in (("onDemandUsed", "on_demand_used"), ("onDemandCap", "on_demand_cap"),
                     ("prepaidBalance", "prepaid_balance")):
        if to_float(cfg.get(src)) is not None:
            detail[dst] = to_float(cfg.get(src))
    if isinstance(user, dict) and user.get("subscriptionTier"):
        detail["subscription_tier"] = user["subscriptionTier"]
    raw = {"credits": credits, "monthly": monthly, "user": user}
    return ProviderState(NAME, windows, now, OK, detail, source="billing-api", raw=raw)


def read_token(now: datetime) -> str:
    """挑第一個還沒過期的 entry。只讀不寫，過期不 refresh（原則 3）。"""
    data = json.loads(auth_path().read_text(encoding="utf-8"))
    entries = [e for e in data.values() if isinstance(e, dict) and e.get("key")]
    if not entries:
        raise AuthExpired("auth.json 沒有 token，請先用 Grok Build CLI 登入")
    for entry in entries:
        expires = parse_time(entry.get("expires_at"))
        if expires is None or expires > now:
            return entry["key"]
    raise AuthExpired("token 已過期，請開一下 Grok CLI")


def fetch(use_token: bool = False, now: datetime | None = None) -> ProviderState:
    now = now or utcnow()
    if not use_token:
        return ProviderState(NAME, [], None, DISABLED, source="billing-api",
                             error="Grok 只有 token 來源，未啟用")
    try:
        token = read_token(now)
        headers = {"Authorization": f"Bearer {token}", "x-grok-client-mode": "cli"}
        credits = net.get_json(f"{BASE_URL}/billing?format=credits", headers)
    except AuthExpired as exc:
        return ProviderState(NAME, [], None, AUTH_EXPIRED, source="billing-api", error=str(exc))

    # 月額度與方案資訊是加分項，失敗不影響週視窗
    optional, errors = {}, {}
    for key, path in (("monthly", "/billing"), ("user", "/user?include=subscription")):
        try:
            optional[key] = net.get_json(BASE_URL + path, headers)
        except (AuthExpired, net.HttpError) as exc:
            errors[key] = str(exc)
    state = parse_billing(credits, optional.get("monthly"), optional.get("user"), now)
    if errors:
        state.detail["optional_errors"] = errors
    return state
