"""Walk-forward validation and the locked holdout.

Three layers of data, from most to least used:

  research   everything before the holdout. The sweep lives here.
    walk-forward: the research days are cut into 5 blocks. For fold i, the best
    variant is picked on blocks 0..i-1 (anchored: the training window only grows)
    and scored on block i, which it has never seen. Four folds, four honest
    out-of-sample scores, stitched together into one out-of-sample record.
  holdout    the last 25% of days, fixed in the database the first time it is
    needed and never used to choose anything. `aptrade holdout` scores one frozen
    variant on it and records every look: the second look is already a little bit
    of optimization, the tenth is a lot.

A variant that only wins in sample, flips between folds, or whose neighbours
(one parameter changed) all lose, is noise that happened to fit."""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from . import stats
from .backtest import ExecConfig, run
from .sessions import Session
from .strategy import ORB

GRID = {
    "or_minutes": [5, 15, 30],
    "stop_rule": ["or_mid", "or_far"],
    "target_r": [1.0, 1.5, 2.0],
    "side": ["long", "short"],
}
MIN_TRAIN_TRADES = 50


def variants(last_entry_bar: int | None = None) -> list[dict]:
    keys = list(GRID)
    return [dict(zip(keys, combo), last_entry_bar=last_entry_bar) for combo in itertools.product(*GRID.values())]


def _label(p: dict) -> str:
    return f"or={p['or_minutes']} stop={p['stop_rule']} target={p['target_r']}R side={p['side']}"


def _neighbours(p: dict, all_params: list[dict]) -> list[dict]:
    """Variants that differ from p in exactly one grid parameter."""
    return [q for q in all_params if sum(q[k] != p[k] for k in GRID) == 1]


def walk_forward(sessions: list[Session], cfg: ExecConfig, folds: int = 4,
                 last_entry_bar: int | None = None) -> dict:
    days = sorted({s.day for s in sessions})
    if len(days) < (folds + 1) * 10:
        raise ValueError(f"only {len(days)} research days: too few for {folds} folds")
    blocks = [list(b) for b in np.array_split(np.array(days, dtype=object), folds + 1)]
    params = variants(last_entry_bar)
    trades = {}
    for p in params:
        t, _ = run(sessions, ORB(**p), cfg)
        trades[_label(p)] = t

    def score(label: str, day_set: set) -> dict:
        t = trades[label]
        return stats.summarize(t[t["day"].isin(day_set)] if not t.empty else t)

    fold_rows, oos = [], []
    for i in range(1, folds + 1):
        train = set(itertools.chain.from_iterable(blocks[:i]))
        test = set(blocks[i])
        scored = [(score(_label(p), train), p) for p in params]
        eligible = [(s, p) for s, p in scored if s["trades"] >= MIN_TRAIN_TRADES]
        row = {"fold": i, "train": f"{min(train)} to {max(train)}", "test": f"{min(test)} to {max(test)}"}
        if not eligible:
            fold_rows.append({**row, "chosen": None, "r_train": None, "n_test": 0, "r_test": None})
            continue
        best_s, best_p = max(eligible, key=lambda sp: sp[0]["avg_r_net"])
        label = _label(best_p)
        t = trades[label]
        t_test = t[t["day"].isin(test)] if not t.empty else t
        oos.append(t_test.assign(fold=i, variant=label))
        s_test = stats.summarize(t_test)
        fold_rows.append({**row, "chosen": label, "r_train": best_s["avg_r_net"],
                          "n_test": s_test["trades"], "r_test": s_test.get("avg_r_net")})

    oos_trades = pd.concat(oos, ignore_index=True) if oos else pd.DataFrame()
    everything = set(days)
    table = []
    for p in params:
        s = score(_label(p), everything)
        table.append({**{k: p[k] for k in GRID}, "trades": s["trades"], "avg_r_net": s.get("avg_r_net"),
                      "ci95_low": s.get("ci95_low"), "ci95_high": s.get("ci95_high")})
    table = pd.DataFrame(table)

    eligible_final = table[table["trades"] >= stats.MIN_TRADES]
    final = None
    if not eligible_final.empty:
        best = eligible_final.sort_values("avg_r_net", ascending=False).iloc[0]
        final_p = next(p for p in params if all(p[k] == best[k] for k in GRID))
        neigh = [_label(q) for q in _neighbours(final_p, params)]
        neigh_r = table.assign(label=[_label(p) for p in params]).set_index("label").loc[neigh, "avg_r_net"]
        final = {"params": final_p, "label": _label(final_p), "research_r": float(best["avg_r_net"]),
                 "research_trades": int(best["trades"]),
                 "neighbours_mean_r": float(neigh_r.mean()), "neighbours_positive": int((neigh_r > 0).sum()),
                 "neighbours": len(neigh_r)}

    chosen = [r["chosen"] for r in fold_rows if r["chosen"]]
    return {
        "research_days": len(days), "folds": pd.DataFrame(fold_rows),
        "oos_trades": oos_trades, "oos_summary": stats.summarize(oos_trades),
        "distinct_choices": len(set(chosen)), "table": table, "final": final,
        "positive_variants": int((table["avg_r_net"] > 0).sum()), "variants": len(table),
    }
