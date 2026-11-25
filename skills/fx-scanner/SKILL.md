---
name: fx-scanner
description: >-
  Forex, Gold & Oil Market Scanner. Scans Forex pairs, XAUUSD (Gold), XAGUSD,
  and Crude Oil (WTI/Brent) using read-only MetaTrader 5 or Yahoo Finance data.
  Detects Long and Short daily setups (20-day breakout/breakdown, bull/bear
  flags, MA20 reclaim/loss, RSI oversold/overbought) and Asia, London, or New
  York session range breakouts on 5-minute bars, writing fx_trader/watchlist.json.
  Use when the user asks to "scan forex", "find gold or oil setups", "london
  breakout", "asia range breakout", "new york setups", or starts a trading session.
---

# fx-scanner

Scans **Forex, Gold (`XAUUSD`), and Crude Oil (`USOIL`/`UKOIL`)** for both **Long** and **Short** setups, writing results to `fx_trader/watchlist.json`.

```bash
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-scanner/scan.py" universe
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-scanner/scan.py" daily
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-scanner/scan.py" session --mode london
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-scanner/scan.py" session --mode asia_breakout --symbols EURUSD,GBPUSD,XAUUSD,USOIL
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-scanner/scan.py" session --mode new_york
```

## Notes
- Reads live MT5 data (read-only) for Forex and Metals when MT5 is running, and automatically falls back to Yahoo Finance (`GC=F`, `CL=F`, `BZ=F`, `EURUSD=X`, etc.) for symbols not carried by the broker (such as spot Oil CFDs).
- Session windows (UTC):
  - `asia_breakout`: 00:00–05:00 UTC Asian range
  - `london`: 08:00–08:15 UTC London opening range
  - `new_york`: 13:30–13:45 UTC New York opening range
- Hand off interesting candidates to `/fx-news` and `/fx-entry`.
