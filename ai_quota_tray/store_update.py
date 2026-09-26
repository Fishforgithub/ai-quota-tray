"""Store 版檢查有沒有新版（做法照 desk-pet 的 src-tauri/src/store_update.rs）。

為什麼要自己查：Store 會自動更新，但時間由 Store 決定，常駐的 App 又沒人會去開 Store——
desk-pet 上架後業主自己那台就停在舊版、Store 頁掛著「更新」鈕。所以查到有新版就提示，
並在設定視窗給一顆直通 Store 商品頁的按鈕，讓使用者在 Store 按更新。

desk-pet 實測的限制（2026-09-24）：
- API 回的那筆 Package.Id.Version 是**已安裝版**，拿不到新版版號 → 提示一律寫「發現新版本」。
- Partner Center 的「強制更新」OS 不會強制也不會提示。
- 更新時 App 可能被關掉、裝完不保證重開（開機啟動下次登入會帶回來）。
只有套件身分（從 Store 安裝）才查；個人版（直接跑 exe／venv）沒有 Store 可以問，回 None。
查詢連的是 Microsoft Store 的服務，只問有沒有更新、不送任何個人資料（隱私權政策 §3 有寫）。
"""
from __future__ import annotations

import asyncio
import logging
import os

from . import startup

log = logging.getLogger(__name__)

STORE_PRODUCT_ID = "9PLDWKRFDGDC"
STORE_PDP_URI = f"ms-windows-store://pdp/?productid={STORE_PRODUCT_ID}"  # Store App 的商品頁
FIRST_CHECK_DELAY_S = 30  # 啟動後先讓 App 安頓好再查
CHECK_INTERVAL_S = 6 * 3600


def _fake() -> bool:
    """只給測試／截圖用：個人版沒有 Store 可問，設了 AIQT_FAKE_UPDATE=1 才看得到通知與按鈕。"""
    return os.environ.get("AIQT_FAKE_UPDATE") == "1"


def can_check() -> bool:
    return _fake() or startup.is_packaged()


def check() -> bool | None:
    """True＝Store 上有新版；False＝已是最新；None＝不能查（個人版）或查詢失敗。會連網，別在主執行緒呼叫。"""
    if _fake():
        return True
    if not startup.is_packaged():
        return None
    try:
        from winrt.windows.services.store import StoreContext

        async def query() -> int:
            updates = await StoreContext.get_default().get_app_and_optional_store_package_updates_async()
            return updates.size

        return asyncio.run(query()) > 0
    except Exception as exc:  # noqa: BLE001 — 查不到就當不知道，不影響其他功能
        log.info("Store 更新檢查失敗：%s", exc)
        return None
