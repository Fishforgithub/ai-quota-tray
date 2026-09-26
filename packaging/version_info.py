"""產生嵌進 AiQuotaTray.exe 的版本資訊（PyInstaller 的 --version-file），由 build.ps1 呼叫。

    .venv\\Scripts\\python packaging\\version_info.py build\\version_info.txt

為什麼要有：沒有版本資訊時，工作管理員「詳細資料」的描述欄是空的、檔案內容也看不出是什麼程式。
exe 檔名刻意維持 AiQuotaTray.exe（manifest、StartupTask、個人版的 Run 機碼都認這個名字），
使用者看得到的產品名稱放在 FileDescription／ProductName。版本號從 pyproject 讀，改版本不會漏。
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCT_NAME = "AI Usage Meter"
COMPANY = "Fish-Zero"


def project_version() -> tuple[int, int, int, int]:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    major, minor, patch = (int(part) for part in version.split("."))  # 三段 semver，MSIX 同樣補第四段 0
    return major, minor, patch, 0


def render(version: tuple[int, int, int, int]) -> str:
    dotted = ".".join(map(str, version))
    strings = {
        "CompanyName": COMPANY,
        "FileDescription": PRODUCT_NAME,
        "FileVersion": dotted,
        "InternalName": "AiQuotaTray",
        "LegalCopyright": f"Copyright 2026 {COMPANY}",
        "OriginalFilename": "AiQuotaTray.exe",
        "ProductName": PRODUCT_NAME,
        "ProductVersion": dotted,
    }
    table = ",\n        ".join(f"StringStruct({k!r}, {v!r})" for k, v in strings.items())
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={version}, prodvers={version}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
        {table}])]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
  ]
)
"""


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(project_version()), encoding="utf-8")
    print(f"版本資訊：{out}（{'.'.join(map(str, project_version()))}）")
