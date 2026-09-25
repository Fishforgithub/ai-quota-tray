"""資料模型與跨 provider 共用的小工具（時間解析、視窗命名、遮罩）。

原則見 CLAUDE.md §1：視窗不寫死、只存 resets_at（UTC）、每家獨立失敗。
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .i18n import tr

# 狀態值。CLAUDE.md §2 列的是 ok / stale / auth_expired / error；
# disabled = 使用者未啟用這個來源。
OK = "ok"
STALE = "stale"
AUTH_EXPIRED = "auth_expired"
ERROR = "error"
DISABLED = "disabled"

# 顯示名稱（個人版）。上線版要避開商標（CLAUDE.md §5），到時只改這裡
DISPLAY_NAME = {"claude": "Claude", "codex": "Codex",
                "antigravity": "Antigravity", "copilot": "Copilot"}

# 檔案來源（statusLine cache、Codex rollout）超過這麼久沒更新就算過期
FILE_STALE_AFTER = timedelta(minutes=15)

_DAY = 86400
_KNOWN_LABELS = {5 * 3600: "5h", _DAY: "日", 7 * _DAY: "週"}


@dataclass
class Window:
    label: str
    used_pct: float | None
    resets_at: datetime | None  # UTC
    duration_s: int | None

    @property
    def remaining_pct(self) -> float | None:
        if self.used_pct is None:
            return None
        return max(0.0, 100.0 - self.used_pct)


@dataclass
class ProviderState:
    name: str
    windows: list[Window]
    fetched_at: datetime | None  # 資料本身的時間（檔案來源 = 寫入時間，不是讀取時間）
    status: str
    detail: dict = field(default_factory=dict)
    source: str | None = None  # 例如 statusline-cache / codex-app-server / rollout
    error: str | None = None
    raw: Any = None  # 只給 probe --raw 用，輸出前一律經過 mask_secrets

    def to_dict(self, include_raw: bool = False) -> dict:
        out = {
            "name": self.name,
            "status": self.status,
            "source": self.source,
            "fetched_at": iso(self.fetched_at),
            "windows": [
                {
                    "label": w.label,
                    "used_pct": w.used_pct,
                    "remaining_pct": w.remaining_pct,
                    "resets_at": iso(w.resets_at),
                    "duration_s": w.duration_s,
                }
                for w in self.windows
            ],
            "detail": self.detail,
            "error": self.error,
        }
        if include_raw:
            out["raw"] = mask_secrets(self.raw)
        return out


class AuthExpired(Exception):
    """Token 過期或被拒（401/403）。依原則不自行 refresh。"""


# ---------- 時間 ----------

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if dt else None


def parse_time(value: Any) -> datetime | None:
    """epoch 秒 / 毫秒（數字或數字字串）、ISO-8601 → UTC datetime；無法解析回 None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        ts = float(value)
        if abs(ts) > 10_000_000_000:  # 毫秒
            ts /= 1000
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return parse_time(float(text))
    # 某些 ISO 時間帶 9 位小數（奈秒），舊版 fromisoformat 只吃到 6 位
    text = re.sub(r"(\.\d{6})\d+", r"\1", text.replace("Z", "+00:00"))
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------- 視窗 ----------

def label_for_duration(seconds: int | None) -> str:
    """由視窗實際長度推導 label（原則 1：不假設 5h + 週）。"""
    if not seconds or seconds <= 0:
        return "?"
    if seconds in _KNOWN_LABELS:
        return _KNOWN_LABELS[seconds]
    if 28 * _DAY <= seconds <= 31 * _DAY:
        return "月"
    if seconds % _DAY == 0:
        return f"{seconds // _DAY}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    return f"{round(seconds / 60)}m"


def make_window(used_pct: Any, resets_at: Any, duration_s: int | None,
                label: str | None = None) -> Window:
    pct = to_float(used_pct)
    if pct is not None:
        pct = min(100.0, max(0.0, pct))
    return Window(
        label=label or label_for_duration(duration_s),
        used_pct=pct,
        resets_at=parse_time(resets_at),
        duration_s=duration_s,
    )


def apply_file_freshness(state: ProviderState, now: datetime) -> ProviderState:
    """檔案來源專用：已過重置時間的視窗歸零、資料太舊標 stale。

    重置時間已過 = 該視窗的計數器已經歸零，繼續顯示舊的已用 % 會誤導。
    但重置後的新用量我們看不到（可能從網頁版用掉），所以同時標 stale。
    """
    rolled = []
    for w in state.windows:
        if w.resets_at is not None and w.resets_at <= now:
            w.used_pct = 0.0
            w.resets_at = None
            rolled.append(w.label)
    if rolled:
        state.detail["rolled_over"] = rolled
    if state.status == OK and (
        rolled or state.fetched_at is None or now - state.fetched_at > FILE_STALE_AFTER
    ):
        state.status = STALE
    return state


def carry_over(prev: ProviderState | None, new: ProviderState, now: datetime) -> ProviderState:
    """這次抓取失敗（auth_expired / error）但上一次有數字 → 保留上一次的視窗。

    狀態維持 new 的（卡片才會提示「請開一下 CLI」），fetched_at 用上一次成功的時間，
    卡片據此顯示「n 分鐘前」。期間經過重置時間的視窗照檔案來源的規則歸零。
    """
    if new.status not in (AUTH_EXPIRED, ERROR) or new.windows or prev is None or not prev.windows:
        return new
    windows, rolled = [], list(prev.detail.get("rolled_over", []))
    for w in prev.windows:
        w = Window(w.label, w.used_pct, w.resets_at, w.duration_s)
        if w.resets_at is not None and w.resets_at <= now:
            w.used_pct, w.resets_at = 0.0, None
            rolled.append(w.label)
        windows.append(w)
    detail = {k: v for k, v in prev.detail.items() if k not in ("api_error", "rolled_over")}
    if rolled:
        detail["rolled_over"] = rolled
    return ProviderState(new.name, windows, prev.fetched_at, new.status, detail,
                         source=prev.source, error=new.error)


# ---------- 顯示格式（CLAUDE.md §4） ----------

def format_countdown(target: datetime | None, now: datetime) -> str:
    """< 24h → hh:mm；≥ 24h → 3d04h。已過時間顯示 00:00（等下一輪抓取更新）。"""
    if target is None:
        return "—"
    s = max(0, int((target - now).total_seconds()))
    if s < _DAY:
        return f"{s // 3600:02d}:{s % 3600 // 60:02d}"
    days, rest = divmod(s, _DAY)
    return f"{days}d{rest // 3600:02d}h"


def format_age(fetched_at: datetime | None, now: datetime) -> str:
    if fetched_at is None:
        return tr("age.unknown")
    s = max(0, int((now - fetched_at).total_seconds()))
    if s < 60:
        return tr("age.now")
    if s < 3600:
        return tr("age.minutes", n=s // 60)
    if s < _DAY:
        return tr("age.hours", n=s // 3600)
    return tr("age.days", n=s // _DAY)


# ---------- 數值 ----------

def to_float(value: Any) -> float | None:
    """數字、數字字串、或 proto 包裝的 {"val": ...} → float。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, dict):
        return to_float(value.get("val"))
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return None


def jwt_exp(token: str) -> datetime | None:
    """讀 JWT payload 的 exp（不驗簽，只用來判斷是否過期）。"""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return None
    return parse_time(data.get("exp")) if isinstance(data, dict) else None


# ---------- 遮罩 ----------

# 各種識別資訊：token、email、姓名、任何 *_id / *Id。寧可多遮，
# probe 輸出是要能貼給別人看的。
_SECRET_KEY = re.compile(
    r"token|key|secret|password|cookie|authorization|session|email|asset"
    r"|[Nn]ame$|(_id|Id|ID)$",
)
_JWT_LIKE = re.compile(r"^eyJ[\w-]+\.[\w-]+")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def mask_value(value: str) -> str:
    # 不留前綴：id / email 的開頭本身就是識別資訊，長度夠用來除錯
    return "***" if len(value) <= 8 else f"***({len(value)})"


def mask_secrets(obj: Any, key: str = "") -> Any:
    if isinstance(obj, dict):
        return {k: mask_secrets(v, str(k)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask_secrets(v, key) for v in obj]
    if isinstance(obj, str):
        if _SECRET_KEY.search(key) or _JWT_LIKE.match(obj):
            return mask_value(obj)
        return _UUID.sub("<uuid>", obj)
    return obj
