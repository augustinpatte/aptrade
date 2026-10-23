"""Synthetic daily bars for the swing tests.

noise:  independent returns, no drift, no persistence. No strategy can beat
        buying SPY here except by luck, so the verdict must not be PASS.
trend:  every asset alternates long up and down regimes (persistent drift), SPY
        included. Buying SPY rides the crashes; a trend follower steps aside. A
        tool that does not find this edge is broken."""
from __future__ import annotations

import numpy as np
import pandas as pd

from aptrade.config import NY


def make_daily(symbols, days=1500, kind="noise", seed=0, start="2016-01-04"):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=days)
    out = {}
    for k, s in enumerate(symbols):
        if s == "BIL":
            r = np.full(days, 0.00008)
            vol = 0.0002
        else:
            vol = 0.008 + 0.006 * rng.random()
            r = rng.normal(0, vol, days)
            if kind == "trend":
                regime = 120 + 40 * k % 60
                sign = np.where((np.arange(days) // regime + k) % 2 == 0, 1, -1)
                r = r + sign * 0.0015
        close = 100 * np.cumprod(1 + r)
        open_ = close / (1 + rng.normal(0, vol / 3, days))
        idx = pd.DatetimeIndex([pd.Timestamp(f"{d.date()} 00:00", tz=NY) for d in dates]).tz_convert("UTC")
        out[s] = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.002,
                               "low": np.minimum(open_, close) * 0.998, "close": close, "volume": 1e6}, index=idx)
    return out
