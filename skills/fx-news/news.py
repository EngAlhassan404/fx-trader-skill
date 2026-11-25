"""Macro, Forex, Gold & Oil News Monitor + DXY / US10Y / Commodity Pulse."""

from __future__ import annotations

import argparse
import datetime as _dt
import email.utils
import json
import ssl
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import fx_core as fx  # noqa: E402

MACRO_PULSE = ("DXY", "US10Y", "XAUUSD", "USOIL", "EURUSD")

TAGS: dict[str, tuple[str, ...]] = {
    "central_bank": ("fed", "fomc", "powell", "ecb", "lagarde", "boe", "boj", "rate cut", "rate hike", "hawkish", "dovish", "central bank"),
    "inflation_cpi": ("cpi", "inflation", "pce", "ppi", "consumer price"),
    "jobs_nfp": ("nonfarm", "nfp", "payroll", "unemployment", "jobless"),
    "opec_oil": ("opec", "crude", "brent", "wti", "oil", "barrel", "pipeline", "inventory", "eia"),
    "gold_safe_haven": ("gold", "bullion", "xau", "safe haven", "treasury", "yield"),
    "geopolitics": ("tariff", "sanction", "war", "ceasefire", "strike", "middle east", "china", "trump"),
}


def tag_headline(text: str) -> list[str]:
    low = text.lower()
    return [k for k, words in TAGS.items() if any(w in low for w in words)]


def fetch_yahoo_rss(sym: str, offline: Path | None = None) -> list[dict[str, Any]]:
    ysym = fx.to_yahoo_symbol(sym)
    if offline:
        p = offline / f"rss-{sym}.xml" if offline.is_dir() else offline
        if not p.exists():
            return []
        raw = p.read_bytes()
    else:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ysym}&region=US&lang=en-US"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            raw = resp.read()
    root = ET.fromstring(raw)
    items: list[dict[str, Any]] = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        pub = (node.findtext("pubDate") or "").strip()
        guid = (node.findtext("guid") or link or title).strip()
        ts = 0
        if pub:
            try:
                ts = int(email.utils.parsedate_to_datetime(pub).astimezone(fx.UTC_TZ).timestamp())
            except Exception:
                ts = 0
        items.append({
            "id": f"rss:{guid}",
            "symbol": fx.canonical_symbol(sym),
            "title": title,
            "link": link,
            "ts": ts,
            "time_utc": _dt.datetime.fromtimestamp(ts, fx.UTC_TZ).strftime("%Y-%m-%d %H:%M") if ts else "",
            "tags": tag_headline(title),
        })
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Macro, Forex, Gold & Oil News Monitor.")
    parser.add_argument("--symbols", help="Comma-separated symbols (default: watchlist/plan + DXY,US10Y,XAUUSD,USOIL)")
    parser.add_argument("--hours", type=int, default=24, help="Lookback hours (default 24)")
    parser.add_argument("--all", action="store_true", help="Show seen items too")
    parser.add_argument("--offline", help="Offline fixture directory or RSS XML")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    base = Path.cwd()
    cfg = fx.load_config(base)
    syms: list[str] = []
    if args.symbols:
        syms = [fx.canonical_symbol(s) for s in args.symbols.split(",") if s.strip()]
    else:
        wl = fx.read_json(fx.work_dir(base) / "watchlist.json") or {}
        syms.extend(h["symbol"] for h in wl.get("hits", [])[:6])
        plan = fx.read_json(fx.work_dir(base) / "plan.json")
        if plan and plan.get("symbol"):
            syms.append(plan["symbol"])
        for m in ("XAUUSD", "USOIL", "EURUSD"):
            if m not in syms:
                syms.append(m)

    # Macro pulse quotes
    pulse: list[dict[str, Any]] = []
    if not args.offline:
        for m in MACRO_PULSE:
            try:
                q = fx.fetch_quote(m, cfg=cfg)
                pulse.append(q)
            except Exception:
                pass

    state_file = fx.state_dir(base) / "news.json"
    state = fx.read_json(state_file) or {"seen": {}}
    seen: dict[str, int] = state.get("seen", {})
    cutoff = int(_dt.datetime.now(fx.UTC_TZ).timestamp()) - args.hours * 3600

    items: list[dict[str, Any]] = []
    for s in syms:
        try:
            for it in fetch_yahoo_rss(s, Path(args.offline) if args.offline else None):
                if it["ts"] and it["ts"] < cutoff:
                    continue
                if not args.all and it["id"] in seen:
                    continue
                items.append(it)
        except Exception:
            continue

    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    now_ts = int(_dt.datetime.now(fx.UTC_TZ).timestamp())
    for it in items:
        seen[it["id"]] = now_ts
    fx.write_json(state_file, {"seen": {k: v for k, v in seen.items() if now_ts - v < 30 * 86400}})

    payload = {"pulse": pulse, "items": items}
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    if pulse:
        print("Macro Pulse:")
        for p in pulse:
            pct_str = f" ({p['pct_change']:+.2f}%)" if p.get("pct_change") is not None else ""
            print(f"  {p['symbol']:<8} {fx.fmt_price(p['price'], p['digits'])}{pct_str}")
    if not items:
        print(f"No new headlines in the last {args.hours}h for {', '.join(syms)}.")
        return 0
    print(f"Headlines ({len(items)} new):")
    for it in items[:20]:
        tag_s = f" [{', '.join(it['tags'])}]" if it["tags"] else ""
        print(f"  {it['time_utc']} UTC | {it['symbol']:<7} | {it['title']}{tag_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
