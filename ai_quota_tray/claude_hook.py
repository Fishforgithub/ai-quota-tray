"""安裝／移除 Claude Code 的狀態列擷取（statusLine hook）。

Claude Code 每次更新狀態列時，會把含 rate_limits 的 JSON 從 stdin 丟給 statusLine.command。
我們放一支 PowerShell 腳本當這個指令：把 rate_limits 存進 ~/.claude/usage-cache.json
（providers/claude.py 讀的就是它），再照常執行使用者原本的狀態列、印出它的內容。
不呼叫任何 API、不碰憑證，只是把 Claude Code 自己已經拿到的數字存起來。

設計（業主 2026-09-26 定）：
- 一定要使用者在設定裡按「安裝」並確認，因為會改到 Claude Code 的設定檔。
- 不蓋掉使用者原本的狀態列：原本的 statusLine 記在 HOOK_DIR/original-statusline.json（移除時還原用），
  指令本身另存成 original.sh／original.ps1，hook 存完數字後照樣執行它：Claude Code 經 Git Bash 呼叫時
  （環境有 MSYSTEM）用 bash 跑 .sh，否則用 PowerShell 跑 .ps1，跟 Claude Code 自己的規則一樣。
  ⚠️ 不能把指令字串直接當參數丟給 bash：PowerShell 5.1 呼叫外部程式時會吃掉參數裡的雙引號，
  `"C:/.../node.EXE" "D:/...js"`（原本是反斜線）到 bash 變成沒引號、反斜線被當跳脫字元吃光（2026-09-26 實測）。
  存成檔案讓 shell 自己讀，就不經過這層轉換。
- 用 PowerShell 不用 Node：Claude Code 用官方安裝程式裝時電腦上不一定有 Node。
- hook 檔放在 ~/.claude/ai-quota-tray/，不放 App 目錄：MSIX 解除安裝時不能跑清理程式，
  設定檔會殘留這個指令；檔案還在的話狀態列照常運作，只是多存一個沒人讀的快取。
- 路徑一律正斜線：Git Bash 會把沒加引號的反斜線當跳脫字元吃掉（官方文件的警告）。
- v2（2026-10-04）：讀 stdin、跑原本的狀態列都有上限（PS_HELPERS）。Claude Code 取消慢的一輪時只結束它直接
  啟動的那一層，底下的行程沒上限就會永遠等輸入結束——業主電腦上一天累積了 1 個 PowerShell、7 個 node。
  原本的狀態列若就是業主自己的 Node 版（LEGACY_MARKERS），不再轉交：它做的事（寫同一個快取、印同格式的一行）
  hook 本身都做了。已安裝的舊版腳本由 refresh() 在 App 啟動時換新（只動 hook 資料夾，不碰設定檔）。

官方文件：https://code.claude.com/docs/en/statusline（Windows configuration 一節）
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

HOOK_VERSION = 2
STDIN_TIMEOUT_MS = 3000  # 呼叫端早就把資料送完了；等這麼久還沒結束＝被取消了
ORIGINAL_TIMEOUT_MS = 5000  # 原本的狀態列最多跑這麼久，超過就連同它的子行程一起結束
NOT_INSTALLED, INSTALLED, LEGACY, NO_CLAUDE, UNREADABLE = (
    "not_installed", "installed", "legacy", "no_claude", "unreadable")
# 業主自己原本的 Node 版 hook（D:\FISH\tools\claude-monitor），寫的是同一個快取檔
LEGACY_MARKERS = ("statusline-usage.js",)
BACKUP_SUFFIX = ".ai-quota-tray.bak"

# 兩支 hook（這裡與 agy_hook.py）共用的 PowerShell 函式：讀 stdin、跑原本的狀態列都有上限（見模組說明 v2）。
# 自己用 StreamReader 讀、自己寫 bytes：不依賴 [Console] 的編碼設定（沒有主控台時設定會失敗）。
PS_HELPERS = r'''$utf8 = New-Object System.Text.UTF8Encoding $false

function Read-Stdin([int]$TimeoutMs) {
    $reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), $utf8)
    $task = $reader.ReadToEndAsync()
    if (-not $task.Wait($TimeoutMs)) { return $null }
    return $task.Result.TrimStart([char]0xFEFF)  # 有些呼叫端（.NET）會在 stdin 開頭塞 BOM
}

function Invoke-Original([string]$File, [string]$Arguments, [string]$Text, [int]$TimeoutMs) {
    # 先照 PATH 找到完整路徑：Process.Start（CreateProcess）會先找 System32，
    # bash 就會變成 WSL 的 System32\bash.exe 而不是 Git Bash（2026-10-04 測試抓到）
    $found = Get-Command $File -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $File = $found.Source }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $File
    $psi.Arguments = $Arguments
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.StandardOutputEncoding = $utf8
    try { $p = [System.Diagnostics.Process]::Start($psi) } catch { return '' }
    $out = $p.StandardOutput.ReadToEndAsync()
    try {
        $bytes = $utf8.GetBytes($Text)
        $p.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
        $p.StandardInput.Close()
    } catch { }
    if (-not $p.WaitForExit($TimeoutMs)) {
        & taskkill.exe /T /F /PID $p.Id | Out-Null
        return ''
    }
    return $out.Result.TrimEnd("`r", "`n")
}
'''

HOOK_SCRIPT = r'''# ai-quota-tray statusline hook v{version}
# 由 AI Usage Meter 安裝。把 Claude Code 給狀態列的 rate_limits 存到本機，再照常顯示原本的狀態列。
# 移除：AI Usage Meter 右鍵 → 設定… → Claude 那一列的「移除擷取」（會還原原本的狀態列設定）。
$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'
{helpers}
[Console]::OutputEncoding = $utf8
$raw = Read-Stdin {stdin_ms}
if ($raw -eq $null) {{ exit 0 }}  # 等不到輸入結束：這一輪已經被取消了，不要留著等
$data = $null
try {{ $data = $raw | ConvertFrom-Json }} catch {{ }}

if ($data -and $data.rate_limits) {{
    $cache = $env:CLAUDE_USAGE_CACHE
    if (-not $cache) {{ $cache = Join-Path $HOME '.claude/usage-cache.json' }}
    try {{
        $ms = [long]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
        $json = @{{ fetchedAt = $ms; rate_limits = $data.rate_limits }} | ConvertTo-Json -Depth 6 -Compress
        $tmp = "$cache.tmp"
        [System.IO.File]::WriteAllText($tmp, $json, $utf8)
        Move-Item -LiteralPath $tmp -Destination $cache -Force
    }} catch {{ }}
}}

# 原本的狀態列：跟 Claude Code 一樣，從 Git Bash 叫起來的就用 bash 跑，否則用 PowerShell
$root = $PSScriptRoot -replace '\\', '/'
if ($env:MSYSTEM -and (Test-Path -LiteralPath "$root/original.sh")) {{
    [Console]::Out.Write((Invoke-Original 'bash' ('"' + $root + '/original.sh"') $raw {original_ms}))
    exit 0
}}
if (Test-Path -LiteralPath "$root/original.ps1") {{
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $root + '/original.ps1"'
    [Console]::Out.Write((Invoke-Original 'powershell' $arguments $raw {original_ms}))
    exit 0
}}

$line = 'Claude'
if ($data) {{
    if ($data.model -and $data.model.display_name) {{ $line = $data.model.display_name }}
    elseif ($data.model -and $data.model.id) {{ $line = $data.model.id }}
    $rl = $data.rate_limits
    if ($rl -and ($rl.five_hour -or $rl.seven_day)) {{
        $fmt = {{ param($w) if ($w -and $w.used_percentage -ne $null) {{ '{{0}}%' -f [math]::Round($w.used_percentage) }} else {{ '--' }} }}
        $line = '{{0}}  5h {{1}} · 7d {{2}}' -f $line, (& $fmt $rl.five_hour), (& $fmt $rl.seven_day)
    }}
}}
[Console]::Out.Write($line)
'''


# 沒有 Git Bash 時用來跑使用者原本的狀態列。PowerShell 5.1 轉手 stdin 給子程式時會在開頭加 BOM，
# 原本的指令（例如 Node）解析 JSON 就會失敗（2026-09-26 實測），所以自己讀、去 BOM、用無 BOM 的 UTF-8 轉交
ORIGINAL_PS1 = r'''$utf8 = New-Object System.Text.UTF8Encoding $false
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$raw = [Console]::In.ReadToEnd().TrimStart([char]0xFEFF)
$raw | {command}
'''


def hook_script() -> str:
    return HOOK_SCRIPT.format(version=HOOK_VERSION, helpers=PS_HELPERS, stdin_ms=STDIN_TIMEOUT_MS,
                              original_ms=ORIGINAL_TIMEOUT_MS)


def script_version(path: Path) -> int:
    """hook 腳本第一行的版號（# ai-quota-tray … hook vN）；讀不到回 0。agy_hook 也用它。"""
    try:
        first = path.read_text(encoding="utf-8-sig").split("\n", 1)[0]
    except OSError:
        return 0
    match = re.search(r"hook v(\d+)", first)
    return int(match.group(1)) if match else 0


def is_legacy(command: str) -> bool:
    return any(marker in command for marker in LEGACY_MARKERS)


def claude_dir() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env) if env else Path.home() / ".claude"


def settings_path() -> Path:
    return claude_dir() / "settings.json"


def hook_dir() -> Path:
    return claude_dir() / "ai-quota-tray"


def hook_path() -> Path:
    return hook_dir() / "statusline.ps1"


def original_path() -> Path:
    return hook_dir() / "original-statusline.json"


def hook_command() -> str:
    # 正斜線＋引號：Git Bash 與 PowerShell 都吃得下，家目錄有空白也不會斷
    return f'powershell -NoProfile -ExecutionPolicy Bypass -File "{hook_path().as_posix()}"'


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


def status() -> str:
    if not claude_dir().is_dir():
        return NO_CLAUDE
    try:
        command = _command_of(_read_settings())
    except HookError:
        return UNREADABLE
    if hook_path().as_posix() in command.replace("\\", "/"):
        return INSTALLED
    if is_legacy(command):
        return LEGACY
    return NOT_INSTALLED


def install() -> None:
    """寫 hook、記下原本的狀態列、把 statusLine 指到 hook。已安裝時只更新 hook 檔。"""
    settings = _read_settings()  # 讀不懂就在這裡丟 HookError，什麼都不動
    current = settings.get("statusLine")
    ours = hook_path().as_posix() in _command_of(settings).replace("\\", "/")
    hook_dir().mkdir(parents=True, exist_ok=True)
    hook_path().write_text(hook_script(), encoding="utf-8-sig")
    if ours:
        return
    _write_json(original_path(), {"statusLine": current})
    command = _command_of({"statusLine": current})
    if command and not is_legacy(command):  # 業主的 Node 版做的事 hook 都做了，不再轉交（見模組說明 v2）
        # 原本指令原封不動寫進檔案，讓 bash／PowerShell 自己解析（見模組說明的 ⚠️）
        (hook_dir() / "original.sh").write_text(command + "\n", encoding="utf-8", newline="\n")
        # PowerShell 5.1 沒 BOM 會把非 ASCII 當 ANSI 碼頁；$input 轉給原本指令的 stdin。
        # 以引號開頭的（"C:\...\node.exe" ...）在 PowerShell 是字串不是指令，要加呼叫運算子 &
        body = "& " + command if command.lstrip().startswith(('"', "'")) else command
        (hook_dir() / "original.ps1").write_text(ORIGINAL_PS1.format(command=body), encoding="utf-8-sig")
    if settings_path().exists():
        shutil.copy2(settings_path(), settings_path().with_name(settings_path().name + BACKUP_SUFFIX))
    # 保留原本的 padding、refreshInterval 等欄位，只換掉指令
    new_line = {k: v for k, v in (current or {}).items() if k not in ("type", "command")} \
        if isinstance(current, dict) else {}
    settings["statusLine"] = {"type": "command", "command": hook_command(), **new_line}
    _write_json(settings_path(), settings)


def refresh() -> bool:
    """App 啟動時叫：已安裝但腳本比這一版舊 → 換新，並拿掉對業主 Node 版的轉交。
    只動 hook 資料夾裡我們自己的檔案，不碰 Claude Code 的設定檔。回傳有沒有換。"""
    if status() != INSTALLED or script_version(hook_path()) >= HOOK_VERSION:
        return False
    hook_path().write_text(hook_script(), encoding="utf-8-sig")
    try:
        original = json.loads(original_path().read_text(encoding="utf-8")).get("statusLine")
    except (OSError, ValueError, AttributeError):
        original = None
    if is_legacy(_command_of({"statusLine": original})):
        for name in ("original.sh", "original.ps1"):
            (hook_dir() / name).unlink(missing_ok=True)
    return True


def uninstall() -> None:
    """還原原本的狀態列並刪掉 hook。使用者之後自己改過狀態列的話，就不動設定檔。"""
    settings = _read_settings()
    if hook_path().as_posix() in _command_of(settings).replace("\\", "/"):
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
