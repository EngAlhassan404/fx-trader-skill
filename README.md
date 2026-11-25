# fx-trader-skill

> **9 AI Agent Skills for Forex, Gold (XAUUSD) & Oil Day Trading**
> Read-only MetaTrader 5 integration · Session-aware · Zero order execution

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-green.svg)](https://www.python.org/)
[![MT5 Read-Only](https://img.shields.io/badge/MT5-Read--Only-orange.svg)](https://www.metatrader5.com/)
[![Works with Any AI Agent](https://img.shields.io/badge/AI%20Agent-Any%20(Claude%20%7C%20Gemini%20%7C%20Cursor%20%7C%20Codex)-purple.svg)](#compatibility)
[![Disclaimer](https://img.shields.io/badge/NOT-Financial%20Advice-red.svg)](#disclaimer)

---

## ⚠️ DISCLAIMER — READ BEFORE USE

> **THIS SOFTWARE IS NOT FINANCIAL ADVICE.**
>
> `fx-trader-skill` is an **informational decision-support tool only**. It does **not** execute, place, modify, or cancel any trades. All signals, risk assessments, lot-size calculations, backtests, and news summaries are provided strictly for **educational and research purposes**.
>
> - **No trade is ever executed automatically.** The software is strictly read-only with respect to your broker account.
> - Past simulation results, backtests, and historical probabilities **do not guarantee future performance**.
> - Forex, Gold (XAUUSD), and Oil (WTI/Brent) trading involves **substantial risk of loss** and may not be suitable for all investors.
> - You may lose **some or all** of your invested capital.
> - The author, contributors, and distributors of this software **bear no liability** for any financial losses, missed opportunities, data errors, or consequential damages arising from the use of this software.
> - Always consult a licensed financial advisor before making trading decisions.
>
> **By using this software, you explicitly agree to this disclaimer and waive any claims against the author.**

---

## Overview

`fx-trader-skill` is a collection of **9 composable AI agent skills** that connect any compatible AI assistant to real-time Forex, Gold, and Oil market data via **MetaTrader 5** (read-only) with automatic **Yahoo Finance fallback**.

The skills cover the complete day-trading workflow — from market scanning and news monitoring, through entry timing and exit planning, to position sizing, risk gating, and trade journaling — all while **never placing a single order**.

```
Market Day Workflow
───────────────────
/fx-scanner → /fx-news → /fx-entry → /fx-exit → /fx-timemachine → /fx-budget → /fx-risk → /fx-ticket
```

---

## Compatibility

This skill package is **AI-agnostic** and works with any agent or assistant that supports the open Agent Skills standard:

| Platform | Install Path | Status |
|---|---|---|
| **Google Antigravity (Gemini)** | `~/.gemini/config/plugins/fx-trader-skill/` | ✅ Supported |
| **Claude Code (Anthropic)** | `~/.claude/skills/fx-trader-skill/` | ✅ Supported |
| **Cursor** | `.cursor/skills/fx-trader-skill/` | ✅ Supported |
| **GitHub Copilot / Codex** | Per workspace config | ✅ Supported |
| **Any Agent (open standard)** | Per agent config | ✅ Supported |

---

## Skills Reference

| Slash Command | Skill | Description |
|---|---|---|
| `/fx-scanner` | **Market Scanner** | Scans FX pairs, XAUUSD, and Oil for Long/Short daily setups and session range breakouts on 5-min bars |
| `/fx-news` | **News Monitor** | Fetches live macro pulse (DXY, US10Y, Gold, Oil, EURUSD) and tagged breaking headlines (Fed, CPI, NFP, OPEC, geopolitics) |
| `/fx-alerts` | **Alerts & Session Clock** | 24/5 session clock (Sydney/Asia/London/NY), live MT5 quotes, and one-shot price alerts |
| `/fx-entry` | **Entry Timer** | Monitors 1m/5m/15m candles for confirmed breakouts of session ranges or custom price levels |
| `/fx-exit` | **Exit Planner** | Sets Stop Loss and Take Profit with pip-accurate calculations and R:R ratios |
| `/fx-timemachine` | **Time Machine Backtester** | Replays the trade plan 10,000 times over 60 days of 5-min history; reports TP-first/SL-first probabilities and edge verdict |
| `/fx-budget` | **Lot-Size Calculator** | Computes exact MT5 lot size (0.01 step) constrained by risk %, max USD loss, margin cap, and leverage |
| `/fx-risk` | **Risk Gate** | Validates orders against market hours, SL geometry, live spread, max loss, R:R minimum, daily loss limit, and margin cap — returns PASS or BLOCK |
| `/fx-ticket` | **Trade Journal & Ticket** | Displays ready-to-enter MT5 order tickets and syncs open positions + closed deals (read-only) |

---

## Architecture

```
fx-trader-skill/
├── plugin.json                     # Agent plugin manifest
├── shared/
│   └── fx_core.py                  # Shared engine: MT5 read-only + Yahoo Finance fallback
├── skills/
│   ├── fx-scanner/
│   │   ├── SKILL.md                # Agent instructions for the skill
│   │   └── scan.py                 # Scanner script
│   ├── fx-news/
│   │   ├── SKILL.md
│   │   └── news.py
│   ├── fx-alerts/
│   │   ├── SKILL.md
│   │   └── alerts.py
│   ├── fx-entry/
│   │   ├── SKILL.md
│   │   └── entry.py
│   ├── fx-exit/
│   │   ├── SKILL.md
│   │   └── exit.py
│   ├── fx-timemachine/
│   │   ├── SKILL.md
│   │   └── timemachine.py
│   ├── fx-budget/
│   │   ├── SKILL.md
│   │   ├── size.py
│   │   └── config.example.json
│   ├── fx-risk/
│   │   ├── SKILL.md
│   │   └── check.py
│   └── fx-ticket/
│       ├── SKILL.md
│       └── ticket.py
└── tests/
    └── test_fx_trader.py           # 10/10 unit tests
```

### Shared Core (`fx_core.py`)

The shared engine provides:
- **MT5 read-only connection** via the official `MetaTrader5` Python package
- **Yahoo Finance fallback** (`yfinance`) for symbols not available on the broker (e.g., Oil CFDs)
- Instrument specs: pip values, digits, contract sizes for FX, XAUUSD, XAGUSD, Oil
- 24/5 market hours: Sun 22:00 UTC → Fri 22:00 UTC
- Session definitions (UTC): Asia 00:00–09:00 · London 08:00–16:30 · New York 13:00–22:00
- Broker clock offset correction (auto-detected via live tick)

### Safety Guarantee

**Zero trade execution.** The codebase contains no `order_send`, `order_modify`, or `order_close` calls. This is enforced by an automated AST-based unit test that fails the entire test suite if any such call is ever introduced.

---

## Requirements

| Dependency | Version | Purpose |
|---|---|---|
| Python | ≥ 3.8 | Runtime |
| `MetaTrader5` | latest | Live quotes and account data (Windows only) |
| `yfinance` | ≥ 0.2 | Fallback quotes for Oil and other symbols |
| `pandas` | ≥ 1.3 | Bar data manipulation |
| `requests` | ≥ 2.28 | News fetching |
| `numpy` | ≥ 1.21 | Statistical calculations |

```bash
pip install MetaTrader5 yfinance pandas requests numpy
```

> **Note:** `MetaTrader5` Python bindings are **Windows-only**. On macOS/Linux the skills automatically fall back to Yahoo Finance for all quotes.

---

## Installation

### Google Antigravity (Gemini)

```bash
# Clone the repo
git clone https://github.com/EngAlhassan404/fx-trader-skill.git

# Copy to Antigravity plugins directory
cp -r fx-trader-skill ~/.gemini/config/plugins/fx-trader-skill

# Restart Antigravity — the 9 skills are auto-detected
```

### Claude Code

```bash
git clone https://github.com/EngAlhassan404/fx-trader-skill.git
cp -r fx-trader-skill ~/.claude/skills/fx-trader-skill
```

### Other Agents

Place the `fx-trader-skill/` directory wherever your agent loads skill or plugin directories. All skills are self-contained `SKILL.md` files with Python helper scripts.

---

## Configuration

Copy the example config and edit it:

```bash
mkdir -p fx_trader
cp skills/fx-budget/config.example.json fx_trader/config.json
```

**`fx_trader/config.json`:**
```json
{
  "account_balance": 10000,
  "leverage": 100,
  "max_risk_pct": 1.0,
  "max_usd_loss": 100,
  "max_lots": 1.0,
  "margin_cap_pct": 5.0,
  "daily_loss_limit_usd": 300,
  "max_trades_per_day": 5,
  "min_rr": 1.5
}
```

> The agent reads account balance and leverage **live from MT5** when connected; `config.json` values serve as fallback and for risk limits.

---

## Usage Examples

Once installed, invoke skills by slash command in your AI agent:

```
/fx-scanner           — scan all instruments for Long/Short setups
/fx-news              — get macro pulse + tagged breaking news
/fx-alerts XAUUSD     — start monitoring Gold price
/fx-entry EURUSD      — wait for confirmed London breakout entry
/fx-exit              — plan Stop Loss and Take Profit
/fx-timemachine       — backtest the plan 10,000 times
/fx-budget            — calculate exact lot size within risk rules
/fx-risk              — gate the trade (PASS or BLOCK)
/fx-ticket            — display the final MT5 order ticket
```

---

## Running Tests

```bash
cd fx-trader-skill
python -m unittest discover -s tests -v
```

Expected output: **10 tests, 0 failures, 0 errors**.

---

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-skill`)
3. Commit your changes (`git commit -m 'Add: new skill'`)
4. Push to your branch and open a Pull Request

Please ensure all 10 existing tests continue to pass and add tests for new features.

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for full text.

You are free to use, copy, modify, merge, publish, distribute, sublicense, and/or **sell copies** of the Software, subject to the conditions of the MIT License, including retention of the copyright notice.

---

## Copyright

**© 2026 Alhassan Ali Bahbah**

All rights reserved under the terms of the MIT License.

---

## Acknowledgements

- [MetaTrader 5](https://www.metatrader5.com/) — industry-standard trading platform
- [yfinance](https://github.com/ranaroussi/yfinance) — open-source Yahoo Finance data library
- Original concept inspired by [Jake Schincariol's day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) for Claude
- Built and extended for multi-agent compatibility by Alhassan Ali Bahbah using Google Antigravity
