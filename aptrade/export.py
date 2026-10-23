"""`aptrade export`: precompute everything the app shows, from the local daily data.

What is written to results/results.json, and what is not:
  - written: MONTHLY returns of each portfolio (enough for the charts), and statistics
    computed on DAILY returns (Sharpe, drawdown, CAGR...), for the full period, the
    research period and the holdout.
  - not written: any price, any daily series. Market-data agreements generally forbid
    redistributing raw data; published research shares results, not prices.

The public demo reads this file only. Anyone with an Alpaca key regenerates it."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from . import store
from .swing import metrics
from .swing.engine import BuyAndHold, run
from .swing.panel import BENCHMARK, CASH, Panel
from .swing.strategies import (WARMUP, Allocation, Blend, MeanReversion, Rotation, StaticBlend,
                               TrendFollowing)

RESULTS = Path(__file__).resolve().parent.parent / "results"
SLIDER = list(range(0, 101, 10))          # % SPY in the app's slider


def portfolios() -> dict:
    """Every portfolio the app can show: the slider's allocations, then the strategies
    with the variant the research singled out (see research/JOURNAL.md)."""
    out = {f"alloc_{p}": ("allocation", Allocation(p / 100)) for p in SLIDER}
    out.update({
        "trend": ("strategy", TrendFollowing(63, "M")),
        "meanrev": ("strategy", MeanReversion(5, 10)),
        "blend": ("strategy", Blend()),
        "static": ("strategy", StaticBlend()),
        "rotation": ("strategy", Rotation()),
    })
    return out


def _monthly(r: pd.Series) -> list:
    m = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    return [[f"{y:04d}-{mo:02d}", round(float(v), 6)] for (y, mo), v in m.items()]


def _stats(r: pd.Series, spy: pd.Series, cash: pd.Series) -> dict:
    if len(r) < 60:
        return {}
    s, b = metrics.summary(r), metrics.summary(spy)
    cw = cash.reindex(r.index).fillna(0.0)
    s["excess_sharpe"] = metrics.sharpe((r - cw).to_numpy())
    b["excess_sharpe"] = metrics.sharpe((spy - cw).to_numpy())
    c = {"strategy": s, "spy": b}
    d = metrics.sharpe_difference(r, spy, cash=cash, n_boot=1000)
    keys = ("start", "end", "days", "total_return_pct", "cagr_pct", "vol_pct", "sharpe", "excess_sharpe",
            "max_drawdown_pct", "worst_month_pct", "pct_months_up")
    clean = lambda s: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items() if k in keys}
    return {"portfolio": clean(c["strategy"]), "spy": clean(c["spy"]),
            "excess_sharpe_diff": {k: round(d[k], 4) for k in ("diff", "ci90_low", "ci90_high", "p_better")}}


THREE_YEARS = 756        # trading days


def _activity(res) -> dict:
    """How the portfolio carries its risk: concentration, exposure, trading."""
    w = res.weights.drop(columns=[CASH], errors="ignore")
    years = len(res.returns) / 252
    held = (w > 0.01).sum(axis=1)
    return {"max_position_pct": round(100 * float(w.max(axis=1).max()), 1),
            "avg_position_pct": round(100 * float((w.sum(axis=1) / held.clip(lower=1)).mean()), 1),
            "avg_positions": round(float(held.mean()), 1),
            "avg_invested_pct": round(100 * float(w.sum(axis=1).mean()), 1),
            "rebalances_per_year": round(res.rebalances / years, 1),
            "turnover_per_year": round(float(res.turnover.sum() / years), 2),
            "cost_pct_per_year": round(100 * float(res.costs.sum() / years), 3)}


def build(panel: Panel, holdout_start, cost_bps: float = 3.0, progress=print) -> dict:
    hold = pd.Timestamp(holdout_start) if holdout_start else None
    cash = panel.close[CASH].pct_change().fillna(0.0)
    spy = run(panel, BuyAndHold(BENCHMARK), WARMUP, cost_bps).returns
    windows = {"full": slice(None), "3y": spy.index >= spy.index[-min(THREE_YEARS, len(spy))]}
    if hold is not None:
        windows["research"] = spy.index < hold
        windows["holdout"] = spy.index >= hold
    out = {}
    for key, (kind, strat) in portfolios().items():
        progress(f"  {key}")
        res = run(panel, strat, WARMUP, cost_bps)
        r = res.returns
        out[key] = {"kind": kind, "label": strat.label(), "params": strat.params(), "monthly": _monthly(r),
                    "activity": _activity(res),
                    "stats": {w: _stats(r[m], spy[m], cash) for w, m in windows.items()}}
    out["spy"] = {"kind": "benchmark", "label": "SPY bought and held", "monthly": _monthly(spy), "stats": {}}
    return {
        "meta": {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "data_start": str(spy.index[0].date()), "data_end": str(spy.index[-1].date()),
                 "holdout_start": str(hold.date()) if hold is not None else None, "cost_bps": cost_bps,
                 "note": "Monthly returns and statistics only; no prices are included."},
        "portfolios": out,
    }


def cmd_export(a, settings):
    from .swing.cli import HOLDOUT_KEY, _panel
    a.refresh, a.feed = False, "sip"
    panel, feed, hold = _panel(a, settings)
    print(f"computing {len(portfolios())} portfolios on {len(panel.dates)} days (a minute or two)", file=sys.stderr)
    doc = build(panel, hold, a.cost_bps, progress=lambda m: print(m, file=sys.stderr))
    doc["meta"]["feed"] = feed
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "results.json"
    path.write_text(json.dumps(doc, indent=1, sort_keys=True))
    print(f"wrote {path} ({path.stat().st_size // 1024} KB). Commit it to update the public demo.")
    from .readme_tables import fill_readmes
    for f in fill_readmes(doc):
        print(f"updated the results tables in {f}")


def add_parser(sub):
    q = sub.add_parser("export", help="precompute the app's results (monthly returns + stats, no prices)")
    q.add_argument("--out", default=str(RESULTS))
    q.add_argument("--start", default="2016-01-01")
    q.add_argument("--end", help="YYYY-MM-DD (default: today)")
    q.add_argument("--cost-bps", type=float, default=3.0)
    q.set_defaults(func=cmd_export)


def load(path: Path | None = None) -> dict | None:
    p = Path(path) if path else RESULTS / "results.json"
    return json.loads(p.read_text()) if p.is_file() else None
