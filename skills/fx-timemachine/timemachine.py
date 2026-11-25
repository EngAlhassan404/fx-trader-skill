"""Forex, Gold & Oil Time Machine: 10,000 Monte Carlo Session Replays + Historical Backtest."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import fx_core as fx  # noqa: E402


def build_intraday_pool(bars: list[dict[str, Any]], as_of_date: str | None = None) -> dict[int, list[tuple[float, float, float, float]]]:
    """Group empirical 5-minute bar ratios by minute-of-day UTC (0..1435)."""
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        day = b["time_utc"][:10]
        if as_of_date and day >= as_of_date:
            continue
        by_day[day].append(b)

    pool: dict[int, list[tuple[float, float, float, float]]] = defaultdict(list)
    for day_bars in by_day.values():
        day_bars.sort(key=lambda x: x["ts"])
        for i in range(1, len(day_bars)):
            prev_c = day_bars[i - 1]["close"]
            cur = day_bars[i]
            if prev_c <= 0 or (cur["ts"] - day_bars[i - 1]["ts"]) != 300:
                continue
            dt = _dt.datetime.fromtimestamp(cur["ts"], fx.UTC_TZ)
            slot = dt.hour * 60 + dt.minute
            pool[slot].append((
                cur["open"] / prev_c,
                cur["high"] / prev_c,
                cur["low"] / prev_c,
                cur["close"] / prev_c,
            ))
    return pool


def run_monte_carlo(
    side: str,
    entry: float,
    stop: float,
    target: float,
    entry_slot_utc: int,
    horizon_bars: int,
    pool: dict[int, list[tuple[float, float, float, float]]],
    replays: int = 10000,
    seed: int = 19,
) -> dict[str, Any]:
    """Simulate ``replays`` paths forward for Long or Short with conservative stop-first tie break."""
    all_ratios = [r for lst in pool.values() for r in lst]
    if len(all_ratios) < 50:
        raise fx.FxError("need at least 50 historical 5m bar ratios to run Monte Carlo replay")

    rng = random.Random(seed)
    risk = abs(entry - stop)
    target_first = 0
    stop_first = 0
    neither = 0
    r_outcomes: list[float] = []
    close_prices: list[float] = []

    for _ in range(replays):
        cur = entry
        hit = None
        for step in range(horizon_bars):
            slot = (entry_slot_utc + step * 5) % 1440
            candidates = pool.get(slot) or all_ratios
            o_r, h_r, l_r, c_r = candidates[rng.randrange(len(candidates))]
            hi = cur * h_r
            lo = cur * l_r
            cl = cur * c_r
            if side == "long":
                if lo <= stop:
                    hit = "stop"
                    stop_first += 1
                    r_outcomes.append(-1.0)
                    close_prices.append(stop)
                    break
                if hi >= target:
                    hit = "target"
                    target_first += 1
                    r_outcomes.append(abs(target - entry) / risk)
                    close_prices.append(target)
                    break
            else:
                if hi >= stop:
                    hit = "stop"
                    stop_first += 1
                    r_outcomes.append(-1.0)
                    close_prices.append(stop)
                    break
                if lo <= target:
                    hit = "target"
                    target_first += 1
                    r_outcomes.append(abs(entry - target) / risk)
                    close_prices.append(target)
                    break
            cur = cl
        if hit is None:
            neither += 1
            pnl = (cur - entry) if side == "long" else (entry - cur)
            r_outcomes.append(pnl / risk)
            close_prices.append(cur)

    decided = target_first + stop_first
    win_decided_pct = round(100.0 * target_first / decided, 1) if decided else 0.0
    breakeven_pct = round(100.0 * risk / (risk + abs(target - entry)), 1)
    avg_r = round(sum(r_outcomes) / len(r_outcomes), 3)
    if decided < replays * 0.05:
        verdict = "mostly unresolved within horizon"
    elif avg_r >= 0.15:
        verdict = "clear positive edge"
    elif avg_r <= -0.10:
        verdict = "negative expectancy"
    else:
        verdict = "close to a coin flip"

    return {
        "replays": replays,
        "seed": seed,
        "horizon_bars": horizon_bars,
        "target_first_pct": round(100.0 * target_first / replays, 1),
        "stop_first_pct": round(100.0 * stop_first / replays, 1),
        "neither_pct": round(100.0 * neither / replays, 1),
        "win_of_decided_pct": win_decided_pct,
        "breakeven_pct": breakeven_pct,
        "avg_r": avg_r,
        "verdict": verdict,
    }


def run_historical_session_check(
    bars: list[dict[str, Any]],
    setup: str,
    side: str,
    target_r: float,
    stop_rule: str,
    horizon_bars: int,
) -> dict[str, Any] | None:
    """Re-run session range breakout rule over past days in the 60d dataset."""
    if setup not in fx.SESSION_OR_WINDOWS_UTC:
        return None
    rs_str, re_str, _ = fx.SESSION_OR_WINDOWS_UTC[setup]
    rs_h, rs_m = map(int, rs_str.split(":"))
    re_h, re_m = map(int, re_str.split(":"))
    rs_slot, re_slot = rs_h * 60 + rs_m, re_h * 60 + re_m

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        by_day[b["time_utc"][:10]].append(b)

    fired = wins = losses = open_end = 0
    for day, dbars in sorted(by_day.items()):
        dbars.sort(key=lambda x: x["ts"])
        rbars = [b for b in dbars if rs_slot <= (_dt.datetime.fromtimestamp(b["ts"], fx.UTC_TZ).hour * 60 + _dt.datetime.fromtimestamp(b["ts"], fx.UTC_TZ).minute) < re_slot]
        pbars = [b for b in dbars if (_dt.datetime.fromtimestamp(b["ts"], fx.UTC_TZ).hour * 60 + _dt.datetime.fromtimestamp(b["ts"], fx.UTC_TZ).minute) >= re_slot]
        if not rbars or not pbars:
            continue
        hi, lo = max(b["high"] for b in rbars), min(b["low"] for b in rbars)
        trig_idx = None
        for idx, b in enumerate(pbars):
            if (side == "long" and b["close"] > hi) or (side == "short" and b["close"] < lo):
                trig_idx = idx
                break
        if trig_idx is None:
            continue
        fired += 1
        ent = pbars[trig_idx]["close"]
        stp = lo if (stop_rule == "range-edge" and side == "long") else (hi if (stop_rule == "range-edge" and side == "short") else (hi + lo) / 2.0)
        risk = abs(ent - stp)
        if risk <= 0:
            continue
        tgt = ent + target_r * risk if side == "long" else ent - target_r * risk
        outcome = "open"
        for fb in pbars[trig_idx + 1: trig_idx + 1 + horizon_bars]:
            if side == "long":
                if fb["low"] <= stp:
                    outcome = "loss"; break
                if fb["high"] >= tgt:
                    outcome = "win"; break
            else:
                if fb["high"] >= stp:
                    outcome = "loss"; break
                if fb["low"] <= tgt:
                    outcome = "win"; break
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        else:
            open_end += 1
    return {"sessions_checked": len(by_day), "fired": fired, "target_first": wins, "stop_first": losses, "neither": open_end}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="10,000-replay Time Machine for Forex, Gold & Oil.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="Run Monte Carlo + historical session replay")
    p_run.add_argument("--symbol")
    p_run.add_argument("--side", choices=["long", "short"])
    p_run.add_argument("--entry", type=float)
    p_run.add_argument("--stop", type=float)
    p_run.add_argument("--target", type=float)
    p_run.add_argument("--hours", type=float, default=6.0, help="Forward replay horizon in hours (default 6h)")
    p_run.add_argument("--replays", type=int, default=10000)
    p_run.add_argument("--seed", type=int, default=19)
    p_run.add_argument("--offline", help="Offline 60d 5m fixture JSON")
    p_run.add_argument("--write", action="store_true")
    p_run.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    base = Path.cwd()
    cfg = fx.load_config(base)

    try:
        plan = fx.read_json(fx.work_dir(base) / "plan.json") or {}
        sym = fx.canonical_symbol(args.symbol or plan.get("symbol", ""))
        side = args.side or plan.get("side")
        entry = args.entry if args.entry is not None else plan.get("entry")
        stop = args.stop if args.stop is not None else plan.get("stop")
        target = args.target if args.target is not None else plan.get("target")
        if not sym or not side or None in (entry, stop, target):
            raise fx.FxError("need fx_trader/plan.json or --symbol, --side, --entry, --stop, --target")

        # Yahoo 60d 5m holds up to ~17,000 bars; MT5 copy_rates up to 15,000 bars
        data = fx.fetch_bars(sym, interval="5m", rng="60d", count=15000, offline=args.offline, cfg=cfg)
        et = plan.get("entry_time_utc")
        slot = 13 * 60 + 30
        as_of_date = None
        if et and len(et) >= 16:
            as_of_date = et[:10]
            hh, mm = map(int, et[11:16].split(":"))
            slot = hh * 60 + mm

        pool = build_intraday_pool(data["bars"], as_of_date=as_of_date)
        horizon_bars = max(6, int(round(args.hours * 12)))
        mc = run_monte_carlo(side, float(entry), float(stop), float(target), slot, horizon_bars, pool, replays=args.replays, seed=args.seed)

        rr_val = abs(float(target) - float(entry)) / abs(float(entry) - float(stop))
        hist = run_historical_session_check(data["bars"], plan.get("setup", "london"), side, rr_val, plan.get("stop_rule", "range-mid"), horizon_bars)

        out = {"symbol": sym, "side": side, "entry": entry, "stop": stop, "target": target, "source": data["source"], "mc": mc, "history": hist}
        if args.write:
            fx.write_json(fx.work_dir(base) / "timemachine.json", out)
        if args.json:
            print(json.dumps(out, indent=2))
            return 0

        print(f"Time Machine ({sym} {side.upper()}, {mc['replays']} replays, {args.hours}h horizon, seed {mc['seed']}):")
        print(f"  Target first  {mc['target_first_pct']}%  |  Stop first  {mc['stop_first_pct']}%  |  Open at end  {mc['neither_pct']}%")
        print(f"  Win of decided {mc['win_of_decided_pct']}% (breakeven {mc['breakeven_pct']}%) | Avg R: {mc['avg_r']:+0.3f}")
        print(f"  Verdict: {mc['verdict']}")
        if hist:
            print(f"  History ({plan.get('setup')}): fired {hist['fired']} / {hist['sessions_checked']} sessions -> {hist['target_first']} target, {hist['stop_first']} stop, {hist['neither']} open")
        return 0
    except fx.FxError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
