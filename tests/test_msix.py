"""MSIX 版：開機啟動走 StartupTask、manifest 樣板與程式碼一致、打包用圖示。

真正的套件環境（loose registration）只能手動實測，見 CLAUDE.md；這裡測得到的是邏輯與一致性。
"""
import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_quota_tray import startup  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = (ROOT / "packaging" / "msix" / "AppxManifest.xml").read_text(encoding="utf-8")


def load_pack_msix():
    spec = importlib.util.spec_from_file_location("pack_msix", ROOT / "packaging" / "pack_msix.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageIdentityTest(unittest.TestCase):
    def test_this_test_process_has_no_package_identity(self):
        # 真正呼叫 GetCurrentPackageFullName；有套件身分的情況只能在 loose registration 裡實測
        self.assertFalse(startup.is_packaged())


class StartupTaskTest(unittest.TestCase):
    def setUp(self):
        from winrt.windows.applicationmodel import StartupTaskState
        self.State = StartupTaskState
        packaged = mock.patch.object(startup, "is_packaged", return_value=True)
        packaged.start()
        self.addCleanup(packaged.stop)

    def fake_task(self, state, after_request=None):
        task = mock.Mock(state=state)
        task.request_enable_async = mock.AsyncMock(return_value=after_request or state)
        return task

    def test_enable_and_state(self):
        task = self.fake_task(self.State.DISABLED, self.State.ENABLED)
        with mock.patch.object(startup, "_task", return_value=task):
            self.assertFalse(startup.is_enabled())
            self.assertIn("ENABLED", startup.enable())
            startup.disable()
        task.disable.assert_called_once()

    def test_blocked_by_user_raises(self):
        task = self.fake_task(self.State.DISABLED_BY_USER)
        with mock.patch.object(startup, "_task", return_value=task):
            with self.assertRaises(startup.StartupBlocked):
                startup.enable()

    def test_packaged_never_touches_run_key(self):
        task = self.fake_task(self.State.ENABLED)
        with mock.patch.object(startup, "_task", return_value=task), \
                mock.patch.object(startup.winreg, "OpenKey") as open_key:
            startup.enable()
            startup.disable()
            startup.is_enabled()
        open_key.assert_not_called()


class StartupBlockedMenuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qapp = QApplication.instance() or QApplication([])

    def test_menu_shows_how_to_turn_it_on(self):
        from ai_quota_tray import app
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for p in (mock.patch.object(app.win32tray, "TrayIcon"),
                  mock.patch.object(app.win32tray, "small_icon_size", return_value=16),
                  mock.patch.object(app.win32tray, "large_icon_size", return_value=32),
                  mock.patch.object(app.Poller, "refresh"),
                  mock.patch.object(app, "AlertStore"),
                  mock.patch.object(app.config, "config_path", return_value=Path(tmp.name) / "c.json"),
                  mock.patch.object(app.startup, "is_enabled", return_value=False),
                  mock.patch.object(app.startup, "enable",
                                    side_effect=app.startup.StartupBlocked("DISABLED_BY_USER"))):
            p.start()
            self.addCleanup(p.stop)
        tray_app = app.TrayApp({"claude"})
        self.addCleanup(tray_app.shutdown)
        tray_app.handle_menu(app.MENU_STARTUP)
        title, body = tray_app.tray.show_balloon.call_args.args
        self.assertIn("Windows 設定", body)


class ManifestTest(unittest.TestCase):
    def test_ids_match_code(self):
        pack = load_pack_msix()
        self.assertIn(f'TaskId="{startup.TASK_ID}"', MANIFEST)
        self.assertIn(f'Application Id="{pack.APP_ID}"', MANIFEST)
        self.assertEqual(set(re.findall(r'Executable="([^"]+)"', MANIFEST)), {"AiQuotaTray.exe"})
        self.assertIn('Name="runFullTrust"', MANIFEST)

    def test_languages_match_package_strings(self):
        pack = load_pack_msix()
        declared = re.findall(r'<Resource Language="([^"]+)"', MANIFEST)
        self.assertEqual(declared, list(pack.PKG_STRINGS))  # 第一個＝預設語言
        keys = set(re.findall(r"ms-resource:(\w+)", MANIFEST))
        for lang, strings in pack.PKG_STRINGS.items():
            self.assertEqual(set(strings), keys, lang)

    def test_placeholders_and_version(self):
        for name in ("IDENTITY_NAME", "PUBLISHER", "PUBLISHER_DISPLAY_NAME", "VERSION"):
            self.assertIn("{{%s}}" % name, MANIFEST)
        self.assertRegex(load_pack_msix().msix_version(), r"^\d+\.\d+\.\d+\.0$")  # 最後一段必須是 0

    def test_package_description_avoids_trademarks(self):
        text = " ".join(v for s in load_pack_msix().PKG_STRINGS.values() for v in s.values())
        for mark in ("Claude", "Codex", "Copilot", "Antigravity", "Grok"):
            self.assertNotIn(mark, text)


class ExeManifestTest(unittest.TestCase):
    """build.ps1 嵌進 exe 的資訊清單：WACK 的 DPI 檢查要 PerMonitorV2，也不能弄丟 PyInstaller 的預設值。"""

    def test_build_script_embeds_it(self):
        self.assertIn(r"--manifest packaging\app.manifest", (ROOT / "packaging" / "build.ps1").read_text(encoding="utf-8-sig"))

    def test_parses_and_keeps_defaults(self):
        from xml.dom import minidom
        text = (ROOT / "packaging" / "app.manifest").read_text(encoding="utf-8")
        minidom.parseString(text.encode("utf-8"))  # PyInstaller 用 minidom 解析；註解裡有 -- 就會在這裡炸
        self.assertIn(">PerMonitorV2<", text)
        self.assertIn('level="asInvoker"', text)
        self.assertIn("{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}", text)  # supportedOS：Windows 10/11
        self.assertIn(">true</longPathAware>", text)


class VersionInfoTest(unittest.TestCase):
    """exe 的版本資訊：工作管理員顯示的描述要是產品名稱，版本號跟 pyproject／MSIX 一致。"""

    def load(self):
        spec = importlib.util.spec_from_file_location("version_info", ROOT / "packaging" / "version_info.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_build_script_embeds_it(self):
        text = (ROOT / "packaging" / "build.ps1").read_text(encoding="utf-8-sig")
        self.assertIn(r"packaging\version_info.py build\version_info.txt", text)
        self.assertIn(r"--version-file build\version_info.txt", text)

    def test_pyinstaller_can_parse_it(self):
        from PyInstaller.utils.win32 import versioninfo
        vi = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "version_info.txt"
            path.write_text(vi.render(vi.project_version()), encoding="utf-8")
            info = versioninfo.load_version_info_from_text_file(str(path))
        text = str(info)
        self.assertIn("'ProductName', 'AI Usage Meter'", text)
        self.assertIn("'FileDescription', 'AI Usage Meter'", text)
        self.assertIn("'OriginalFilename', 'AiQuotaTray.exe'", text)  # exe 檔名刻意不改

    def test_version_matches_msix(self):
        self.assertEqual(".".join(map(str, self.load().project_version())), load_pack_msix().msix_version())


class ImagesTest(unittest.TestCase):
    def test_every_manifest_image_exists_at_the_right_size(self):
        from PIL import Image
        pack = load_pack_msix()
        with tempfile.TemporaryDirectory() as tmp:
            images = Path(tmp) / "images"
            pack.write_images(images)
            for ref in re.findall(r'images\\([\w.]+\.png)', MANIFEST):
                self.assertTrue((images / ref).exists(), ref)
            sizes = {"Square44x44Logo.png": (44, 44), "Square150x150Logo.png": (150, 150),
                     "Wide310x150Logo.png": (310, 150), "StoreLogo.png": (50, 50),
                     "Square44x44Logo.targetsize-24_altform-unplated.png": (24, 24)}
            for name, size in sizes.items():
                with Image.open(images / name) as img:
                    self.assertEqual(img.size, size, name)


if __name__ == "__main__":
    unittest.main()
