"""活動偵測 + 分級輪詢：看本機檔案的 mtime 知道哪一家「正在用」，只有那一家才提高查詢頻率。

背景閒置時不連網（業主 2026-09-26 定）；有人在用某一家 → 那一家每 ACTIVE_INTERVAL_S 秒查一次，
停止使用 COOLDOWN_S 秒後再補查一次抓收尾數字，然後回到慢速（打開卡片才查）。
檢查 mtime 只是 stat，幾乎沒有成本。

各家的活動訊號（2026-09-29 在本機實測）：
- claude：`~/.claude/projects/<專案>/*.jsonl`、`usage-cache.json`。
- codex：`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`。
- antigravity：`~/.gemini/antigravity-cli/brain/<對話>/.system_generated/logs/transcript.jsonl`。
  ⚠️ `log/cli-*.log`、`cli.log`、`conversation_summaries.db` 我們自己的 `agy -p /usage` 也會寫，不能用。
- copilot（只涵蓋 VS Code 的 Copilot Chat）：`%APPDATA%\\Code\\User\\globalStorage\\emptyWindowChatSessions\\*.jsonl`
  與 `workspaceStorage\\*\\chatSessions\\*.jsonl`（後者沒開資料夾以外的情況沒實測）。
  ⚠️ `~/.copilot/logs/process-*.log` 是我們自己的 SDK 查詢寫的；`state.vscdb` 平常就會寫，不能用。
  CLI、JetBrains、網頁版本機沒有痕跡，偵測不到。

mtime 代表「使用者有互動」，不保證真的消耗額度；它只是決定要不要查的條件。
"""
from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

ACTIVE_WINDOW_S = 60  # 最近這麼久有寫入 → 活躍（實測對話中每 3～20 秒寫一次，等核可時會停十幾秒）
ACTIVE_INTERVAL_S = 25  # 活躍時每家最短查詢間隔
# Antigravity 沒裝狀態列擷取時，每查一次就是冷啟動一支 190 MB 的 agy（2～5 秒、偶爾卡 30 秒，2026-10-03 調查）
# → 放慢；有裝擷取時 providers/antigravity.py 直接讀快取，間隔多少都很便宜
ACTIVE_INTERVAL_BY_NAME = {"antigravity": 60}
COOLDOWN_S = 90  # 停止寫入這麼久才算用完，補查一次收尾
MAX_BACKOFF_S = 300  # 查詢失敗時間隔逐次加倍，最多到這裡
CHECK_INTERVAL_S = 8  # app 多久呼叫一次 tick
RESCAN_INTERVAL_S = 60  # 多久完整列一次檔案；中間只 stat 最近動過的幾個
HOT_FILES = 8


def _claude_dir() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env) if env else Path.home() / ".claude"


def _codex_dir() -> Path:
    env = os.environ.get("CODEX_HOME")
    return Path(env) if env else Path.home() / ".codex"


def _appdata() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")


def _scan(directory: Path) -> list[os.DirEntry]:
    try:
        with os.scandir(directory) as it:
            return list(it)
    except OSError:
        return []


def _files_claude() -> list[str]:
    base = _claude_dir()
    files = [str(base / "usage-cache.json")]
    for project in _scan(base / "projects"):
        files += [e.path for e in _scan(Path(project.path)) if e.name.endswith(".jsonl")]
    return files


def _files_codex() -> list[str]:
    # 只看最新兩個日期資料夾（跨午夜時昨天的 rollout 還在寫）
    root = _codex_dir() / "sessions"
    days: list[Path] = []
    for year in sorted((e for e in _scan(root) if e.is_dir()), key=lambda e: e.name, reverse=True)[:2]:
        for month in sorted((e for e in _scan(Path(year.path)) if e.is_dir()),
                            key=lambda e: e.name, reverse=True)[:2]:
            days += [Path(e.path) for e in sorted((e for e in _scan(Path(month.path)) if e.is_dir()),
                                                  key=lambda e: e.name, reverse=True)[:2]]
    days = days[:2]
    return [e.path for d in days for e in _scan(d) if e.name.startswith("rollout-")]


def _files_antigravity() -> list[str]:
    base = Path.home() / ".gemini" / "antigravity-cli" / "brain"
    return [str(Path(e.path) / ".system_generated" / "logs" / "transcript.jsonl")
            for e in _scan(base) if e.is_dir()]


def _files_copilot() -> list[str]:
    storage = _appdata() / "Code" / "User"
    files = [e.path for e in _scan(storage / "globalStorage" / "emptyWindowChatSessions")
             if e.name.endswith(".jsonl")]
    for workspace in _scan(storage / "workspaceStorage"):
        files += [e.path for e in _scan(Path(workspace.path) / "chatSessions")
                  if e.name.endswith(".jsonl")]
    return files


LISTERS: dict[str, Callable[[], list[str]]] = {
    "claude": _files_claude,
    "codex": _files_codex,
    "antigravity": _files_antigravity,
    "copilot": _files_copilot,
}


def _mtime(path: str) -> float | None:
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None


class FileWatcher:
    """一家的活動訊號：回傳「最新寫入時間」。完整列檔慢（每 RESCAN 秒），平常只 stat 最近動過的幾個。"""

    def __init__(self, lister: Callable[[], list[str]], stat: Callable[[str], float | None] = _mtime,
                 clock: Callable[[], float] = time.monotonic):
        self._lister, self._stat, self._clock = lister, stat, clock
        self._hot: list[str] = []
        self._scanned_at: float | None = None

    def latest_mtime(self) -> float | None:
        now = self._clock()
        if self._scanned_at is None or now - self._scanned_at >= RESCAN_INTERVAL_S:
            self._scanned_at = now
            stamped = [(m, p) for p in self._lister() if (m := self._stat(p)) is not None]
            stamped.sort(reverse=True)
            self._hot = [p for _, p in stamped[:HOT_FILES]]
            return stamped[0][0] if stamped else None
        times = [m for p in self._hot if (m := self._stat(p)) is not None]
        return max(times) if times else None


class Scheduler:
    """決定這一輪哪幾家該查。純邏輯（時間、mtime 都能注入），測試不用真的等。"""

    def __init__(self, names: list[str], latest: Callable[[str], float | None],
                 wall: Callable[[], float] = time.time, clock: Callable[[], float] = time.monotonic):
        self._latest, self._wall, self._clock = latest, wall, clock
        self._names = names
        self._active: dict[str, bool] = {n: False for n in names}
        self._last_fetch: dict[str, float] = {}
        self._failures: dict[str, int] = {}

    def is_active(self, name: str) -> bool:
        return self._active.get(name, False)

    def note_fetch(self, name: str, ok: bool) -> None:
        """app 每次查完回報：失敗就退避（間隔加倍），成功清零。"""
        self._failures[name] = 0 if ok else min(self._failures.get(name, 0) + 1, 8)

    def note_attempt(self, name: str) -> None:
        """有人從別的路徑查了（打開卡片、手動刷新）也算，免得剛查完又查。"""
        self._last_fetch[name] = self._clock()

    def _interval(self, name: str) -> float:
        base = ACTIVE_INTERVAL_BY_NAME.get(name, ACTIVE_INTERVAL_S)
        return min(base * 2 ** self._failures.get(name, 0), MAX_BACKOFF_S)

    def tick(self, enabled: set[str]) -> list[str]:
        """回傳現在該查的服務。"""
        due: list[str] = []
        now, wall = self._clock(), self._wall()
        for name in self._names:
            if name not in enabled:
                self._active[name] = False
                continue
            latest = self._latest(name)
            idle_for = None if latest is None else wall - latest
            was_active = self._active[name]
            active = idle_for is not None and idle_for <= (COOLDOWN_S if was_active else ACTIVE_WINDOW_S)
            self._active[name] = active
            last = self._last_fetch.get(name)
            if active:
                if last is None or now - last >= self._interval(name):
                    due.append(name)
            elif was_active:
                due.append(name)  # 剛用完：補查一次收尾數字，之後回到慢速
            if name in due:
                self._last_fetch[name] = now
        return due
