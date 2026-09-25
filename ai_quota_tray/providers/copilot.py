"""GitHub Copilot account quota through the official Copilot Python SDK.

The SDK starts its bundled Copilot runtime and uses the account signed in there.
This provider never reads credentials or calls GitHub's private HTTP endpoints.

Runtime（約 111 MB）：SDK 第一次用時才從 GitHub 下載（有 sha256 校驗），放在
%LOCALAPPDATA%/github-copilot-sdk。授權含微軟專有元件，所以不打包進我們的安裝檔；
改成使用者勾選 Copilot 時就在背景先下載（start_prepare），下載完成前 fetch 回 PREPARING，
不會在查詢途中卡住下載。SDK 沒有公開的下載函式，官方做法是 `python -m copilot download-runtime`
（打包版沒有 python -m 可用），所以直接呼叫它內部用的同一組函式；pyproject 已釘死 SDK 版本。
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ..model import (AUTH_EXPIRED, ERROR, OK, PREPARING, ProviderState, make_window,
                     parse_time, to_float, utcnow)

NAME = "copilot"
SOURCE = "copilot-sdk"
FETCH_TIMEOUT_S = 45  # 正常約 5 秒（啟動 runtime＋查詢）；SDK 預設不設逾時，卡住就永遠不回來
# SDK 的錯誤訊息裡出現這些字 → 當成沒登入（account.getCurrentAuth 在 SDK 1.0.14 解析不了回傳，不能用）
AUTH_WORDS = ("not authenticated", "unauthenticated", "unauthorized", "not signed in",
              "sign in", "log in", "login", "401")
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


# ---------- Runtime 預先下載 ----------

_prep_lock = threading.Lock()
_prep_thread: threading.Thread | None = None
_prep_error: str | None = None


def _runtime_pair() -> tuple[Any, Any, str]:
    from copilot import _cli_download as d
    wrapper = "copilot-runtime.exe" if sys.platform == "win32" else "copilot-runtime"
    return d, d.get_cache_dir(d.CLI_VERSION) / "prebuilds" / d.get_runtime_platform(), wrapper


def runtime_ready() -> bool:
    """跟 SDK 自己的判斷一致（get_cached_cli_path 會要求一個實際不存在的 copilot.exe，不能用）。"""
    if os.environ.get("COPILOT_CLI_PATH"):
        return True
    try:
        d, pair_dir, wrapper = _runtime_pair()
        return bool(d._runtime_bundle_is_complete(pair_dir, wrapper))
    except (ImportError, AttributeError, RuntimeError, OSError):
        return True  # 判斷不了就交給 SDK 自己處理（它會在第一次查詢時下載）


def preparing() -> bool:
    return _prep_thread is not None and _prep_thread.is_alive()


def _prepare(on_done: Callable[[], None] | None) -> None:
    global _prep_error
    try:
        d, _, _ = _runtime_pair()
        d.ensure_runtime_wrapper()
        _prep_error = None
    except Exception as exc:  # noqa: BLE001 — 網路、磁碟、校驗失敗都一樣記下來給卡片看
        _prep_error = f"{type(exc).__name__}: {exc}"
    finally:
        if on_done is not None:
            on_done()


def start_prepare(on_done: Callable[[], None] | None = None) -> bool:
    """背景下載 runtime。回傳 True＝正在下載（這次開始的或早就在跑）；已經好了回 False。"""
    global _prep_thread
    with _prep_lock:
        if preparing():
            return True
        if runtime_ready():
            return False
        _prep_thread = threading.Thread(target=_prepare, args=(on_done,),
                                        name="copilot-runtime", daemon=True)
        _prep_thread.start()
        return True


# ---------- 查詢 ----------

async def _read_quota() -> Any:
    # A new runtime on each poll avoids a process-lifetime quota cache in the
    # SDK runtime. No agent session or model request is created.
    from copilot import CopilotClient
    from copilot.generated.rpc import AccountGetQuotaRequest

    async with CopilotClient() as client:
        return await client.rpc.account.get_quota(AccountGetQuotaRequest())


def _looks_unauthenticated(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(word in text for word in AUTH_WORDS)


def fetch(use_token: bool = False, now: datetime | None = None) -> ProviderState:
    """Read the current signed-in Copilot account via the official SDK.

    ``use_token`` remains for the common provider interface and is ignored.
    """
    now = now or utcnow()
    if not runtime_ready():
        failed = _prep_error if not preparing() else None
        start_prepare()  # 上次下載失敗的話這次重試
        if failed:
            return ProviderState(NAME, [], None, ERROR, source=SOURCE,
                                 error=f"Copilot 元件下載失敗：{failed}")
        return ProviderState(NAME, [], None, PREPARING, source=SOURCE)
    try:
        result = asyncio.run(asyncio.wait_for(_read_quota(), FETCH_TIMEOUT_S))
    except TimeoutError as exc:
        raise TimeoutError(f"Copilot SDK 超過 {FETCH_TIMEOUT_S} 秒沒有回應") from exc
    except Exception as exc:  # noqa: BLE001 — 只挑出「沒登入」，其他照舊往上丟給 fetch_one
        if _looks_unauthenticated(exc):
            return ProviderState(NAME, [], None, AUTH_EXPIRED, source=SOURCE,
                                 error=f"{type(exc).__name__}: {exc}")
        raise
    return parse_quota(result, now)
