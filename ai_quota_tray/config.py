"""使用者設定：%LOCALAPPDATA%\\ai-quota-tray\\config.json。

目前只有一項：哪幾家用 API（token 來源），其餘讀本機紀錄。在「設定」視窗切換（settings.py）。

預設：Claude、Codex 讀本機紀錄（不碰 token）；Grok 沒有本機紀錄，只能用 API。
⚠️ 上線版（CLAUDE.md §5）不能碰 token → 到時 Grok 要整個拿掉或預設關閉。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# 有沒有不碰 token 的本機紀錄可讀。沒有的一律用 API（設定視窗裡「本機紀錄」是停用的）
HAS_LOCAL_SOURCE = {"claude": True, "codex": True, "grok": False}
DEFAULT_TOKEN_SOURCES = frozenset({"grok"})


def _forced(known: set[str]) -> set[str]:
    return {name for name in known if not HAS_LOCAL_SOURCE.get(name, True)}


def data_dir() -> Path:
    # MSIX 下 %LOCALAPPDATA% 會被重導到套件目錄，一樣能用（CLAUDE.md §5）
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "ai-quota-tray"


def config_path() -> Path:
    return data_dir() / "config.json"


def load_token_sources(known: set[str], path: Path | None = None) -> set[str]:
    """回傳要用 API 的 provider。沒有設定檔或讀不懂 → 預設值。沒有本機紀錄的一定在裡面。"""
    path = path or config_path()
    default = set(DEFAULT_TOKEN_SOURCES & known)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default | _forced(known)
    except (OSError, ValueError) as exc:
        log.warning("讀不到 %s：%s（改用預設）", path, exc)
        return default | _forced(known)
    sources = data.get("token_sources") if isinstance(data, dict) else None
    if not isinstance(sources, list):
        return default | _forced(known)
    return {s for s in sources if s in known} | _forced(known)  # 不認得的名字直接忽略


def save_token_sources(sources: set[str], path: Path | None = None) -> None:
    path = path or config_path()
    data: dict = {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded  # 保留其他欄位
    except (OSError, ValueError):
        pass
    data["token_sources"] = sorted(sources)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("寫不進 %s：%s", path, exc)
