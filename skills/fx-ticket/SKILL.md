---
name: fx-ticket
description: >-
  Read-Only MT5 Manual Order Ticket & Trade Journal. Displays ready-to-enter
  MetaTrader 5 order tickets (Symbol, BUY/SELL, Lots, Entry, SL, TP) ONLY after
  /fx-risk issues PASS, and syncs open MT5 positions and closed deals in
  strictly read-only mode. Never places or modifies orders on MT5. Use when the
  user asks "show my ticket", "prepare MT5 order", "sync MT5 positions", or
  after /fx-risk passes.
---

# fx-ticket

Formats verified **manual** MT5 tickets and keeps your trade journal in sync (strictly **read-only**—zero order execution).

```bash
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-ticket/ticket.py" show
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-ticket/ticket.py" sync-mt5
python "C:/Users/محمد علي/.gemini/config/plugins/fx-trader-skill/skills/fx-ticket/ticket.py" log-manual --index 1 --status placed
```

## Safety Guarantee
- Automated order placement (`order_send`) is **completely absent** from this plugin. You enter the ticket manually in MetaTrader 5.
- Only tickets that passed `/fx-risk` today are marked `READY`.
