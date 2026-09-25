"""Claude 狀態列擷取（claude_hook.py）：安裝、還原、不蓋掉原本的狀態列、實際執行 hook。

全部在暫存的 CLAUDE_CONFIG_DIR 裡做，絕不碰真正的 ~/.claude。
"""
import json
import os
import subprocess
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
