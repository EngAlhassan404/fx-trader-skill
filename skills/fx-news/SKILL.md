---
name: fx-news
description: >-
  Macro, Forex, Gold & Oil News Monitor. Fetches live macro pulse (DXY Dollar
  Index, US 10-Year Yield, Gold, WTI Oil, EURUSD) and breaking Yahoo Finance
  headlines tagged for Central Banks (Fed/ECB/BoE/BoJ), CPI/NFP, OPEC/Oil,
  Gold safe-haven drivers, and geopolitics, showing only unseen items. Use when
  the user asks "what's moving gold", "why is oil moving", "macro news",
  "forex news today", "DXY check", or before taking a trade.
---

# fx-news

Checks macro drivers (`DXY`, `US10Y`, `XAUUSD`, `USOIL`, `EURUSD`) and breaking news before you enter a Forex, Gold, or Oil trade.

```bash
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-news/news.py"
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-news/news.py" --symbols XAUUSD,USOIL,EURUSD --hours 12
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-news/news.py" --all
```

## Rules
- Headlines are leads, not trading signals. Always verify high-impact scheduled events (FOMC, CPI, NFP, OPEC meetings) before entering near a release.
- Deduplicates shown headlines in `fx_trader/state/news.json`.
