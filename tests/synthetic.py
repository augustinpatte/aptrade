"""Synthetic 5-minute bars for end-to-end tests.

A pure random walk has no edge by construction, so the pipeline must report none
(and lose about the costs). With `drift_after_breakout`, prices keep drifting the
way of an opening-range breakout: a planted edge the pipeline must find. A tool
that cannot tell these two apart cannot be trusted on real data."""
from __future__ import annotations

import numpy as np
import pandas as pd

from aptrade.config import NY, SESSION_BARS

SUB = 5          # one-minute steps per bar


def make_bars(symbol_seed: int, days: int = 300, sigma: float = 0.0012,
              drift_after_breakout: float = 0.0, or_bars: int = 3, start="2024-01-02") -> pd.DataFrame:
    rng = np.random.default_rng(symbol_seed)
    dates = pd.bdate_range(start, periods=days)
    frames = []
    price = 100.0 + 50 * rng.random()
    for d in dates:
        o = np.empty(SESSION_BARS); h = np.empty(SESSION_BARS); l = np.empty(SESSION_BARS); c = np.empty(SESSION_BARS)
        or_hi, or_lo, direction = -np.inf, np.inf, 0
        for i in range(SESSION_BARS):
            mu = drift_after_breakout * direction
            steps = price * np.cumprod(1 + rng.normal(mu / SUB, sigma / np.sqrt(SUB), SUB))
            o[i], c[i] = price, steps[-1]
            h[i], l[i] = max(price, steps.max()), min(price, steps.min())
            price = c[i]
            if i < or_bars:
                or_hi, or_lo = max(or_hi, h[i]), min(or_lo, l[i])
            elif direction == 0 and c[i] > or_hi:
                direction = 1
            elif direction == 0 and c[i] < or_lo:
                direction = -1
        idx = pd.date_range(pd.Timestamp(f"{d.date()} 09:30", tz=NY), periods=SESSION_BARS, freq="5min")
        frames.append(pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": 1000}, index=idx))
        price *= 1 + rng.normal(0, 0.01)                       # overnight gap
    df = pd.concat(frames)
    df.index = df.index.tz_convert("UTC")
    return df


def universe(n: int = 8, **kw) -> dict[str, pd.DataFrame]:
    return {f"S{i:02d}": make_bars(100 + i, **kw) for i in range(n)}
