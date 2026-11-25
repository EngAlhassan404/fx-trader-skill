---
name: fx-entry
description: >-
  Forex, Gold & Oil Long/Short Entry Timer. Monitors 1m, 5m, or 15m closed
  candles for confirmed Long or Short breakouts of the Asia, London, or New
  York session range, or a custom price level, writing fx_trader/entry.json for
  /fx-exit. Never places orders. Use when the user asks "check entry on
  XAUUSD", "did EURUSD break out", "watch oil for a short/long", or after
  /fx-scanner.
---

# fx-entry

Confirms **closed-candle** Long or Short entries on Forex pairs, Gold (`XAUUSD`), and Oil (`USOIL`/`UKOIL`).

```bash
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-entry/entry.py" check XAUUSD --setup london --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-entry/entry.py" check EURUSD --setup asia_breakout --side both --write
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-entry/entry.py" check USOIL --setup level --side short --level 82.50 --write
```

## Notes
- Only **completed** bars count (wicks alone do not trigger).
- Hand off triggered setups directly to `/fx-exit`.
