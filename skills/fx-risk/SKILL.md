---
name: fx-risk
description: >-
  Forex, Gold & Oil Risk & Spread Gate. Validates proposed MT5 orders against
  24/5 market hours, Stop-Loss geometry, live MT5 spread vs stop distance, max
  USD loss per trade, minimum R:R, daily loss limit, max trades per day, and
  margin cap. Prints PASS or BLOCK and saves verdicts to
  fx_trader/state/risk.json. Use before /fx-ticket, always.
---

# fx-risk

Mandatory safety gate before showing any manual MT5 ticket.

```bash
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-risk/check.py"
```

## What It Blocks
- Missing Stop Loss or Stop/Target on the wrong side of entry.
- Wide live spread exceeding category limits or eating too much of the Stop distance.
- Orders exceeding `max_loss_per_trade_usd`, `max_daily_loss_usd`, `max_trades_per_day`, `min_reward_risk`, or `max_margin_pct`.
