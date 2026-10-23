"""Target-weight portfolio engine on daily bars.

Each day:
  open   orders decided at the previous close execute at this open: the portfolio
         is resized to the target weights, every dollar traded pays cost_bps.
  close  the portfolio is marked; the strategy sees closes up to today only and may
         return new target weights (or None: keep what you hold, let it drift).

Weights are fractions of equity; whatever the strategy does not allocate goes to
CASH (BIL). Shares are fractional. Returns are daily close-to-close, with the
first day measured from the starting capital."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .panel import CASH, Panel


@dataclass
class RunResult:
    returns: pd.Series          # daily returns on the evaluation days
    weights: pd.DataFrame       # end-of-day weights, evaluation days
    turnover: pd.Series         # dollars traded / equity, per day
    costs: pd.Series            # cost / equity, per day
    rebalances: int


def _normalise(target: dict, symbols: list[str]) -> np.ndarray:
    w = np.array([max(0.0, float(target.get(s, 0.0))) for s in symbols])
    total = w.sum()
    if total > 1 + 1e-9:
        w = w / total                       # never more than 100%: no leverage
    cash_i = symbols.index(CASH)
    w[cash_i] += max(0.0, 1.0 - w.sum())
    return w


def run(panel: Panel, strategy, start_index: int, cost_bps: float = 3.0) -> RunResult:
    symbols = list(panel.close.columns)
    if CASH not in symbols:
        raise ValueError(f"{CASH} must be in the panel")
    O = panel.open.to_numpy(float)
    C = panel.close.to_numpy(float)
    n = len(symbols)
    if start_index < 1:
        raise ValueError("start_index must leave one day of history for the first signal")
    strategy.prepare(panel.close)
    strategy.reset()

    bps = cost_bps / 10_000
    shares = np.zeros(n)
    equity_prev = 1.0
    cash_i = symbols.index(CASH)
    shares[cash_i] = 1.0 / O[start_index, cash_i]     # start fully in cash at the first open
    first = strategy.on_close(start_index - 1, _weights_at(shares, C[start_index - 1]), symbols)
    pending = _normalise(first, symbols) if first is not None else None

    rets, wts, turns, costs, rebal = [], [], [], [], 0
    for i in range(start_index, len(panel.dates)):
        turn = cost = 0.0
        if pending is not None:
            value = float(shares @ O[i])
            new_shares = pending * value / O[i]
            traded = float(np.abs(new_shares - shares) @ O[i])
            cost = traded * bps
            shares = pending * (value - cost) / O[i]
            turn, cost = traded / value, cost / value
            rebal += 1
            pending = None
        eq = float(shares @ C[i])
        rets.append(eq / equity_prev - 1)
        equity_prev = eq
        w_now = shares * C[i] / eq
        wts.append(w_now)
        turns.append(turn)
        costs.append(cost)
        if i < len(panel.dates) - 1:
            tgt = strategy.on_close(i, dict(zip(symbols, w_now)), symbols)
            if tgt is not None:
                pending = _normalise(tgt, symbols)

    idx = panel.dates[start_index:]
    return RunResult(pd.Series(rets, idx), pd.DataFrame(wts, idx, symbols), pd.Series(turns, idx),
                     pd.Series(costs, idx), rebal)


def _weights_at(shares, prices) -> dict:
    return {}   # before the first open the portfolio is all cash: no risky weights


class BuyAndHold:
    """The benchmark: buy one symbol at the first open, hold it."""
    name = "buy_and_hold"

    def __init__(self, symbol: str = "SPY"):
        self.symbol = symbol

    def params(self) -> dict:
        return {"symbol": self.symbol}

    def prepare(self, closes):
        pass

    def reset(self):
        self.done = False

    def on_close(self, i, weights, symbols):
        if self.done:
            return None
        self.done = True
        return {self.symbol: 1.0}
