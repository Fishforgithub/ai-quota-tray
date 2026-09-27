@echo off
rem Double-click to run WACK on build\msix\stage (asks for admin). See wack.ps1.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0wack.ps1" %*
