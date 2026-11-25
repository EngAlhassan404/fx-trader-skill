---
name: fx-budget
description: >-
  Forex, Gold & Oil Lot-Size Manager. Reads account balance & leverage from
  read-only MT5 (or fx_trader/config.json) and exact pip/tick values for FX,
  XAUUSD, and Oil to compute exact MT5 lot size (0.01 step) constrained by
  max risk %, max USD loss, margin cap, and max lots, writing
  fx_trader/orders.json. Use when the user asks "what lot size", "size this
  gold trade", "how many lots", or right after /fx-timemachine.
---

# fx-budget

Calculates exact **MT5 lot size** (`0.01` step) so your loss at Stop Loss fits your risk budget.

```bash
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-budget/size.py" --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-budget/size.py" --balance 5000 --risk-pct 1.0 --write
```

## Notes
- Reads `balance` and `leverage` from MT5 in **read-only** mode when connected (unless `--balance` or `--offline` is passed).
- Always pass the generated order through `/fx-risk` before viewing the ticket in `/fx-ticket`.
