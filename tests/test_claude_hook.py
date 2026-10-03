"""Claude 狀態列擷取（claude_hook.py）：安裝、還原、不蓋掉原本的狀態列、實際執行 hook。

全部在暫存的 CLAUDE_CONFIG_DIR 裡做，絕不碰真正的 ~/.claude。
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ai_quota_tray import claude_hook as h

SAMPLE = {"model": {"display_name": "Opus"}, "cwd": "D:/中文資料夾",
          "rate_limits": {"five_hour": {"used_percentage": 23.5, "resets_at": 1790340000},
                          "seven_day": {"used_percentage": 41.2, "resets_at": 1790800000}}}


class HookTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.claude = self.root / ".claude"
        env = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.claude),
                                           "CLAUDE_USAGE_CACHE": str(self.root / "cache.json")})
        env.start()
        self.addCleanup(env.stop)

    def write_settings(self, data):
        self.claude.mkdir(parents=True, exist_ok=True)
        h.settings_path().write_text(json.dumps(data, indent=4), encoding="utf-8")

    def settings(self):
        return json.loads(h.settings_path().read_text(encoding="utf-8"))


class InstallTest(HookTestBase):
    def test_status_without_claude_code(self):
        self.assertEqual(h.status(), h.NO_CLAUDE)

    def test_install_keeps_other_settings_and_original_statusline(self):
        original = {"type": "command", "command": "~/.claude/mine.sh", "padding": 2,
                    "refreshInterval": 5}
        self.write_settings({"model": "opus", "statusLine": original})
        self.assertEqual(h.status(), h.NOT_INSTALLED)
        h.install()
        self.assertEqual(h.status(), h.INSTALLED)
        s = self.settings()
        self.assertEqual(s["model"], "opus")
        self.assertEqual(s["statusLine"]["command"], h.hook_command())
        self.assertEqual((s["statusLine"]["padding"], s["statusLine"]["refreshInterval"]), (2, 5))
        self.assertNotIn("\\", s["statusLine"]["command"])  # Git Bash 會吃掉反斜線
        self.assertTrue((self.claude / ("settings.json" + h.BACKUP_SUFFIX)).exists())
        self.assertEqual((h.hook_dir() / "original.sh").read_text(encoding="utf-8"), "~/.claude/mine.sh\n")

    def test_reinstall_does_not_record_itself_as_original(self):
        self.write_settings({"statusLine": {"type": "command", "command": "echo mine"}})
        h.install()
        h.install()
        saved = json.loads(h.original_path().read_text(encoding="utf-8"))
        self.assertEqual(saved["statusLine"]["command"], "echo mine")

    def test_uninstall_restores_exactly(self):
        original = {"type": "command", "command": "echo mine", "padding": 1}
        self.write_settings({"statusLine": original, "x": 1})
        h.install()
        h.uninstall()
        self.assertEqual(self.settings(), {"statusLine": original, "x": 1})
        self.assertFalse(h.hook_dir().exists())
        self.assertEqual(h.status(), h.NOT_INSTALLED)

    def test_uninstall_without_original_removes_statusline(self):
        self.write_settings({"x": 1})
        h.install()
        h.uninstall()
        self.assertEqual(self.settings(), {"x": 1})

    def test_uninstall_leaves_settings_alone_if_user_changed_statusline(self):
        self.write_settings({})
        h.install()
        mine = {"statusLine": {"type": "command", "command": "echo changed later"}}
        self.write_settings(mine)
        h.uninstall()
        self.assertEqual(self.settings(), mine)
        self.assertFalse(h.hook_dir().exists())

    def test_quoted_original_gets_call_operator_for_powershell(self):
        self.write_settings({"statusLine": {"type": "command",
                                            "command": r'"C:\node\node.exe" "D:\x\s.js"'}})
        h.install()
        ps1 = (h.hook_dir() / "original.ps1").read_text(encoding="utf-8-sig")
        self.assertIn(r'$raw | & "C:\node\node.exe" "D:\x\s.js"', ps1)

    def test_legacy_node_hook_is_recognised(self):
        self.write_settings({"statusLine": {"type": "command",
                                            "command": '"node" "D:/x/statusline-usage.js"'}})
        self.assertEqual(h.status(), h.LEGACY)

    def test_legacy_node_original_is_not_chained(self):
        # 業主自己的 Node 版做的事（寫同一個快取、印同格式的一行）hook 都做了，轉交只會多留卡住的 node
        legacy = {"type": "command", "command": '"node" "D:/x/statusline-usage.js"'}
        self.write_settings({"statusLine": legacy})
        h.install()
        self.assertFalse((h.hook_dir() / "original.sh").exists())
        self.assertFalse((h.hook_dir() / "original.ps1").exists())
        h.uninstall()
        self.assertEqual(self.settings()["statusLine"], legacy, "移除時照樣還原")

    def test_refresh_upgrades_old_script_only_when_installed(self):
        self.assertFalse(h.refresh(), "沒裝 Claude Code：什麼都不做")
        legacy = {"type": "command", "command": '"node" "D:/x/statusline-usage.js"'}
        self.write_settings({"statusLine": legacy})
        self.assertFalse(h.refresh(), "沒裝擷取：什麼都不做")
        h.install()
        # 模擬 0.1.4 以前裝的：v1 腳本，而且轉交給 Node 版
        h.hook_path().write_text("# ai-quota-tray statusline hook v1\n", encoding="utf-8-sig")
        (h.hook_dir() / "original.sh").write_text('"node" "D:/x/statusline-usage.js"\n', encoding="utf-8")
        (h.hook_dir() / "original.ps1").write_text("x", encoding="utf-8")
        before = h.settings_path().read_bytes()
        self.assertTrue(h.refresh())
        self.assertEqual(h.script_version(h.hook_path()), h.HOOK_VERSION)
        self.assertFalse((h.hook_dir() / "original.sh").exists())
        self.assertFalse((h.hook_dir() / "original.ps1").exists())
        self.assertEqual(h.settings_path().read_bytes(), before, "不碰 Claude Code 的設定檔")
        self.assertFalse(h.refresh(), "已經是新版")

    def test_refresh_keeps_chain_for_other_custom_statuslines(self):
        self.write_settings({"statusLine": {"type": "command", "command": "echo mine"}})
        h.install()
        h.hook_path().write_text("# ai-quota-tray statusline hook v1\n", encoding="utf-8-sig")
        self.assertTrue(h.refresh())
        self.assertTrue((h.hook_dir() / "original.sh").exists())

    def test_unreadable_settings_are_never_touched(self):
        self.claude.mkdir(parents=True)
        h.settings_path().write_text("{ // comment\n", encoding="utf-8")
        self.assertEqual(h.status(), h.UNREADABLE)
        with self.assertRaises(h.HookError):
            h.install()
        self.assertEqual(h.settings_path().read_text(encoding="utf-8"), "{ // comment\n")
        self.assertFalse((self.claude / ("settings.json" + h.BACKUP_SUFFIX)).exists())


@unittest.skipUnless(sys.platform == "win32", "hook 是 PowerShell 腳本")
class RunHookTest(HookTestBase):
    """真的跑一次 hook（約 1～2 秒）：Claude Code 就是這樣餵 stdin 的。"""

    def run_hook(self):
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(h.hook_path())],
            input=json.dumps(SAMPLE, ensure_ascii=False).encode("utf-8"),
            capture_output=True, timeout=60)
        return proc.stdout.decode("utf-8", "replace")

    def cache(self):
        return json.loads((self.root / "cache.json").read_text(encoding="utf-8"))

    def test_saves_rate_limits_and_prints_default_line(self):
        self.write_settings({})
        h.install()
        out = self.run_hook()
        self.assertIn("5h 24%", out)
        self.assertEqual(self.cache()["rate_limits"], SAMPLE["rate_limits"])
        self.assertIsInstance(self.cache()["fetchedAt"], int)

    def test_chains_original_statusline_with_same_stdin(self):
        script = self.root / "orig.py"
        script.write_text("import sys, json\nd = json.load(sys.stdin)\n"
                          "sys.stdout.buffer.write(('原本｜' + d['model']['display_name']).encode())\n",
                          encoding="utf-8")
        # 故意用反斜線＋引號：這正是 PowerShell 5.1 轉給 bash 時會被吃掉的寫法
        self.write_settings({"statusLine": {"type": "command",
                                            "command": f'"{sys.executable}" "{script}"'}})
        h.install()
        self.assertIn("原本｜Opus", self.run_hook())
        self.assertIn("rate_limits", self.cache())

    def test_hung_original_is_ended_with_its_children(self):
        """原本的狀態列卡住：時限到就連同子行程一起結束，hook 自己也結束（2026-10-04 累積過 7 個 node）。"""
        marker = f"aiqt-hang-{os.getpid()}"
        script = self.root / "hang.py"
        script.write_text(f"import time  # {marker}\ntime.sleep(120)\n", encoding="utf-8")
        self.write_settings({"statusLine": {"type": "command", "command": f'"{sys.executable}" "{script}"'}})
        h.install()
        start = time.monotonic()
        self.run_hook()
        self.assertLess(time.monotonic() - start, h.ORIGINAL_TIMEOUT_MS / 1000 + 20)
        self.assertIn("rate_limits", self.cache(), "快取照樣先寫好")
        time.sleep(1)
        self.assertFalse(processes_with(marker), "卡住的原本狀態列要被收掉")

    def test_stdin_that_never_ends_does_not_hang(self):
        """呼叫端被取消、輸入一直沒結束：hook 等 STDIN_TIMEOUT_MS 就自己結束，不寫快取。"""
        self.write_settings({})
        h.install()
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(h.hook_path())],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.addCleanup(proc.stdin.close)
        proc.stdin.write(b'{"rate_limits":')
        proc.stdin.flush()
        try:
            proc.wait(timeout=h.STDIN_TIMEOUT_MS / 1000 + 20)
        finally:
            proc.kill()
            proc.stdout.close()
        self.assertEqual(proc.returncode, 0)
        self.assertFalse((self.root / "cache.json").exists())


def processes_with(marker: str) -> list[str]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process | ForEach-Object { $_.CommandLine }"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    return [line for line in out.splitlines() if marker in line and "Get-CimInstance" not in line]


if __name__ == "__main__":
    unittest.main()
