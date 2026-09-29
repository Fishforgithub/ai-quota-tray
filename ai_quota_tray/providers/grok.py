"""Grok（最脆弱的一家）。⚠️ 只在個人版（沒有 MSIX 套件身分）才註冊，Store 版沒有這一家（providers/__init__）。

xAI 沒有公開的額度介面，也還沒回覆能不能給第三方 App 用（CLAUDE.md 📨）；這裡讀本機 Grok Build CLI
的 token 去打它自己的 billing 端點，所以是「讀 token」的例外，只有使用者自己勾選才會跑。

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
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .. import net
from ..model import (AUTH_EXPIRED, OK, AuthExpired, ProviderState, Window,
                     make_window, parse_time, to_float, utcnow)

NAME = "grok"
BASE_URL = "https://cli-chat-proxy.grok.com/v1"
WEEKLY = "USAGE_PERIOD_TYPE_WEEKLY"
_PERIOD_DURATION = {"USAGE_PERIOD_TYPE_DAILY": 86400, WEEKLY: 7 * 86400}


def auth_path() -> Path:
    env = os.environ.get("GROK_HOME")
    return (Path(env) if env else Path.home() / ".grok") / "auth.json"


REFRESH_TIMEOUT_S = 30
EXPIRY_MARGIN = timedelta(minutes=2)  # 快過期就先續期，免得查到一半失效


def find_cli() -> str | None:
    """Grok Build CLI 的執行檔：PATH，其次官方安裝位置 ~/.grok/bin。"""
    found = shutil.which("grok")
    if found:
        return found
    home = Path(os.environ.get("GROK_HOME") or Path.home() / ".grok")
    candidate = home / "bin" / ("grok.exe" if sys.platform == "win32" else "grok")
    return str(candidate) if candidate.exists() else None


def refresh_via_cli() -> bool:
    """token 約 6 小時就過期，而 CLI 沒開就沒人續期。請官方 CLI 自己續：`grok models` 只是列模型
    （不呼叫模型、不耗額度），但會順便把 auth.json 的 access token 換新（2026-09-29 實測 expires_at
    從過期日變成 +6 小時）。我們自己不碰 refresh_token，不會把 CLI 的登入搞壞（原則 3）。"""
    exe = find_cli()
    if exe is None:
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    try:
        subprocess.run([exe, "models"], stdin=subprocess.DEVNULL, capture_output=True,
                       timeout=REFRESH_TIMEOUT_S, creationflags=flags, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return True


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
        if expires is None or expires > now + EXPIRY_MARGIN:
            return entry["key"]
    raise AuthExpired("token 已過期，請開一下 Grok CLI")


def read_fresh_token(now: datetime) -> str:
    """有效就直接用；過期或快過期就請官方 CLI 續期一次再讀。續期不了才回報過期。"""
    try:
        return read_token(now)
    except AuthExpired:
        if not refresh_via_cli():
            raise
    return read_token(utcnow())


def fetch(use_token: bool = False, now: datetime | None = None) -> ProviderState:
    # use_token 是 P1 留下的旗標，其他家早就不用；Grok 沒被勾選就根本不會呼叫到這裡
    now = now or utcnow()
    try:
        token = read_fresh_token(now)
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
