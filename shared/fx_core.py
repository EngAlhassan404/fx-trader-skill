"""Shared core utilities for fx-trader-skill (Forex, Gold, Oil + Read-Only MT5).

Strictly read-only with respect to MetaTrader 5: this module never imports or
invokes order placement APIs. All workspace state lives under ``fx_trader/``.
"""

from __future__ import annotations

import datetime as _dt
import gzip
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")

# Default curated universe covering major/cross FX, Metals, and Oil benchmarks.
DEFAULT_UNIVERSE: list[dict[str, str]] = [
    # Major FX
    {"symbol": "EURUSD", "category": "forex", "yahoo": "EURUSD=X", "mt5": "EURUSD", "name": "Euro / US Dollar"},
    {"symbol": "GBPUSD", "category": "forex", "yahoo": "GBPUSD=X", "mt5": "GBPUSD", "name": "British Pound / US Dollar"},
    {"symbol": "USDJPY", "category": "forex", "yahoo": "USDJPY=X", "mt5": "USDJPY", "name": "US Dollar / Japanese Yen"},
    {"symbol": "USDCHF", "category": "forex", "yahoo": "USDCHF=X", "mt5": "USDCHF", "name": "US Dollar / Swiss Franc"},
    {"symbol": "USDCAD", "category": "forex", "yahoo": "USDCAD=X", "mt5": "USDCAD", "name": "US Dollar / Canadian Dollar"},
    {"symbol": "AUDUSD", "category": "forex", "yahoo": "AUDUSD=X", "mt5": "AUDUSD", "name": "Australian Dollar / US Dollar"},
    {"symbol": "NZDUSD", "category": "forex", "yahoo": "NZDUSD=X", "mt5": "NZDUSD", "name": "New Zealand Dollar / US Dollar"},
    # Active FX Crosses
    {"symbol": "EURJPY", "category": "forex", "yahoo": "EURJPY=X", "mt5": "EURJPY", "name": "Euro / Japanese Yen"},
    {"symbol": "GBPJPY", "category": "forex", "yahoo": "GBPJPY=X", "mt5": "GBPJPY", "name": "British Pound / Japanese Yen"},
    {"symbol": "EURGBP", "category": "forex", "yahoo": "EURGBP=X", "mt5": "EURGBP", "name": "Euro / British Pound"},
    {"symbol": "EURAUD", "category": "forex", "yahoo": "EURAUD=X", "mt5": "EURAUD", "name": "Euro / Australian Dollar"},
    {"symbol": "GBPAUD", "category": "forex", "yahoo": "GBPAUD=X", "mt5": "GBPAUD", "name": "British Pound / Australian Dollar"},
    {"symbol": "AUDJPY", "category": "forex", "yahoo": "AUDJPY=X", "mt5": "AUDJPY", "name": "Australian Dollar / Japanese Yen"},
    {"symbol": "CADJPY", "category": "forex", "yahoo": "CADJPY=X", "mt5": "CADJPY", "name": "Canadian Dollar / Japanese Yen"},
    # Precious Metals (Gold & Silver)
    {"symbol": "XAUUSD", "category": "metal", "yahoo": "GC=F", "mt5": "XAUUSD", "name": "Gold vs US Dollar"},
    {"symbol": "XAGUSD", "category": "metal", "yahoo": "SI=F", "mt5": "XAGUSD", "name": "Silver vs US Dollar"},
    # Crude Oil Benchmarks
    {"symbol": "USOIL", "category": "oil", "yahoo": "CL=F", "mt5": "USOIL", "name": "WTI Crude Oil"},
    {"symbol": "UKOIL", "category": "oil", "yahoo": "BZ=F", "mt5": "UKOIL", "name": "Brent Crude Oil"},
]

SYMBOL_ALIASES: dict[str, str] = {
    "GOLD": "XAUUSD",
    "GC=F": "XAUUSD",
    "XAUUSD=X": "XAUUSD",
    "SILVER": "XAGUSD",
    "SI=F": "XAGUSD",
    "XAGUSD=X": "XAGUSD",
    "WTI": "USOIL",
    "XTIUSD": "USOIL",
    "CL=F": "USOIL",
    "CRUDE": "USOIL",
    "OIL": "USOIL",
    "BRENT": "UKOIL",
    "XBRUSD": "UKOIL",
    "BZ=F": "UKOIL",
}

YAHOO_MAP: dict[str, str] = {
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "USOIL": "CL=F",
    "UKOIL": "BZ=F",
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
}

DEFAULT_CONFIG: dict[str, Any] = {
    "account_currency": "USD",
    "balance_usd": 10000.0,
    "leverage": 100,
    "use_mt5_balance": True,
    "data_source": "auto",  # auto (MT5 read-only then Yahoo), mt5, yahoo
    "risk_per_trade_pct": 1.0,
    "max_loss_per_trade_usd": 100.0,
    "max_daily_loss_usd": 300.0,
    "max_trades_per_day": 4,
    "max_margin_pct": 40.0,
    "max_lots": 5.0,
    "min_reward_risk": 1.5,
    "max_spread_pips": {
        "forex": 3.0,
        "metal": 45.0,   # XAUUSD 45 points = $0.45
        "oil": 6.0,      # $0.06
    },
    "max_spread_to_stop_pct": 25.0,
    "require_stop": True,
    "allow_short": True,
    "flat_by_utc": None,  # e.g. "20:55" to flatten intraday, or None for no forced close
    "blocked": [],
    "mt5_symbol_overrides": {},  # e.g. {"USOIL": "WTI_CFD"} if broker uses custom suffix
}

# Standard trading sessions in UTC (start_hour_min, end_hour_min)
SESSIONS_UTC: dict[str, tuple[str, str]] = {
    "sydney": ("22:00", "07:00"),
    "asia": ("00:00", "09:00"),
    "london": ("08:00", "16:30"),
    "new_york": ("13:00", "22:00"),
}

# Default Opening Range windows in UTC for session breakout scanning
SESSION_OR_WINDOWS_UTC: dict[str, tuple[str, str, str]] = {
    # mode: (range_start_utc, range_end_utc, session_end_utc)
    "asia_breakout": ("00:00", "05:00", "16:30"),   # Asia range -> trade London/NY breakout
    "london": ("08:00", "08:15", "16:30"),          # First 15m of London
    "new_york": ("13:30", "13:45", "20:00"),        # First 15m of NY stock/gold overlap
}


class FxError(RuntimeError):
    """Domain error with a single-line human-readable explanation."""


def work_dir(base: str | Path | None = None) -> Path:
    """Return the workspace ``fx_trader`` directory path."""
    root = Path(base) if base else Path.cwd()
    return root / "fx_trader"


def state_dir(base: str | Path | None = None) -> Path:
    return work_dir(base) / "state"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    tmp.replace(path)
    return path


def load_config(base: str | Path | None = None) -> dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    user_cfg = read_json(work_dir(base) / "config.json")
    if isinstance(user_cfg, dict):
        for k, v in user_cfg.items():
            if k == "max_spread_pips" and isinstance(v, dict):
                cfg["max_spread_pips"].update(v)
            elif k == "mt5_symbol_overrides" and isinstance(v, dict):
                cfg["mt5_symbol_overrides"].update(v)
            else:
                cfg[k] = v
    return cfg


def canonical_symbol(sym: str) -> str:
    """Normalize user input like 'eur/usd', 'EURUSD=X', 'gold', 'cl=f' -> 'EURUSD'/'XAUUSD'/'USOIL'."""
    s = re.sub(r"[/\s]", "", sym.strip().upper())
    if s in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[s]
    if s.endswith("=X") and len(s) == 8:
        return s[:-2]
    return s


def infer_category(sym: str) -> str:
    c = canonical_symbol(sym)
    for item in DEFAULT_UNIVERSE:
        if item["symbol"] == c:
            return item["category"]
    if c.startswith(("XAU", "XAG", "XPT", "XPD")) or c in {"GOLD", "SILVER", "COPPER"}:
        return "metal"
    if any(k in c for k in ("OIL", "WTI", "BRENT", "CL=", "BZ=")):
        return "oil"
    if len(c) == 6 and c.isalpha():
        return "forex"
    return "forex"


def to_yahoo_symbol(sym: str) -> str:
    raw = sym.strip().upper()
    if raw.endswith("=X") or raw.endswith("=F") or raw.startswith("^") or "-" in raw:
        return raw
    c = canonical_symbol(raw)
    if c in YAHOO_MAP:
        return YAHOO_MAP[c]
    if len(c) == 6 and c.isalpha():
        return f"{c}=X"
    return c


def default_spec(sym: str) -> dict[str, Any]:
    """Return sensible fallback contract & pip specs for FX, Gold, Silver, and Oil."""
    c = canonical_symbol(sym)
    cat = infer_category(c)
    if cat == "metal":
        if "XAG" in c or c == "SILVER":
            return {
                "symbol": c, "category": "metal", "digits": 3, "point": 0.001,
                "pip_size": 0.01, "contract_size": 5000.0,
                "volume_min": 0.01, "volume_step": 0.01, "volume_max": 100.0,
                "quote_ccy": "USD", "source": "fallback",
            }
        # XAUUSD: 1 lot = 100 oz, 1 pip = $0.10 (10 points at 2 digits) -> $10/lot per pip, $1/lot per 0.01
        return {
            "symbol": c, "category": "metal", "digits": 2, "point": 0.01,
            "pip_size": 0.10, "contract_size": 100.0,
            "volume_min": 0.01, "volume_step": 0.01, "volume_max": 100.0,
            "quote_ccy": "USD", "source": "fallback",
        }
    if cat == "oil":
        # WTI / Brent standard CFD: 1 lot = 100 barrels (or 1000 on futures; 100 is common retail CFD)
        # 1 pip = $0.01 -> $1.00/lot per pip at 100 barrels
        return {
            "symbol": c, "category": "oil", "digits": 2, "point": 0.01,
            "pip_size": 0.01, "contract_size": 100.0,
            "volume_min": 0.01, "volume_step": 0.01, "volume_max": 100.0,
            "quote_ccy": "USD", "source": "fallback",
        }
    # Standard Forex pair (6 chars)
    quote_ccy = c[3:6] if len(c) == 6 else "USD"
    is_jpy = quote_ccy == "JPY"
    digits = 3 if is_jpy else 5
    point = 0.001 if is_jpy else 0.00001
    pip_size = 0.01 if is_jpy else 0.0001
    return {
        "symbol": c, "category": "forex", "digits": digits, "point": point,
        "pip_size": pip_size, "contract_size": 100000.0,
        "volume_min": 0.01, "volume_step": 0.01, "volume_max": 500.0,
        "quote_ccy": quote_ccy, "source": "fallback",
    }


def round_price(value: float | Decimal | str, digits: int, mode: str = "nearest") -> float:
    """Round a price cleanly to ``digits`` decimal places."""
    try:
        d = Decimal(str(value))
    except InvalidOperation as exc:
        raise FxError(f"invalid numeric price: {value!r}") from exc
    q = Decimal(10) ** (-digits)
    if mode == "down":
        return float(d.quantize(q, rounding=ROUND_FLOOR))
    if mode == "up":
        return float(d.quantize(q, rounding=ROUND_CEILING))
    return float(d.quantize(q, rounding=ROUND_HALF_UP))


def fmt_price(value: float, digits: int) -> str:
    return f"{value:.{digits}f}"


def parse_now_utc(now_str: str | None = None) -> _dt.datetime:
    """Parse '--now' string as UTC (e.g. '2026-11-25 14:15' or ISO) or return current UTC."""
    if not now_str:
        return _dt.datetime.now(UTC_TZ)
    text = now_str.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = _dt.datetime.strptime(text, fmt)
            return dt.replace(tzinfo=UTC_TZ)
        except ValueError:
            continue
    raise FxError(f"invalid UTC timestamp {now_str!r}; expected 'YYYY-MM-DD HH:MM'")


def is_fx_market_open(now_utc: _dt.datetime | None = None) -> tuple[bool, str]:
    """Return whether the global 24/5 FX market is open (Sun 22:00 UTC -> Fri 22:00 UTC)."""
    dt = (now_utc or _dt.datetime.now(UTC_TZ)).astimezone(UTC_TZ)
    wd = dt.weekday()  # Mon=0 .. Sun=6
    hm = dt.hour * 60 + dt.minute
    if wd == 5:
        return False, "Weekend (Saturday): Forex/Metals/Oil CFD markets closed"
    if wd == 6 and hm < 22 * 60:
        return False, "Weekend (Sunday before 22:00 UTC): market opens at 22:00 UTC"
    if wd == 4 and hm >= 22 * 60:
        return False, "Weekend (Friday after 22:00 UTC): market closed for the week"
    return True, "Global 24/5 market open"


def active_sessions_utc(now_utc: _dt.datetime | None = None) -> list[str]:
    """List currently active FX sessions in UTC."""
    is_open, _ = is_fx_market_open(now_utc)
    if not is_open:
        return []
    dt = (now_utc or _dt.datetime.now(UTC_TZ)).astimezone(UTC_TZ)
    hm = dt.hour * 60 + dt.minute
    active: list[str] = []
    for name, (s_str, e_str) in SESSIONS_UTC.items():
        sh, sm = map(int, s_str.split(":"))
        eh, em = map(int, e_str.split(":"))
        s_m, e_m = sh * 60 + sm, eh * 60 + em
        if s_m < e_m:
            if s_m <= hm < e_m:
                active.append(name)
        else:
            if hm >= s_m or hm < e_m:
                active.append(name)
    return active


# ---------------------------------------------------------------------------
# Read-only MetaTrader 5 helper (NEVER imports or calls order_send)
# ---------------------------------------------------------------------------

def _try_mt5_module():
    try:
        import MetaTrader5 as mt5  # type: ignore
        return mt5
    except ImportError:
        return None


def _resolve_mt5_symbol(mt5: Any, sym: str, cfg: dict[str, Any] | None = None) -> str | None:
    c = canonical_symbol(sym)
    overrides = (cfg or {}).get("mt5_symbol_overrides") or {}
    candidates: list[str] = []
    if c in overrides:
        candidates.append(str(overrides[c]))
    candidates.extend([c, sym.strip()])
    if c == "USOIL":
        candidates.extend(["USOIL", "WTI", "XTIUSD", "CL"])
    elif c == "UKOIL":
        candidates.extend(["UKOIL", "BRENT", "XBRUSD"])

    for cand in candidates:
        info = mt5.symbol_info(cand)
        if info is not None:
            # Skip ETFs/Stocks if looking for Oil/FX
            path_u = (getattr(info, "path", "") or "").upper()
            if c in {"USOIL", "UKOIL"} and ("ETF" in path_u or "NASDAQ" in path_u or "NYSE" in path_u):
                continue
            mt5.symbol_select(cand, True)
            return cand
    return None


def mt5_read_account(cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Read-only account snapshot from local MetaTrader 5 terminal, or None."""
    if (cfg or {}).get("data_source") == "yahoo":
        return None
    mt5 = _try_mt5_module()
    if mt5 is None:
        return None
    if not mt5.initialize():
        return None
    try:
        ai = mt5.account_info()
        ti = mt5.terminal_info()
        if ai is None:
            return None
        mode_map = {0: "demo", 1: "contest", 2: "real"}
        return {
            "connected": bool(ti and ti.connected),
            "trade_mode": mode_map.get(getattr(ai, "trade_mode", -1), "unknown"),
            "currency": getattr(ai, "currency", "USD") or "USD",
            "balance": float(getattr(ai, "balance", 0.0)),
            "equity": float(getattr(ai, "equity", 0.0)),
            "margin": float(getattr(ai, "margin", 0.0)),
            "margin_free": float(getattr(ai, "margin_free", 0.0)),
            "leverage": int(getattr(ai, "leverage", 100) or 100),
        }
    finally:
        mt5.shutdown()


def _mt5_server_offset_sec(mt5: Any, tick: Any = None) -> int:
    """Estimate broker server clock offset vs UTC rounded to nearest 15 minutes."""
    now_ts = int(_dt.datetime.now(UTC_TZ).timestamp())
    t = tick
    if t is None:
        for probe in ("EURUSD", "XAUUSD", "GBPUSD"):
            t = mt5.symbol_info_tick(probe)
            if t is not None and getattr(t, "time", 0):
                break
    if t is None or not getattr(t, "time", 0):
        return 0
    return int(round((int(t.time) - now_ts) / 900.0) * 900)


def mt5_read_positions(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]] | None:
    """Read-only snapshot of open positions in MT5."""
    mt5 = _try_mt5_module()
    if mt5 is None or not mt5.initialize():
        return None
    try:
        offset = _mt5_server_offset_sec(mt5)
        pos = mt5.positions_get() or []
        out: list[dict[str, Any]] = []
        for p in pos:
            ts_utc = int(p.time) - offset
            out.append({
                "ticket": int(p.ticket),
                "symbol": str(p.symbol),
                "side": "buy" if p.type == 0 else "sell",
                "volume": float(p.volume),
                "entry": float(p.price_open),
                "sl": float(p.sl),
                "tp": float(p.tp),
                "price_current": float(p.price_current),
                "profit_usd": float(p.profit),
                "time_utc": _dt.datetime.fromtimestamp(ts_utc, UTC_TZ).strftime("%Y-%m-%d %H:%M"),
            })
        return out
    finally:
        mt5.shutdown()


def mt5_read_today_deals(now_utc: _dt.datetime | None = None) -> list[dict[str, Any]] | None:
    """Read-only snapshot of closed deals today (UTC) in MT5."""
    mt5 = _try_mt5_module()
    if mt5 is None or not mt5.initialize():
        return None
    try:
        offset = _mt5_server_offset_sec(mt5)
        dt = (now_utc or _dt.datetime.now(UTC_TZ)).astimezone(UTC_TZ)
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0) + _dt.timedelta(seconds=offset)
        end = dt + _dt.timedelta(seconds=offset + 300)
        deals = mt5.history_deals_get(start, end) or []
        out: list[dict[str, Any]] = []
        for d in deals:
            if getattr(d, "entry", -1) in (1, 2):  # OUT or INOUT
                ts_utc = int(d.time) - offset
                out.append({
                    "ticket": int(d.ticket),
                    "order": int(d.order),
                    "symbol": str(d.symbol),
                    "volume": float(d.volume),
                    "price": float(d.price),
                    "profit_usd": float(d.profit) + float(getattr(d, "commission", 0.0)) + float(getattr(d, "swap", 0.0)),
                    "time_utc": _dt.datetime.fromtimestamp(ts_utc, UTC_TZ).strftime("%Y-%m-%d %H:%M"),
                })
        return out
    finally:
        mt5.shutdown()


def get_symbol_spec(sym: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Get exact contract/pip specification (live MT5 read-only first, else analytical fallback)."""
    spec = default_spec(sym)
    if (cfg or {}).get("data_source") == "yahoo":
        return spec
    mt5 = _try_mt5_module()
    if mt5 is None or not mt5.initialize():
        return spec
    try:
        msym = _resolve_mt5_symbol(mt5, sym, cfg)
        if not msym:
            return spec
        info = mt5.symbol_info(msym)
        tick = mt5.symbol_info_tick(msym)
        if info is None:
            return spec
        digits = int(info.digits)
        point = float(info.point)
        # In FX 5-digit/3-digit, 1 pip = 10 points. For Gold (2 digits), 1 pip = 0.10 (10 points). For Oil (2 digits), 1 pip = 0.01.
        if spec["category"] == "forex" and digits in (3, 5):
            pip_size = round(point * 10.0, digits)
        elif spec["category"] == "metal" and digits == 2 and "XAU" in canonical_symbol(sym):
            pip_size = 0.10
        else:
            pip_size = point
        tick_size = float(info.trade_tick_size) or point
        tick_val = float(info.trade_tick_value)
        pip_value_per_lot = tick_val * (pip_size / tick_size) if tick_val > 0 and tick_size > 0 else None
        bid = float(tick.bid) if tick else None
        ask = float(tick.ask) if tick else None
        spread_pips = round((ask - bid) / pip_size, 2) if (bid and ask and pip_size > 0) else None
        spec.update({
            "mt5_symbol": msym,
            "digits": digits,
            "point": point,
            "pip_size": pip_size,
            "trade_tick_size": tick_size,
            "trade_tick_value": tick_val,
            "pip_value_per_lot": pip_value_per_lot,
            "contract_size": float(info.trade_contract_size),
            "volume_min": float(info.volume_min),
            "volume_step": float(info.volume_step),
            "volume_max": float(info.volume_max),
            "bid": bid,
            "ask": ask,
            "spread_pips": spread_pips,
            "source": "mt5",
        })
        return spec
    finally:
        mt5.shutdown()


def estimate_pip_value_usd(
    sym: str,
    price: float,
    spec: dict[str, Any] | None = None,
    quote_rates: dict[str, float] | None = None,
) -> float:
    """Estimate USD value of 1 pip for 1.00 standard lot."""
    sp = spec or default_spec(sym)
    if sp.get("pip_value_per_lot"):
        return float(sp["pip_value_per_lot"])
    pip_size = float(sp["pip_size"])
    contract = float(sp["contract_size"])
    raw_quote_val = pip_size * contract
    quote_ccy = sp.get("quote_ccy", "USD")
    if quote_ccy == "USD":
        return raw_quote_val
    c = canonical_symbol(sym)
    # Direct quote USDXXX (e.g., USDJPY, USDCAD, USDCHF)
    if c.startswith("USD") and price > 0:
        return raw_quote_val / price
    # Cross pair (e.g., EURGBP, EURJPY): check quote_rates
    rates = quote_rates or {}
    if f"{quote_ccy}USD" in rates and rates[f"{quote_ccy}USD"] > 0:
        return raw_quote_val * rates[f"{quote_ccy}USD"]
    if f"USD{quote_ccy}" in rates and rates[f"USD{quote_ccy}"] > 0:
        return raw_quote_val / rates[f"USD{quote_ccy}"]
    # Approximate fallback if cross conversion rate isn't provided
    if quote_ccy == "JPY":
        return raw_quote_val / 155.0
    return raw_quote_val


# ---------------------------------------------------------------------------
# Market Bars & Quotes (MT5 Read-Only -> Yahoo Finance -> Offline Fixtures)
# ---------------------------------------------------------------------------

def _yahoo_request(path: str) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    last_err: Exception | None = None
    for host in ("query2.finance.yahoo.com", "query1.finance.yahoo.com"):
        url = f"https://{host}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as err:
                last_err = err
                if err.code == 404:
                    raise FxError(f"Yahoo Finance 404 for {path}") from err
                if err.code == 429 and attempt == 0:
                    time.sleep(1.0)
                    continue
                break
            except Exception as err:
                last_err = err
                break
    raise FxError(f"Yahoo Finance request failed for {path}: {last_err}")


def _bars_from_yahoo_payload(payload: dict[str, Any], interval_sec: int, as_of_utc: _dt.datetime | None = None) -> dict[str, Any]:
    res = (payload.get("chart") or {}).get("result")
    if not res:
        raise FxError("Yahoo chart response had no result")
    item = res[0]
    meta = item.get("meta") or {}
    ts_list = item.get("timestamp") or []
    quote = ((item.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    vols = quote.get("volume") or []

    cutoff = int(as_of_utc.timestamp()) if as_of_utc else None
    bars: list[dict[str, Any]] = []
    for i, ts in enumerate(ts_list):
        if ts is None:
            continue
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        c = closes[i] if i < len(closes) else None
        if None in (o, h, l, c):
            continue
        if cutoff is not None and (ts + interval_sec) > cutoff:
            continue
        v = vols[i] if i < len(vols) and vols[i] is not None else 0
        bars.append({
            "ts": int(ts),
            "time_utc": _dt.datetime.fromtimestamp(ts, UTC_TZ).strftime("%Y-%m-%d %H:%M"),
            "open": float(o),
            "high": float(h),
            "low": float(l),
            "close": float(c),
            "volume": float(v),
        })
    return {
        "source": "yahoo",
        "price": float(meta.get("regularMarketPrice")) if meta.get("regularMarketPrice") is not None else (bars[-1]["close"] if bars else None),
        "prev_close": float(meta.get("chartPreviousClose") or meta.get("previousClose") or 0.0) or None,
        "bars": bars,
    }


def _load_offline_file(path: Path) -> dict[str, Any]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def fetch_bars(
    sym: str,
    interval: str = "5m",
    rng: str = "5d",
    count: int = 500,
    offline: str | Path | None = None,
    as_of_utc: _dt.datetime | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch OHLCV bars from offline fixture, MT5 (read-only), or Yahoo Finance."""
    interval_sec_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}
    if interval not in interval_sec_map:
        raise FxError(f"unsupported interval {interval!r}; use 1m, 5m, 15m, 1h, or 1d")
    isec = interval_sec_map[interval]
    c = canonical_symbol(sym)

    if offline:
        p = Path(offline)
        if p.is_dir():
            candidates = [p / f"{c}.json", p / f"{c}.json.gz", p / f"{to_yahoo_symbol(c)}.json", p / f"{to_yahoo_symbol(c)}.json.gz"]
            found = next((x for x in candidates if x.exists()), None)
            if not found:
                raise FxError(f"no offline fixture for {c} in {p}")
            p = found
        payload = _load_offline_file(p)
        if "bars" in payload:
            bars = [b for b in payload["bars"] if as_of_utc is None or (b["ts"] + isec) <= int(as_of_utc.timestamp())]
            return {"symbol": c, "source": "offline", "price": payload.get("price") or (bars[-1]["close"] if bars else None), "prev_close": payload.get("prev_close"), "bars": bars}
        parsed = _bars_from_yahoo_payload(payload, isec, as_of_utc)
        parsed["symbol"] = c
        return parsed

    # Try MT5 read-only when allowed and not historical-backdated far beyond MT5 buffer
    use_mt5 = (cfg or {}).get("data_source", "auto") in ("auto", "mt5")
    if use_mt5 and as_of_utc is None:
        mt5 = _try_mt5_module()
        if mt5 is not None and mt5.initialize():
            try:
                msym = _resolve_mt5_symbol(mt5, sym, cfg)
                if msym:
                    tf_map = {
                        "1m": mt5.TIMEFRAME_M1,
                        "5m": mt5.TIMEFRAME_M5,
                        "15m": mt5.TIMEFRAME_M15,
                        "1h": mt5.TIMEFRAME_H1,
                        "1d": mt5.TIMEFRAME_D1,
                    }
                    rates = mt5.copy_rates_from_pos(msym, tf_map[interval], 0, count)
                    tick = mt5.symbol_info_tick(msym)
                    offset = _mt5_server_offset_sec(mt5, tick)
                    if rates is not None and len(rates) > 0:
                        now_ts = int(_dt.datetime.now(UTC_TZ).timestamp())
                        bars: list[dict[str, Any]] = []
                        for r in rates:
                            ts = int(r["time"]) - offset
                            # MT5 copy_rates returns complete + current forming bar; drop forming bar for intraday
                            if interval != "1d" and (ts + isec) > now_ts:
                                continue
                            bars.append({
                                "ts": ts,
                                "time_utc": _dt.datetime.fromtimestamp(ts, UTC_TZ).strftime("%Y-%m-%d %H:%M"),
                                "open": float(r["open"]),
                                "high": float(r["high"]),
                                "low": float(r["low"]),
                                "close": float(r["close"]),
                                "volume": float(r["tick_volume"]),
                            })
                        if bars:
                            # Fetch daily bar for prev_close
                            d_rates = mt5.copy_rates_from_pos(msym, mt5.TIMEFRAME_D1, 0, 2)
                            prev_close = float(d_rates[0]["close"]) if d_rates is not None and len(d_rates) >= 2 else None
                            price = float(tick.bid) if tick and tick.bid else bars[-1]["close"]
                            return {
                                "symbol": c,
                                "mt5_symbol": msym,
                                "source": "mt5",
                                "price": price,
                                "bid": float(tick.bid) if tick else price,
                                "ask": float(tick.ask) if tick else price,
                                "prev_close": prev_close,
                                "bars": bars,
                            }
            finally:
                mt5.shutdown()

    if (cfg or {}).get("data_source") == "mt5":
        raise FxError(f"MT5 could not provide bars for {c}")

    ysym = to_yahoo_symbol(sym)
    payload = _yahoo_request(f"/v8/finance/chart/{ysym}?range={rng}&interval={interval}")
    parsed = _bars_from_yahoo_payload(payload, isec, as_of_utc)
    parsed["symbol"] = c
    return parsed


def fetch_quote(sym: str, offline: str | Path | None = None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fetch latest quote (Bid/Ask/Spread if MT5, else Yahoo last/prev_close)."""
    spec = get_symbol_spec(sym, cfg) if not offline else default_spec(sym)
    data = fetch_bars(sym, interval="5m", rng="5d", count=30, offline=offline, cfg=cfg)
    price = data.get("price")
    prev = data.get("prev_close")
    pct = round((price / prev - 1.0) * 100.0, 2) if (price and prev) else None
    return {
        "symbol": canonical_symbol(sym),
        "category": spec["category"],
        "digits": spec["digits"],
        "pip_size": spec["pip_size"],
        "price": price,
        "bid": data.get("bid") or spec.get("bid") or price,
        "ask": data.get("ask") or spec.get("ask") or price,
        "spread_pips": spec.get("spread_pips"),
        "prev_close": prev,
        "pct_change": pct,
        "source": data["source"],
        "as_of_utc": _dt.datetime.now(UTC_TZ).strftime("%Y-%m-%d %H:%M"),
    }
