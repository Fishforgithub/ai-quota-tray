"""最小的 JSON GET／POST。只用標準函式庫，打包時少一個相依。"""
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
    return _request(url, headers, None)


def post_json(url: str, headers: dict[str, str], body: dict) -> dict:
    """Antigravity 的 Cloud Code API 查詢也是 POST（body 是查詢條件，不會改到任何東西）。"""
    return _request(url, {"Content-Type": "application/json", **headers},
                    json.dumps(body).encode("utf-8"))


def _request(url: str, headers: dict[str, str], data: bytes | None) -> dict:
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", **headers}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = exc.read(200).decode("utf-8", "replace").lstrip()
        # 403 + HTML 多半是 Cloudflare 擋人，不是 token 問題
        if exc.code == 401 or (exc.code == 403 and not err_body.startswith("<")):
            raise AuthExpired(f"HTTP {exc.code}（前 80 字：{err_body[:80]!r}）") from exc
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
