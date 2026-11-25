"""Pre-Trade Risk & Spread Gate for Forex, Gold & Oil (PASS / BLOCK)."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import fx_core as fx  # noqa: E402


def check_order(
    order: dict[str, Any],
    cfg: dict[str, Any],
    now_utc: _dt.datetime,
    daily_loss_used: float = 0.0,
    trades_today: int = 0,
    live_spread_pips: float | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []

    sym = fx.canonical_symbol(str(order.get("symbol", "")))
    cat = order.get("category") or fx.infer_category(sym)
    side = str(order.get("side", "")).lower()
    lots = float(order.get("volume_lots", 0.0) or 0.0)
    entry = float(order.get("entry", 0.0) or 0.0)
    sl = order.get("sl")
    tp = order.get("tp")

    # 1. Market hours
    mkt_open, mkt_msg = fx.is_fx_market_open(now_utc)
    if not mkt_open:
        reasons.append(f"market closed: {mkt_msg}")

    # 2. Blocked list
    blocked = {fx.canonical_symbol(b) for b in (cfg.get("blocked") or [])}
    if sym in blocked:
        reasons.append(f"{sym} is on blocked list")

    # 3. Side & Short policy
    if side not in ("buy", "sell"):
        reasons.append(f"invalid side {side!r}")
    elif side == "sell" and not cfg.get("allow_short", True):
        reasons.append("short (sell) trades disabled by config")

    # 4. Stop-Loss & Take-Profit geometry
    if cfg.get("require_stop", True) and sl is None:
        reasons.append("stop-loss (SL) is required")
    elif sl is not None:
        sl_f = float(sl)
        if side == "buy" and sl_f >= entry:
            reasons.append(f"BUY SL ({sl_f}) must be below entry ({entry})")
        if side == "sell" and sl_f <= entry:
            reasons.append(f"SELL SL ({sl_f}) must be above entry ({entry})")
    if tp is not None:
        tp_f = float(tp)
        if side == "buy" and tp_f <= entry:
            reasons.append(f"BUY TP ({tp_f}) must be above entry ({entry})")
        if side == "sell" and tp_f >= entry:
            reasons.append(f"SELL TP ({tp_f}) must be below entry ({entry})")

    # 5. Lot limits
    if lots <= 0:
        reasons.append("volume_lots must be > 0")
    if lots > float(cfg.get("max_lots", 5.0)):
        reasons.append(f"volume {lots} lots exceeds max_lots {cfg['max_lots']}")

    # 6. Risk per trade & Reward:Risk
    max_loss_usd = float(order.get("max_loss_usd", 0.0) or 0.0)
    cap_usd = float(cfg.get("max_loss_per_trade_usd", 100.0))
    if max_loss_usd > cap_usd + 0.05:
        reasons.append(f"max loss ${max_loss_usd:.2f} exceeds limit ${cap_usd:.2f}")

    rr = float(order.get("reward_risk", 0.0) or 0.0)
    min_rr = float(cfg.get("min_reward_risk", 1.5))
    if rr < min_rr:
        reasons.append(f"R:R {rr:.2f} below minimum {min_rr:.2f}")

    # 7. Spread check
    spread = live_spread_pips if live_spread_pips is not None else order.get("spread_pips")
    if spread is not None:
        spread_f = float(spread)
        max_sp_map = cfg.get("max_spread_pips") or {}
        max_sp = float(max_sp_map.get(cat, 5.0))
        if spread_f > max_sp:
            reasons.append(f"spread {spread_f} pips exceeds {cat} max {max_sp} pips")
        risk_pips = float(order.get("risk_pips", 0.0) or 0.0)
        max_sp_pct = float(cfg.get("max_spread_to_stop_pct", 25.0))
        if risk_pips > 0 and (spread_f / risk_pips) * 100.0 > max_sp_pct:
            reasons.append(f"spread {spread_f}p is {(spread_f / risk_pips) * 100:.1f}% of {risk_pips}p stop (max {max_sp_pct}%)")

    # 8. Daily loss & trade count limits
    max_daily = float(cfg.get("max_daily_loss_usd", 300.0))
    if daily_loss_used + max_loss_usd > max_daily + 0.05:
        reasons.append(f"daily risk ${daily_loss_used + max_loss_usd:.2f} would exceed ${max_daily:.2f} daily loss limit")
    max_trades = int(cfg.get("max_trades_per_day", 4))
    if trades_today >= max_trades:
        reasons.append(f"daily trade limit reached ({trades_today}/{max_trades})")

    # 9. Margin limit
    bal = float(order.get("balance_usd") or cfg.get("balance_usd", 10000.0))
    margin_usd = float(order.get("margin_usd", 0.0) or 0.0)
    max_m_pct = float(cfg.get("max_margin_pct", 40.0))
    if bal > 0 and (margin_usd / bal) * 100.0 > max_m_pct:
        reasons.append(f"margin ${margin_usd:.2f} exceeds {max_m_pct}% of balance")

    verdict = "PASS" if not reasons else "BLOCK"
    return {
        "symbol": sym,
        "side": side,
        "volume_lots": lots,
        "fingerprint": order.get("fingerprint"),
        "verdict": verdict,
        "reasons": reasons,
        "warnings": warnings,
        "checked_utc": now_utc.strftime("%Y-%m-%d %H:%M"),
        "date_utc": now_utc.strftime("%Y-%m-%d"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Risk & Spread Gate for Forex, Gold & Oil.")
    parser.add_argument("--now", help="UTC timestamp 'YYYY-MM-DD HH:MM'")
    parser.add_argument("--offline", action="store_true", help="Skip live MT5 checks")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    base = Path.cwd()
    cfg = fx.load_config(base)

    try:
        orders_doc = fx.read_json(fx.work_dir(base) / "orders.json")
        if not orders_doc or not orders_doc.get("orders"):
            raise fx.FxError("fx_trader/orders.json not found or empty; run fx-budget --write first")

        now_utc = fx.parse_now_utc(args.now)
        today_str = now_utc.strftime("%Y-%m-%d")

        # Gather today's loss/trades from journal and (optionally) live read-only MT5 deals
        journal = fx.read_json(fx.state_dir(base) / "journal.json") or {"entries": [], "mt5_deals": []}
        daily_loss = 0.0
        trades_today = 0
        for e in journal.get("entries", []):
            if e.get("date_utc") == today_str and e.get("status") in ("placed", "closed"):
                trades_today += 1
                daily_loss += float(e.get("max_loss_usd", 0.0))

        if not args.offline:
            deals = fx.mt5_read_today_deals(now_utc)
            if deals:
                realized_neg = sum(abs(d["profit_usd"]) for d in deals if d["profit_usd"] < 0)
                daily_loss = max(daily_loss, realized_neg)
                trades_today = max(trades_today, len(deals))

        results: list[dict[str, Any]] = []
        for order in orders_doc["orders"]:
            live_sp = None
            if not args.offline:
                sp_info = fx.get_symbol_spec(order["symbol"], cfg)
                live_sp = sp_info.get("spread_pips")
            res = check_order(order, cfg, now_utc, daily_loss_used=daily_loss, trades_today=trades_today, live_spread_pips=live_sp)
            results.append(res)
            if res["verdict"] == "PASS":
                daily_loss += float(order.get("max_loss_usd", 0.0))
                trades_today += 1

        out = {"as_of_utc": now_utc.strftime("%Y-%m-%d %H:%M"), "date_utc": today_str, "results": results}
        if not args.no_write:
            fx.write_json(fx.state_dir(base) / "risk.json", out)

        if args.json:
            print(json.dumps(out, indent=2))
            return 0 if all(r["verdict"] == "PASS" for r in results) else 1

        for r in results:
            print(f"{r['verdict']}: {r['symbol']} {r['side'].upper()} {r['volume_lots']} lots")
            for reason in r["reasons"]:
                print(f"  - BLOCKED: {reason}")
        return 0 if all(r["verdict"] == "PASS" for r in results) else 1
    except fx.FxError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
