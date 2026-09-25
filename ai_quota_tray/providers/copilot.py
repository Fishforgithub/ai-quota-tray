"""GitHub Copilot account quota through the official Copilot Python SDK.

The SDK starts its bundled Copilot runtime and uses the account signed in there.
This provider never reads credentials or calls GitHub's private HTTP endpoints.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from ..model import OK, ProviderState, make_window, parse_time, to_float, utcnow

NAME = "copilot"
SOURCE = "copilot-sdk"
QUOTAS = (("premium_interactions", "進階"), ("chat", "Chat"),
          ("completions", "補全"))


def _next_month_reset(now: datetime) -> datetime:
    """GitHub's included monthly allowance resets on the first at 00:00 UTC."""
    now = now.astimezone(timezone.utc)
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return datetime(year, month, 1, tzinfo=now.tzinfo)


def _field(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def parse_quota(result: Any, now: datetime) -> ProviderState:
    """Convert the documented AccountGetQuotaResult into tray quota windows."""
    snapshots = _field(result, "quota_snapshots", {}) or {}
    windows = []
    unlimited = []
    estimated_resets = []
    raw = {}
    for key, label in QUOTAS:
        snapshot = snapshots.get(key)
        if snapshot is None:
            continue
        entitlement = to_float(_field(snapshot, "entitlement_requests"))
        used = to_float(_field(snapshot, "used_requests"))
        remaining = to_float(_field(snapshot, "remaining_percentage"))
        is_unlimited = bool(_field(snapshot, "is_unlimited_entitlement")) or entitlement == -1
        reset = _field(snapshot, "reset_date")
        raw[key] = {"entitlement_requests": entitlement, "used_requests": used,
                    "remaining_percentage": remaining, "is_unlimited_entitlement": is_unlimited,
                    "reset_date": reset}
        if is_unlimited:
            unlimited.append(label)
            continue
        if entitlement is None or entitlement <= 0:
            continue
        if remaining is None and used is not None:
            remaining = (entitlement - used) / entitlement * 100
        if remaining is None:
            continue
        # The SDK has reported a fetch timestamp as reset_date in some versions.
        # Use GitHub's published monthly reset schedule when that field is invalid.
        reset_at = parse_time(reset)
        if reset_at is not None and reset_at <= now + timedelta(minutes=5):
            reset_at = _next_month_reset(now)
            estimated_resets.append(label)
        elif reset_at is None:
            reset_at = _next_month_reset(now)
            estimated_resets.append(label)
        windows.append(make_window(100 - remaining, reset_at, None, label=label))
    detail: dict[str, Any] = {}
    if unlimited:
        detail["unlimited"] = unlimited
    if estimated_resets:
        detail["estimated_resets"] = estimated_resets
    if not windows and not unlimited:
        raise ValueError("Copilot SDK 回傳中找不到可辨識的額度資料")
    return ProviderState(NAME, windows, now, OK, detail, source=SOURCE,
                         raw={"quota_snapshots": raw})


async def _read_quota() -> Any:
    # A new runtime on each poll avoids a process-lifetime quota cache in the
    # SDK runtime. No agent session or model request is created.
    from copilot import CopilotClient
    from copilot.generated.rpc import AccountGetQuotaRequest

    async with CopilotClient() as client:
        return await client.rpc.account.get_quota(AccountGetQuotaRequest())


def fetch(use_token: bool = False, now: datetime | None = None) -> ProviderState:
    """Read the current signed-in Copilot account via the official SDK.

    ``use_token`` remains for the common provider interface and is ignored.
    """
    result = asyncio.run(_read_quota())
    return parse_quota(result, now or utcnow())
