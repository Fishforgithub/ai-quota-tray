"""Command line entry: ``tray`` runs the tray; ``probe`` prints quota JSON."""
from __future__ import annotations

import argparse
import json
import logging
import sys

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
    args = parser.parse_args(argv)

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


if __name__ == "__main__":
    sys.exit(main())
