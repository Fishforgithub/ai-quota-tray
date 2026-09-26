"""Codex App Server 的本機 stdio 用戶端；登入憑證由 Codex 自行管理。"""
from __future__ import annotations

import atexit
import json
import queue
import shutil
import subprocess
import sys
import threading
from typing import Any

from . import __version__

RESPONSE_TIMEOUT_S = 12
CLOSE_GRACE_S = 2


class AppServerError(RuntimeError):
    """Codex App Server 無法提供資料。"""


def _kill_tree(process: subprocess.Popen) -> None:
    """卡住不退時連子行程一起殺。

    Windows 上 `codex` 是 npm 的 codex.CMD：cmd.exe → node.exe → codex.exe 三層。
    Popen.kill() 只殺得到最外層的 cmd.exe，裡面兩層會變成孤兒，所以用 taskkill /T。
    """
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        process.kill()
    try:
        process.wait(timeout=CLOSE_GRACE_S)
    except subprocess.TimeoutExpired:
        pass


class AppServerClient:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[dict | None] = queue.Queue()
        self._next_id = 1

    def _read_stdout(self, process: subprocess.Popen[str], messages: queue.Queue[dict | None]) -> None:
        assert process.stdout is not None
        try:
            for line in process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(message, dict):
                    messages.put(message)
        finally:
            messages.put(None)

    def _send(self, message: dict) -> None:
        assert self._process is not None and self._process.stdin is not None
        self._process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def _request(self, method: str, params: dict | None = None) -> dict:
        request_id = self._next_id
        self._next_id += 1
        request: dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            request["params"] = params
        self._send(request)
        while True:
            try:
                message = self._messages.get(timeout=RESPONSE_TIMEOUT_S)
            except queue.Empty as exc:
                raise AppServerError(f"Codex App Server {method} 回應逾時") from exc
            if message is None:
                raise AppServerError("Codex App Server 已結束")
            if message.get("id") != request_id:
                continue  # 通知沒有 id；可能穿插在回應之間
            if "error" in message:
                error = message["error"]
                detail = error.get("message", str(error)) if isinstance(error, dict) else str(error)
                raise AppServerError(f"Codex App Server {method}: {detail}")
            result = message.get("result")
            if not isinstance(result, dict):
                raise AppServerError(f"Codex App Server {method} 回傳格式不符")
            return result

    def _start(self) -> None:
        executable = shutil.which("codex")
        if not executable:
            raise AppServerError("找不到 Codex CLI")
        self._messages = queue.Queue()
        self._next_id = 1
        self._process = subprocess.Popen(
            [executable, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._read_stdout, args=(self._process, self._messages),
                         name="codex-app-server-reader", daemon=True).start()
        self._request("initialize", {"clientInfo": {
            "name": "ai_quota_tray", "title": "AI Usage Meter", "version": __version__,
        }})
        self._send({"method": "initialized"})

    def rate_limits(self) -> dict:
        with self._lock:
            try:
                if self._process is None or self._process.poll() is not None:
                    self._close_unlocked()
                    self._start()
                return self._request("account/rateLimits/read")
            except (AppServerError, OSError, BrokenPipeError):
                self._close_unlocked()
                raise

    def _close_unlocked(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=CLOSE_GRACE_S)  # 正常：關掉 stdin 後 codex 自己退出，整串一起結束
        except subprocess.TimeoutExpired:
            _kill_tree(process)

    def close(self) -> None:
        with self._lock:
            self._close_unlocked()


client = AppServerClient()
atexit.register(client.close)
