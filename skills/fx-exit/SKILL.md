---
name: fx-exit
description: >-
  Pip-Accurate Long & Short Exit Planner for Forex, Gold & Oil. Sets Stop Loss
  (range-mid, range-edge, pips:X, price:X, pct:X, or atr:K) and Take Profit
  (1R, 1.5R, 2R, 3R, pips:X, or price:X) with automatic instrument precision
  (5 digits FX, 3 digits JPY, 2 digits Gold/Oil), rounding stops away from
  entry, and writing fx_trader/plan.json. Use when the user asks "set stop and
  target", "plan exit", "calculate R:R", or right after /fx-entry.
---

# fx-exit

Decides Stop Loss and Take Profit **before** calculating lot size or entering.

```bash
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-exit/exit.py" plan --stop range-mid --target 2R --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-exit/exit.py" plan --symbol XAUUSD --side short --entry 3500.00 --stop pips:80 --target 2R --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-exit/exit.py" plan --symbol EURUSD --side long --entry 1.09500 --stop atr:1.5 --target 2R --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-exit/exit.py" show
```

## Notes
- Stops always round **away** from entry (down for Long, up for Short).
- Hand off the written plan to `/fx-timemachine` to test the odds, then `/fx-budget` for exact MT5 lot sizing.
