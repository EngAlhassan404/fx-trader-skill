"""Forex, Gold & Oil Lot-Size Budget Manager (MT5 Read-Only + Analytical Fallback)."""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import fx_core as fx  # noqa: E402


def estimate_margin_per_lot_usd(sym: str, price: float, spec: dict[str, Any], leverage: int) -> float:
    contract = float(spec["contract_size"])
    lev = max(1, int(leverage))
    c = fx.canonical_symbol(sym)
    if spec["category"] == "forex" and c.startswith("USD"):
        return contract / lev
    return (contract * price) / lev


def order_fingerprint(order: dict[str, Any]) -> str:
    keys = ("symbol", "side", "volume_lots", "entry", "sl", "tp")
    raw = "|".join(str(order.get(k)) for k in keys)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def size_order(
    plan: dict[str, Any],
    cfg: dict[str, Any],
    spec: dict[str, Any],
    balance_usd: float,
    leverage: int,
    now_utc: _dt.datetime | None = None,
) -> dict[str, Any]:
    sym = plan["symbol"]
    side = "buy" if plan["side"] == "long" else "sell"
    entry = float(plan["entry"])
    sl = float(plan["stop"])
    tp = float(plan["target"])
    risk_pips = float(plan["risk_pips"])

    pct_cap = balance_usd * (float(cfg["risk_per_trade_pct"]) / 100.0)
    usd_cap = float(cfg["max_loss_per_trade_usd"])
    risk_budget = min(pct_cap, usd_cap)

    pip_val_lot = fx.estimate_pip_value_usd(sym, entry, spec)
    loss_per_lot = risk_pips * pip_val_lot
    if loss_per_lot <= 0:
        raise fx.FxError("computed loss per lot is non-positive")

    lots_by_risk = risk_budget / loss_per_lot
    margin_per_lot = estimate_margin_per_lot_usd(sym, entry, spec, leverage)
    margin_cap_usd = balance_usd * (float(cfg["max_margin_pct"]) / 100.0)
    lots_by_margin = margin_cap_usd / margin_per_lot if margin_per_lot > 0 else float(cfg["max_lots"])
    max_lots = float(cfg["max_lots"])

    raw_lots = min(lots_by_risk, lots_by_margin, max_lots)
    if raw_lots == lots_by_risk:
        limiter = "max_risk"
    elif raw_lots == lots_by_margin:
        limiter = "max_margin"
    else:
        limiter = "max_lots"

    step = float(spec.get("volume_step", 0.01))
    vol_min = float(spec.get("volume_min", 0.01))
    vol_max = float(spec.get("volume_max", 500.0))
    capped = min(raw_lots, vol_max)
    lots = round(math.floor((capped + 1e-12) / step) * step, 4)

    if lots < vol_min:
        min_loss = round(vol_min * loss_per_lot, 2)
        raise fx.FxError(
            f"stop too wide ({risk_pips} pips): even minimum {vol_min} lot risks ${min_loss} > ${risk_budget:.2f} budget"
        )

    actual_loss = round(lots * loss_per_lot, 2)
    actual_profit = round(lots * float(plan["reward_pips"]) * pip_val_lot, 2)
    margin_req = round(lots * margin_per_lot, 2)
    ts_str = (now_utc or _dt.datetime.now(fx.UTC_TZ)).strftime("%Y-%m-%d %H:%M")

    order = {
        "symbol": sym,
        "mt5_symbol": spec.get("mt5_symbol", sym),
        "category": spec["category"],
        "side": side,
        "order_type": "market",
        "volume_lots": lots,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "risk_pips": risk_pips,
        "reward_pips": float(plan["reward_pips"]),
        "reward_risk": float(plan["reward_risk"]),
        "pip_value_per_lot": round(pip_val_lot, 4),
        "max_loss_usd": actual_loss,
        "target_profit_usd": actual_profit,
        "margin_usd": margin_req,
        "balance_usd": round(balance_usd, 2),
        "leverage": leverage,
        "limiter": limiter,
        "digits": int(spec["digits"]),
        "spread_pips": spec.get("spread_pips"),
        "created_utc": ts_str,
    }
    order["fingerprint"] = order_fingerprint(order)
    return order


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lot-Size Budget Manager for Forex, Gold & Oil.")
    parser.add_argument("--balance", type=float, help="Override account balance in USD")
    parser.add_argument("--risk-pct", type=float, help="Override risk per trade %%")
    parser.add_argument("--now", help="UTC timestamp 'YYYY-MM-DD HH:MM'")
    parser.add_argument("--offline", action="store_true", help="Skip live MT5 lookup")
    parser.add_argument("--write", action="store_true", help="Write fx_trader/orders.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    base = Path.cwd()
    cfg = fx.load_config(base)
    if args.risk_pct is not None:
        cfg["risk_per_trade_pct"] = args.risk_pct

    try:
        plan = fx.read_json(fx.work_dir(base) / "plan.json")
        if not plan:
            raise fx.FxError("fx_trader/plan.json not found; run fx-exit --write first")

        sym = plan["symbol"]
        spec = fx.default_spec(sym) if args.offline else fx.get_symbol_spec(sym, cfg)
        balance = float(cfg["balance_usd"])
        leverage = int(cfg["leverage"])
        bal_src = "config"

        if not args.offline and cfg.get("use_mt5_balance", True) and args.balance is None:
            acct = fx.mt5_read_account(cfg)
            if acct and acct["balance"] > 0:
                balance = float(acct["balance"])
                leverage = int(acct["leverage"])
                bal_src = f"mt5 ({acct['trade_mode']})"
        if args.balance is not None:
            balance = float(args.balance)
            bal_src = "cli"

        now_utc = fx.parse_now_utc(args.now)
        order = size_order(plan, cfg, spec, balance, leverage, now_utc=now_utc)
        order["balance_source"] = bal_src

        if args.write:
            fx.write_json(fx.work_dir(base) / "orders.json", {"as_of_utc": order["created_utc"], "orders": [order]})

        if args.json:
            print(json.dumps(order, indent=2))
            return 0

        d = order["digits"]
        print(f"Lot Sizing: {order['symbol']} {order['side'].upper()} ({bal_src}, balance ${order['balance_usd']:.2f}, 1:{order['leverage']})")
        print(f"  Volume        {order['volume_lots']} lots (limited by {order['limiter']})")
        print(f"  Entry / SL/TP {fx.fmt_price(order['entry'], d)} / SL {fx.fmt_price(order['sl'], d)} / TP {fx.fmt_price(order['tp'], d)}")
        print(f"  Risk / Reward -${order['max_loss_usd']:.2f} ({order['risk_pips']} pips) / +${order['target_profit_usd']:.2f} ({order['reward_pips']} pips) [1:{order['reward_risk']}]")
        print(f"  Est. Margin   ${order['margin_usd']:.2f} | Pip Value ${order['pip_value_per_lot']:.2f}/lot")
        return 0
    except fx.FxError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
