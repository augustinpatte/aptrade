"""Run a user's own portfolio against SPY: the engine behind the app's
"My portfolio" page. Same engine, costs and metrics as the research."""
from __future__ import annotations

from datetime import date, datetime, timezone

from ..data import load_bars
from . import metrics
from .engine import BuyAndHold, run
from .panel import BENCHMARK, CASH, build_panel
from .strategies import WARMUP, CustomAllocation, make

START = "2016-01-01"


def _dt(d) -> datetime:
    d = date.fromisoformat(str(d)) if not isinstance(d, date) else d
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def evaluate(strategy, bars: dict, cost_bps: float = 3.0, trim_start: bool = True) -> dict:
    """Run `strategy` on `bars` (daily, must include SPY and BIL) and compare with SPY.
    Fixed allocations start trading on the first common day; signal strategies keep
    their pre-registered warm-up so their numbers match the research."""
    symbols = sorted(set(strategy.universe) | {BENCHMARK, CASH})
    panel = build_panel(bars, symbols, trim_start=trim_start)
    start = 1 if isinstance(strategy, CustomAllocation) else WARMUP
    if len(panel.dates) <= start + 60:
        raise ValueError(f"only {len(panel.dates)} common days of history: too short to judge anything")
    res = run(panel, strategy, start, cost_bps)
    spy = run(panel, BuyAndHold(BENCHMARK), start, cost_bps).returns
    cash = panel.close[CASH].pct_change().fillna(0.0)
    cmp_ = metrics.compare(res.returns, spy, cash)
    growth = (1 + res.returns).cumprod()
    spy_growth = (1 + spy).cumprod()
    return {"label": strategy.label(), "compare": cmp_, "growth": growth, "spy_growth": spy_growth,
            "weights": res.weights, "rebalances": res.rebalances,
            "cost_pct_year": 100 * float(res.costs.sum() / (len(res.costs) / 252))}


def load_daily(symbols, settings, end=None, feed="sip"):
    end_dt = _dt(end) if end else _dt(date.today())
    bars, used = load_bars(sorted(set(symbols) | {BENCHMARK, CASH}), _dt(START), end_dt, settings,
                           feed=feed, timeframe="1d")
    return bars, used


def run_custom(weights: dict, rebalance: str, settings, cost_bps: float = 3.0) -> dict:
    strat = CustomAllocation(weights, rebalance)
    bars, _ = load_daily(strat.universe, settings)
    return evaluate(strat, bars, cost_bps)


def run_named(name: str, settings, cost_bps: float = 3.0, **kw) -> dict:
    strat = make(name, **kw)
    bars, _ = load_daily(strat.universe, settings)
    return evaluate(strat, bars, cost_bps, trim_start=False)
