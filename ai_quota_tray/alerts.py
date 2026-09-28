"""低額度通知與重置通知（CLAUDE.md §6 P4；門檻與重置通知在進階設定）。

每個視窗「每個重置週期」只通知一次：鍵＝provider｜label｜resets_at。
通知過的鍵存在 state.json，程式重開也不會重複跳；重置時間過了就清掉。
清掉的那一刻＝那個視窗剛重置，額度回來了：進階設定開著「重置通知」就再說一聲。
只有跳過低額度通知的視窗才有鍵，所以不會每 5 小時就跳一次。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from .config import data_dir
from .i18n import tr, window_label
from .icon import RED_BELOW
from .model import DISPLAY_NAME, OK, STALE, ProviderState, format_countdown, iso, parse_time

log = logging.getLogger(__name__)

THRESHOLD = RED_BELOW  # 預設與卡片進度條變紅同一條線；進階設定可改（config.ALERT_THRESHOLDS）
MAX_KEYS = 200
# 重置已經過了這麼久才發現（電腦睡著、程式沒開）就不通知了，那時候說「額度回來了」只是雜訊
RESET_NOTIFY_WITHIN = timedelta(hours=1)


def state_path() -> Path:
    return data_dir() / "state.json"


def alert_key(name: str, label: str, resets_at: datetime | None) -> str:
    return f"{name}|{label}|{iso(resets_at) or '-'}"


def _split_key(key: str) -> tuple[str, str, datetime | None]:
    parts = key.split("|")
    if len(parts) < 3:  # state.json 被手動改壞：當成沒有重置時間，留著不管
        return key, "", None
    stamp = parts[-1]
    return parts[0], "|".join(parts[1:-1]), (parse_time(stamp) if stamp != "-" else None)


def due_alerts(states: list[ProviderState], notified: set[str], now: datetime,
               threshold: float = THRESHOLD) -> list[tuple[str, str, str]]:
    """回傳 [(鍵, 標題, 內文)]。只看確定是真數字的狀態（ok / stale）。threshold ≤ 0＝不通知。"""
    out = []
    if threshold <= 0:
        return out
    for s in states:
        if s.status not in (OK, STALE):
            continue
        for w in s.windows:
            r = w.remaining_pct
            if r is None or r >= threshold:
                continue
            key = alert_key(s.name, w.label, w.resets_at)
            if key in notified:
                continue
            args = {"name": DISPLAY_NAME.get(s.name, s.name), "label": window_label(w.label),
                    "pct": int(r)}
            reset = tr("alert.reset", countdown=format_countdown(w.resets_at, now)) \
                if w.resets_at else ""
            out.append((key, tr("alert.title", **args), tr("alert.body", reset=reset, **args)))
    return out


def expired(notified: set[str], now: datetime) -> set[str]:
    """重置時間已過的鍵（下一個週期的 resets_at 會不同，留著沒用）。"""
    out = set()
    for key in notified:
        at = _split_key(key)[2]
        if at is not None and at <= now:
            out.add(key)
    return out


def prune(notified: set[str], now: datetime) -> set[str]:
    return set(sorted(notified - expired(notified, now))[-MAX_KEYS:])


def reset_alerts(keys: set[str], now: datetime) -> list[tuple[str, str]]:
    """剛重置的視窗 → [(標題, 內文)]。同一個視窗只說一次（resets_at 抖動過會有好幾個鍵）。"""
    seen, out = set(), []
    for key in sorted(keys):
        name, label, at = _split_key(key)
        if at is None or now - at > RESET_NOTIFY_WITHIN or (name, label) in seen:
            continue
        seen.add((name, label))
        args = {"name": DISPLAY_NAME.get(name, name), "label": window_label(label)}
        out.append((tr("alert.reset_title", **args), tr("alert.reset_body", **args)))
    return out


class AlertStore:
    def __init__(self, path: Path | None = None):
        self.path = path or state_path()
        self.notified: set[str] = set()
        self._just_reset: set[str] = set()  # 清掉了、還沒被 take_resets 拿走的鍵
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.notified = set(data.get("notified_alerts", []))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            log.warning("讀不到 %s：%s（當作沒通知過）", self.path, exc)

    def _prune(self, now: datetime) -> bool:
        """清掉過期的鍵並記下來；有清掉回 True（呼叫端決定要不要存檔）。"""
        gone = expired(self.notified, now)
        self._just_reset |= gone
        before = self.notified
        self.notified = prune(self.notified, now)
        return self.notified != before

    def take_due(self, states: list[ProviderState], now: datetime,
                 threshold: float = THRESHOLD) -> list[tuple[str, str]]:
        """找出該通知的，記下來並存檔，回傳 [(標題, 內文)]。"""
        self._prune(now)
        due = due_alerts(states, self.notified, now, threshold)
        if due:
            self.notified.update(key for key, _, _ in due)
            self._save()
        return [(title, body) for _, title, body in due]

    def take_resets(self, now: datetime, names: set[str] | None = None) -> list[tuple[str, str]]:
        """剛重置的視窗 → [(標題, 內文)]。names：只通知這幾家（沒啟用的不說）。

        拿走就清掉，不管有沒有通知；程式重開時啟動前就過期的鍵也在這裡被丟掉（RESET_NOTIFY_WITHIN）。
        """
        if self._prune(now):
            self._save()
        keys, self._just_reset = self._just_reset, set()
        if names is not None:
            keys = {k for k in keys if _split_key(k)[0] in names}
        return reset_alerts(keys, now)

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
