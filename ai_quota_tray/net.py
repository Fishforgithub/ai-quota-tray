"""最小的 JSON GET。只用標準函式庫，打包時少一個相依。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .model import AuthExpired

USER_AGENT = "ai-quota-tray/0.1"
TIMEOUT_S = 15


class HttpError(Exception):
    pass


def get_json(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **headers}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = exc.read(200).decode("utf-8", "replace").lstrip()
        # 403 + HTML 多半是 Cloudflare 擋人，不是 token 問題
        if exc.code == 401 or (exc.code == 403 and not err_body.startswith("<")):
            raise AuthExpired(f"HTTP {exc.code}") from exc
        raise HttpError(f"HTTP {exc.code}（前 80 字：{err_body[:80]!r}）") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HttpError(f"連線失敗：{exc}") from exc
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        # Cloudflare 擋下時常回 HTML
        raise HttpError(f"回傳不是 JSON（前 80 字：{body[:80]!r}）") from exc
    if not isinstance(data, dict):
        raise HttpError("回傳不是 JSON 物件")
    return data
