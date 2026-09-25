"""各家 provider。每個模組提供 NAME 與 fetch(use_token, now) -> ProviderState。"""
from __future__ import annotations

import traceback
from datetime import datetime

from ..model import ERROR, ProviderState
from . import antigravity, claude, codex, copilot

# 順序＝卡片與設定視窗的顯示順序
ALL = {m.NAME: m for m in (claude, codex, antigravity, copilot)}


def fetch_one(name: str, use_token: bool, now: datetime) -> ProviderState:
    """每家獨立失敗：任何例外都收斂成該家的 error 狀態（原則 4）。"""
    try:
        return ALL[name].fetch(use_token=use_token, now=now)
    except Exception as exc:  # noqa: BLE001 — 這裡就是要全收
        return ProviderState(name, [], None, ERROR, error=f"{type(exc).__name__}: {exc}",
                             detail={"trace": traceback.format_exc(limit=3).splitlines()[-3:]})
