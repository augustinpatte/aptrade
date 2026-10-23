"""Plain-text reports for the terminal."""
from __future__ import annotations

import pandas as pd

from . import stats


def _r(x: float) -> str:
    return f"{x:+.3f}R"


def summary_block(s: dict, title: str = "") -> str:
    if not s.get("trades"):
        return f"{title}\n  no trades\n" if title else "  no trades\n"
    lines = [title] if title else []
    lines += [
        f"  trades            {s['trades']}  ({s['symbols']} symbols, {s['days']} days)",
        f"  win rate          {100 * s['win_rate']:.1f}%",
        f"  avg R, gross      {_r(s['avg_r_gross'])}",
        f"  costs per trade   {_r(-s['cost_per_trade_r'])}",
        f"  avg R, net        {_r(s['avg_r_net'])}",
        f"  95% CI (by day)   {_r(s['ci95_low'])} to {_r(s['ci95_high'])}",
        f"  profit factor     {s['profit_factor']:.2f}",
        f"  total, net        {s['total_r_net']:+.1f}R",
        f"  max drawdown      {s['max_drawdown_r']:.1f}R",
        f"  longest losing    {s['longest_losing_streak']} trades",
        f"  median risk       {s['median_risk_pct']:.2f}% of price",
        f"  exits             " + ", ".join(f"{k} {v}" for k, v in sorted(s["exits"].items())),
    ]
    return "\n".join(lines) + "\n"


def _table(df: pd.DataFrame) -> str:
    f = df.copy()
    f["avg_r_net"] = f["avg_r_net"].map(lambda x: f"{x:+.3f}")
    f["win_rate"] = f["win_rate"].map(lambda x: f"{100 * x:.0f}%")
    f["total_r_net"] = f["total_r_net"].map(lambda x: f"{x:+.1f}")
    return f.to_string()


def full_report(trades: pd.DataFrame, counters: dict, header: str) -> str:
    s = stats.summarize(trades)
    out = [header, "", summary_block(s, "RESULT"), f"VERDICT  {s.get('verdict', 'no trades')}", ""]
    skipped = {k: v for k, v in counters.items() if k.startswith("skipped_")}
    out.append(f"sessions {counters['sessions']}, signals {counters['signals']}, trades {counters['trades']}"
               + (", " + ", ".join(f"{k[8:]} {v}" for k, v in skipped.items()) if skipped else ""))
    if trades.empty:
        return "\n".join(out) + "\n"
    a, b = stats.halves(trades)
    out += ["", "STABILITY  (a real edge should hold in both halves)",
            summary_block(a, "first half"), summary_block(b, "second half")]
    out += ["BY QUARTER", _table(stats.breakdown(trades, "quarter")), ""]
    if trades["side"].nunique() > 1:
        out += ["BY SIDE", _table(stats.breakdown(trades, "side")), ""]
    sym = stats.breakdown(trades, "symbol")
    if len(sym) > 10:
        out += ["BY SYMBOL  (best 5, worst 5; with this many symbols, the extremes are mostly luck)",
                _table(sym.head(5)), "...", _table(sym.tail(5)), ""]
    elif len(sym) > 1:
        out += ["BY SYMBOL", _table(sym), ""]
    return "\n".join(out) + "\n"


def coverage_block(cov: pd.DataFrame) -> str:
    if cov.empty:
        return "COVERAGE  no data"
    dropped = cov[~cov["kept"]]
    line = (f"COVERAGE  {int(cov['kept'].sum())}/{len(cov)} symbols kept (>= 90% of the "
            f"{int(cov['expected'].iloc[0])} reference sessions), median {100 * cov['coverage'].median():.0f}%")
    if not dropped.empty:
        line += "\n  excluded: " + ", ".join(f"{r.symbol} {100 * r.coverage:.0f}%" for r in dropped.itertuples())
    return line + "\n"


def portfolio_block(est: dict, pcount: dict, taken_summary: dict) -> str:
    if not est:
        return "PORTFOLIO  no trading days\n"
    c = pcount.get("config", {})
    rej = pcount.get("rejected", {})
    lines = [
        "PORTFOLIO  " + (f"{c.get('capital', 0):,.0f} $, {c.get('risk_pct')}% risk per trade, "
                         f"{c.get('daily_loss_pct')}% daily loss limit, {c.get('max_positions')} positions max"
                         if c else ""),
        f"  end equity        {est['end_equity']:,.2f} $  ({est['total_return_pct']:+.2f}%, "
        f"{est['annualized_return_pct']:+.2f}% a year)",
        f"  max drawdown      {est['max_drawdown_pct']:.2f}%  ({est['max_drawdown_usd']:,.2f} $, at the closes)",
        f"  worst / best day  {est['worst_day_pct']:+.2f}% / {est['best_day_pct']:+.2f}%",
        f"  daily Sharpe      {est['sharpe_daily_annualized']:.2f} (annualized)",
        f"  trades taken      {est['trades_taken']} on {est['days_with_trades']} of {est['trading_days']} days, "
        f"avg {est['avg_qty']:.0f} shares, {est['avg_notional_pct']:.0f}% of capital each",
        f"  daily limit hit   {est['days_daily_limit_hit']} days",
        f"  sized by cash     {pcount.get('sized_by_cash', 0)} of {est['trades_taken']} trades (stop so tight that "
        f"the cash, not the risk budget, set the size: you risk less than planned)",
        "  rejected          " + (", ".join(f"{k} {v}" for k, v in sorted(rej.items())) or "none"),
    ]
    if taken_summary.get("trades"):
        lines.append(f"  taken trades      {_r(taken_summary['avg_r_net'])} net per trade, 95% CI "
                     f"{_r(taken_summary['ci95_low'])} to {_r(taken_summary['ci95_high'])} "
                     f"(the subset the account could actually take)")
    return "\n".join(lines) + "\n"


def sweep_report(wf: dict) -> str:
    out = ["WALK-FORWARD  (best variant chosen on the past, scored on the next block it never saw)"]
    f = wf["folds"].copy()
    for col in ("r_train", "r_test"):
        f[col] = f[col].map(lambda x: f"{x:+.3f}" if pd.notna(x) else "")
    out += [f.to_string(index=False), ""]
    out.append(summary_block(wf["oos_summary"], "OUT OF SAMPLE, all folds stitched together"))
    if wf["oos_summary"].get("trades"):
        out.append(f"VERDICT  {wf['oos_summary']['verdict']}")
    out.append(f"  {wf['distinct_choices']} different variants chosen across the folds "
               f"(1 is stable, one per fold is noise).")
    out.append(f"  {wf['positive_variants']} of {wf['variants']} variants are positive on the whole research period.")
    fin = wf["final"]
    if fin:
        out += ["", f"CANDIDATE FOR THE HOLDOUT  {fin['label']}",
                f"  research          {_r(fin['research_r'])} over {fin['research_trades']} trades "
                f"(selected on this: biased up)",
                f"  its neighbours    {_r(fin['neighbours_mean_r'])} on average, {fin['neighbours_positive']} of "
                f"{fin['neighbours']} positive (one parameter changed; if they lose, the winner is a fluke)",
                "  Next: if the out-of-sample record above is clearly positive, run `aptrade holdout` ONCE with "
                "these parameters."]
    t = wf["table"].sort_values("avg_r_net", ascending=False).copy()
    for col in ("avg_r_net", "ci95_low", "ci95_high"):
        t[col] = t[col].map(lambda x: f"{x:+.3f}" if pd.notna(x) else "")
    out += ["", "ALL VARIANTS, whole research period (for context, not for picking)", t.to_string(index=False)]
    return "\n".join(out) + "\n"
