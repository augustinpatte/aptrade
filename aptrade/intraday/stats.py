"""Statistics that answer one question: is there an edge after costs, or not?

The confidence interval is a bootstrap that resamples whole DAYS, not single
trades. Breakouts on the same morning are correlated (the whole market moves
together), so treating 50 same-day trades as 50 independent coin flips would make
the interval look far tighter than it is."""
from __future__ import annotations

import numpy as np
import pandas as pd

# The bar to clear before paper trading is worth your time, and paper before real money.
EDGE_BAR_R = 0.10
MIN_TRADES = 100


def max_drawdown(r: np.ndarray) -> float:
    """Largest peak-to-trough fall of the cumulative R curve (a positive number)."""
    if len(r) == 0:
        return 0.0
    curve = np.concatenate([[0.0], np.cumsum(r)])
    return float((np.maximum.accumulate(curve) - curve).max())


def longest_losing_streak(r: np.ndarray) -> int:
    best = cur = 0
    for x in r:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


def day_bootstrap_ci(trades: pd.DataFrame, col: str = "r_net", n_boot: int = 5000,
                     level: float = 0.95, seed: int = 7) -> tuple[float, float]:
    """CI of the mean R per trade, resampling trading days with replacement."""
    daily = trades.groupby("day")[col].agg(["sum", "count"])
    sums, counts = daily["sum"].to_numpy(), daily["count"].to_numpy()
    if len(sums) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(sums), size=(n_boot, len(sums)))
    means = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    a = (1 - level) / 2
    return float(np.quantile(means, a)), float(np.quantile(means, 1 - a))


def summarize(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0}
    r = trades["r_net"].to_numpy(float)
    wins, losses = r[r > 0], r[r < 0]
    lo, hi = day_bootstrap_ci(trades)
    out = {
        "trades": int(len(r)),
        "days": int(trades["day"].nunique()),
        "symbols": int(trades["symbol"].nunique()),
        "win_rate": float((r > 0).mean()),
        "avg_r_gross": float(trades["r_gross"].mean()),
        "avg_r_net": float(r.mean()),
        "cost_per_trade_r": float((trades["r_gross"] - trades["r_net"]).mean()),
        "median_r_net": float(np.median(r)),
        "ci95_low": lo, "ci95_high": hi,
        "profit_factor": float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() else float("inf"),
        "total_r_net": float(r.sum()),
        "max_drawdown_r": max_drawdown(r),
        "longest_losing_streak": longest_losing_streak(r),
        "median_risk_pct": float(trades["risk_pct"].median()),
        "exits": trades["exit_reason"].value_counts().to_dict(),
    }
    out["verdict"] = verdict(out)
    return out


def verdict(s: dict) -> str:
    n, lo, hi, m = s["trades"], s["ci95_low"], s["ci95_high"], s["avg_r_net"]
    if n < MIN_TRADES:
        return f"INCONCLUSIVE: {n} trades, fewer than {MIN_TRADES}. Widen the universe or the period."
    if hi < 0:
        return "NO EDGE: losing after costs, and the whole 95% interval is below zero."
    if lo > 0 and m >= EDGE_BAR_R:
        return (f"CANDIDATE EDGE: the 95% interval is above zero and the mean clears "
                f"+{EDGE_BAR_R}R. Next step: paper trade it with the rules frozen.")
    if lo > 0:
        return (f"WEAK EDGE: above zero, but under +{EDGE_BAR_R}R per trade. Real-world "
                f"frictions you did not model can erase it.")
    return "NO EVIDENCE OF EDGE: the 95% interval straddles zero."


def breakdown(trades: pd.DataFrame, by: str) -> pd.DataFrame:
    """Mean R, trade count and win rate per group (year, quarter, symbol, side...)."""
    t = trades.copy()
    if by in ("year", "quarter"):
        d = pd.to_datetime(t["day"])
        t[by] = d.dt.year.astype(str) if by == "year" else d.dt.to_period("Q").astype(str)
    g = t.groupby(by)["r_net"]
    out = pd.DataFrame({"trades": g.size(), "avg_r_net": g.mean(), "win_rate": g.apply(lambda x: (x > 0).mean()),
                        "total_r_net": g.sum()})
    return out.sort_values("avg_r_net", ascending=False) if by == "symbol" else out.sort_index()


def halves(trades: pd.DataFrame) -> tuple[dict, dict]:
    """First and second half of the period, split by date. A real edge should show up
    in both; one that lives in a single half is probably a regime, not an edge."""
    days = sorted(trades["day"].unique())
    cut = days[len(days) // 2]
    return summarize(trades[trades["day"] < cut]), summarize(trades[trades["day"] >= cut])
