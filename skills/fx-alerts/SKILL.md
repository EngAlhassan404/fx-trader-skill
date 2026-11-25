---
name: fx-alerts
description: >-
  24/5 Forex, Gold & Oil Session Clock, Live MT5 Quotes & One-Shot Alerts.
  Knows global 24/5 market hours (Sun 22:00 UTC to Fri 22:00 UTC) and active
  Sydney, Asia, London, New York sessions and London-NY overlap. Reads live
  MT5 Bid/Ask/Spread (read-only) with Yahoo Finance fallback, saves quotes to
  fx_trader/prices.json, and fires one-shot alerts for price levels, stops,
  targets, spread spikes, and session opens. Use when the user asks "is forex
  open", "what session is active", "price of gold", "quote XAUUSD", "alert me
  when EURUSD hits", or right after /fx-exit.
---

# fx-alerts

Tracks active trading sessions, live MT5 Bid/Ask/Spread quotes, and one-shot trade alerts. Alerts are purely informational—nothing executes orders.

```bash
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-alerts/alerts.py" clock
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-alerts/alerts.py" quote XAUUSD --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-alerts/alerts.py" quote EURUSD --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-alerts/alerts.py" quote USOIL --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-alerts/alerts.py" add --from-plan
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-alerts/alerts.py" add --symbol XAUUSD --above 3520 --below 3460
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-alerts/alerts.py" check
```
