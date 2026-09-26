"""打包 Store 版 MSIX：PyInstaller 產物 → 組打包暫存區 → makepri → makeappx。

    .venv\\Scripts\\python packaging\\pack_msix.py              先跑 build.ps1 再打包
    .venv\\Scripts\\python packaging\\pack_msix.py --no-build   沿用現有的 dist\\AiQuotaTray
    .venv\\Scripts\\python packaging\\pack_msix.py --register   打包後 loose registration 裝到本機試跑

流程照 desk-pet/scripts/pack-msix.mjs（已在 Store 上架過），踩過的坑都保留在這裡：
- 產出的 .msix **沒有簽章**：上 Partner Center 由微軟代簽。本機試跑用 --register
  （開發者模式的 loose registration，免簽章，**就地參照 stage 資料夾**，不複製檔案）。
- Identity／Publisher 出廠是佔位值，Partner Center 保留名稱後要換成真值，否則上傳會被拒。
  用環境變數或專案根目錄的 .env.local（已 gitignore）覆蓋：
      AIQT_MSIX_IDENTITY / AIQT_MSIX_PUBLISHER / AIQT_MSIX_PUBLISHER_DISPLAY
- 顯示名與描述是 ms-resource:，resources.pri 沒產出來套件就裝不起來；makepri 預設會把非預設語言
  拆成 resources.language-en.pri（給 .msixbundle 用），單一 .msix 不會載入 → 要拿掉 <packaging>。
  ms-resource 解析不到時 makeappx 照樣打得出包，要到安裝或送審才壞，所以打包前 dump 逐字串核對。
- 重打包前要先移除指向同一個 stage 的舊註冊，否則檔案被鎖、刪不掉 stage。
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "AiQuotaTray"
OUT = ROOT / "build" / "msix"
STAGE = OUT / "stage"
TEMPLATE = ROOT / "packaging" / "msix" / "AppxManifest.xml"
BRAND = ROOT / "ai_quota_tray" / "assets" / "app.png"
APP_ID = "AiQuotaTray"  # 與 AppxManifest.xml 的 Application Id 一致

PLACEHOLDER_IDENTITY = "FishZero.AIQuotaTray"
PLACEHOLDER_PUBLISHER = "CN=FishZero"

# 套件裡跟著語言走的字串（manifest 的 ms-resource:<key>）。語言要與 <Resources> 一致，第一個是預設。
# ⚠️ 顯示名必須是 Partner Center 保留過的名稱。描述不提各家產品名（商標）。
# 用 "en" 不用 "en-US"：宣告 en-US 會被 Partner Center 當成另一個語言、多要一份空白 listing（desk-pet 經驗）。
PKG_STRINGS = {
    "zh-TW": {
        "AppDisplayName": "AI Usage Meter",
        "AppDescription": "在系統匣顯示 AI 程式開發工具的剩餘用量與重置倒數；滑鼠移到圖示上就看得到。",
        "TileDescription": "AI 程式開發工具的剩餘用量。",
    },
    "en": {
        "AppDisplayName": "AI Usage Meter",
        "AppDescription": "Shows how much of your AI coding tools' usage is left and when it resets, "
                          "right in the system tray. Hover the icon to see it.",
        "TileDescription": "Remaining usage of your AI coding tools.",
    },
}


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    local = ROOT / ".env.local"
    if local.exists():
        for line in local.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env.setdefault(key.strip(), value.strip())
    return env


def msix_version() -> str:
    """pyproject 是三段 semver；MSIX 要四段且最後一段必須是 0。"""
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit(f"pyproject 的 version 不是三段 semver：{version}")
    return f"{version}.0"


def sdk_tool(name: str) -> Path:
    base = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    versions = sorted((d for d in base.glob("10.*") if d.is_dir()),
                      key=lambda d: [int(x) for x in d.name.split(".")], reverse=True)
    for v in versions:
        if (v / "x64" / name).exists():
            return v / "x64" / name
    sys.exit(f"找不到 {name}——請安裝 Windows SDK（Visual Studio Installer 勾「Windows 10/11 SDK」）")


def powershell(command: str) -> str:
    r = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def registrations() -> list[str]:
    """指向這個 stage 的 loose registration（每使用者；只查得到跑這支腳本的帳號）。"""
    out = powershell(f"Get-AppxPackage | Where-Object {{ $_.InstallLocation -eq '{STAGE}' }} "
                     "| ForEach-Object { $_.PackageFullName }")
    return [line for line in out.splitlines() if line.strip()]


# ---------- 圖示 ----------

def _icon(size: int, box: tuple[int, int] | None = None, ratio: float = 1.0) -> Image.Image:
    """品牌圖示縮到 size，貼在 box（預設正方形）透明畫布正中間；ratio＝圖示佔畫布短邊的比例。"""
    box = box or (size, size)
    side = round(min(box) * ratio)
    with Image.open(BRAND) as src:
        art = src.convert("RGBA").resize((side, side), Image.LANCZOS)
    canvas = Image.new("RGBA", box, (0, 0, 0, 0))
    canvas.paste(art, ((box[0] - side) // 2, (box[1] - side) // 2), art)
    return canvas


def write_images(images: Path) -> None:
    images.mkdir(parents=True)
    # 開始功能表的磚塊留邊（官方建議圖示約佔 2/3）；應用程式清單／工作列用的 44x44 與商店圖示滿版
    tiles = {"Square71x71Logo": (71, 0.7), "Square150x150Logo": (150, 0.66),
             "Square310x310Logo": (310, 0.66), "Square44x44Logo": (44, 1.0), "StoreLogo": (50, 1.0)}
    for name, (size, ratio) in tiles.items():
        _icon(size, ratio=ratio).save(images / f"{name}.png")
        if size * 2 <= 512:  # 原圖 512px，放大就糊了
            _icon(size * 2, ratio=ratio).save(images / f"{name}.scale-200.png")
    _icon(150, (310, 150), 0.8).save(images / "Wide310x150Logo.png")
    _icon(300, (620, 300), 0.8).save(images / "Wide310x150Logo.scale-200.png")
    # 工作列、開始功能表清單用的各種實際像素；unplated＝不墊系統強調色的底
    for px in (16, 24, 32, 48, 256):
        icon = _icon(px)
        icon.save(images / f"Square44x44Logo.targetsize-{px}.png")
        icon.save(images / f"Square44x44Logo.targetsize-{px}_altform-unplated.png")


# ---------- resources.pri ----------

def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def make_pri(makepri: Path, identity: str) -> None:
    strings_dir = STAGE / "strings"  # resw 只是 makepri 的輸入，放 stage 裡才吃得到語言資料夾，產完就刪
    for lang, strings in PKG_STRINGS.items():
        (strings_dir / lang).mkdir(parents=True)
        items = "\n".join(f'  <data name="{k}" xml:space="preserve"><value>{_xml_escape(v)}</value></data>'
                          for k, v in strings.items())
        (strings_dir / lang / "Resources.resw").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n<root>\n'
            '  <resheader name="resmimetype"><value>text/microsoft-resx</value></resheader>\n'
            f'  <resheader name="version"><value>2.0</value></resheader>\n{items}\n</root>\n',
            encoding="utf-8")
    cfg, pri = OUT / "priconfig.xml", STAGE / "resources.pri"  # priconfig 放 stage 外，免得被打包
    default_lang = next(iter(PKG_STRINGS))
    run([makepri, "createconfig", "/cf", cfg, "/dq", default_lang, "/pv", "10.0.0", "/o"])
    # 拿掉 <packaging>：否則非預設語言被拆去 resources.language-en.pri，單一 .msix 不會載入
    cfg.write_text(re.sub(r"\s*<packaging>[\s\S]*?</packaging>", "", cfg.read_text(encoding="utf-8")),
                   encoding="utf-8")
    run([makepri, "new", "/pr", STAGE, "/cf", cfg, "/mn", STAGE / "AppxManifest.xml", "/of", pri, "/o"])
    shutil.rmtree(strings_dir)
    split = [p.name for p in STAGE.glob("resources.*.pri")]
    if split:
        sys.exit(f"makepri 又把資源拆包了（{'、'.join(split)}）——priconfig 的 <packaging> 沒拿掉？")

    dump_path = OUT / "resources.pri.xml"
    run([makepri, "dump", "/if", pri, "/of", dump_path, "/dt", "Detailed", "/o"])
    raw = dump_path.read_bytes()
    dump = raw.decode("utf-16") if raw[:2] == b"\xff\xfe" else raw.decode("utf-8")
    missing = [f"{lang} {k}" for lang, strings in PKG_STRINGS.items()
               for k, v in strings.items() if _xml_escape(v) not in dump]
    if not re.search(rf'<ResourceMap[^>]*\sname="{re.escape(identity)}"', dump):
        missing.append(f"ResourceMap 名稱不是 {identity}（ms-resource 會找不到字串）")
    if "Square44x44Logo" not in dump:
        missing.append("圖示沒有被索引進 pri（targetsize 變體會失效）")
    if missing:
        sys.exit("resources.pri 缺東西：\n   " + "\n   ".join(missing) + f"\n   看 {dump_path}")
    print(f"✅ resources.pri：{'／'.join(PKG_STRINGS)}")


def run(cmd: list, **kwargs) -> None:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kwargs)
    if r.returncode != 0:
        sys.exit(f"{Path(str(cmd[0])).name} 失敗（{r.returncode}）：\n{r.stdout}\n{r.stderr}")


# ---------- 主流程 ----------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-build", action="store_true", help="沿用現有的 dist\\AiQuotaTray")
    parser.add_argument("--register", action="store_true", help="打包後 loose registration 裝到本機")
    args = parser.parse_args()

    env = load_env()
    identity = env.get("AIQT_MSIX_IDENTITY", PLACEHOLDER_IDENTITY)
    publisher = env.get("AIQT_MSIX_PUBLISHER", PLACEHOLDER_PUBLISHER)
    publisher_display = env.get("AIQT_MSIX_PUBLISHER_DISPLAY", "Fish Zero")
    version = msix_version()
    print(f"▶ AI Usage Meter MSIX v{version}（Identity {identity}）")
    if identity == PLACEHOLDER_IDENTITY or publisher == PLACEHOLDER_PUBLISHER:
        print("⚠️  Identity/Publisher 仍是佔位值——本機試跑可以，上 Partner Center 前務必換成保留到的真值。")

    if not args.no_build:
        print("▶ build.ps1 …")
        r = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File",
                            str(ROOT / "packaging" / "build.ps1")], cwd=ROOT)
        if r.returncode != 0:
            sys.exit("build.ps1 失敗")
    if not (DIST / "AiQuotaTray.exe").exists():
        sys.exit(f"找不到 {DIST}\\AiQuotaTray.exe（--no-build 時要先自己跑過 build.ps1）")

    makeappx, makepri = sdk_tool("makeappx.exe"), sdk_tool("makepri.exe")

    for full_name in registrations():  # 舊註冊會鎖住 stage 裡的檔
        print(f"▶ 移除指向 stage 的舊註冊：{full_name}")
        powershell(f"Remove-AppxPackage -Package '{full_name}'")
    try:
        shutil.rmtree(STAGE, ignore_errors=False) if STAGE.exists() else None
    except OSError as exc:
        sys.exit(f"刪不掉 {STAGE}：{exc}\n   打包版還在跑？或別的帳號註冊了這個 stage？")
    shutil.copytree(DIST, STAGE)
    write_images(STAGE / "images")
    manifest = (TEMPLATE.read_text(encoding="utf-8")
                .replace("{{IDENTITY_NAME}}", identity)
                .replace("{{PUBLISHER}}", publisher)
                .replace("{{PUBLISHER_DISPLAY_NAME}}", publisher_display)
                .replace("{{VERSION}}", version))
    manifest = re.sub(r"<!--[\s\S]*?-->\s*", "", manifest, count=1)  # 樣板說明不進套件
    (STAGE / "AppxManifest.xml").write_text(manifest, encoding="utf-8")

    print("▶ makepri …")
    make_pri(makepri, identity)

    msix = OUT / f"AiQuotaTray-{version}-x64.msix"
    print("▶ makeappx pack …")
    run([makeappx, "pack", "/d", STAGE, "/p", msix, "/o"])
    print(f"✅ 產出：{msix}（{msix.stat().st_size / 1024 / 1024:.1f} MB）")

    if args.register:
        print("▶ Add-AppxPackage -Register（loose registration）…")
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"Add-AppxPackage -Register '{STAGE / 'AppxManifest.xml'}'"])
        if r.returncode != 0:
            sys.exit("註冊失敗（需要開發者模式：設定 → 系統 → 開發人員專用）")
        pfn = powershell(f"(Get-AppxPackage | Where-Object {{ $_.InstallLocation -eq '{STAGE}' }} "
                         "| Select-Object -First 1 -ExpandProperty PackageFamilyName)")
        print(f"✅ 已註冊：{pfn}")
        print(f"   以套件身分啟動：explorer.exe shell:AppsFolder\\{pfn}!{APP_ID}")
        print("   ⚠️ 直接跑 stage 裡的 exe 不算有套件身分（開機啟動、LocalCache 重導都測不到）。")


if __name__ == "__main__":
    main()
