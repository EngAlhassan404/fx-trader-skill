---
name: fx-timemachine
description: >-
  Forex, Gold & Oil Time Machine. Replays every possible outcome of a Long or
  Short trade plan 10,000 times from the instrument's own last 60 days of
  5-minute bars (at the same UTC time-of-day) plus historical session
  backtesting. Reports Target-first vs Stop-first probabilities, Average R, and
  an honest edge verdict, writing fx_trader/timemachine.json. Use when the user
  asks "run the time machine", "what are the odds", "simulate this gold trade",
  "backtest this setup", or after /fx-exit before /fx-budget.
---

# fx-timemachine

Replays your exact Long or Short trade plan **10,000 times** before you size a lot.

```bash
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-timemachine/timemachine.py" run --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-timemachine/timemachine.py" run --hours 8 --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-timemachine/timemachine.py" run --symbol XAUUSD --side short --entry 3500 --stop 3508 --target 3484 --hours 6
```

## Notes
- Simulation based on the last 60 days of 5-minute bars—not a prediction. Major macro shocks (FOMC/CPI/NFP) can exceed historical volatility.
- Hand off to `/fx-budget` next for exact MT5 lot sizing.
