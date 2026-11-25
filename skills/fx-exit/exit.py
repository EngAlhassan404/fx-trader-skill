"""Pip-accurate Long/Short Exit Planner for Forex, Gold & Oil."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import fx_core as fx  # noqa: E402


def compute_atr(bars: list[dict[str, Any]], period: int = 14) -> float:
    if len(bars) < 2:
        raise fx.FxError("need at least 2 bars to compute ATR")
    trs: list[float] = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    window = trs[-period:]
    return sum(window) / len(window)


def build_plan(
    sym: str,
    side: str,
    entry: float,
    spec: dict[str, Any],
    stop_spec: str = "range-mid",
    target_spec: str = "2R",
    range_high: float | None = None,
    range_low: float | None = None,
    entry_time_utc: str | None = None,
    setup: str = "manual",
    atr_value: float | None = None,
    flat_by_utc: str | None = None,
) -> dict[str, Any]:
    side_l = side.lower()
    if side_l not in ("long", "short"):
        raise fx.FxError(f"side must be 'long' or 'short', got {side!r}")

    digits = int(spec["digits"])
    pip_size = float(spec["pip_size"])
    entry_r = fx.round_price(entry, digits)

    # Resolve stop
    s_low = stop_spec.strip().lower()
    if s_low == "range-mid":
        if range_high is None or range_low is None:
            raise fx.FxError("range-mid stop requires range_high and range_low (or use --stop pips:X / price:X / atr:K)")
        raw_stop = (range_high + range_low) / 2.0
    elif s_low == "range-edge":
        if range_high is None or range_low is None:
            raise fx.FxError("range-edge stop requires range_high and range_low")
        raw_stop = range_low if side_l == "long" else range_high
    elif s_low.startswith("price:"):
        raw_stop = float(s_low.split(":", 1)[1])
    elif s_low.startswith("pips:"):
        pips = float(s_low.split(":", 1)[1])
        raw_stop = entry_r - pips * pip_size if side_l == "long" else entry_r + pips * pip_size
    elif s_low.startswith("pct:"):
        pct = float(s_low.split(":", 1)[1]) / 100.0
        raw_stop = entry_r * (1.0 - pct) if side_l == "long" else entry_r * (1.0 + pct)
    elif s_low.startswith("atr:"):
        k = float(s_low.split(":", 1)[1])
        if atr_value is None:
            raise fx.FxError("atr stop requires bar history")
        raw_stop = entry_r - k * atr_value if side_l == "long" else entry_r + k * atr_value
    else:
        raise fx.FxError(f"unsupported --stop {stop_spec!r}")

    # Round stop AWAY from entry
    stop_r = fx.round_price(raw_stop, digits, mode="down" if side_l == "long" else "up")
    if side_l == "long" and stop_r >= entry_r:
        raise fx.FxError(f"long stop {stop_r} must be strictly below entry {entry_r}")
    if side_l == "short" and stop_r <= entry_r:
        raise fx.FxError(f"short stop {stop_r} must be strictly above entry {entry_r}")

    risk_price = abs(entry_r - stop_r)
    risk_pips = round(risk_price / pip_size, 2)
    if risk_pips < 1.0:
        raise fx.FxError(f"stop too tight ({risk_pips} pips < 1.0 pip minimum); inside spread noise")

    # Resolve target
    t_low = target_spec.strip().lower()
    if t_low.endswith("r"):
        r_mult = float(t_low[:-1])
        raw_target = entry_r + r_mult * risk_price if side_l == "long" else entry_r - r_mult * risk_price
    elif t_low.startswith("price:"):
        raw_target = float(t_low.split(":", 1)[1])
    elif t_low.startswith("pips:"):
        tp_pips = float(t_low.split(":", 1)[1])
        raw_target = entry_r + tp_pips * pip_size if side_l == "long" else entry_r - tp_pips * pip_size
    else:
        raise fx.FxError(f"unsupported --target {target_spec!r}")

    target_r = fx.round_price(raw_target, digits, mode="nearest")
    if side_l == "long" and target_r <= entry_r:
        raise fx.FxError(f"long target {target_r} must be strictly above entry {entry_r}")
    if side_l == "short" and target_r >= entry_r:
        raise fx.FxError(f"short target {target_r} must be strictly below entry {entry_r}")

    reward_price = abs(target_r - entry_r)
    reward_pips = round(reward_price / pip_size, 2)
    rr = round(reward_price / risk_price, 2)

    return {
        "symbol": fx.canonical_symbol(sym),
        "category": spec["category"],
        "side": side_l,
        "setup": setup,
        "entry": entry_r,
        "entry_time_utc": entry_time_utc or _dt.datetime.now(fx.UTC_TZ).strftime("%Y-%m-%d %H:%M"),
        "stop": stop_r,
        "stop_rule": stop_spec,
        "target": target_r,
        "target_rule": target_spec,
        "risk_pips": risk_pips,
        "reward_pips": reward_pips,
        "reward_risk": rr,
        "digits": digits,
        "pip_size": pip_size,
        "range_high": range_high,
        "range_low": range_low,
        "flat_by_utc": flat_by_utc,
        "spread_pips": spec.get("spread_pips"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Long/Short Exit Planner for Forex, Gold & Oil.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="Create stop & target plan")
    p_plan.add_argument("--symbol")
    p_plan.add_argument("--side", choices=["long", "short"])
    p_plan.add_argument("--entry", type=float)
    p_plan.add_argument("--range-high", type=float)
    p_plan.add_argument("--range-low", type=float)
    p_plan.add_argument("--stop", default="range-mid")
    p_plan.add_argument("--target", default="2R")
    p_plan.add_argument("--flat-by-utc", default=None)
    p_plan.add_argument("--offline", help="Offline fixture for ATR stop")
    p_plan.add_argument("--write", action="store_true")
    p_plan.add_argument("--json", action="store_true")

    sub.add_parser("show", help="Display current fx_trader/plan.json")

    args = parser.parse_args(argv)
    base = Path.cwd()
    cfg = fx.load_config(base)

    try:
        if args.cmd == "show":
            plan = fx.read_json(fx.work_dir(base) / "plan.json")
            if not plan:
                raise fx.FxError("fx_trader/plan.json not found")
            print(json.dumps(plan, indent=2))
            return 0

        entry_data = fx.read_json(fx.work_dir(base) / "entry.json") or {}
        sym = fx.canonical_symbol(args.symbol or entry_data.get("symbol", ""))
        if not sym:
            raise fx.FxError("provide --symbol or run fx-entry --write first")
        side = args.side or entry_data.get("side")
        entry_px = args.entry if args.entry is not None else entry_data.get("entry")
        if not side or entry_px is None:
            raise fx.FxError("need --side and --entry (or a triggered fx_trader/entry.json)")

        spec = fx.default_spec(sym) if args.offline else fx.get_symbol_spec(sym, cfg)
        atr_val = None
        if args.stop.lower().startswith("atr:"):
            bars_data = fx.fetch_bars(sym, interval="5m", rng="5d", count=100, offline=args.offline, cfg=cfg)
            atr_val = compute_atr(bars_data["bars"], 14)

        r_high = args.range_high if args.range_high is not None else entry_data.get("range_high")
        r_low = args.range_low if args.range_low is not None else entry_data.get("range_low")
        stop_rule = args.stop
        if stop_rule == "range-mid" and (r_high is None or r_low is None):
            raise fx.FxError("no opening range in entry.json; specify --stop pips:X, price:X, or atr:K")

        plan = build_plan(
            sym=sym, side=side, entry=float(entry_px), spec=spec,
            stop_spec=stop_rule, target_spec=args.target,
            range_high=r_high, range_low=r_low,
            entry_time_utc=entry_data.get("time_utc"),
            setup=entry_data.get("setup", "manual"),
            atr_value=atr_val,
            flat_by_utc=args.flat_by_utc if args.flat_by_utc is not None else cfg.get("flat_by_utc"),
        )
        if args.write:
            fx.write_json(fx.work_dir(base) / "plan.json", plan)
        if args.json:
            print(json.dumps(plan, indent=2))
            return 0

        d = plan["digits"]
        print(f"Exit Plan: {plan['symbol']} {plan['side'].upper()} ({plan['setup']})")
        print(f"  Entry   {fx.fmt_price(plan['entry'], d)} ({plan['entry_time_utc']} UTC)")
        print(f"  Stop    {fx.fmt_price(plan['stop'], d)} ({plan['stop_rule']}, risk {plan['risk_pips']} pips)")
        print(f"  Target  {fx.fmt_price(plan['target'], d)} ({plan['target_rule']}, reward {plan['reward_pips']} pips)")
        print(f"  R:R     1 : {plan['reward_risk']}")
        return 0
    except fx.FxError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
