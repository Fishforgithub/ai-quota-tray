"""PyInstaller 的進入點（__main__.py 用相對 import，不能直接當腳本打包）。

build.ps1 要帶 --paths .：venv 裡是 pip install -e 的 editable 安裝（import hook），PyInstaller 追不到。
"""
import sys

from ai_quota_tray.__main__ import main

sys.exit(main())
