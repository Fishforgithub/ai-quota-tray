"""剩餘 < 10% 的通知（CLAUDE.md §6 P4）。

每個視窗「每個重置週期」只通知一次：鍵＝provider｜label｜resets_at。
通知過的鍵存在 state.json，程式重開也不會重複跳；重置時間過了就清掉。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from .config import data_dir
from .i18n import tr, window_label
from .icon import RED_BELOW
from .model import DISPLAY_NAME, OK, STALE, ProviderState, format_countdown, iso, parse_time

log = logging.getLogger(__name__)

THRESHOLD = RED_BELOW  # 與圖示變紅同一條線
MAX_KEYS = 200


def state_path() -> Path:
    return data_dir() / "state.json"


def alert_key(name: str, label: str, resets_at: datetime | None) -> str:
    return f"{name}|{label}|{iso(resets_at) or '-'}"


def due_alerts(states: list[ProviderState], notified: set[str],
               now: datetime) -> list[tuple[str, str, str]]:
    """回傳 [(鍵, 標題, 內文)]。只看確定是真數字的狀態（ok / stale）。"""
    out = []
    for s in states:
        if s.status not in (OK, STALE):
            continue
        for w in s.windows:
            r = w.remaining_pct
            if r is None or r >= THRESHOLD:
                continue
            key = alert_key(s.name, w.label, w.resets_at)
            if key in notified:
                continue
            args = {"name": DISPLAY_NAME.get(s.name, s.name), "label": window_label(w.label),
                    "pct": int(r)}
            reset = tr("alert.reset", countdown=format_countdown(w.resets_at, now))                 if w.resets_at else ""
            out.append((key, tr("alert.title", **args), tr("alert.body", reset=reset, **args)))
    return out


def prune(notified: set[str], now: datetime) -> set[str]:
    """重置時間已過的鍵沒用了（下一個週期的 resets_at 會不同）。"""
    keep = set()
    for key in notified:
        stamp = key.rsplit("|", 1)[-1]
        at = parse_time(stamp) if stamp != "-" else None
        if at is None or at > now:
            keep.add(key)
    return set(sorted(keep)[-MAX_KEYS:])


class AlertStore:
    def __init__(self, path: Path | None = None):
        self.path = path or state_path()
        self.notified: set[str] = set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.notified = set(data.get("notified_alerts", []))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            log.warning("讀不到 %s：%s（當作沒通知過）", self.path, exc)

    def take_due(self, states: list[ProviderState], now: datetime) -> list[tuple[str, str]]:
        """找出該通知的，記下來並存檔，回傳 [(標題, 內文)]。"""
        self.notified = prune(self.notified, now)
        due = due_alerts(states, self.notified, now)
        if due:
            self.notified.update(key for key, _, _ in due)
            self._save()
        return [(title, body) for _, title, body in due]

    def _save(self) -> None:
        data = {}  # 保留檔案裡其他欄位（之後可能放設定）；壞掉就重寫
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data["notified_alerts"] = sorted(self.notified)
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, ValueError) as exc:
            log.warning("寫不進 %s：%s", self.path, exc)
