"""24/5 Forex, Gold & Oil Session Clock, Live MT5/Yahoo Quotes, and One-Shot Alerts."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import fx_core as fx  # noqa: E402


def cmd_clock(now_utc: _dt.datetime) -> dict[str, Any]:
    is_open, msg = fx.is_fx_market_open(now_utc)
    sessions = fx.active_sessions_utc(now_utc)
    return {
        "utc": now_utc.strftime("%Y-%m-%d %H:%M"),
        "ny_time": now_utc.astimezone(fx.NY_TZ).strftime("%Y-%m-%d %H:%M"),
        "open": is_open,
        "status": msg,
        "active_sessions": sessions,
        "overlap": ("london" in sessions and "new_york" in sessions),
    }


def evaluate_rule(rule: dict[str, Any], quote: dict[str, Any], now_utc: _dt.datetime) -> tuple[bool, str]:
    rtype = rule.get("type")
    sym = rule.get("symbol", "")
    price = quote.get("price")
    digits = int(quote.get("digits", 5))
    if rtype == "above" and price is not None and price >= float(rule["level"]):
        return True, f"{sym} reached {fx.fmt_price(price, digits)} >= {rule['level']}"
    if rtype == "below" and price is not None and price <= float(rule["level"]):
        return True, f"{sym} dropped to {fx.fmt_price(price, digits)} <= {rule['level']}"
    if rtype == "stop":
        side = rule.get("side", "long").lower()
        lvl = float(rule["level"])
        if price is not None and ((side == "long" and price <= lvl) or (side == "short" and price >= lvl)):
            return True, f"{sym} ({side.upper()}) STOP hit at {fx.fmt_price(price, digits)} (stop {lvl})"
    if rtype == "target":
        side = rule.get("side", "long").lower()
        lvl = float(rule["level"])
        if price is not None and ((side == "long" and price >= lvl) or (side == "short" and price <= lvl)):
            return True, f"{sym} ({side.upper()}) TARGET hit at {fx.fmt_price(price, digits)} (target {lvl})"
    if rtype == "pct" and quote.get("pct_change") is not None:
        if abs(float(quote["pct_change"])) >= abs(float(rule["pct"])):
            return True, f"{sym} moved {quote['pct_change']:+.2f}% today"
    if rtype == "spread" and quote.get("spread_pips") is not None:
        if float(quote["spread_pips"]) >= float(rule["max_pips"]):
            return True, f"{sym} spread spiked to {quote['spread_pips']} pips (>= {rule['max_pips']})"
    if rtype == "session":
        sess = rule.get("session", "london")
        if sess in fx.active_sessions_utc(now_utc):
            return True, f"{sess.replace('_', ' ').title()} session is active ({now_utc.strftime('%H:%M')} UTC)"
    if rtype == "time":
        target_hm = rule.get("at_utc", "")
        if now_utc.strftime("%H:%M") >= target_hm:
            return True, f"Time alert {target_hm} UTC reached"
    return False, ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="24/5 Forex, Gold & Oil Alerts and Quotes.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_clk = sub.add_parser("clock", help="Show UTC/NY time, 24/5 status, and active FX sessions")
    p_clk.add_argument("--now", help="UTC timestamp 'YYYY-MM-DD HH:MM'")
    p_clk.add_argument("--json", action="store_true")

    p_q = sub.add_parser("quote", help="Fetch live quote (MT5 Bid/Ask/Spread or Yahoo)")
    p_q.add_argument("symbol")
    p_q.add_argument("--write", action="store_true", help="Save to fx_trader/prices.json")
    p_q.add_argument("--offline", help="Offline fixture file or dir")
    p_q.add_argument("--json", action="store_true")

    p_add = sub.add_parser("add", help="Add one-shot price, stop/target, spread, or session alert")
    p_add.add_argument("--from-plan", action="store_true", help="Import stop & target from fx_trader/plan.json")
    p_add.add_argument("--symbol")
    p_add.add_argument("--above", type=float)
    p_add.add_argument("--below", type=float)
    p_add.add_argument("--pct", type=float)
    p_add.add_argument("--max-spread", type=float)
    p_add.add_argument("--session", choices=list(fx.SESSIONS_UTC.keys()))
    p_add.add_argument("--at", help="UTC HH:MM")

    p_chk = sub.add_parser("check", help="Evaluate alerts once")
    p_chk.add_argument("--now", help="UTC timestamp 'YYYY-MM-DD HH:MM'")
    p_chk.add_argument("--offline", help="Offline fixture dir")
    p_chk.add_argument("--json", action="store_true")

    sub.add_parser("list", help="List configured alerts")
    p_rst = sub.add_parser("reset", help="Reset a fired alert id (or 'all')")
    p_rst.add_argument("id")

    args = parser.parse_args(argv)
    base = Path.cwd()
    cfg = fx.load_config(base)
    alerts_file = fx.work_dir(base) / "alerts.json"
    state_file = fx.state_dir(base) / "alerts.json"

    try:
        if args.cmd == "clock":
            st = cmd_clock(fx.parse_now_utc(args.now))
            if args.json:
                print(json.dumps(st, indent=2))
            else:
                sess = ", ".join(s.replace("_", " ").title() for s in st["active_sessions"]) or "None"
                ov = " [LONDON-NY OVERLAP]" if st["overlap"] else ""
                print(f"UTC {st['utc']} | NY {st['ny_time']} -> {st['status']}")
                print(f"Active sessions: {sess}{ov}")
            return 0 if st["open"] else 1

        if args.cmd == "quote":
            q = fx.fetch_quote(args.symbol, offline=args.offline, cfg=cfg)
            if args.write:
                prices = fx.read_json(fx.work_dir(base) / "prices.json") or {}
                prices[q["symbol"]] = q
                fx.write_json(fx.work_dir(base) / "prices.json", prices)
            if args.json:
                print(json.dumps(q, indent=2))
            else:
                d = q["digits"]
                sp = f" | spread {q['spread_pips']} pips" if q.get("spread_pips") is not None else ""
                pct = f" ({q['pct_change']:+.2f}%)" if q.get("pct_change") is not None else ""
                print(f"{q['symbol']}: bid {fx.fmt_price(q['bid'], d)} / ask {fx.fmt_price(q['ask'], d)}{sp}{pct} [{q['source']}]")
            return 0

        if args.cmd == "add":
            rules: list[dict[str, Any]] = fx.read_json(alerts_file) or []
            added: list[dict[str, Any]] = []
            if args.from_plan:
                plan = fx.read_json(fx.work_dir(base) / "plan.json")
                if not plan:
                    raise fx.FxError("fx_trader/plan.json not found; run fx-exit first")
                sym = plan["symbol"]
                side = plan["side"]
                added.append({"id": f"{sym.lower()}-plan-stop", "type": "stop", "symbol": sym, "side": side, "level": plan["stop"]})
                added.append({"id": f"{sym.lower()}-plan-target", "type": "target", "symbol": sym, "side": side, "level": plan["target"]})
            elif args.session:
                added.append({"id": f"session-{args.session}", "type": "session", "session": args.session})
            elif args.at:
                added.append({"id": f"time-{args.at.replace(':', '')}", "type": "time", "at_utc": args.at})
            elif args.symbol:
                sym = fx.canonical_symbol(args.symbol)
                if args.above is not None:
                    added.append({"id": f"{sym.lower()}-above-{args.above}", "type": "above", "symbol": sym, "level": args.above})
                if args.below is not None:
                    added.append({"id": f"{sym.lower()}-below-{args.below}", "type": "below", "symbol": sym, "level": args.below})
                if args.pct is not None:
                    added.append({"id": f"{sym.lower()}-pct-{args.pct}", "type": "pct", "symbol": sym, "pct": args.pct})
                if args.max_spread is not None:
                    added.append({"id": f"{sym.lower()}-spread-{args.max_spread}", "type": "spread", "symbol": sym, "max_pips": args.max_spread})
            if not added:
                raise fx.FxError("specify --from-plan, --session, --at, or --symbol with --above/--below/--pct/--max-spread")
            by_id = {r["id"]: r for r in rules}
            for r in added:
                by_id[r["id"]] = r
            fx.write_json(alerts_file, list(by_id.values()))
            print(f"Added {len(added)} alert(s) -> fx_trader/alerts.json")
            return 0

        if args.cmd == "list":
            rules = fx.read_json(alerts_file) or []
            if not rules:
                print("No alerts configured.")
                return 0
            for r in rules:
                print(" ", r)
            return 0

        if args.cmd == "reset":
            st = fx.read_json(state_file) or {"fired": {}}
            if args.id == "all":
                st["fired"] = {}
            else:
                st.get("fired", {}).pop(args.id, None)
            fx.write_json(state_file, st)
            print(f"Reset {args.id}")
            return 0

        if args.cmd == "check":
            now_utc = fx.parse_now_utc(args.now)
            rules = fx.read_json(alerts_file) or []
            st = fx.read_json(state_file) or {"fired": {}}
            fired: dict[str, str] = st.get("fired", {})
            today_key = now_utc.strftime("%Y-%m-%d")
            quotes: dict[str, dict[str, Any]] = {}
            triggered: list[dict[str, str]] = []
            for r in rules:
                rid = r["id"]
                if r.get("type") == "session" and fired.get(rid) == today_key:
                    continue
                if r.get("type") != "session" and rid in fired:
                    continue
                sym = r.get("symbol")
                q: dict[str, Any] = {}
                if sym:
                    if sym not in quotes:
                        quotes[sym] = fx.fetch_quote(sym, offline=args.offline, cfg=cfg)
                    q = quotes[sym]
                hit, msg = evaluate_rule(r, q, now_utc)
                if hit:
                    fired[rid] = today_key if r.get("type") == "session" else now_utc.strftime("%Y-%m-%d %H:%M")
                    triggered.append({"id": rid, "message": msg})
            fx.write_json(state_file, {"fired": fired})
            if args.json:
                print(json.dumps({"triggered": triggered}, indent=2))
            else:
                if not triggered:
                    print("No alerts triggered.")
                for t in triggered:
                    print(f"ALERT [{t['id']}]: {t['message']}")
            return 0 if triggered else 1

    except fx.FxError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
