"""Grok（SpaceXAI 的 Grok Build CLI）。預設不啟用。

透過官方 Grok Build CLI 的 Agent 模式（ACP：JSON-RPC over stdio）查詢：

    grok agent --no-leader stdio   →  initialize  →  _x.ai/billing

`grok agent stdio` 是官方文件寫明給 IDE／SDK／自訂 App 用的介面（`~/.grok/docs/user-guide/15-agent-mode.md`），
`x.ai/*` 是它的擴充方法；`x.ai/billing` 就是 CLI 自己的 /usage 在用的那一個（開源的 xai-org/grok-build：
`crates/codegen/xai-grok-shell/src/extensions/billing.rs`，Apache-2.0）。ACP 的擴充方法在線上要加底線前綴。
登入與續期都由 Grok CLI 自己處理：tray 不讀 `~/.grok/auth.json`、不碰 token（原則 3、5）。
只做 initialize 與 billing，不開 session、不送 prompt，不耗額度。每次查詢起一個行程、查完就關，不常駐。

2026-06 改制後是「每週共用運算額度池」，沒有 5h 視窗；部分方案另有月額度（舊欄位 monthlyLimit／used）。
⚠️ proto3：值為 0 的欄位會被省略；數值可能包成 {"val": ...}。
⚠️ token 約 6 小時過期。agent 啟動時會自己排程續期（`AuthManager.start_proactive_refresh`，過期的 1 秒後就續），
但 billing 拿的是「目前或已過期」的 token，剛啟動就問可能回 401 → 等一下再問同一個行程（AUTH_RETRY_DELAYS_S）。
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import __version__
from ..codex_app_server import kill_tree
from ..model import (AUTH_EXPIRED, OK, AuthExpired, ProviderState, Window,
                     make_window, parse_time, to_float, utcnow)

NAME = "grok"
SOURCE = "grok-cli"
WEEKLY = "USAGE_PERIOD_TYPE_WEEKLY"
_PERIOD_DURATION = {"USAGE_PERIOD_TYPE_DAILY": 86400, WEEKLY: 7 * 86400}

BILLING_METHOD = "_x.ai/billing"
RESPONSE_TIMEOUT_S = 20  # CLI 自己對上游設 15 秒逾時；實測 initialize 約 0.9 秒、billing 約 1 秒
CLOSE_GRACE_S = 2
AUTH_RETRY_DELAYS_S = (3, 6)  # 401 時等 CLI 自己續期再問
ACP_AUTH_REQUIRED = -32000  # ACP 規格的 auth_required：根本沒登入，重試也沒用
_UNAUTHORIZED_WORDS = ("401", "unauthorized", "unauthenticated", "expired")


class AcpError(RuntimeError):
    def __init__(self, method: str, code: Any, text: str):
        super().__init__(f"Grok CLI {method}: {text}")
        self.code = code
        self.text = text

    @property
    def auth_required(self) -> bool:
        return self.code == ACP_AUTH_REQUIRED or "grok login" in self.text.lower()

    @property
    def unauthorized(self) -> bool:
        return any(w in self.text.lower() for w in _UNAUTHORIZED_WORDS)


def find_cli() -> str | None:
    """Grok Build CLI 的執行檔：PATH，其次官方安裝位置 ~/.grok/bin。"""
    found = shutil.which("grok")
    if found:
        return found
    home = Path(os.environ.get("GROK_HOME") or Path.home() / ".grok")
    candidate = home / "bin" / ("grok.exe" if sys.platform == "win32" else "grok")
    return str(candidate) if candidate.exists() else None


def agent_command(exe: str) -> list[str]:
    # --no-leader：不要接到（或叫起）使用者設定的共用 leader 行程，查完就整個結束
    return [exe, "agent", "--no-leader", "stdio"]


class _Agent:
    """一次查詢用的 `grok agent stdio`。with 結束時關 stdin 讓它自己退，退不了才連子行程一起殺。"""

    def __init__(self, command: list[str]):
        self._process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._messages: queue.Queue[dict | None] = queue.Queue()
        self._next_id = 1
        self._reader = threading.Thread(target=self._read_stdout, name="grok-agent-reader", daemon=True)
        self._reader.start()

    def __enter__(self) -> "_Agent":
        return self

    def __exit__(self, *exc_info) -> None:
        process = self._process
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=CLOSE_GRACE_S)
        except subprocess.TimeoutExpired:
            kill_tree(process)
        self._reader.join(timeout=CLOSE_GRACE_S)  # 行程結束後讀到 EOF 就會停
        if process.stdout and not self._reader.is_alive():
            process.stdout.close()

    def _read_stdout(self) -> None:
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(message, dict):
                    self._messages.put(message)
        finally:
            self._messages.put(None)

    def request(self, method: str, params: dict) -> dict:
        request_id = self._next_id
        self._next_id += 1
        assert self._process.stdin is not None
        message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        try:
            self._process.stdin.write(json.dumps(message) + "\n")
            self._process.stdin.flush()
        except OSError as exc:
            raise RuntimeError(f"Grok CLI 已結束：{exc}") from exc
        deadline = time.monotonic() + RESPONSE_TIMEOUT_S
        while True:
            try:
                reply = self._messages.get(timeout=max(0.0, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise TimeoutError(f"Grok CLI {method} 回應逾時（超過 {RESPONSE_TIMEOUT_S} 秒）") from exc
            if reply is None:
                raise RuntimeError(f"Grok CLI 在回應 {method} 前就結束了")
            if reply.get("id") != request_id:
                continue  # 通知（例如 _x.ai/mcp/servers_updated）沒有我們的 id
            if "error" in reply:
                error = reply["error"] if isinstance(reply["error"], dict) else {"message": str(reply["error"])}
                text = " ".join(str(error[k]) for k in ("message", "data") if error.get(k))
                raise AcpError(method, error.get("code"), text)
            result = reply.get("result")
            if not isinstance(result, dict):
                raise RuntimeError(f"Grok CLI {method} 回傳格式不符")
            return result


def query_billing() -> dict:
    exe = find_cli()
    if exe is None:
        raise FileNotFoundError("找不到 Grok Build CLI（grok），請先安裝並執行 grok login")
    with _Agent(agent_command(exe)) as agent:
        agent.request("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False},
                                   "terminal": False},
            "clientInfo": {"name": "ai_quota_tray", "title": "AI Usage Meter", "version": __version__},
        })
        last: AcpError | None = None
        for delay in (0,) + AUTH_RETRY_DELAYS_S:
            if delay:
                time.sleep(delay)
            try:
                return agent.request(BILLING_METHOD, {})
            except AcpError as exc:
                if exc.auth_required:
                    raise AuthExpired(f"Grok CLI 尚未登入：{exc.text}") from exc
                if not exc.unauthorized:
                    raise
                last = exc
        raise AuthExpired(f"Grok CLI 登入已失效：{last.text if last else ''}")


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


def parse_billing(result: dict, now: datetime) -> ProviderState:
    """`x.ai/billing` 的回傳：{"config": {...}, "subscription_tier": "SuperGrok", ...}。"""
    cfg = _config(result)
    windows = [w for w in (weekly_window(cfg), monthly_window(cfg)) if w]
    detail: dict[str, Any] = {}
    period = cfg.get("currentPeriod")
    if isinstance(period, dict) and period.get("type"):
        detail["period_type"] = period["type"]
    for src, dst in (("onDemandUsed", "on_demand_used"), ("onDemandCap", "on_demand_cap"),
                     ("prepaidBalance", "prepaid_balance")):
        if to_float(cfg.get(src)) is not None:
            detail[dst] = to_float(cfg.get(src))
    tier = result.get("subscription_tier") if isinstance(result, dict) else None
    if tier:
        detail["subscription_tier"] = tier
    return ProviderState(NAME, windows, now, OK, detail, source=SOURCE, raw=result)


def fetch(use_token: bool = False, now: datetime | None = None) -> ProviderState:
    # use_token 是 P1 留下的旗標，其他家早就不用
    now = now or utcnow()
    try:
        result = query_billing()
    except AuthExpired as exc:
        return ProviderState(NAME, [], None, AUTH_EXPIRED, source=SOURCE, error=str(exc))
    return parse_billing(result, now)
