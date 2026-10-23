"""Market data: Alpaca historical 5-minute bars with a local cache, plus a Yahoo
chart JSON reader used by the parity test.

Every loader returns a DataFrame indexed by bar START time (UTC, tz-aware) with
columns open, high, low, close, volume."""
from __future__ import annotations

import gzip
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

COLS = ["open", "high", "low", "close", "volume"]


class DataError(RuntimeError):
    pass


# ------------------------------------------------------------------ cache

TIMEFRAMES = ("5m", "1d")


def _cache_path(data_dir: Path, feed: str, symbol: str, timeframe: str = "5m") -> Path:
    return data_dir / "cache" / feed / f"{symbol}_{timeframe}.csv.gz"


def _read_cache(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def _utc(x) -> pd.Timestamp:
    """Any date or datetime, naive (taken as UTC) or tz-aware, as a UTC Timestamp."""
    ts = pd.Timestamp(x)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _covers(df: pd.DataFrame, start: datetime, end: datetime) -> bool:
    if df is None or df.empty:
        return False
    # four days of slack on each side: weekends and holidays have no bars
    return df.index.min() <= _utc(start) + pd.Timedelta(days=4) and \
        df.index.max() >= _utc(end) - pd.Timedelta(days=4)


# ------------------------------------------------------------------ alpaca

def _alpaca_fetch(symbols, start, end, feed, api_key, secret_key, timeframe="5m") -> dict[str, pd.DataFrame]:
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    client = StockHistoricalDataClient(api_key, secret_key)
    req = StockBarsRequest(
        symbol_or_symbols=list(symbols),
        timeframe=TimeFrame(5, TimeFrameUnit.Minute) if timeframe == "5m" else TimeFrame(1, TimeFrameUnit.Day),
        start=start,
        end=end,
        adjustment=Adjustment.ALL,          # splits and dividends folded into past prices
        feed=DataFeed.SIP if feed == "sip" else DataFeed.IEX,
    )
    df = client.get_stock_bars(req).df
    out = {}
    if df is None or df.empty:
        return out
    for sym, part in df.groupby(level="symbol"):
        part = part.droplevel("symbol")[COLS].copy()
        part.index = pd.to_datetime(part.index, utc=True)
        out[sym] = part.sort_index()
    return out


DAILY_SOURCES = ("alpaca", "yahoo", "tiingo")


def daily_source(settings) -> str:
    """APTRADE_DATA picks the source of daily prices. 'auto' (default): Alpaca when its
    keys are set, else Tiingo when TIINGO_API_KEY is set, else Yahoo (no key needed)."""
    import os
    s = (os.environ.get("APTRADE_DATA") or "auto").strip().lower()
    if s == "auto":
        if settings.api_key and settings.secret_key:
            return "alpaca"
        return "tiingo" if os.environ.get("TIINGO_API_KEY") else "yahoo"
    if s not in DAILY_SOURCES:
        raise DataError(f"APTRADE_DATA must be auto or one of {DAILY_SOURCES}, not {s!r}")
    return s


def _other_daily(symbols, start, end, settings, source, refresh) -> tuple[dict, str]:
    import os

    from . import sources
    out = {}
    for s in symbols:
        path = _cache_path(settings.data_dir, source, s, "1d")
        cached = None if refresh else _read_cache(path)
        if not _covers(cached, start, end):
            print(f"  fetching {s} ({source}, 1d)", file=sys.stderr)
            try:
                if source == "yahoo":
                    cached = sources.yahoo_daily(s, start, end)
                else:
                    cached = sources.tiingo_daily(s, start, end, os.environ.get("TIINGO_API_KEY", ""))
            except sources.SourceError as exc:
                raise DataError(str(exc)) from exc
            if cached.empty:
                print(f"  WARNING: no bars returned for {s}", file=sys.stderr)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            cached.to_csv(path, compression="gzip")
        out[s] = cached[(cached.index >= _utc(start)) & (cached.index <= _utc(end))]
    return out, source


def load_bars(symbols, start: datetime, end: datetime, settings, feed: str = "sip",
              batch: int = 10, refresh: bool = False, timeframe: str = "5m") -> tuple[dict[str, pd.DataFrame], str]:
    """Bars for every symbol, from the cache when it covers [start, end], else from
    Alpaca. Returns (bars by symbol, the feed actually used).

    SIP is the consolidated tape (every US exchange). If the account cannot read it,
    this falls back to IEX and says so: IEX is a single exchange, so its 5-minute
    bars are thinner and many sessions will be dropped as incomplete."""
    if timeframe == "1d" and daily_source(settings) != "alpaca":
        return _other_daily(symbols, start, end, settings, daily_source(settings), refresh)
    out, missing = {}, []
    for s in symbols:
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {TIMEFRAMES}")
        cached = None if refresh else _read_cache(_cache_path(settings.data_dir, feed, s, timeframe))
        if _covers(cached, start, end):
            out[s] = cached[(cached.index >= _utc(start)) & (cached.index <= _utc(end))]
        else:
            missing.append(s)
    if not missing:
        return out, feed
    if not (settings.api_key and settings.secret_key):
        raise DataError("ALPACA_API_KEY and ALPACA_SECRET_KEY are not set (see .env.example)")

    used = feed
    for i in range(0, len(missing), batch):
        chunk = missing[i:i + batch]
        print(f"  fetching {', '.join(chunk)} ({used}, {timeframe})", file=sys.stderr)
        try:
            got = _alpaca_fetch(chunk, start, end, used, settings.api_key, settings.secret_key, timeframe)
        except Exception as exc:  # the SDK raises APIError, the message names the cause
            if used == "sip" and "subscription" in str(exc).lower():
                print("  WARNING: this account cannot read SIP data, falling back to IEX. "
                      "Results on IEX bars are less reliable.", file=sys.stderr)
                used = "iex"
                got = _alpaca_fetch(chunk, start, end, used, settings.api_key, settings.secret_key, timeframe)
            else:
                raise DataError(f"Alpaca request failed for {chunk}: {exc}") from exc
        for sym, df in got.items():
            path = _cache_path(settings.data_dir, used, sym, timeframe)
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(path, compression="gzip")
            out[sym] = df[(df.index >= _utc(start)) & (df.index <= _utc(end))]   # same window as a cache read
        for sym in chunk:
            if sym not in got:
                print(f"  WARNING: no bars returned for {sym}", file=sys.stderr)
    return out, used


# ------------------------------------------------------------------ yahoo (tests)

def load_yahoo_chart(path: str | Path) -> pd.DataFrame:
    """A saved Yahoo v8 chart JSON (.json or .json.gz) as a bar DataFrame."""
    p = Path(path)
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rt") as fh:
        doc = json.load(fh)
    res = doc["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({c: q.get(c) for c in COLS},
                      index=pd.to_datetime(res["timestamp"], unit="s", utc=True))
    return df.dropna(subset=["open", "high", "low", "close"]).astype(float)
