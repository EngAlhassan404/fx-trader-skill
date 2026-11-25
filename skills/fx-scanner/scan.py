"""FX, Gold & Oil Market Scanner.

Scans Forex pairs, Gold/Silver, and Crude Oil for:
- Daily setups (Long & Short): breakout_20d, breakdown_20d, bull_flag,
  bear_flag, reclaim_ma20, lose_ma20, oversold, overbought, oversold_bounce,
  overbought_reject.
- Session range breakouts (Long & Short) on 5m bars: asia_breakout, london,
  new_york.
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


def wilder_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = [max(0.0, closes[i] - closes[i - 1]) for i in range(1, period + 1)]
    losses = [max(0.0, closes[i - 1] - closes[i]) for i in range(1, period + 1)]
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period
    out[period] = 100.0 if avg_l == 0 else 100.0 - (100.0 / (1.0 + avg_g / avg_l))
    for i in range(period + 1, len(closes)):
        chg = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(0.0, chg)) / period
        avg_l = (avg_l * (period - 1) + max(0.0, -chg)) / period
        out[i] = 100.0 if avg_l == 0 else 100.0 - (100.0 / (1.0 + avg_g / avg_l))
    return out


def analyze_daily(sym: str, bars: list[dict[str, Any]], digits: int) -> list[dict[str, Any]]:
    """Detect Long & Short daily setups on closed daily bars."""
    if len(bars) < 22:
        return []
    closes = [b["close"] for b in bars]
    last = closes[-1]
    prev = closes[-2]
    ma20_now = sum(closes[-20:]) / 20.0
    ma20_prev = sum(closes[-21:-1]) / 20.0
    rsi_vals = wilder_rsi(closes, 14)
    rsi_now = rsi_vals[-1]
    rsi_prev = rsi_vals[-2]

    hits: list[dict[str, Any]] = []
    if last > max(closes[-21:-1]):
        hits.append({"setup": "breakout_20d", "side": "long", "level": fx.round_price(max(closes[-21:-1]), digits)})
    if last < min(closes[-21:-1]):
        hits.append({"setup": "breakdown_20d", "side": "short", "level": fx.round_price(min(closes[-21:-1]), digits)})

    # Flags: strong 10-bar impulse followed by tight 5-bar consolidation (<= 5% range)
    if len(closes) >= 16:
        imp_start = closes[-16]
        imp_end = closes[-6]
        consol = closes[-5:]
        c_range_pct = ((max(consol) - min(consol)) / max(consol)) * 100.0 if max(consol) > 0 else 999.0
        imp_pct = ((imp_end / imp_start) - 1.0) * 100.0 if imp_start > 0 else 0.0
        if imp_pct >= 2.0 and c_range_pct <= 2.5:
            hits.append({"setup": "bull_flag", "side": "long", "level": fx.round_price(max(consol), digits)})
        elif imp_pct <= -2.0 and c_range_pct <= 2.5:
            hits.append({"setup": "bear_flag", "side": "short", "level": fx.round_price(min(consol), digits)})

    if prev < ma20_prev and last > ma20_now:
        hits.append({"setup": "reclaim_ma20", "side": "long", "level": fx.round_price(ma20_now, digits)})
    if prev > ma20_prev and last < ma20_now:
        hits.append({"setup": "lose_ma20", "side": "short", "level": fx.round_price(ma20_now, digits)})

    if rsi_now is not None:
        if rsi_now < 30.0:
            hits.append({"setup": "oversold", "side": "long", "rsi": round(rsi_now, 1)})
        if rsi_now > 70.0:
            hits.append({"setup": "overbought", "side": "short", "rsi": round(rsi_now, 1)})
        if rsi_prev is not None and rsi_prev < 30.0 and last > prev:
            hits.append({"setup": "oversold_bounce", "side": "long", "rsi": round(rsi_now, 1)})
        if rsi_prev is not None and rsi_prev > 70.0 and last < prev:
            hits.append({"setup": "overbought_reject", "side": "short", "rsi": round(rsi_now, 1)})

    return hits


def analyze_session_breakout(
    sym: str,
    bars: list[dict[str, Any]],
    mode: str,
    now_utc: _dt.datetime,
    digits: int,
    pip_size: float,
) -> dict[str, Any] | None:
    """Detect Long or Short breakout of an Asia/London/NY opening range on 5m bars."""
    if mode not in fx.SESSION_OR_WINDOWS_UTC:
        raise fx.FxError(f"unknown session mode {mode!r}; use asia_breakout, london, or new_york")
    rs_str, re_str, _ = fx.SESSION_OR_WINDOWS_UTC[mode]
    today_str = now_utc.strftime("%Y-%m-%d")
    rs_dt = _dt.datetime.strptime(f"{today_str} {rs_str}", "%Y-%m-%d %H:%M").replace(tzinfo=fx.UTC_TZ)
    re_dt = _dt.datetime.strptime(f"{today_str} {re_str}", "%Y-%m-%d %H:%M").replace(tzinfo=fx.UTC_TZ)
    rs_ts, re_ts = int(rs_dt.timestamp()), int(re_dt.timestamp())

    range_bars = [b for b in bars if rs_ts <= b["ts"] < re_ts]
    post_bars = [b for b in bars if b["ts"] >= re_ts]
    if not range_bars or not post_bars:
        return None

    or_high = max(b["high"] for b in range_bars)
    or_low = min(b["low"] for b in range_bars)
    for b in post_bars:
        if b["close"] > or_high:
            dist_pips = round((b["close"] - or_high) / pip_size, 1)
            return {
                "symbol": sym,
                "mode": mode,
                "side": "long",
                "price": fx.round_price(b["close"], digits),
                "range_high": fx.round_price(or_high, digits),
                "range_low": fx.round_price(or_low, digits),
                "breakout_pips": dist_pips,
                "trigger_time_utc": b["time_utc"],
            }
        if b["close"] < or_low:
            dist_pips = round((or_low - b["close"]) / pip_size, 1)
            return {
                "symbol": sym,
                "mode": mode,
                "side": "short",
                "price": fx.round_price(b["close"], digits),
                "range_high": fx.round_price(or_high, digits),
                "range_low": fx.round_price(or_low, digits),
                "breakout_pips": dist_pips,
                "trigger_time_utc": b["time_utc"],
            }
    return None


def cmd_universe(base: Path | None, cfg: dict[str, Any]) -> list[dict[str, str]]:
    """Build Forex, Gold/Metals, and Oil universe (MT5 Forex+Metals + curated benchmarks)."""
    seen: dict[str, dict[str, str]] = {item["symbol"]: dict(item) for item in fx.DEFAULT_UNIVERSE}
    mt5 = fx._try_mt5_module()
    if cfg.get("data_source", "auto") != "yahoo" and mt5 is not None and mt5.initialize():
        try:
            for s in mt5.symbols_get() or []:
                path_u = (getattr(s, "path", "") or "").upper()
                if path_u.startswith("FOREX\\") or path_u.startswith("METALS\\"):
                    c = fx.canonical_symbol(s.name)
                    if c not in seen:
                        cat = "metal" if path_u.startswith("METALS\\") else "forex"
                        seen[c] = {
                            "symbol": c,
                            "category": cat,
                            "yahoo": fx.to_yahoo_symbol(c),
                            "mt5": s.name,
                            "name": getattr(s, "description", "") or c,
                        }
        finally:
            mt5.shutdown()

    items = list(seen.values())
    lines = [f"{it['symbol']}|{it['category']}|{it['name']}" for it in items]
    u_path = fx.work_dir(base) / "universe.txt"
    u_path.parent.mkdir(parents=True, exist_ok=True)
    u_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return items


def resolve_symbols(args_symbols: str | None, base: Path | None) -> list[str]:
    if args_symbols:
        return [fx.canonical_symbol(s) for s in args_symbols.split(",") if s.strip()]
    return [item["symbol"] for item in fx.DEFAULT_UNIVERSE]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan Forex, Gold, and Oil setups.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("universe", help="Build Forex, Metals, and Oil symbol universe")

    p_daily = sub.add_parser("daily", help="Scan daily closes for Long & Short setups")
    p_daily.add_argument("--symbols", help="Comma-separated symbols (default: curated 18 FX/Gold/Oil)")
    p_daily.add_argument("--offline", help="Directory or JSON fixture")
    p_daily.add_argument("--no-write", action="store_true")
    p_daily.add_argument("--json", action="store_true")

    p_sess = sub.add_parser("session", help="Scan Asia/London/NY session breakouts (5m bars)")
    p_sess.add_argument("--mode", default="london", choices=list(fx.SESSION_OR_WINDOWS_UTC.keys()))
    p_sess.add_argument("--symbols", help="Comma-separated symbols")
    p_sess.add_argument("--now", help="UTC timestamp 'YYYY-MM-DD HH:MM'")
    p_sess.add_argument("--offline", help="Directory or JSON fixture")
    p_sess.add_argument("--no-write", action="store_true")
    p_sess.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    base = Path.cwd()
    cfg = fx.load_config(base)

    try:
        if args.cmd == "universe":
            items = cmd_universe(base, cfg)
            print(f"Universe built: {len(items)} instruments -> fx_trader/universe.txt")
            return 0

        syms = resolve_symbols(args.symbols, base)
        hits: list[dict[str, Any]] = []
        failed: list[str] = []

        if args.cmd == "daily":
            for sym in syms:
                try:
                    spec = fx.default_spec(sym) if args.offline else fx.get_symbol_spec(sym, cfg)
                    data = fx.fetch_bars(sym, interval="1d", rng="3mo", count=90, offline=args.offline, cfg=cfg)
                    found = analyze_daily(sym, data["bars"], spec["digits"])
                    for f in found:
                        hits.append({
                            "symbol": sym,
                            "category": spec["category"],
                            "price": fx.round_price(data["bars"][-1]["close"], spec["digits"]),
                            "digits": spec["digits"],
                            "source": data["source"],
                            **f,
                        })
                except Exception as exc:
                    failed.append(f"{sym}: {exc}")

            out = {"mode": "daily", "as_of_utc": fx.parse_now_utc().strftime("%Y-%m-%d %H:%M"), "scanned": len(syms), "failed": failed, "hits": hits}
            if not args.no_write:
                fx.write_json(fx.work_dir(base) / "watchlist.json", out)
            if args.json:
                print(json.dumps(out, indent=2))
            else:
                if not hits:
                    print(f"No daily setups across {len(syms)} symbols.")
                    return 1
                print(f"Daily scan ({len(hits)} hits across {len(syms)} symbols):")
                for h in hits:
                    print(f"  {h['symbol']:<8} {h['side'].upper():<5} {h['setup']:<18} price {fx.fmt_price(h['price'], h['digits'])} ({h['source']})")
            return 0 if hits else 1

        if args.cmd == "session":
            now_utc = fx.parse_now_utc(args.now)
            for sym in syms:
                try:
                    spec = fx.default_spec(sym) if args.offline else fx.get_symbol_spec(sym, cfg)
                    data = fx.fetch_bars(sym, interval="5m", rng="5d", count=400, offline=args.offline, as_of_utc=now_utc if args.offline else None, cfg=cfg)
                    hit = analyze_session_breakout(sym, data["bars"], args.mode, now_utc, spec["digits"], spec["pip_size"])
                    if hit:
                        hit["category"] = spec["category"]
                        hit["digits"] = spec["digits"]
                        hit["source"] = data["source"]
                        hits.append(hit)
                except Exception as exc:
                    failed.append(f"{sym}: {exc}")

            out = {"mode": args.mode, "as_of_utc": now_utc.strftime("%Y-%m-%d %H:%M"), "scanned": len(syms), "failed": failed, "hits": hits}
            if not args.no_write:
                fx.write_json(fx.work_dir(base) / "watchlist.json", out)
            if args.json:
                print(json.dumps(out, indent=2))
            else:
                if not hits:
                    print(f"No {args.mode} session breakouts across {len(syms)} symbols as of {out['as_of_utc']} UTC.")
                    return 1
                print(f"Session breakout scan ({args.mode}, {len(hits)} hits):")
                for h in hits:
                    d = h["digits"]
                    print(
                        f"  {h['symbol']:<8} {h['side'].upper():<5} {fx.fmt_price(h['price'], d)} "
                        f"(range {fx.fmt_price(h['range_low'], d)}-{fx.fmt_price(h['range_high'], d)}, +{h['breakout_pips']} pips at {h['trigger_time_utc']} UTC)"
                    )
            return 0 if hits else 1

    except fx.FxError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
