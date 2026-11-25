"""Read-Only MT5 Manual Order Ticket Formatter & Trade Journal.

STRICT SAFETY GUARANTEE: This script NEVER calls MetaTrader5.order_send or
executes trades. It only formats verified manual tickets and reads MT5
positions/history in read-only mode.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import fx_core as fx  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manual MT5 Ticket Viewer & Read-Only Journal.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show READY manual MT5 order tickets (requires PASS from fx-risk)")
    p_show.add_argument("--now", help="UTC timestamp 'YYYY-MM-DD HH:MM'")
    p_show.add_argument("--json", action="store_true")

    p_sync = sub.add_parser("sync-mt5", help="Read-only sync of open positions and today's deals from MT5")
    p_sync.add_argument("--json", action="store_true")

    p_log = sub.add_parser("log-manual", help="Record a manual trade you entered on MT5")
    p_log.add_argument("--index", type=int, default=1)
    p_log.add_argument("--status", default="placed", choices=["placed", "skipped", "closed"])
    p_log.add_argument("--now", help="UTC timestamp 'YYYY-MM-DD HH:MM'")

    args = parser.parse_args(argv)
    base = Path.cwd()
    cfg = fx.load_config(base)
    journal_file = fx.state_dir(base) / "journal.json"

    try:
        if args.cmd == "show":
            orders_doc = fx.read_json(fx.work_dir(base) / "orders.json")
            risk_doc = fx.read_json(fx.state_dir(base) / "risk.json")
            if not orders_doc or not orders_doc.get("orders"):
                raise fx.FxError("fx_trader/orders.json not found")
            if not risk_doc or not risk_doc.get("results"):
                raise fx.FxError("fx_trader/state/risk.json not found; run fx-risk first")

            today_str = fx.parse_now_utc(args.now).strftime("%Y-%m-%d")
            pass_fps = {
                r["fingerprint"]
                for r in risk_doc["results"]
                if r.get("verdict") == "PASS" and r.get("date_utc") == today_str
            }

            tickets: list[dict[str, Any]] = []
            for idx, o in enumerate(orders_doc["orders"], 1):
                ready = o.get("fingerprint") in pass_fps
                tickets.append({"index": idx, "ready": ready, **o})

            if args.json:
                print(json.dumps({"tickets": tickets}, indent=2))
                return 0

            for t in tickets:
                d = int(t.get("digits", 5))
                tag = "READY (MANUAL MT5 ENTRY)" if t["ready"] else "NOT READY (Run fx-risk PASS today)"
                print(f"TICKET #{t['index']} [{tag}]")
                print(f"  Symbol      {t['mt5_symbol']} ({t['symbol']})")
                print(f"  Type        {t['side'].upper()} (Market)")
                print(f"  Volume      {t['volume_lots']} lots")
                print(f"  Est. Entry  {fx.fmt_price(t['entry'], d)}")
                print(f"  Stop Loss   {fx.fmt_price(t['sl'], d)}  (-${t['max_loss_usd']:.2f} / {t['risk_pips']} pips)")
                print(f"  Take Profit {fx.fmt_price(t['tp'], d)}  (+${t['target_profit_usd']:.2f} / {t['reward_pips']} pips, 1:{t['reward_risk']})")
                print("  Execution   MANUAL ONLY (automated execution disabled)")
            return 0 if any(t["ready"] for t in tickets) else 1

        if args.cmd == "sync-mt5":
            acct = fx.mt5_read_account(cfg)
            pos = fx.mt5_read_positions(cfg)
            deals = fx.mt5_read_today_deals()
            if acct is None:
                raise fx.FxError("MT5 terminal not connected")
            journal = fx.read_json(journal_file) or {"entries": []}
            journal["last_sync_utc"] = _dt.datetime.now(fx.UTC_TZ).strftime("%Y-%m-%d %H:%M")
            journal["mt5_account"] = acct
            journal["mt5_positions"] = pos or []
            journal["mt5_deals_today"] = deals or []
            fx.write_json(journal_file, journal)
            if args.json:
                print(json.dumps(journal, indent=2))
                return 0
            print(f"MT5 Synced ({acct['trade_mode'].upper()}, balance ${acct['balance']:.2f}, equity ${acct['equity']:.2f}, free margin ${acct['margin_free']:.2f})")
            print(f"  Open positions: {len(pos or [])} | Closed deals today: {len(deals or [])}")
            for p in pos or []:
                print(f"  OPEN #{p['ticket']}: {p['symbol']} {p['side'].upper()} {p['volume']} @ {p['entry']} (SL {p['sl']}, TP {p['tp']}, P/L ${p['profit_usd']:+.2f})")
            return 0

        if args.cmd == "log-manual":
            orders_doc = fx.read_json(fx.work_dir(base) / "orders.json") or {}
            orders = orders_doc.get("orders") or []
            if args.index < 1 or args.index > len(orders):
                raise fx.FxError(f"invalid ticket index {args.index}")
            o = orders[args.index - 1]
            now_utc = fx.parse_now_utc(args.now)
            journal = fx.read_json(journal_file) or {"entries": []}
            journal.setdefault("entries", []).append({
                "date_utc": now_utc.strftime("%Y-%m-%d"),
                "time_utc": now_utc.strftime("%Y-%m-%d %H:%M"),
                "symbol": o["symbol"],
                "side": o["side"],
                "volume_lots": o["volume_lots"],
                "entry": o["entry"],
                "sl": o["sl"],
                "tp": o["tp"],
                "max_loss_usd": o["max_loss_usd"],
                "status": args.status,
                "fingerprint": o.get("fingerprint"),
            })
            fx.write_json(journal_file, journal)
            print(f"Logged {o['symbol']} {o['side'].upper()} {o['volume_lots']} lots as '{args.status}' -> fx_trader/state/journal.json")
            return 0

    except fx.FxError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
