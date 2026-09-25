# 打包成 dist\AiQuotaTray\AiQuotaTray.exe（--onedir，CLAUDE.md §5：不要 --onefile）
# 用法：在專案根目錄執行  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

.venv\Scripts\python -m pip install -q pyinstaller
.venv\Scripts\pyinstaller --noconfirm --clean --onedir --windowed `
    --name AiQuotaTray `
    --distpath dist --workpath build `
    --paths . `
    --exclude-module tkinter `
    packaging\launch.py
if ($LASTEXITCODE -ne 0) { throw "pyinstaller 失敗（$LASTEXITCODE）" }

# 用不到的大檔：軟體 OpenGL 備援（純 QWidget 不需要）、Qt 內建翻譯
Remove-Item dist\AiQuotaTray\_internal\PySide6\opengl32sw.dll -ErrorAction SilentlyContinue
Remove-Item dist\AiQuotaTray\_internal\PySide6\translations -Recurse -ErrorAction SilentlyContinue

$size = (Get-ChildItem dist\AiQuotaTray -Recurse | Measure-Object Length -Sum).Sum / 1MB
"完成：dist\AiQuotaTray\AiQuotaTray.exe（整個資料夾 {0:N1} MB）" -f $size
