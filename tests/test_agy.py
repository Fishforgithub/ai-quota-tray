"""Antigravity：狀態列擷取（agy_hook.py）與查詢（providers/antigravity.py 的快取優先、CLI 重試）。

業主 2026-10-04 定：照 Claude 的做法，裝擷取讀本機；沒有或太舊才跑 agy -p /usage，逾時重試一次。
payload 照 2026-10-04 在業主電腦（agy 1.2.16）實測抓到的結構（email 換成假的）。
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import agy_hook, i18n  # noqa: E402
from ai_quota_tray.model import (AUTH_EXPIRED, ERROR, OK, STALE, ProviderState,  # noqa: E402
                                 carry_over, make_window)
from ai_quota_tray.providers import antigravity  # noqa: E402

NOW = datetime(2026, 10, 4, 0, 0, tzinfo=timezone.utc)
QUOTA = {"3p-weekly": {"remaining_fraction": 1, "reset_time": "2026-10-10T16:10:07Z", "reset_in_seconds": 604799},
         "gemini-weekly": {"remaining_fraction": 0.920852, "reset_time": "2026-10-10T16:07:10Z",
                           "reset_in_seconds": 604621}}
PAYLOAD = {"agent_state": "idle", "cwd": "D:\\work", "email": "someone@example.com", "product": "antigravity",
           "plan_tier": "Antigravity Starter Quota", "quota": QUOTA, "version": "1.2.16"}


class FakeAgyHome(unittest.TestCase):
    """把 ~/.gemini/antigravity-cli 指到暫存資料夾。"""
    subdir = "agy"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / self.subdir
        self.dir.mkdir()
        patch = mock.patch.object(agy_hook, "agy_dir", return_value=self.dir)
        patch.start()
        self.addCleanup(patch.stop)

    def write_settings(self, data):
        agy_hook.settings_path().write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def settings(self):
        return json.loads(agy_hook.settings_path().read_text(encoding="utf-8"))


class HookInstallTest(FakeAgyHome):
    def test_no_agy_and_unreadable(self):
        with mock.patch.object(agy_hook, "agy_dir", return_value=self.dir / "missing"):
            self.assertEqual(agy_hook.status(), agy_hook.NO_AGY)
        agy_hook.settings_path().write_text("{not json", encoding="utf-8")
        self.assertEqual(agy_hook.status(), agy_hook.UNREADABLE)
        with self.assertRaises(agy_hook.HookError):
            agy_hook.install()
        self.assertEqual(agy_hook.settings_path().read_text(encoding="utf-8"), "{not json", "讀不懂就整個不動")

    def test_install_without_custom_statusline_keeps_builtin_one(self):
        self.write_settings({"model": "gemini", "trustedWorkspaces": ["D:\\中文"]})
        self.assertEqual(agy_hook.status(), agy_hook.NOT_INSTALLED)
        agy_hook.install()
        line = self.settings()["statusLine"]
        self.assertEqual(line["command"], agy_hook.hook_command())
        self.assertIn(f"-File {agy_hook.hook_path().as_posix()}", line["command"])
        self.assertTrue(line["stack_with_default"], "我們不印東西，agy 內建的狀態列照常顯示")
        self.assertTrue(line["enabled"])
        self.assertEqual(self.settings()["trustedWorkspaces"], ["D:\\中文"], "其他欄位不動")
        self.assertTrue(agy_hook.hook_path().read_bytes().startswith(b"\xef\xbb\xbf"), "PowerShell 5.1 要 BOM")
        self.assertFalse(agy_hook.original_command_path().exists())
        self.assertTrue((self.dir / ("settings.json" + agy_hook.BACKUP_SUFFIX)).exists())
        self.assertEqual(agy_hook.status(), agy_hook.INSTALLED)

        agy_hook.install()  # 再按一次：只更新腳本，不會把自己記成「原本的狀態列」
        self.assertEqual(json.loads(agy_hook.original_path().read_text(encoding="utf-8")), {"statusLine": None})
        agy_hook.uninstall()
        self.assertNotIn("statusLine", self.settings())
        self.assertFalse(agy_hook.hook_dir().exists())
        self.assertEqual(agy_hook.status(), agy_hook.NOT_INSTALLED)

    def test_custom_statusline_is_chained_and_restored(self):
        original = {"type": "command", "command": "bash C:/me/line.sh", "padding": 1, "enabled": True}
        self.write_settings({"statusLine": original})
        agy_hook.install()
        line = self.settings()["statusLine"]
        self.assertEqual(line["padding"], 1, "保留原本的其他欄位")
        self.assertNotIn("stack_with_default", line)
        self.assertEqual(agy_hook.original_command_path().read_text(encoding="utf-8"), "bash C:/me/line.sh")
        agy_hook.uninstall()
        self.assertEqual(self.settings()["statusLine"], original)

    def test_disabled_custom_statusline_is_not_turned_on(self):
        self.write_settings({"statusLine": {"type": "command", "command": "x.exe", "enabled": False}})
        agy_hook.install()
        self.assertFalse(agy_hook.original_command_path().exists())
        self.assertTrue(self.settings()["statusLine"]["enabled"])

    def test_user_changed_statusline_later_is_left_alone(self):
        self.write_settings({})
        agy_hook.install()
        self.write_settings({"statusLine": {"type": "command", "command": "mine.exe"}})
        self.assertEqual(agy_hook.status(), agy_hook.NOT_INSTALLED)
        agy_hook.uninstall()
        self.assertEqual(self.settings()["statusLine"]["command"], "mine.exe")

    def test_refresh_replaces_old_script_only(self):
        self.assertFalse(agy_hook.refresh(), "沒裝擷取：什麼都不做")
        self.write_settings({})
        agy_hook.install()
        agy_hook.hook_path().write_text("# ai-quota-tray agy statusline hook v1\n", encoding="utf-8-sig")
        before = agy_hook.settings_path().read_bytes()
        self.assertTrue(agy_hook.refresh())
        self.assertIn("Read-Stdin", agy_hook.hook_path().read_text(encoding="utf-8-sig"))
        self.assertEqual(agy_hook.settings_path().read_bytes(), before, "不碰 agy 的設定檔")
        self.assertFalse(agy_hook.refresh(), "已經是新版")


class UnsafePathTest(FakeAgyHome):
    subdir = "user name & co"  # 家目錄有空白、cmd 的特殊字元

    def test_path_with_spaces_uses_encoded_command(self):
        self.write_settings({})
        agy_hook.install()
        command = self.settings()["statusLine"]["command"]
        self.assertIn("-EncodedCommand", command)
        self.assertNotIn(" & ", command)
        self.assertEqual(len(command.split()), 7, "agy 用空白切參數：每個參數裡都不能有空白")
        self.assertTrue(agy_hook.is_ours(command))
        self.assertEqual(agy_hook.status(), agy_hook.INSTALLED)
        self.assertFalse(agy_hook.is_ours("powershell.exe -EncodedCommand %%%"))


@unittest.skipUnless(sys.platform == "win32", "跑真的 PowerShell")
class HookScriptRunTest(FakeAgyHome):
    """照 agy 的方式（空白切開、經 cmd.exe）真的跑一次 hook。"""

    def run_hook(self, payload: dict) -> str:
        args = ["cmd.exe", "/d", "/c", *agy_hook.hook_command().split()]
        proc = subprocess.run(args, input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                              capture_output=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.decode("utf-8")

    def test_saves_only_quota_and_prints_nothing_without_custom_line(self):
        self.write_settings({})
        agy_hook.install()
        self.assertEqual(self.run_hook({**PAYLOAD, "agent_state": "authenticating", "quota": None}), "")
        self.assertFalse(agy_hook.cache_path().exists(), "登入中 quota 是 null：不存")
        before = time.time() * 1000
        self.assertEqual(self.run_hook(PAYLOAD), "")
        cache = json.loads(agy_hook.cache_path().read_text(encoding="utf-8"))
        self.assertEqual(cache["quota"], QUOTA)
        self.assertGreaterEqual(cache["fetchedAt"], before - 1000)
        self.assertEqual(set(cache), {"fetchedAt", "quota"}, "email 等個資不存")
        self.assertEqual(list(agy_hook.hook_dir().glob("*.tmp")), [])

    def test_custom_line_gets_stdin_and_its_output_is_shown(self):
        self.write_settings({"statusLine": {"type": "command", "command": "findstr agent_state"}})
        agy_hook.install()
        out = self.run_hook(PAYLOAD)
        self.assertIn('"agent_state"', out, "原本的指令收到 stdin，輸出照印")
        self.assertFalse(out.startswith("\ufeff"), "轉手給原本指令的 stdin 不能多 BOM")
        self.assertTrue(agy_hook.cache_path().exists())

    def test_hung_custom_line_is_ended(self):
        marker = f"aiqt-agy-hang-{os.getpid()}"
        script = self.dir / "hang.py"
        script.write_text(f"import time  # {marker}\ntime.sleep(120)\n", encoding="utf-8")
        self.write_settings({"statusLine": {"type": "command", "command": f"{sys.executable} {script.as_posix()}"}})
        agy_hook.install()
        start = time.monotonic()
        self.assertEqual(self.run_hook(PAYLOAD), "")
        self.assertLess(time.monotonic() - start, agy_hook.ORIGINAL_TIMEOUT_MS / 1000 + 20)
        time.sleep(1)
        self.assertFalse(processes_with(marker), "卡住的原本狀態列要被收掉")


class UnsafePathRunTest(HookScriptRunTest):
    subdir = "user name & co"

    def test_custom_line_gets_stdin_and_its_output_is_shown(self):
        pass  # 只看路徑有空白時的 -EncodedCommand 能不能跑起來

    def test_hung_custom_line_is_ended(self):
        pass  # 同上


class CacheParseTest(unittest.TestCase):
    def cache(self, age_s=60, quota=QUOTA):
        return {"fetchedAt": (NOW - timedelta(seconds=age_s)).timestamp() * 1000, "quota": quota}

    def test_parse_real_payload(self):
        state = antigravity.parse_cache(self.cache(), NOW)
        self.assertEqual(state.status, OK)
        self.assertEqual(state.source, "agy-statusline")
        self.assertEqual([(w.label, w.used_pct, w.duration_s) for w in state.windows],
                         [("Gemini", 7.9, 604800), ("Claude/GPT", 0.0, 604800)], "標籤跟 /usage 一樣")
        self.assertEqual(state.windows[0].resets_at, datetime(2026, 10, 10, 16, 7, 10, tzinfo=timezone.utc))
        self.assertEqual(state.fetched_at, NOW - timedelta(seconds=60))

    def test_other_windows_omitted_fraction_and_freshness(self):
        quota = {"gemini-5h": {"reset_time": "2026-10-04T03:00:00Z"}}  # proto3 省略 0
        state = antigravity.parse_cache(self.cache(age_s=20 * 60, quota=quota), NOW)
        self.assertEqual((state.windows[0].label, state.windows[0].used_pct, state.windows[0].duration_s),
                         ("Gemini 5h", 100.0, 5 * 3600))
        self.assertEqual(state.status, STALE, "跟其他檔案來源一樣 15 分鐘就算過期")
        for bad in (None, {}, {"gemini-weekly": "x"}):
            with self.assertRaises(ValueError):
                antigravity.parse_cache(self.cache(quota=bad), NOW)

    def test_cli_labels_match_cache_labels(self):
        usage = {"status": "SUCCESS", "command": {"data": {"groups": [
            {"name": "Gemini Models", "buckets": [{"window": "weekly", "remaining_fraction": 0.5}]},
            {"name": "Claude and GPT models", "buckets": [{"window": "5h", "remaining_fraction": 0.5}]}]}}}
        self.assertEqual([w.label for w in antigravity.parse_usage(usage, NOW).windows],
                         ["Gemini", "Claude/GPT 5h"])


class FetchTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cache_file = Path(tmp.name) / "usage-cache.json"
        for patch in (mock.patch.object(antigravity.agy_hook, "cache_path", return_value=self.cache_file),
                      mock.patch.object(antigravity.config, "data_dir", return_value=Path(tmp.name) / "data")):
            patch.start()
            self.addCleanup(patch.stop)

    def write_cache(self, age_s):
        self.cache_file.write_text(json.dumps(
            {"fetchedAt": (NOW - timedelta(seconds=age_s)).timestamp() * 1000, "quota": QUOTA}), encoding="utf-8")

    def test_fresh_cache_skips_cli(self):
        self.write_cache(60)
        with mock.patch.object(antigravity, "run_agy_usage") as run:
            state = antigravity.fetch(now=NOW)
        run.assert_not_called()
        self.assertEqual((state.status, state.source), (OK, "agy-statusline"))
        self.assertEqual(antigravity.fetch_local(NOW).windows[0].label, "Gemini")

    def test_old_cache_runs_cli(self):
        self.write_cache(10 * 60)
        with mock.patch.object(antigravity, "run_agy_usage", return_value=AntigravityUsage.SAMPLE) as run:
            state = antigravity.fetch(now=NOW)
        run.assert_called_once()
        self.assertEqual(state.source, "agy-cli")

    def test_cli_failure_falls_back_to_cache(self):
        self.write_cache(10 * 60)
        with mock.patch.object(antigravity, "run_agy_usage", side_effect=TimeoutError("逾時")):
            state = antigravity.fetch(now=NOW)
        self.assertEqual(state.source, "agy-statusline")
        self.assertIn("逾時", state.detail["api_error"])

    def test_timeout_without_cache_is_marked(self):
        with mock.patch.object(antigravity, "run_agy_usage", side_effect=TimeoutError("逾時")):
            state = antigravity.fetch(now=NOW)
        self.assertEqual((state.status, state.detail.get("timeout")), (ERROR, True))
        with mock.patch.object(antigravity, "run_agy_usage", side_effect=RuntimeError("壞了")):
            with self.assertRaises(RuntimeError):  # 其他錯誤照常往上丟，fetch_one 收成 error
                antigravity.fetch(now=NOW)
        from ai_quota_tray.model import AuthExpired
        with mock.patch.object(antigravity, "run_agy_usage", side_effect=AuthExpired("未登入")):
            self.assertEqual(antigravity.fetch(now=NOW).status, AUTH_EXPIRED)

    def test_retry_once_after_timeout(self):
        with mock.patch.object(antigravity, "find_agy_bin", return_value="agy"), \
                mock.patch.object(antigravity.time, "sleep") as sleep, \
                mock.patch.object(antigravity, "_run_once",
                                  side_effect=[TimeoutError("1"), AntigravityUsage.SAMPLE]) as once:
            self.assertEqual(antigravity.run_agy_usage(), AntigravityUsage.SAMPLE)
        self.assertEqual(once.call_count, 2)
        sleep.assert_called_once_with(antigravity.STAGGER_S)  # 先錯開，不跟其他家同時起來
        with mock.patch.object(antigravity, "find_agy_bin", return_value="agy"), \
                mock.patch.object(antigravity.time, "sleep"), \
                mock.patch.object(antigravity, "_run_once", side_effect=TimeoutError("x")) as once:
            with self.assertRaises(TimeoutError):
                antigravity.run_agy_usage()
        self.assertEqual(once.call_count, antigravity.ATTEMPTS)

    def test_run_once_closes_stdin_fixes_cwd_and_salvages_output(self):
        done = subprocess.CompletedProcess([], 0, json.dumps(AntigravityUsage.SAMPLE), "")
        with mock.patch.object(antigravity.subprocess, "run", return_value=done) as run:
            antigravity._run_once("agy", 25)
        kwargs = run.call_args.kwargs
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["cwd"], antigravity.config.data_dir())
        self.assertTrue(antigravity.config.data_dir().is_dir())
        late = subprocess.TimeoutExpired("agy", 25, output=json.dumps(AntigravityUsage.SAMPLE).encode())
        with mock.patch.object(antigravity.subprocess, "run", side_effect=late):
            self.assertEqual(antigravity._run_once("agy", 25), AntigravityUsage.SAMPLE, "答案已經印出來了就用")
        with mock.patch.object(antigravity.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("agy", 25, output=b"")):
            with self.assertRaises(TimeoutError):
                antigravity._run_once("agy", 25)


def processes_with(marker: str) -> list[str]:
    """目前在跑、命令列含 marker 的行程（跟 test_claude_hook 那支一樣；測試檔之間不互相 import）。"""
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process | ForEach-Object { $_.CommandLine }"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    return [line for line in out.splitlines() if marker in line and "Get-CimInstance" not in line]


class AntigravityUsage:
    SAMPLE = {"status": "SUCCESS", "command": {"data": {"groups": [
        {"name": "Gemini Models", "buckets": [{"window": "weekly", "remaining_fraction": 0.8,
                                               "reset_time": "2026-10-10T15:00:00Z"}]}]}}}


class TimeoutDisplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def test_timeout_is_grey_not_red_and_survives_carry_over(self):
        from PySide6.QtWidgets import QLabel
        from ai_quota_tray import card, strip
        prev = ProviderState("antigravity", [make_window(20, NOW + timedelta(days=3), 604800, label="Gemini")],
                             NOW - timedelta(minutes=10), OK, source="agy-cli")
        new = ProviderState("antigravity", [], None, ERROR, {"timeout": True}, error="逾時")
        kept = carry_over(prev, new, NOW)
        self.assertTrue(kept.detail["timeout"])
        self.assertFalse(card.is_failure(kept))
        self.assertEqual(card.status_message(kept), i18n.tr("card.timeout"))
        later = carry_over(kept, ProviderState("antigravity", [], None, ERROR, error="壞了"), NOW)
        self.assertNotIn("timeout", later.detail, "下一次是別的錯誤就不能還說逾時")
        self.assertTrue(card.is_failure(later))

        c = card.Card()
        self.addCleanup(c.close)
        c.set_states([("antigravity", kept)])
        msg = next(lbl for lbl in c.findChildren(QLabel) if lbl.text() == i18n.tr("card.timeout"))
        self.assertIn(c._theme["dim"], msg.styleSheet())
        bar = strip.Strip()
        self.addCleanup(bar.close)
        bar.set_states([("antigravity", kept)])
        self.assertNotIn("!", [lbl.text() for lbl in bar.findChildren(QLabel)])


class SettingsAgyButtonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def make(self, status):
        from ai_quota_tray import claude_hook
        from ai_quota_tray.settings import SettingsDialog
        with mock.patch.object(agy_hook, "status", return_value=status), \
                mock.patch.object(claude_hook, "status", return_value=claude_hook.NOT_INSTALLED):
            dlg = SettingsDialog({"antigravity"}, "zh-TW", lambda *a: None)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_button_follows_status_and_installs_agy_hook_only(self):
        from ai_quota_tray import claude_hook
        dlg = self.make(agy_hook.NOT_INSTALLED)
        button = dlg.hook_buttons["antigravity"]
        self.assertEqual(button.objectName(), "agyHookButton")
        self.assertEqual(button.text(), "安裝擷取")
        self.assertIn("agy", dlg.hook_descs["antigravity"].text())
        with mock.patch.object(dlg, "confirm", return_value=True) as confirm, \
                mock.patch.object(agy_hook, "install") as install, \
                mock.patch.object(claude_hook, "install") as claude_install, \
                mock.patch.object(agy_hook, "status", return_value=agy_hook.INSTALLED):
            button.click()
        install.assert_called_once()
        claude_install.assert_not_called()
        self.assertIn(str(agy_hook.settings_path()), confirm.call_args.args[0])
        self.assertEqual(button.text(), "移除擷取")
        self.assertIn("重開 agy", dlg.hook_descs["antigravity"].text())
        for status in (agy_hook.NO_AGY, agy_hook.UNREADABLE):
            hidden = self.make(status)
            self.assertFalse(hidden.hook_buttons["antigravity"].isVisibleTo(hidden), status)
            self.assertTrue(hidden.hook_descs["antigravity"].text())


if __name__ == "__main__":
    unittest.main()
