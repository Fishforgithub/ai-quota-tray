"""Persist enabled services, UI language and advanced options in the local config file."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .i18n import resolve

log = logging.getLogger(__name__)

# 新安裝預設顯示 Claude 與 Codex；各服務的取得方式由 provider 固定。
DEFAULT_ENABLED = frozenset({"claude", "codex"})


def data_dir() -> Path:
    # MSIX 下 %LOCALAPPDATA% 會被重導到套件目錄，一樣能用（CLAUDE.md §5）
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "ai-quota-tray"


def config_path() -> Path:
    return data_dir() / "config.json"


def _load(path: Path) -> dict | None:
    """讀不到或讀不懂 → None（呼叫端用預設值）。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        log.warning("讀不到 %s：%s（改用預設）", path, exc)
        return None
    return data if isinstance(data, dict) else None


def _names(data: dict | None, key: str, known: set[str], default: frozenset) -> set[str]:
    value = (data or {}).get(key)
    if not isinstance(value, list):
        return set(default & known)
    return {s for s in value if s in known}  # 不認得的名字直接忽略


def load_enabled(known: set[str], path: Path | None = None) -> set[str]:
    """回傳要抓的 provider。舊版設定檔沒有這個欄位 → 預設（只有 Claude、Codex）。"""
    return _names(_load(path or config_path()), "enabled", known, DEFAULT_ENABLED)


def load_language(path: Path | None = None) -> str:
    value = (_load(path or config_path()) or {}).get("language")
    return resolve(value)


def load_demo(path: Path | None = None) -> bool:
    """示範模式（demo.py）：顯示範例資料、不查詢任何服務。給 Store 審核人員用，預設關。"""
    return (_load(path or config_path()) or {}).get("demo") is True


def load_welcomed(path: Path | None = None) -> bool:
    """第一次啟動的歡迎通知跳過了沒（app.run）。只跳一次，之後靠「再啟動一次就打開卡片」。"""
    return (_load(path or config_path()) or {}).get("welcomed") is True


# 低額度通知門檻可選的值（剩餘 % 低於它就通知）；0＝不通知
ALERT_THRESHOLDS = (0, 10, 20, 30)


@dataclass(frozen=True)
class Advanced:
    """設定視窗的「進階設定」。預設值＝加這些選項之前的行為，再加上新功能。"""
    alert_threshold: int = 10  # 與卡片進度條變紅同一條線（icon.RED_BELOW）
    reset_alert: bool = True  # 跳過低額度通知的視窗重置時再通知一次
    pace: bool = False  # 卡片顯示用量速度（model.pace）；業主 2026-09-28 定預設不勾
    spend_limit: bool = True  # 顯示 Claude apps gateway 的花費上限

    def to_dict(self) -> dict:
        return asdict(self)


def load_advanced(path: Path | None = None) -> Advanced:
    """欄位缺、型別不對、門檻不在選項裡 → 那一欄用預設，其他欄照讀。"""
    value = (_load(path or config_path()) or {}).get("advanced")
    value = value if isinstance(value, dict) else {}
    default = Advanced()
    threshold = value.get("alert_threshold")
    if isinstance(threshold, bool) or threshold not in ALERT_THRESHOLDS:
        threshold = default.alert_threshold

    def flag(name: str) -> bool:
        v = value.get(name)
        return v if isinstance(v, bool) else getattr(default, name)

    return Advanced(threshold, flag("reset_alert"), flag("pace"), flag("spend_limit"))


def save(path: Path | None = None, **fields: set[str] | str | bool | Advanced) -> None:
    """更新指定欄位，保留其他欄位；壞檔直接覆寫。例：save(enabled=..., language="en")。"""
    path = path or config_path()
    data = _load(path) or {}
    data.pop("token_sources", None)  # Drop obsolete source setting.
    for key, value in fields.items():
        if isinstance(value, Advanced):
            data[key] = value.to_dict()
        else:
            data[key] = value if isinstance(value, (str, bool)) else sorted(value)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("寫不進 %s：%s", path, exc)
