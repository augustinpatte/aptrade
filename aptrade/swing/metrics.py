"""Account metrics and the pre-registered verdict against SPY."""
from __future__ import annotations

import numpy as np
import pandas as pd

DAYS = 252
BLOCK = 20
N_BOOT = 2000


def sharpe(r: np.ndarray) -> float:
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(DAYS)) if sd > 0 else float("nan")


def max_drawdown(r: np.ndarray) -> float:
    eq = np.cumprod(1 + r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return float((1 - eq / peak).max()) if len(r) else 0.0


def summary(r: pd.Series) -> dict:
    a = r.to_numpy(float)
    if len(a) < 2:
        return {"days": len(a)}
    years = len(a) / DAYS
    growth = float(np.prod(1 + a))
    monthly = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    mdd = max_drawdown(a)
    cagr = growth ** (1 / years) - 1
    return {
        "days": len(a), "start": str(r.index[0].date()), "end": str(r.index[-1].date()),
        "total_return_pct": 100 * (growth - 1), "cagr_pct": 100 * cagr,
        "vol_pct": 100 * a.std(ddof=1) * np.sqrt(DAYS), "sharpe": sharpe(a),
        "max_drawdown_pct": 100 * mdd, "calmar": cagr / mdd if mdd > 0 else float("nan"),
        "worst_month_pct": 100 * float(monthly.min()), "best_month_pct": 100 * float(monthly.max()),
        "pct_months_up": 100 * float((monthly > 0).mean()),
    }


def _stationary_indices(n: int, rng, block: int) -> np.ndarray:
    """Politis-Romano stationary bootstrap: blocks of geometric length (mean `block`),
    wrapping around, so autocorrelation and volatility clusters survive resampling."""
    idx = np.empty(n, dtype=int)
    i = 0
    p = 1 / block
    while i < n:
        start = rng.integers(0, n)
        length = rng.geometric(p)
        take = min(length, n - i)
        idx[i:i + take] = (start + np.arange(take)) % n
        i += take
    return idx


def sharpe_difference(r: pd.Series, bench: pd.Series, n_boot: int = N_BOOT, block: int = BLOCK,
                      seed: int = 11, level: float = 0.90, cash: pd.Series | None = None) -> dict:
    """Sharpe(strategy) - Sharpe(benchmark) with an interval at `level`. Both series are
    resampled with the SAME indices, so their correlation is kept. With `cash`, both
    are measured in excess of it."""
    a, b = r.to_numpy(float), bench.reindex(r.index).to_numpy(float)
    if cash is not None:
        c = cash.reindex(r.index).fillna(0.0).to_numpy(float)
        a, b = a - c, b - c
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for k in range(n_boot):
        ix = _stationary_indices(len(a), rng, block)
        diffs[k] = sharpe(a[ix]) - sharpe(b[ix])
    tail = (1 - level) / 2
    return {"diff": sharpe(a) - sharpe(b), "ci90_low": float(np.quantile(diffs, tail)),
            "ci90_high": float(np.quantile(diffs, 1 - tail)), "p_better": float((diffs > 0).mean()),
            "level": level, "excess": cash is not None}


def verdict(strat: dict, bench: dict, diff: dict) -> str:
    better_dd = strat["max_drawdown_pct"] < bench["max_drawdown_pct"]
    better_sharpe = diff["diff"] > 0
    if better_sharpe and better_dd and diff["ci90_low"] > 0:
        return "PASS: higher Sharpe than SPY (90% interval above zero) and a smaller drawdown."
    if better_sharpe and better_dd:
        return ("WEAK: higher Sharpe and smaller drawdown than SPY, but the 90% interval of the "
                "Sharpe difference includes zero. Not enough evidence.")
    reasons = []
    if not better_sharpe:
        reasons.append("Sharpe below SPY")
    if not better_dd:
        reasons.append("drawdown not smaller than SPY")
    return "FAIL: " + " and ".join(reasons) + "."


def compare(r: pd.Series, bench: pd.Series, cash: pd.Series | None = None) -> dict:
    s, b = summary(r), summary(bench.reindex(r.index))
    if cash is not None:
        c = cash.reindex(r.index).fillna(0.0)
        s["excess_sharpe"] = sharpe((r - c).to_numpy())
        b["excess_sharpe"] = sharpe((bench.reindex(r.index) - c).to_numpy())
    d = sharpe_difference(r, bench)
    return {"strategy": s, "spy": b, "sharpe_diff": d, "verdict": verdict(s, b, d)}


def verdict_blend(s: dict, b: dict) -> str:
    """H3 criterion (PREREGISTRATION.md addendum): less risk at a bounded cost."""
    checks = [
        (s["max_drawdown_pct"] <= 0.6 * b["max_drawdown_pct"],
         f"max drawdown {s['max_drawdown_pct']:.1f}% vs limit {0.6 * b['max_drawdown_pct']:.1f}% (60% of SPY's)"),
        (s["excess_sharpe"] >= b["excess_sharpe"] - 0.10,
         f"excess Sharpe {s['excess_sharpe']:.2f} vs limit {b['excess_sharpe'] - 0.10:.2f} (SPY's minus 0.10)"),
        (s["cagr_pct"] >= (0.5 * b["cagr_pct"] if b["cagr_pct"] > 0 else b["cagr_pct"]),
         f"CAGR {s['cagr_pct']:+.1f}% vs limit {(0.5 * b['cagr_pct'] if b['cagr_pct'] > 0 else b['cagr_pct']):+.1f}% "
         f"(half of SPY's)"),
    ]
    lines = [("  ok    " if ok else "  MISS  ") + text for ok, text in checks]
    head = "PASS: less risk at the agreed cost." if all(ok for ok, _ in checks) else \
        f"FAIL: {sum(not ok for ok, _ in checks)} of 3 conditions missed."
    return head + "\n" + "\n".join(lines)


def verdict_rotation(s: dict, b: dict, d: dict) -> str:
    """H5 criterion: excess Sharpe above SPY's with the 98% interval above zero
    (Bonferroni over 5 hypotheses), and a smaller max drawdown."""
    better_dd = s["max_drawdown_pct"] < b["max_drawdown_pct"]
    if d["diff"] > 0 and better_dd and d["ci90_low"] > 0:
        return "PASS: higher excess Sharpe than SPY (98% interval above zero) and a smaller drawdown."
    if d["diff"] > 0 and better_dd:
        return "WEAK: higher excess Sharpe and smaller drawdown, but the 98% interval includes zero."
    reasons = []
    if d["diff"] <= 0:
        reasons.append("excess Sharpe not above SPY")
    if not better_dd:
        reasons.append("drawdown not smaller than SPY")
    return "FAIL: " + " and ".join(reasons) + "."
