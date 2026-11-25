"""Comprehensive unit and end-to-end tests for fx-trader-skill."""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "skills" / "fx-scanner"))
sys.path.insert(0, str(ROOT / "skills" / "fx-entry"))
sys.path.insert(0, str(ROOT / "skills" / "fx-exit"))
sys.path.insert(0, str(ROOT / "skills" / "fx-timemachine"))
sys.path.insert(0, str(ROOT / "skills" / "fx-budget"))
sys.path.insert(0, str(ROOT / "skills" / "fx-risk"))
sys.path.insert(0, str(ROOT / "skills" / "fx-ticket"))
sys.path.insert(0, str(ROOT / "skills" / "fx-alerts"))

import fx_core as fx  # noqa: E402
import scan as fx_scan  # noqa: E402
import entry as fx_entry  # noqa: E402
import exit as fx_exit  # noqa: E402
import timemachine as fx_tm  # noqa: E402
import size as fx_budget  # noqa: E402
import check as fx_risk  # noqa: E402
import ticket as fx_ticket  # noqa: E402
import alerts as fx_alerts  # noqa: E402


def _make_5m_bars(start_dt: _dt.datetime, count: int, base_px: float = 3500.0, step: float = 0.5) -> list[dict]:
    bars = []
    px = base_px
    for i in range(count):
        dt = start_dt + _dt.timedelta(minutes=5 * i)
        o = px
        c = px + (step if i % 3 != 0 else -step * 0.6)
        h = max(o, c) + abs(step) * 0.5
        l = min(o, c) - abs(step) * 0.5
        bars.append({
            "ts": int(dt.timestamp()),
            "time_utc": dt.strftime("%Y-%m-%d %H:%M"),
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "volume": 100.0,
        })
        px = c
    return bars


class TestSafetyAndCore(unittest.TestCase):
    def test_no_order_send_anywhere_in_plugin(self):
        import ast
        for py in ROOT.rglob("*.py"):
            if py.resolve() == Path(__file__).resolve():
                continue
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    self.assertNotEqual(node.attr, "order_send", f"forbidden order_send in {py}")
                elif isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "order_send", f"forbidden order_send in {py}")

    def test_symbol_normalization_and_specs(self):
        self.assertEqual(fx.canonical_symbol("eur/usd"), "EURUSD")
        self.assertEqual(fx.canonical_symbol("EURUSD=X"), "EURUSD")
        self.assertEqual(fx.canonical_symbol("gold"), "XAUUSD")
        self.assertEqual(fx.canonical_symbol("GC=F"), "XAUUSD")
        self.assertEqual(fx.canonical_symbol("CL=F"), "USOIL")
        self.assertEqual(fx.canonical_symbol("brent"), "UKOIL")

        self.assertEqual(fx.default_spec("EURUSD")["digits"], 5)
        self.assertEqual(fx.default_spec("USDJPY")["digits"], 3)
        self.assertEqual(fx.default_spec("XAUUSD")["digits"], 2)
        self.assertEqual(fx.default_spec("USOIL")["digits"], 2)

    def test_market_hours_and_sessions(self):
        sun_closed = _dt.datetime(2026, 11, 22, 20, 0, tzinfo=fx.UTC_TZ)
        sun_open = _dt.datetime(2026, 11, 22, 22, 30, tzinfo=fx.UTC_TZ)
        fri_closed = _dt.datetime(2026, 11, 27, 22, 15, tzinfo=fx.UTC_TZ)
        wed_overlap = _dt.datetime(2026, 11, 25, 14, 0, tzinfo=fx.UTC_TZ)

        self.assertFalse(fx.is_fx_market_open(sun_closed)[0])
        self.assertTrue(fx.is_fx_market_open(sun_open)[0])
        self.assertFalse(fx.is_fx_market_open(fri_closed)[0])
        self.assertIn("london", fx.active_sessions_utc(wed_overlap))
        self.assertIn("new_york", fx.active_sessions_utc(wed_overlap))


class TestScannerEntryExit(unittest.TestCase):
    def test_daily_long_and_short_setups(self):
        bars_up = [{"close": 1.08 + i * 0.001} for i in range(25)]
        hits_up = fx_scan.analyze_daily("EURUSD", bars_up, 5)
        self.assertTrue(any(h["setup"] == "breakout_20d" and h["side"] == "long" for h in hits_up))

        bars_dn = [{"close": 1.12 - i * 0.001} for i in range(25)]
        hits_dn = fx_scan.analyze_daily("EURUSD", bars_dn, 5)
        self.assertTrue(any(h["setup"] == "breakdown_20d" and h["side"] == "short" for h in hits_dn))

    def test_london_breakout_short_entry_and_exit(self):
        day = _dt.datetime(2026, 11, 25, 8, 0, tzinfo=fx.UTC_TZ)
        bars = [
            {"ts": int(day.timestamp()), "time_utc": "2026-11-25 08:00", "open": 3500.0, "high": 3505.0, "low": 3495.0, "close": 3499.0, "volume": 100},
            {"ts": int((day + _dt.timedelta(minutes=5)).timestamp()), "time_utc": "2026-11-25 08:05", "open": 3499.0, "high": 3502.0, "low": 3496.0, "close": 3497.0, "volume": 100},
            {"ts": int((day + _dt.timedelta(minutes=10)).timestamp()), "time_utc": "2026-11-25 08:10", "open": 3497.0, "high": 3501.0, "low": 3495.5, "close": 3496.0, "volume": 100},
            # Post range bar closes BELOW 3495.0 -> SHORT trigger!
            {"ts": int((day + _dt.timedelta(minutes=15)).timestamp()), "time_utc": "2026-11-25 08:15", "open": 3496.0, "high": 3497.0, "low": 3491.0, "close": 3492.5, "volume": 120},
        ]
        spec = fx.default_spec("XAUUSD")
        ent = fx_entry.check_entry("XAUUSD", bars, spec, setup="london", side="both", now_utc=day + _dt.timedelta(minutes=25))
        self.assertEqual(ent["status"], "triggered")
        self.assertEqual(ent["side"], "short")
        self.assertEqual(ent["entry"], 3492.5)

        plan = fx_exit.build_plan("XAUUSD", "short", ent["entry"], spec, stop_spec="range-mid", target_spec="2R", range_high=ent["range_high"], range_low=ent["range_low"])
        self.assertEqual(plan["stop"], 3500.0)
        self.assertEqual(plan["risk_pips"], 75.0)  # $7.50 / $0.10 = 75 pips
        self.assertEqual(plan["target"], 3477.5)
        self.assertEqual(plan["reward_risk"], 2.0)

    def test_exit_refuses_bad_stops(self):
        spec = fx.default_spec("EURUSD")
        with self.assertRaises(fx.FxError):
            fx_exit.build_plan("EURUSD", "long", 1.10000, spec, stop_spec="price:1.10100")
        with self.assertRaises(fx.FxError):
            fx_exit.build_plan("EURUSD", "short", 1.10000, spec, stop_spec="pips:0.5")


class TestTimeMachineBudgetRisk(unittest.TestCase):
    def test_monte_carlo_long_and_short_reproducible(self):
        start = _dt.datetime(2026, 11, 1, 0, 0, tzinfo=fx.UTC_TZ)
        bars = _make_5m_bars(start, 600, base_px=1.0900, step=0.0002)
        pool = fx_tm.build_intraday_pool(bars)
        r1 = fx_tm.run_monte_carlo("long", 1.10000, 1.09800, 1.10400, 13 * 60, 48, pool, replays=500, seed=19)
        r2 = fx_tm.run_monte_carlo("long", 1.10000, 1.09800, 1.10400, 13 * 60, 48, pool, replays=500, seed=19)
        self.assertEqual(r1, r2)
        rs = fx_tm.run_monte_carlo("short", 1.10000, 1.10200, 1.09600, 13 * 60, 48, pool, replays=500, seed=19)
        self.assertIn("verdict", rs)

    def test_lot_sizing_eurusd_gold_oil_and_jpy(self):
        cfg = json.loads(json.dumps(fx.DEFAULT_CONFIG))
        # EURUSD: $10,000 balance, 1% risk = $100, stop = 20 pips -> $10/pip/lot -> 0.50 lots
        spec_eu = fx.default_spec("EURUSD")
        plan_eu = fx_exit.build_plan("EURUSD", "long", 1.10000, spec_eu, stop_spec="pips:20", target_spec="2R")
        ord_eu = fx_budget.size_order(plan_eu, cfg, spec_eu, 10000.0, 100)
        self.assertEqual(ord_eu["volume_lots"], 0.5)
        self.assertEqual(ord_eu["max_loss_usd"], 100.0)

        # XAUUSD: $10,000 balance, $100 risk, 50 pips ($5.00 stop, $10/pip/lot) -> 0.20 lots
        spec_au = fx.default_spec("XAUUSD")
        plan_au = fx_exit.build_plan("XAUUSD", "short", 3500.00, spec_au, stop_spec="pips:50", target_spec="2R")
        ord_au = fx_budget.size_order(plan_au, cfg, spec_au, 10000.0, 100)
        self.assertEqual(ord_au["volume_lots"], 0.2)
        self.assertEqual(ord_au["max_loss_usd"], 100.0)

        # USOIL: $10,000 balance, $100 risk, 100 pips ($1.00 stop, $1/pip/lot) -> 1.00 lot
        spec_oil = fx.default_spec("USOIL")
        plan_oil = fx_exit.build_plan("USOIL", "long", 80.00, spec_oil, stop_spec="pips:100", target_spec="2R")
        ord_oil = fx_budget.size_order(plan_oil, cfg, spec_oil, 10000.0, 100)
        self.assertEqual(ord_oil["volume_lots"], 1.0)
        self.assertEqual(ord_oil["max_loss_usd"], 100.0)

        # Too-wide stop refuses below 0.01 lot
        plan_wide = fx_exit.build_plan("XAUUSD", "long", 3500.00, spec_au, stop_spec="pips:1500", target_spec="2R")
        with self.assertRaises(fx.FxError):
            fx_budget.size_order(plan_wide, cfg, spec_au, 10000.0, 100)

    def test_risk_gate_spread_and_limits(self):
        cfg = json.loads(json.dumps(fx.DEFAULT_CONFIG))
        spec = fx.default_spec("EURUSD")
        plan = fx_exit.build_plan("EURUSD", "sell" if False else "short", 1.10000, spec, stop_spec="pips:20", target_spec="2R")
        order = fx_budget.size_order(plan, cfg, spec, 10000.0, 100)
        wed = _dt.datetime(2026, 11, 25, 14, 0, tzinfo=fx.UTC_TZ)

        ok = fx_risk.check_order(order, cfg, wed, live_spread_pips=1.2)
        self.assertEqual(ok["verdict"], "PASS")

        wide_sp = fx_risk.check_order(order, cfg, wed, live_spread_pips=6.0)
        self.assertEqual(wide_sp["verdict"], "BLOCK")

        sat = _dt.datetime(2026, 11, 28, 14, 0, tzinfo=fx.UTC_TZ)
        wknd = fx_risk.check_order(order, cfg, sat, live_spread_pips=1.0)
        self.assertEqual(wknd["verdict"], "BLOCK")


class TestEndToEndPipeline(unittest.TestCase):
    def test_cli_pipeline_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = Path.cwd()
            os.chdir(tmp)
            try:
                tmp_path = Path(tmp)
                start = _dt.datetime(2026, 11, 10, 0, 0, tzinfo=fx.UTC_TZ)
                bars = _make_5m_bars(start, 600, base_px=3480.0, step=0.6)
                # Append today's London opening range + breakout
                day = _dt.datetime(2026, 11, 25, 8, 0, tzinfo=fx.UTC_TZ)
                bars.extend([
                    {"ts": int(day.timestamp()), "time_utc": "2026-11-25 08:00", "open": 3500.0, "high": 3504.0, "low": 3496.0, "close": 3502.0, "volume": 100},
                    {"ts": int((day + _dt.timedelta(minutes=5)).timestamp()), "time_utc": "2026-11-25 08:05", "open": 3502.0, "high": 3503.0, "low": 3497.0, "close": 3501.0, "volume": 100},
                    {"ts": int((day + _dt.timedelta(minutes=10)).timestamp()), "time_utc": "2026-11-25 08:10", "open": 3501.0, "high": 3503.5, "low": 3498.0, "close": 3502.5, "volume": 100},
                    {"ts": int((day + _dt.timedelta(minutes=15)).timestamp()), "time_utc": "2026-11-25 08:15", "open": 3502.5, "high": 3508.0, "low": 3502.0, "close": 3507.0, "volume": 150},
                ])
                fix_file = tmp_path / "XAUUSD.json"
                fix_file.write_text(json.dumps({"price": 3507.0, "prev_close": 3495.0, "bars": bars}), encoding="utf-8")

                self.assertEqual(fx_entry.main(["check", "XAUUSD", "--setup", "london", "--now", "2026-11-25 08:25", "--offline", str(fix_file), "--write"]), 0)
                self.assertEqual(fx_exit.main(["plan", "--stop", "range-mid", "--target", "2R", "--offline", str(fix_file), "--write"]), 0)
                self.assertEqual(fx_tm.main(["run", "--replays", "300", "--offline", str(fix_file), "--write"]), 0)
                self.assertEqual(fx_budget.main(["--balance", "10000", "--now", "2026-11-25 08:25", "--offline", "--write"]), 0)
                self.assertEqual(fx_risk.main(["--now", "2026-11-25 08:25", "--offline"]), 0)
                self.assertEqual(fx_ticket.main(["show", "--now", "2026-11-25 08:25"]), 0)
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
