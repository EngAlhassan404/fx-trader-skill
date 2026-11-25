"""Forex, Gold & Oil Long/Short Entry Timer on closed 1m/5m/15m bars."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import fx_core as fx  # noqa: E402


def check_entry(
    sym: str,
    bars: list[dict[str, Any]],
    spec: dict[str, Any],
    setup: str = "london",
    side: str = "both",
    level: float | None = None,
    now_utc: _dt.datetime | None = None,
) -> dict[str, Any]:
    now = now_utc or _dt.datetime.now(fx.UTC_TZ)
    digits = int(spec["digits"])
    pip_size = float(spec["pip_size"])

    if not bars:
        return {"symbol": sym, "status": "no_data", "setup": setup}

    if setup == "level":
        if level is None:
            raise fx.FxError("--setup level requires --level PRICE")
        if side not in ("long", "short"):
            raise fx.FxError("--setup level requires --side long or --side short")
        # Check the most recent closed bars from today UTC
        today_str = now.strftime("%Y-%m-%d")
        today_ts = int(_dt.datetime.strptime(today_str, "%Y-%m-%d").replace(tzinfo=fx.UTC_TZ).timestamp())
        post = [b for b in bars if b["ts"] >= today_ts] or bars[-20:]
        for b in post:
            if side == "long" and b["close"] > level:
                return {
                    "symbol": sym, "category": spec["category"], "setup": "level", "side": "long",
                    "status": "triggered", "entry": fx.round_price(b["close"], digits),
                    "level": fx.round_price(level, digits), "time_utc": b["time_utc"],
                    "digits": digits, "pip_size": pip_size, "spread_pips": spec.get("spread_pips"),
                }
            if side == "short" and b["close"] < level:
                return {
                    "symbol": sym, "category": spec["category"], "setup": "level", "side": "short",
                    "status": "triggered", "entry": fx.round_price(b["close"], digits),
                    "level": fx.round_price(level, digits), "time_utc": b["time_utc"],
                    "digits": digits, "pip_size": pip_size, "spread_pips": spec.get("spread_pips"),
                }
        last = bars[-1]
        dist_pips = round(abs(level - last["close"]) / pip_size, 1)
        return {
            "symbol": sym, "category": spec["category"], "setup": "level", "side": side,
            "status": "waiting", "last_close": fx.round_price(last["close"], digits),
            "level": fx.round_price(level, digits), "distance_pips": dist_pips,
            "time_utc": last["time_utc"], "digits": digits, "pip_size": pip_size,
        }

    if setup not in fx.SESSION_OR_WINDOWS_UTC:
        raise fx.FxError(f"unknown setup {setup!r}; use asia_breakout, london, new_york, or level")

    rs_str, re_str, _ = fx.SESSION_OR_WINDOWS_UTC[setup]
    today_str = now.strftime("%Y-%m-%d")
    rs_ts = int(_dt.datetime.strptime(f"{today_str} {rs_str}", "%Y-%m-%d %H:%M").replace(tzinfo=fx.UTC_TZ).timestamp())
    re_ts = int(_dt.datetime.strptime(f"{today_str} {re_str}", "%Y-%m-%d %H:%M").replace(tzinfo=fx.UTC_TZ).timestamp())

    range_bars = [b for b in bars if rs_ts <= b["ts"] < re_ts]
    if not range_bars:
        return {
            "symbol": sym, "category": spec["category"], "setup": setup,
            "status": "forming", "message": f"waiting for {setup} range ({rs_str}-{re_str} UTC) to complete",
            "digits": digits, "pip_size": pip_size,
        }
    or_high = fx.round_price(max(b["high"] for b in range_bars), digits)
    or_low = fx.round_price(min(b["low"] for b in range_bars), digits)
    post_bars = [b for b in bars if b["ts"] >= re_ts]

    for b in post_bars:
        if side in ("both", "long") and b["close"] > or_high:
            return {
                "symbol": sym, "category": spec["category"], "setup": setup, "side": "long",
                "status": "triggered", "entry": fx.round_price(b["close"], digits),
                "range_high": or_high, "range_low": or_low, "time_utc": b["time_utc"],
                "digits": digits, "pip_size": pip_size, "spread_pips": spec.get("spread_pips"),
            }
        if side in ("both", "short") and b["close"] < or_low:
            return {
                "symbol": sym, "category": spec["category"], "setup": setup, "side": "short",
                "status": "triggered", "entry": fx.round_price(b["close"], digits),
                "range_high": or_high, "range_low": or_low, "time_utc": b["time_utc"],
                "digits": digits, "pip_size": pip_size, "spread_pips": spec.get("spread_pips"),
            }

    last = post_bars[-1] if post_bars else range_bars[-1]
    return {
        "symbol": sym, "category": spec["category"], "setup": setup, "side": side,
        "status": "waiting", "last_close": fx.round_price(last["close"], digits),
        "range_high": or_high, "range_low": or_low,
        "to_high_pips": round((or_high - last["close"]) / pip_size, 1),
        "to_low_pips": round((last["close"] - or_low) / pip_size, 1),
        "time_utc": last["time_utc"], "digits": digits, "pip_size": pip_size,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Long/Short Entry Timer for Forex, Gold & Oil.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_chk = sub.add_parser("check", help="Check symbol for confirmed closed-candle trigger")
    p_chk.add_argument("symbol")
    p_chk.add_argument("--setup", default="london", choices=["asia_breakout", "london", "new_york", "level"])
    p_chk.add_argument("--side", default="both", choices=["both", "long", "short"])
    p_chk.add_argument("--level", type=float)
    p_chk.add_argument("--interval", default="5m", choices=["1m", "5m", "15m"])
    p_chk.add_argument("--now", help="UTC timestamp 'YYYY-MM-DD HH:MM'")
    p_chk.add_argument("--offline", help="Offline fixture file or dir")
    p_chk.add_argument("--write", action="store_true", help="Write fx_trader/entry.json")
    p_chk.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    base = Path.cwd()
    cfg = fx.load_config(base)

    try:
        sym = fx.canonical_symbol(args.symbol)
        now_utc = fx.parse_now_utc(args.now)
        spec = fx.default_spec(sym) if args.offline else fx.get_symbol_spec(sym, cfg)
        data = fx.fetch_bars(sym, interval=args.interval, rng="5d", count=500, offline=args.offline, as_of_utc=now_utc if args.offline else None, cfg=cfg)
        res = check_entry(sym, data["bars"], spec, setup=args.setup, side=args.side, level=args.level, now_utc=now_utc)
        res["source"] = data["source"]
        if args.write:
            fx.write_json(fx.work_dir(base) / "entry.json", res)
        if args.json:
            print(json.dumps(res, indent=2))
            return 0 if res["status"] == "triggered" else 1

        d = res.get("digits", spec["digits"])
        if res["status"] == "triggered":
            print(f"TRIGGERED {sym} {res['side'].upper()} at {fx.fmt_price(res['entry'], d)} ({res['time_utc']} UTC, {res['setup']}, source={res['source']})")
            return 0
        if res["status"] == "waiting":
            if res["setup"] == "level":
                print(f"WAITING {sym} ({res['side']}): close {fx.fmt_price(res['last_close'], d)}, {res['distance_pips']} pips from level {fx.fmt_price(res['level'], d)}")
            else:
                print(
                    f"WAITING {sym} ({res['setup']}): close {fx.fmt_price(res['last_close'], d)} "
                    f"inside {fx.fmt_price(res['range_low'], d)}-{fx.fmt_price(res['range_high'], d)} "
                    f"(+{res['to_high_pips']}p to high / -{res['to_low_pips']}p to low)"
                )
            return 1
        print(f"{res['status'].upper()} {sym}: {res.get('message', '')}")
        return 1
    except fx.FxError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
