"""活動偵測（activity.py）：排程狀態機、檔案觀察、各家的檔案位置。時間與 mtime 都用假的。"""
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import activity, win32tray  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 單獨跑這個檔也找得到 test_launch
from test_launch import TrayAppTestBase  # noqa: E402


class Fake:
    def __init__(self):
        self.now = 10_000.0  # 同時當 time.time 與 time.monotonic
        self.mtime: dict[str, float | None] = {}

    def make(self, names):
        return activity.Scheduler(names, lambda n: self.mtime.get(n), wall=lambda: self.now,
                                  clock=lambda: self.now)


class SchedulerTest(unittest.TestCase):
    def test_idle_never_fetches(self):
        f = Fake()
        s = f.make(["codex"])
        f.mtime["codex"] = f.now - 3600
        for _ in range(20):
            f.now += 8
            self.assertEqual(s.tick({"codex"}), [])

    def test_active_fetches_at_interval_then_final_fetch(self):
        f = Fake()
        s = f.make(["codex"])
        f.mtime["codex"] = f.now - 5
        self.assertEqual(s.tick({"codex"}), ["codex"])  # 一偵測到就查
        f.now += 10
        self.assertEqual(s.tick({"codex"}), [])  # 間隔內不重複
        f.now += activity.ACTIVE_INTERVAL_S
        f.mtime["codex"] = f.now - 2
        self.assertEqual(s.tick({"codex"}), ["codex"])
        # 停止寫入：冷卻期內仍算活躍，繼續照間隔查；過了冷卻補查一次就停
        fetched = 0
        for _ in range(60):
            f.now += 8
            fetched += len(s.tick({"codex"}))
        self.assertFalse(s.is_active("codex"))
        self.assertLessEqual(fetched, (activity.COOLDOWN_S // activity.ACTIVE_INTERVAL_S) + 2)
        for _ in range(20):
            f.now += 8
            self.assertEqual(s.tick({"codex"}), [])

    def test_antigravity_waits_longer_while_active(self):
        # 沒裝擷取時每查一次就是冷啟動一支 agy（2026-10-03 調查）→ 活躍時 60 秒一次，不是 25 秒
        f = Fake()
        s = f.make(["antigravity"])
        f.mtime["antigravity"] = f.now - 5
        self.assertEqual(s.tick({"antigravity"}), ["antigravity"])
        f.now += activity.ACTIVE_INTERVAL_S + 1
        f.mtime["antigravity"] = f.now - 2
        self.assertEqual(s.tick({"antigravity"}), [], "25 秒還不到它的間隔")
        f.now += activity.ACTIVE_INTERVAL_BY_NAME["antigravity"] - activity.ACTIVE_INTERVAL_S
        f.mtime["antigravity"] = f.now - 2
        self.assertEqual(s.tick({"antigravity"}), ["antigravity"])

    def test_final_fetch_happens_once_after_cooldown(self):
        f = Fake()
        s = f.make(["codex"])
        f.mtime["codex"] = f.now
        s.tick({"codex"})
        f.now += activity.COOLDOWN_S + 1  # 一次跳過冷卻：這一輪要補查
        self.assertEqual(s.tick({"codex"}), ["codex"])
        f.now += 8
        self.assertEqual(s.tick({"codex"}), [])

    def test_only_active_provider_is_fetched(self):
        f = Fake()
        s = f.make(["claude", "codex", "copilot"])
        f.mtime.update(claude=f.now - 1, codex=f.now - 999, copilot=None)
        self.assertEqual(s.tick({"claude", "codex", "copilot"}), ["claude"])

    def test_disabled_provider_ignored(self):
        f = Fake()
        s = f.make(["claude", "codex"])
        f.mtime.update(claude=f.now, codex=f.now)
        self.assertEqual(s.tick({"claude"}), ["claude"])

    def test_failures_back_off_and_recover(self):
        f = Fake()
        s = f.make(["codex"])
        f.mtime["codex"] = f.now
        s.tick({"codex"})
        s.note_fetch("codex", False)
        s.note_fetch("codex", False)
        f.now += activity.ACTIVE_INTERVAL_S * 2  # 失敗兩次 → 間隔 4 倍，還沒到
        f.mtime["codex"] = f.now
        self.assertEqual(s.tick({"codex"}), [])
        f.now += activity.ACTIVE_INTERVAL_S * 2
        f.mtime["codex"] = f.now
        self.assertEqual(s.tick({"codex"}), ["codex"])
        s.note_fetch("codex", True)
        f.now += activity.ACTIVE_INTERVAL_S
        f.mtime["codex"] = f.now
        self.assertEqual(s.tick({"codex"}), ["codex"])

    def test_backoff_is_capped(self):
        f = Fake()
        s = f.make(["codex"])
        for _ in range(20):
            s.note_fetch("codex", False)
        self.assertEqual(s._interval("codex"), activity.MAX_BACKOFF_S)

    def test_manual_fetch_counts_as_attempt(self):
        f = Fake()
        s = f.make(["codex"])
        f.mtime["codex"] = f.now
        s.note_attempt("codex")  # 剛好使用者打開卡片查過
        f.now += 5
        f.mtime["codex"] = f.now
        self.assertEqual(s.tick({"codex"}), [])

    def test_missing_files_are_idle(self):
        f = Fake()
        s = f.make(["copilot"])
        self.assertEqual(s.tick({"copilot"}), [])


class FileWatcherTest(unittest.TestCase):
    def test_rescans_rarely_and_stats_only_hot_files(self):
        clock = [0.0]
        stats = {f"f{i}": float(i) for i in range(30)}
        calls = {"list": 0, "stat": 0}

        def lister():
            calls["list"] += 1
            return list(stats)

        def stat(p):
            calls["stat"] += 1
            return stats.get(p)

        w = activity.FileWatcher(lister, stat, lambda: clock[0])
        self.assertEqual(w.latest_mtime(), 29.0)
        calls["stat"] = 0
        clock[0] += 10
        stats["f3"] = 500.0  # 熱門檔之外的舊檔案被寫：要等下一次完整掃描才會發現
        self.assertEqual(w.latest_mtime(), 29.0)
        self.assertEqual(calls["list"], 1)
        self.assertEqual(calls["stat"], activity.HOT_FILES)
        stats["f29"] = 900.0  # 熱門檔被寫：馬上看得到
        clock[0] += 10
        self.assertEqual(w.latest_mtime(), 900.0)
        clock[0] += activity.RESCAN_INTERVAL_S
        self.assertEqual(w.latest_mtime(), 900.0)
        self.assertEqual(calls["list"], 2)

    def test_new_file_seen_after_rescan(self):
        clock = [0.0]
        files = {"a": 1.0}
        w = activity.FileWatcher(lambda: list(files), files.get, lambda: clock[0])
        self.assertEqual(w.latest_mtime(), 1.0)
        files["b"] = 50.0
        clock[0] += activity.RESCAN_INTERVAL_S
        self.assertEqual(w.latest_mtime(), 50.0)

    def test_no_files(self):
        w = activity.FileWatcher(lambda: [], lambda p: None, lambda: 0.0)
        self.assertIsNone(w.latest_mtime())


class ListerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def touch(self, *parts) -> str:
        p = self.tmp.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
        return str(p)

    def test_claude(self):
        a = self.touch("projects", "proj1", "s1.jsonl")
        self.touch("projects", "proj1", "notes.txt")
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.tmp)}):
            files = activity._files_claude()
        self.assertIn(a, files)
        self.assertIn(str(self.tmp / "usage-cache.json"), files)
        self.assertFalse(any(f.endswith("notes.txt") for f in files))

    def test_codex_only_newest_days(self):
        old = self.touch("sessions", "2026", "09", "01", "rollout-a.jsonl")
        new = self.touch("sessions", "2026", "09", "29", "rollout-b.jsonl")
        newer = self.touch("sessions", "2026", "09", "28", "rollout-c.jsonl")
        third = self.touch("sessions", "2026", "09", "27", "rollout-d.jsonl")
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(self.tmp)}):
            files = activity._files_codex()
        self.assertEqual(set(files), {new, newer})
        self.assertNotIn(old, files)
        self.assertNotIn(third, files)

    def test_antigravity_uses_transcript_only(self):
        brain = self.tmp / ".gemini" / "antigravity-cli" / "brain" / "c1"
        (brain / ".system_generated" / "logs").mkdir(parents=True)
        self.touch(".gemini", "antigravity-cli", "log", "cli-1.log")  # 我們自己的 /usage 也會寫
        with mock.patch.object(Path, "home", return_value=self.tmp):
            files = activity._files_antigravity()
        self.assertEqual(files, [str(brain / ".system_generated" / "logs" / "transcript.jsonl")])

    def test_copilot_chat_sessions_only(self):
        a = self.touch("Code", "User", "globalStorage", "emptyWindowChatSessions", "s1.jsonl")
        b = self.touch("Code", "User", "workspaceStorage", "abc", "chatSessions", "s2.jsonl")
        self.touch("Code", "User", "workspaceStorage", "abc", "state.vscdb")  # 平常就會寫
        with mock.patch.dict(os.environ, {"APPDATA": str(self.tmp)}):
            files = activity._files_copilot()
        self.assertEqual(set(files), {a, b})

    def test_missing_directories_are_empty(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.tmp / "no"),
                                          "CODEX_HOME": str(self.tmp / "no"),
                                          "APPDATA": str(self.tmp / "no")}), \
                mock.patch.object(Path, "home", return_value=self.tmp / "no"):
            self.assertEqual(activity._files_codex(), [])
            self.assertEqual(activity._files_antigravity(), [])
            self.assertEqual(activity._files_copilot(), [])


class UserIdleTest(unittest.TestCase):
    def test_idle_seconds_is_a_small_nonnegative_number(self):
        idle = win32tray.user_idle_seconds()
        self.assertIsNotNone(idle)
        self.assertGreaterEqual(idle, 0)
        self.assertLess(idle, 60 * 60 * 24 * 50)


class TickGateTest(TrayAppTestBase):
    """人不在（滑鼠鍵盤停 USER_IDLE_S）時活動偵測不查；回來後才補查。"""

    def tick(self, idle):
        self.tray_app._activity = mock.Mock()
        self.tray_app._activity.tick.return_value = ["codex"]
        self.tray_app.poller.enabled.add("codex")
        self.app_mod.Poller.refresh.reset_mock()
        with mock.patch.object(self.app_mod.win32tray, "user_idle_seconds", return_value=idle):
            self.tray_app._activity_tick()

    def test_user_away_skips_everything(self):
        self.tick(self.app_mod.USER_IDLE_S + 1)
        self.tray_app._activity.tick.assert_not_called()  # 排程狀態不動，回來才處理
        self.app_mod.Poller.refresh.assert_not_called()

    def test_user_present_fetches_active_provider(self):
        self.tick(5.0)
        self.app_mod.Poller.refresh.assert_called_once_with("codex")

    def test_unknown_idle_time_does_not_block(self):
        self.tick(None)
        self.app_mod.Poller.refresh.assert_called_once_with("codex")

    def test_screen_locked_skips(self):
        self.tray_app._anim_blockers.add("locked")
        self.tick(1.0)
        self.app_mod.Poller.refresh.assert_not_called()

    def test_demo_skips(self):
        self.tray_app.demo = True
        self.tick(1.0)
        self.app_mod.Poller.refresh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
