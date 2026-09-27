# 對 build\msix\stage 跑 Windows App Certification Kit（WACK），跑完自動移除註冊。
# 用法：雙擊 packaging\wack.cmd（會跳 UAC）；或
#   powershell -ExecutionPolicy Bypass -File packaging\wack.ps1
#   powershell -ExecutionPolicy Bypass -File packaging\wack.ps1 -Summary build\msix\wack-report-xxx.xml   只整理現有報告
#
# 前提：先跑 .venv\Scripts\python packaging\pack_msix.py 產出 stage；Windows 已開「開發人員模式」。
# 踩過的坑（CLAUDE.md §0 MSIX 打包／WACK）：
# - 要系統管理員；管理員視窗可能是另一個帳號，所以註冊與 WACK 都在這個提升權限的視窗裡做完。
# - appcert 遇到報告檔已存在不會覆蓋也不寫新的 → 檔名一律帶版本與時間。
# - loose registration 與 Store 正式版同一個 Identity，測完一定要 Remove-AppxPackage。
param([string]$Summary)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$OutDir = Join-Path $Root "build\msix"
$Stage = Join-Path $OutDir "stage"
$Manifest = Join-Path $Stage "AppxManifest.xml"
$AppCert = "${env:ProgramFiles(x86)}\Windows Kits\10\App Certification Kit\appcert.exe"

function Show-Summary([string]$Report) {
    [xml]$xml = Get-Content -LiteralPath $Report -Encoding UTF8
    $overall = $xml.REPORT.OVERALL_RESULT
    $tests = @($xml.SelectNodes("//TEST"))
    $bad = @($tests | Where-Object { $_.RESULT.'#cdata-section' -ne "PASS" })
    Write-Host ""
    Write-Host "報告：$Report"
    $color = if ($overall -eq "PASS") { "Green" } elseif ($overall -eq "WARNING") { "Yellow" } else { "Red" }
    Write-Host "總結果：$overall（$($tests.Count) 項，$($tests.Count - $bad.Count) 項 PASS）" -ForegroundColor $color
    foreach ($t in $bad) {
        $tag = if ($t.OPTIONAL -eq "TRUE") { "選用" } else { "必要" }
        Write-Host ("  [{0}] {1}：{2}" -f $tag, $t.RESULT.'#cdata-section', $t.NAME)
    }
    if ($bad | Where-Object { $_.OPTIONAL -eq "TRUE" }) {
        Write-Host "  💡 選用項目 FAIL 不影響總結果（「封鎖的可執行檔」「封存檔案」是 Python／Qt 自帶的，歷次都有）。"
    }
}

function Wait-Close { Write-Host ""; Read-Host "按 Enter 關閉" | Out-Null }

if ($Summary) { Show-Summary (Resolve-Path $Summary).Path; exit 0 }

# ---------- 提升權限 ----------
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "WACK 需要系統管理員權限，開啟提升權限的視窗…"
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"")
    exit 0
}

$pfn = $null
try {
    # ---------- 檢查 ----------
    if (-not (Test-Path $AppCert)) { throw "找不到 appcert.exe：$AppCert（要裝 Windows SDK 的 App Certification Kit）" }
    if (-not (Test-Path $Manifest)) { throw "找不到 $Manifest，先跑 .venv\Scripts\python packaging\pack_msix.py" }
    $dev = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" -ErrorAction SilentlyContinue
    if (-not $dev -or $dev.AllowDevelopmentWithoutDevLicense -ne 1) {
        throw "Windows 沒開「開發人員模式」（設定 → 系統 → 開發人員專用），loose registration 裝不起來"
    }

    [xml]$m = Get-Content -LiteralPath $Manifest -Encoding UTF8
    $name, $version = $m.Package.Identity.Name, $m.Package.Identity.Version
    Write-Host "▶ 套件：$name $version（$Stage）"
    $msix = Join-Path $OutDir "AiUsageMeter-$version-x64.msix"
    if (-not (Test-Path $msix)) { Write-Host "  ⚠️ 沒有 $msix；stage 可能不是最後一次打包的結果" -ForegroundColor Yellow }

    # 這個帳號已經裝了同名套件：指向 stage 的是上次沒清掉的，移除；其他（Store 正式版）不碰
    foreach ($p in @(Get-AppxPackage -Name $name)) {
        if ($p.InstallLocation -eq $Stage) {
            Write-Host "▶ 移除上次留下的註冊：$($p.PackageFullName)"
            Remove-AppxPackage -Package $p.PackageFullName
        } else {
            throw "這個帳號（$env:USERNAME）已從 Store 安裝 $($p.PackageFullName)，會與 loose registration 衝突。先解除安裝它再跑。"
        }
    }

    # ---------- 註冊 → WACK ----------
    Write-Host "▶ loose registration"
    Add-AppxPackage -Register $Manifest
    $pfn = (Get-AppxPackage -Name $name | Where-Object { $_.InstallLocation -eq $Stage }).PackageFullName
    if (-not $pfn) { throw "註冊後查不到套件" }
    Write-Host "  $pfn"

    $report = Join-Path $OutDir ("wack-report-{0}-{1}.xml" -f $version, (Get-Date -Format "yyyyMMdd-HHmmss"))
    Write-Host "▶ appcert reset"
    & $AppCert reset | Out-Host
    Write-Host "▶ appcert test（約 3～5 分鐘，期間會自動啟動、關閉 App）"
    & $AppCert test -packagefullname $pfn -reportoutputpath $report | Out-Host
    if (-not (Test-Path $report)) { throw "appcert 沒有產出報告（結束碼 $LASTEXITCODE）" }
} catch {
    Write-Host ""
    Write-Host "❌ $($_.Exception.Message)" -ForegroundColor Red
} finally {
    if ($pfn) {
        Write-Host "▶ 移除註冊：$pfn"
        try { Remove-AppxPackage -Package $pfn } catch { Write-Host "  ⚠️ 移除失敗，請手動：Remove-AppxPackage $pfn" -ForegroundColor Yellow }
    }
}

if ($report -and (Test-Path $report)) { Show-Summary $report }
Wait-Close
