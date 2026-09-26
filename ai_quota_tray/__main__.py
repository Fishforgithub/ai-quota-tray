"""命令列入口：tray＝系統匣常駐；probe＝印出各家額度 JSON；startup＝查／開／關開機啟動。

startup 主要給 MSIX 實測用：StartupTask 只能由帶套件身分的行程呼叫，
用 Invoke-CommandInDesktopPackage 以套件身分跑 `AiQuotaTray.exe startup on --out FILE`
就能驗證，不必真人點右鍵選單。打包版沒有主控台，所以結果可寫到 --out 指定的檔案。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .model import utcnow
from .providers import ALL, fetch_one


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:  # 打包版直接雙擊 exe
        argv = ["tray"]
    parser = argparse.ArgumentParser(prog="ai_quota_tray")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe", help="抓一次各家額度並輸出 JSON")
    p.add_argument("--provider", action="append", choices=list(ALL),
                   help="只測這家（可重複），預設全部")
    p.add_argument("--raw", action="store_true", help="附上原始回傳（已遮罩）")
    t = sub.add_parser("tray", help="系統匣常駐")
    t.add_argument("--debug", action="store_true", help="印出系統匣事件與每次抓取結果")
    t.add_argument("--log", metavar="FILE", help="log 寫到檔案（pythonw／打包版沒有主控台）")
    st = sub.add_parser("startup", help="查／開／關開機啟動（MSIX 版走 StartupTask）")
    st.add_argument("action", nargs="?", choices=("status", "on", "off"), default="status")
    st.add_argument("--out", metavar="FILE", help="結果寫到檔案（打包版沒有主控台）")
    args = parser.parse_args(argv)

    if args.cmd == "startup":
        return _startup_command(args.action, args.out)

    if args.cmd == "tray":
        if sys.stderr is not None:  # pythonw 底下沒有 stderr
            sys.stderr.reconfigure(encoding="utf-8")
        logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                            **({"filename": args.log, "encoding": "utf-8"} if args.log else {}))
        logging.getLogger("PIL").setLevel(logging.INFO)  # --debug 時 Pillow 會逐塊印 PNG 解碼
        logging.getLogger("copilot").setLevel(logging.INFO)  # SDK 會逐筆印 JSON-RPC 請求
        from .app import run  # 延後 import：probe 不需要裝 PySide6
        return run()

    now = utcnow()
    states = [fetch_one(n, False, now) for n in (args.provider or list(ALL))]
    out = {"probed_at": now.isoformat().replace("+00:00", "Z"),
           "providers": [s.to_dict(include_raw=args.raw) for s in states]}
    # Windows 主控台預設 cp950，直接 print 中文可能炸
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _startup_command(action: str, out: str | None) -> int:
    from . import startup
    code = 0
    try:
        if action == "on":
            startup.enable()
        elif action == "off":
            startup.disable()
        text = f"packaged={startup.is_packaged()} {startup.describe()}"
    except Exception as exc:  # noqa: BLE001 — 實測用，錯誤原樣寫出來
        text, code = f"packaged={startup.is_packaged()} error={type(exc).__name__}: {exc}", 1
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    elif sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
