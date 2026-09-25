"""使用者設定：%LOCALAPPDATA%\\ai-quota-tray\\config.json。

目前只有一項：哪幾家改用 token 來源（右鍵選單切換）。
預設全部不用 token（CLAUDE.md §1 原則 5：上線版不碰 token，要使用者自己打開）。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def data_dir() -> Path:
    # MSIX 下 %LOCALAPPDATA% 會被重導到套件目錄，一樣能用（CLAUDE.md §5）
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "ai-quota-tray"


def config_path() -> Path:
    return data_dir() / "config.json"


def load_token_sources(known: set[str], path: Path | None = None) -> set[str]:
    path = path or config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    except (OSError, ValueError) as exc:
        log.warning("讀不到 %s：%s（當作全部不用 token）", path, exc)
        return set()
    sources = data.get("token_sources") if isinstance(data, dict) else None
    if not isinstance(sources, list):
        return set()
    return {s for s in sources if s in known}  # 不認得的名字直接忽略


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
