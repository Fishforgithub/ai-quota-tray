"""安裝／移除 Antigravity CLI（agy）的狀態列擷取（statusLine hook）。

agy 的互動介面每次狀態改變（authenticating／idle／thinking…）都會執行 settings.json 的 statusLine.command，
把狀態 JSON 從 stdin 丟進去；裡面的 quota 就是 /usage 那兩個額度池（官方文件
https://antigravity.google/docs/cli/statusline）。我們放一支 PowerShell 腳本當這個指令：把 quota 存到
HOOK_DIR/usage-cache.json（providers/antigravity.py 先讀它），使用者原本有自訂狀態列就照常執行、印出它的輸出。
不呼叫任何 API、不碰憑證。跟 Claude 的做法一樣（claude_hook.py），業主 2026-10-04 選的：比每次冷啟動一支
190 MB 的 agy 去查 /usage 輕很多，也不會卡在 agy 啟動時的後端請求（2026-10-03 調查：約 4% 卡超過 30 秒）。

2026-10-04 在業主電腦（agy 1.2.16）實測，寫法都照這些結果：
- quota 只有兩個鍵：{"gemini-weekly": {...}, "3p-weekly": {...}}，各有 remaining_fraction（0～1）、
  reset_time（ISO，Z 結尾）、reset_in_seconds。3p＝第三方模型（Claude／GPT）。
  agy 剛啟動、還在登入（authenticating）時 quota 是 null → 不存，免得蓋掉好的快取。
- agy 經 cmd.exe 執行指令，而且自己用空白切參數、**不理會引號**（"two words" 到我們手上是 `"two`、`words"`）
  → 指令裡不能有含空白的路徑。路徑只有安全字元就用 `-File 路徑`；否則（家目錄有空白、中文、& 之類）
  改用 `-EncodedCommand`（Base64：沒有空白、引號，也沒有 cmd 的特殊字元）。
- 會同時開好幾個（啟動時 2 秒內 7 次），慢的不會被砍（2.5 秒的照樣跑完）→ 寫快取用各自的暫存檔再換名。
- 已經在跑的 agy 不會重讀設定：裝好之後要重開 agy 才生效（設定視窗的說明有寫）。
- stdin 是沒有 BOM 的 UTF-8；PowerShell 5.1 在德文等地區設定下 ConvertTo-Json 的小數點照樣是「.」。
- 沒有原本的狀態列：設 stack_with_default=true、我們什麼都不印 → agy 內建的狀態列照常顯示。
  原本有自訂狀態列：照 agy 的規則（空白切開、經 cmd.exe）再跑一次原本的指令，把它的輸出印出來。
- hook 檔放 ~/.gemini/antigravity-cli/ai-quota-tray/（理由同 claude_hook：MSIX 解除安裝不能跑清理程式）。
- v2：讀 stdin、跑原本的狀態列都有上限（跟 Claude 共用 claude_hook.PS_HELPERS；Claude 那邊實際累積過卡住的行程）。
  已安裝的舊版腳本由 refresh() 在 App 啟動時換新。
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
from pathlib import Path

from .claude_hook import ORIGINAL_TIMEOUT_MS, PS_HELPERS, STDIN_TIMEOUT_MS, script_version

HOOK_VERSION = 2
NOT_INSTALLED, INSTALLED, NO_AGY, UNREADABLE = "not_installed", "installed", "no_agy", "unreadable"
BACKUP_SUFFIX = ".ai-quota-tray.bak"
SAFE_PATH = re.compile(r"[A-Za-z0-9_.:/\-]+")  # 不會被 agy 的空白切割或 cmd.exe 誤解的路徑
POWERSHELL = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass"
ENCODED_FLAGS = ("-encodedcommand", "-enc", "-ec", "-e")

HOOK_SCRIPT = r'''# ai-quota-tray agy statusline hook v{version}
# 由 AI Usage Meter 安裝。把 Antigravity CLI 給狀態列的 quota 存到本機，原本有自訂狀態列就照常顯示。
# 移除：AI Usage Meter 右鍵 → 設定… → Antigravity 那一列的「移除擷取」（會還原原本的狀態列設定）。
$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'
{helpers}
[Console]::OutputEncoding = $utf8
$raw = Read-Stdin {stdin_ms}
if ($raw -eq $null) {{ exit 0 }}  # 等不到輸入結束：這一輪已經被取消了，不要留著等
$data = $null
try {{ $data = $raw | ConvertFrom-Json }} catch {{ }}

if ($data -and $data.quota) {{
    $cache = Join-Path $PSScriptRoot 'usage-cache.json'
    $tmp = "$cache.$PID.tmp"
    try {{
        $ms = [long]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
        $json = @{{ fetchedAt = $ms; quota = $data.quota }} | ConvertTo-Json -Depth 6 -Compress
        [System.IO.File]::WriteAllText($tmp, $json, $utf8)
        Move-Item -LiteralPath $tmp -Destination $cache -Force
    }} catch {{ }}
    Remove-Item -LiteralPath $tmp -Force
}}

# 原本的狀態列：照 agy 的規則（空白切開參數、經 cmd.exe）再跑一次，印出它的輸出
$orig = Join-Path $PSScriptRoot 'original-command.txt'
if (Test-Path -LiteralPath $orig) {{
    $parts = @(([System.IO.File]::ReadAllText($orig, $utf8)).Trim() -split '\s+' | Where-Object {{ $_ }})
    if ($parts.Count -gt 0) {{
        [Console]::Out.Write((Invoke-Original 'cmd.exe' ('/d /c ' + ($parts -join ' ')) $raw {original_ms}))
    }}
}}
'''


def hook_script() -> str:
    return HOOK_SCRIPT.format(version=HOOK_VERSION, helpers=PS_HELPERS, stdin_ms=STDIN_TIMEOUT_MS,
                              original_ms=ORIGINAL_TIMEOUT_MS)


def agy_dir() -> Path:
    return Path.home() / ".gemini" / "antigravity-cli"


def settings_path() -> Path:
    return agy_dir() / "settings.json"


def hook_dir() -> Path:
    return agy_dir() / "ai-quota-tray"


def hook_path() -> Path:
    return hook_dir() / "statusline.ps1"


def cache_path() -> Path:
    return hook_dir() / "usage-cache.json"


def original_path() -> Path:
    return hook_dir() / "original-statusline.json"


def original_command_path() -> Path:
    return hook_dir() / "original-command.txt"


def hook_command() -> str:
    """agy 用空白切參數、不理會引號（見模組說明）：路徑安全就直接給，否則包成 -EncodedCommand。"""
    path = hook_path().as_posix()
    if SAFE_PATH.fullmatch(path):
        return f"{POWERSHELL} -File {path}"
    launcher = "& '" + str(hook_path()).replace("'", "''") + "'"
    encoded = base64.b64encode(launcher.encode("utf-16-le")).decode("ascii")
    return f"{POWERSHELL} -EncodedCommand {encoded}"


class HookError(Exception):
    """設定檔讀不懂，或寫不進去。不動任何檔案。"""


def _read_settings() -> dict:
    path = settings_path()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError as exc:
        raise HookError(f"{path} 不是有效的 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise HookError(f"{path} 的最上層不是物件")
    return data


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _command_of(settings: dict) -> str:
    line = settings.get("statusLine")
    return str(line.get("command") or "") if isinstance(line, dict) else ""


def is_ours(command: str) -> bool:
    if hook_path().as_posix() in command.replace("\\", "/"):
        return True
    parts = command.split()
    for flag, value in zip(parts, parts[1:]):
        if flag.lower() in ENCODED_FLAGS:
            try:
                text = base64.b64decode(value, validate=True).decode("utf-16-le")
            except ValueError:  # binascii.Error 與 UnicodeDecodeError 都是 ValueError
                return False
            return str(hook_path()).replace("'", "''") in text
    return False


def status() -> str:
    if not agy_dir().is_dir():
        return NO_AGY
    try:
        command = _command_of(_read_settings())
    except HookError:
        return UNREADABLE
    return INSTALLED if is_ours(command) else NOT_INSTALLED


def install() -> None:
    """寫 hook、記下原本的狀態列、把 statusLine 指到 hook。已安裝時只更新 hook 檔。"""
    settings = _read_settings()  # 讀不懂就在這裡丟 HookError，什麼都不動
    current = settings.get("statusLine")
    hook_dir().mkdir(parents=True, exist_ok=True)
    hook_path().write_text(hook_script(), encoding="utf-8-sig")
    if is_ours(_command_of(settings)):
        return
    _write_json(original_path(), {"statusLine": current})
    command = _command_of({"statusLine": current})
    # 原本關掉（enabled=false）的自訂狀態列不要幫它打開：當作沒有
    chain = bool(command) and not (isinstance(current, dict) and current.get("enabled") is False)
    if chain:
        original_command_path().write_text(command, encoding="utf-8")
    else:
        original_command_path().unlink(missing_ok=True)
    if settings_path().exists():
        shutil.copy2(settings_path(), settings_path().with_name(settings_path().name + BACKUP_SUFFIX))
    if chain:  # 保留原本的 padding、stack_with_default 等欄位，只換掉指令
        keep = {k: v for k, v in current.items() if k not in ("type", "command")}
        settings["statusLine"] = {"type": "command", "command": hook_command(), **keep}
    else:  # 我們不印東西，agy 內建的狀態列照常顯示
        settings["statusLine"] = {"type": "command", "command": hook_command(),
                                  "enabled": True, "stack_with_default": True}
    _write_json(settings_path(), settings)


def refresh() -> bool:
    """App 啟動時叫：已安裝但腳本比這一版舊 → 換新（只動 hook 資料夾，不碰 agy 的設定檔）。回傳有沒有換。"""
    if status() != INSTALLED or script_version(hook_path()) >= HOOK_VERSION:
        return False
    hook_path().write_text(hook_script(), encoding="utf-8-sig")
    return True


def uninstall() -> None:
    """還原原本的狀態列並刪掉 hook（連同快取）。使用者之後自己改過狀態列的話，就不動設定檔。"""
    settings = _read_settings()
    if is_ours(_command_of(settings)):
        original = None
        try:
            original = json.loads(original_path().read_text(encoding="utf-8")).get("statusLine")
        except (OSError, ValueError, AttributeError):
            pass
        if original is None:
            settings.pop("statusLine", None)
        else:
            settings["statusLine"] = original
        _write_json(settings_path(), settings)
    shutil.rmtree(hook_dir(), ignore_errors=True)
