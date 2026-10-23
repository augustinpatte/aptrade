"""Daily prices from sources other than Alpaca, over plain HTTPS (no extra package).

- Yahoo: no key, covers US and European listings. Unofficial: Yahoo does not document
  or promise this endpoint, it can change or rate-limit without notice, and its terms
  restrict use to personal use. Good enough to start; do not build a business on it.
- Tiingo: official API, free key (tiingo.com), US stocks and ETFs, adjusted prices.

Every function returns bars in the same shape as the Alpaca loader: a DataFrame indexed
by UTC timestamps with open, high, low, close, volume, adjusted for splits and dividends."""
from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import pandas as pd

COLS = ["open", "high", "low", "close", "volume"]
UA = {"User-Agent": "Mozilla/5.0 (aptrade; +https://github.com/augustinpatte/aptrade)"}


class SourceError(RuntimeError):
    pass


def _ssl_context() -> ssl.SSLContext:
    """Python from python.org on macOS ships without root certificates until one runs
    "Install Certificates.command": use certifi's bundle so HTTPS works everywhere."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def http_json(url: str, headers: dict | None = None, method: str = "GET", body: dict | None = None,
              timeout: float = 20.0):
    """One HTTP call returning parsed JSON. Tests replace this function."""
    data = json.dumps(body).encode() if body is not None else None
    h = {**UA, **(headers or {})}
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            raw = r.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode(errors="replace")
        raise SourceError(f"{method} {url.split('?')[0]} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SourceError(f"{method} {url.split('?')[0]} unreachable: {exc.reason}") from exc
    return json.loads(raw) if raw else None


def _noon(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """One timestamp per trading day, at 12:00 UTC: whatever the time zone it is read in
    (New York for the panel), it stays on the same calendar date."""
    return idx.normalize() + pd.Timedelta(hours=12)


def _ts(d) -> int:
    d = pd.Timestamp(d)
    d = d.tz_localize("UTC") if d.tzinfo is None else d.tz_convert("UTC")
    return int(d.timestamp())


# ------------------------------------------------------------------ yahoo

def yahoo_daily(symbol: str, start, end) -> pd.DataFrame:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
           f"?period1={_ts(start)}&period2={_ts(end) + 86400}&interval=1d&events=div%2Csplit"
           f"&includeAdjustedClose=true")
    doc = http_json(url)
    res = (doc or {}).get("chart", {}).get("result")
    if not res:
        err = (doc or {}).get("chart", {}).get("error")
        raise SourceError(f"Yahoo has no data for {symbol}: {err}")
    return chart_frame(res[0])


def chart_frame(res: dict) -> pd.DataFrame:
    """A Yahoo v8 chart result as adjusted daily bars (O/H/L scaled like the close)."""
    if not res.get("timestamp"):
        return pd.DataFrame(columns=COLS)
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({c: q.get(c) for c in COLS}, index=pd.to_datetime(res["timestamp"], unit="s", utc=True))
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    if adj is not None:
        factor = pd.Series(adj, index=df.index) / df["close"]
        for c in ("open", "high", "low", "close"):
            df[c] = df[c] * factor
    df.index = _noon(df.index)
    return df.dropna(subset=["close"]).astype(float).sort_index()


def yahoo_last(symbol: str) -> tuple[float, str]:
    """Latest price and its currency (as Yahoo reports it: USD, EUR, GBp...)."""
    doc = http_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
                    f"?range=5d&interval=1d")
    res = (doc or {}).get("chart", {}).get("result")
    if not res:
        raise SourceError(f"Yahoo has no price for {symbol}")
    meta = res[0]["meta"]
    price = meta.get("regularMarketPrice")
    if not price:
        raise SourceError(f"Yahoo returned no current price for {symbol}")
    return float(price), str(meta.get("currency", ""))


# ------------------------------------------------------------------ tiingo

def tiingo_daily(symbol: str, start, end, token: str) -> pd.DataFrame:
    if not token:
        raise SourceError("TIINGO_API_KEY is not set (free key at tiingo.com, then put it in .env)")
    d0, d1 = pd.Timestamp(start).strftime("%Y-%m-%d"), pd.Timestamp(end).strftime("%Y-%m-%d")
    url = (f"https://api.tiingo.com/tiingo/daily/{urllib.parse.quote(symbol.lower())}/prices"
           f"?startDate={d0}&endDate={d1}&format=json&resampleFreq=daily")
    rows = http_json(url, headers={"Authorization": f"Token {token}"})
    if not rows:
        return pd.DataFrame(columns=COLS)
    df = pd.DataFrame(rows)
    out = pd.DataFrame({"open": df["adjOpen"], "high": df["adjHigh"], "low": df["adjLow"],
                        "close": df["adjClose"], "volume": df["adjVolume"]})
    out.index = _noon(pd.DatetimeIndex(pd.to_datetime(df["date"], utc=True)))
    return out.astype(float).sort_index()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
