"""各家 provider。每個模組提供 NAME 與 fetch(use_token, now) -> ProviderState。

有本機紀錄可讀的另外提供 fetch_local(now)：只讀檔案、不連網，給系統匣背景定時用。
"""
from __future__ import annotations

import traceback
from datetime import datetime

from ..model import ERROR, ProviderState
from .. import startup
from . import antigravity, claude, codex, copilot, grok

# 順序＝卡片與設定視窗的顯示順序。
# Grok 要讀本機 Grok Build CLI 的 token（xAI 還沒回覆能不能用），只給個人版：
# 有 MSIX 套件身分（Store 版）就不註冊，設定、卡片、通知都看不到它。
def modules(packaged: bool) -> tuple:
    return (claude, codex, antigravity, copilot) + (() if packaged else (grok,))


ALL = {m.NAME: m for m in modules(startup.is_packaged())}


def has_local(name: str) -> bool:
    return hasattr(ALL[name], "fetch_local")


def fetch_local_one(name: str, now: datetime) -> ProviderState:
    """只讀本機紀錄。失敗一樣收斂成 error（呼叫端會丟掉，不蓋掉手上的數字）。"""
    try:
        return ALL[name].fetch_local(now)
    except Exception as exc:  # noqa: BLE001
        return ProviderState(name, [], None, ERROR, error=f"{type(exc).__name__}: {exc}")


def fetch_one(name: str, use_token: bool, now: datetime) -> ProviderState:
    """每家獨立失敗：任何例外都收斂成該家的 error 狀態（原則 4）。"""
    try:
        return ALL[name].fetch(use_token=use_token, now=now)
    except Exception as exc:  # noqa: BLE001 — 這裡就是要全收
        return ProviderState(name, [], None, ERROR, error=f"{type(exc).__name__}: {exc}",
                             detail={"trace": traceback.format_exc(limit=3).splitlines()[-3:]})
