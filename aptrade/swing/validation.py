"""Walk-forward over the pre-registered grid, research data only.

Each variant runs ONCE over the research panel (the holdout is cut off before the
run, so nothing after it is ever computed). Its daily returns are then sliced into
5 blocks. For fold k = 1..4, the variant with the best Sharpe on blocks 0..k-1 is
scored on block k. The 4 test blocks stitched together are the out-of-sample record,
compared with SPY on exactly the same days."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics
from .engine import BuyAndHold, run
from .panel import Panel
from .strategies import WARMUP, grid


def walk_forward(panel: Panel, strategy: str, cost_bps: float = 3.0, folds: int = 4) -> dict:
    if len(panel.dates) < WARMUP + (folds + 1) * 40:
        raise ValueError(f"only {len(panel.dates)} research days: too few for {folds} folds")
    variants = grid(strategy)
    rets = {v.label(): run(panel, v, WARMUP, cost_bps) for v in variants}
    spy = run(panel, BuyAndHold("SPY"), WARMUP, cost_bps).returns
    days = spy.index
    blocks = np.array_split(np.arange(len(days)), folds + 1)

    rows, oos = [], []
    for k in range(1, folds + 1):
        train = days[np.concatenate(blocks[:k])]
        test = days[blocks[k]]
        scores = {lab: metrics.sharpe(res.returns.loc[train].to_numpy()) for lab, res in rets.items()}
        best = max(scores, key=scores.get)
        r_test = rets[best].returns.loc[test]
        oos.append(r_test)
        rows.append({"fold": k, "train": f"{train[0].date()} to {train[-1].date()}",
                     "test": f"{test[0].date()} to {test[-1].date()}", "chosen": best,
                     "sharpe_train": scores[best], "sharpe_test": metrics.sharpe(r_test.to_numpy()),
                     "spy_sharpe_test": metrics.sharpe(spy.loc[test].to_numpy())})
    oos_r = pd.concat(oos)
    table = []
    for v in variants:
        res = rets[v.label()]
        s = metrics.summary(res.returns)
        table.append({"variant": v.label(), "sharpe": s["sharpe"], "cagr_pct": s["cagr_pct"],
                      "max_dd_pct": s["max_drawdown_pct"], "turnover_yr": float(res.turnover.sum() / (len(res.turnover) / 252)),
                      "cost_drag_pct_yr": 100 * float(res.costs.sum() / (len(res.costs) / 252))})
    table = pd.DataFrame(table).sort_values("sharpe", ascending=False)
    best_all = table.iloc[0]["variant"]
    chosen = [r["chosen"] for r in rows]
    return {"folds": pd.DataFrame(rows), "oos": metrics.compare(oos_r, spy), "table": table,
            "spy_research": metrics.summary(spy), "candidate": next(v for v in variants if v.label() == best_all),
            "distinct_choices": len(set(chosen)), "research_days": len(days)}
