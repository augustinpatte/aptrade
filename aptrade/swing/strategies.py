"""The two pre-registered strategies (PREREGISTRATION.md). Do not change the rules
here without a new pre-registration.

Contract with the engine:
  prepare(closes)            compute indicators on the full close panel. Every
                             indicator at row i must use rows <= i only (rolling,
                             shift); tests perturb the future to check this.
  reset()                    clear state before a run.
  on_close(i, weights, syms) closes up to row i are known; return target weights
                             for the next open, or None to hold."""
from __future__ import annotations

import numpy as np
import pandas as pd

TREND_UNIVERSE = ["SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ", "TLT", "IEF", "TIP", "LQD", "HYG",
                  "GLD", "SLV", "DBC", "UUP"]
MEANREV_UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP",
                    "XLU", "XLB"]
WARMUP = 260            # trading days of history before the first scored day (12-month lookback, 200-day SMA)
VOL_WINDOW = 60


def rsi_wilder(closes: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    d = closes.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    down = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / down.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.where(down > 0, 100.0).where(up.notna())


def period_ends(dates: pd.DatetimeIndex, freq: str) -> np.ndarray:
    """True on the last trading day of each week ('W'), month ('M'), quarter ('Q') or
    year ('Y'). Uses only the calendar, which is known in advance, never prices."""
    key = dates.to_period({"W": "W-FRI", "M": "M", "Q": "Q", "Y": "Y"}[freq])
    nxt = np.append(key[1:].to_numpy(), None)
    return np.array([k != n for k, n in zip(key.to_numpy(), nxt)])


class TrendFollowing:
    """H1: hold an ETF while its total return over the lookback is positive; inverse-
    volatility weights over the whole universe; downtrends hand their weight to cash."""
    name = "trend"

    def __init__(self, lookback: int = 252, rebalance: str = "M", universe=None):
        if lookback not in (63, 126, 252) or rebalance not in ("W", "M"):
            raise ValueError("pre-registered grid: lookback in {63, 126, 252}, rebalance in {W, M}")
        self.lookback, self.rebalance = lookback, rebalance
        self.universe = list(universe or TREND_UNIVERSE)

    def params(self) -> dict:
        return {"lookback": self.lookback, "rebalance": self.rebalance}

    def label(self) -> str:
        return f"trend lookback={self.lookback}d rebalance={'weekly' if self.rebalance == 'W' else 'monthly'}"

    def prepare(self, closes: pd.DataFrame):
        c = closes[self.universe]
        self.mom = (c / c.shift(self.lookback) - 1).to_numpy()
        self.vol = c.pct_change().rolling(VOL_WINDOW).std().to_numpy()
        self.ends = period_ends(closes.index, self.rebalance)

    def reset(self):
        pass

    def on_close(self, i, weights, symbols):
        if not self.ends[i]:
            return None
        inv = 1 / self.vol[i]
        if not np.isfinite(inv).all():
            return None
        w = inv / inv.sum()
        w = np.where(self.mom[i] > 0, w, 0.0)
        return dict(zip(self.universe, w))


class MeanReversion:
    """H2: buy an ETF above its 200-day average after a 2-day RSI washout; sell when it
    closes above its 5-day average or after max_hold days. 5 slots of 20%."""
    name = "meanrev"
    SLOTS = 5

    def __init__(self, rsi_threshold: float = 10, max_hold: int = 10, universe=None):
        if rsi_threshold not in (5, 10, 20) or max_hold not in (5, 10):
            raise ValueError("pre-registered grid: rsi in {5, 10, 20}, max_hold in {5, 10}")
        self.thr, self.max_hold = rsi_threshold, max_hold
        self.universe = list(universe or MEANREV_UNIVERSE)

    def params(self) -> dict:
        return {"rsi_threshold": self.thr, "max_hold": self.max_hold}

    def label(self) -> str:
        return f"meanrev rsi<{self.thr} max_hold={self.max_hold}d"

    def prepare(self, closes: pd.DataFrame):
        c = closes[self.universe]
        self.c = c.to_numpy()
        self.sma200 = c.rolling(200).mean().to_numpy()
        self.sma5 = c.rolling(5).mean().to_numpy()
        self.rsi = rsi_wilder(c, 2).to_numpy()

    def reset(self):
        self.entry: dict[str, int] = {}

    def on_close(self, i, weights, symbols):
        changed = False
        exited = set()
        for s in list(self.entry):
            j = self.universe.index(s)
            if self.c[i, j] > self.sma5[i, j] or i - self.entry[s] >= self.max_hold:
                del self.entry[s]
                exited.add(s)
                changed = True
        free = self.SLOTS - len(self.entry)
        if free > 0:
            cands = [(self.rsi[i, j], s) for j, s in enumerate(self.universe)
                     if s not in self.entry and s not in exited and np.isfinite(self.sma200[i, j]) and np.isfinite(self.rsi[i, j])
                     and self.c[i, j] > self.sma200[i, j] and self.rsi[i, j] < self.thr]
            for _, s in sorted(cands)[:free]:
                self.entry[s] = i
                changed = True
        if not changed:
            return None
        # held positions keep their current weight (no needless trading); new ones get one slot
        out = {}
        for s in self.entry:
            out[s] = weights.get(s, 0.0) if self.entry[s] < i else 1 / self.SLOTS
        return out


class Blend:
    """H3: 50% SPY + 50% the trend sleeve (63 days, monthly), back to 50/50 at every
    month-end. Fixed by the addendum in PREREGISTRATION.md: no parameter to tune."""
    name = "blend"
    SPY_WEIGHT = 0.5

    def __init__(self):
        self.trend = TrendFollowing(63, "M")
        self.universe = sorted(set(self.trend.universe) | {"SPY"})

    def params(self) -> dict:
        return {"spy_weight": self.SPY_WEIGHT, "trend": self.trend.params()}

    def label(self) -> str:
        return "blend 50% SPY + 50% trend lookback=63d monthly"

    def prepare(self, closes: pd.DataFrame):
        self.trend.prepare(closes)

    def reset(self):
        self.trend.reset()

    def on_close(self, i, weights, symbols):
        if not self.trend.ends[i]:
            return None
        sleeve = self.trend.on_close(i, weights, symbols)
        if sleeve is None:             # volatility not available yet: trend half waits in cash
            sleeve = {}
        out = {s: (1 - self.SPY_WEIGHT) * w for s, w in sleeve.items()}
        out["SPY"] = out.get("SPY", 0.0) + self.SPY_WEIGHT
        return out


class Allocation:
    """A fixed allocation, no signal: x% SPY + the rest in the 15 diversified ETFs at
    inverse-volatility weights, back to target at every month-end. The app's slider.
    With spy_weight 0.5 it is exactly H4."""
    name = "alloc"

    def __init__(self, spy_weight: float = 0.5):
        if not 0 <= spy_weight <= 1:
            raise ValueError("spy_weight must be between 0 and 1")
        self.SPY_WEIGHT = spy_weight
        self.universe = list(TREND_UNIVERSE)

    def params(self) -> dict:
        return {"spy_weight": self.SPY_WEIGHT, "sleeve": "inverse volatility, no signal"}

    def label(self) -> str:
        return f"{100 * self.SPY_WEIGHT:.0f}% SPY + {100 * (1 - self.SPY_WEIGHT):.0f}% diversified ETFs (no signal)"

    def prepare(self, closes: pd.DataFrame):
        c = closes[self.universe]
        self.vol = c.pct_change().rolling(VOL_WINDOW).std().to_numpy()
        self.ends = period_ends(closes.index, "M")

    def reset(self):
        pass

    def on_close(self, i, weights, symbols):
        if not self.ends[i]:
            return None
        inv = 1 / self.vol[i]
        if not np.isfinite(inv).all():
            return None
        w = inv / inv.sum()
        out = {s: (1 - self.SPY_WEIGHT) * x for s, x in zip(self.universe, w)}
        out["SPY"] = out.get("SPY", 0.0) + self.SPY_WEIGHT
        return out


class StaticBlend(Allocation):
    """H4, the control: H3 without the trend signal. 50% SPY + 50% the 15 ETFs."""
    name = "static"

    def __init__(self):
        super().__init__(0.5)

    def label(self) -> str:
        return "static 50% SPY + 50% diversified ETFs (no signal)"


class CustomAllocation:
    """Any fixed weights over any tickers, rebalanced monthly, quarterly, yearly or never.
    Whatever is not allocated sits in BIL (cash)."""
    name = "custom"

    def __init__(self, weights: dict, rebalance: str = "Q"):
        w = {s.upper(): float(v) for s, v in weights.items() if float(v) > 0}
        if not w:
            raise ValueError("give at least one ticker with a positive weight")
        if sum(w.values()) > 1 + 1e-9:
            raise ValueError(f"weights add up to {100 * sum(w.values()):.0f}%: at most 100% (no leverage)")
        if rebalance not in ("M", "Q", "Y", "none"):
            raise ValueError("rebalance must be M, Q, Y or none")
        self.weights, self.rebalance = w, rebalance
        self.universe = sorted(w)

    def params(self) -> dict:
        return {"weights": self.weights, "rebalance": self.rebalance}

    def label(self) -> str:
        return " + ".join(f"{100 * v:.0f}% {s}" for s, v in sorted(self.weights.items(), key=lambda x: -x[1]))

    def prepare(self, closes: pd.DataFrame):
        self.ends = period_ends(closes.index, self.rebalance) if self.rebalance != "none" else None

    def reset(self):
        self.started = False

    def on_close(self, i, weights, symbols):
        if not self.started:
            self.started = True
            return dict(self.weights)
        if self.ends is not None and self.ends[i]:
            return dict(self.weights)
        return None


class Rotation:
    """H5: each month, the top 3 of the 15 ETFs by 12-month return, 1/3 each, only if
    they beat cash (BIL) over the same 12 months; otherwise that slot stays in cash."""
    name = "rotation"
    LOOKBACK = 252
    TOP = 3

    def __init__(self):
        self.universe = list(TREND_UNIVERSE)

    def params(self) -> dict:
        return {"lookback": self.LOOKBACK, "top": self.TOP, "absolute_filter": "beats BIL"}

    def label(self) -> str:
        return "rotation top 3 of 15 by 12-month return, if above cash"

    def prepare(self, closes: pd.DataFrame):
        c = closes[self.universe]
        self.mom = (c / c.shift(self.LOOKBACK) - 1).to_numpy()
        self.cash_mom = (closes["BIL"] / closes["BIL"].shift(self.LOOKBACK) - 1).to_numpy()
        self.ends = period_ends(closes.index, "M")

    def reset(self):
        pass

    def on_close(self, i, weights, symbols):
        if not self.ends[i] or not np.isfinite(self.mom[i]).all() or not np.isfinite(self.cash_mom[i]):
            return None
        order = np.argsort(-self.mom[i], kind="stable")[:self.TOP]
        return {self.universe[j]: 1 / self.TOP for j in order if self.mom[i, j] > self.cash_mom[i]}


def make(strategy: str, **kw):
    if strategy == "blend":
        return Blend()
    if strategy == "static":
        return StaticBlend()
    if strategy == "alloc":
        return Allocation(kw.get("spy_weight", 0.5))
    if strategy == "rotation":
        return Rotation()
    if strategy == "trend":
        return TrendFollowing(**{k: v for k, v in kw.items() if k in ("lookback", "rebalance")})
    if strategy == "meanrev":
        return MeanReversion(**{k: v for k, v in kw.items() if k in ("rsi_threshold", "max_hold")})
    raise ValueError("strategy must be trend or meanrev")


def grid(strategy: str) -> list:
    if strategy == "trend":
        return [TrendFollowing(lb, rb) for lb in (63, 126, 252) for rb in ("W", "M")]
    return [MeanReversion(t, h) for t in (5, 10, 20) for h in (5, 10)]
