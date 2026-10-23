"""`aptrade swing ...` commands."""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone

import pandas as pd

from .. import store
from ..data import load_bars
from . import metrics
from .engine import BuyAndHold, run
from .panel import BENCHMARK, CASH, build_panel
from .strategies import MEANREV_UNIVERSE, TREND_UNIVERSE, WARMUP, make
from .validation import walk_forward

HOLDOUT_KEY = "swing_holdout_start"
HOLDOUT_KIND = "swing_holdout"
DEFAULT_START = "2016-01-01"
ALL_SYMBOLS = sorted(set(TREND_UNIVERSE) | set(MEANREV_UNIVERSE) | {BENCHMARK, CASH})


def _dt(text: str) -> datetime:
    d = datetime.strptime(text, "%Y-%m-%d")
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _panel(a, settings):
    start = _dt(a.start)
    end = _dt(a.end) if a.end else datetime(*date.today().timetuple()[:3], tzinfo=timezone.utc)
    print(f"loading {len(ALL_SYMBOLS)} ETFs, daily, {start.date()} to {end.date()}", file=sys.stderr)
    bars, feed = load_bars(ALL_SYMBOLS, start, end, settings, feed=a.feed, refresh=a.refresh, timeframe="1d")
    try:
        panel = build_panel(bars, ALL_SYMBOLS)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")
    if len(panel.dates) <= WARMUP + 200:
        raise SystemExit(f"only {len(panel.dates)} days of data: need well over {WARMUP}")
    hold = store.get_meta(settings.db_path, HOLDOUT_KEY)
    if hold is None:
        scored = panel.dates[WARMUP:]
        hold = str(scored[int(len(scored) * 0.75)].date())
        store.set_meta(settings.db_path, HOLDOUT_KEY, hold)
        print(f"swing holdout locked: every day from {hold} on is reserved (stored in {settings.db_path})",
              file=sys.stderr)
    filled = {s: n for s, n in panel.filled.items() if n}
    if filled:
        print("forward-filled days (no bar that day): " + ", ".join(f"{s} {n}" for s, n in filled.items()),
              file=sys.stderr)
    return panel, feed, pd.Timestamp(hold)


def _strategy(a):
    try:
        return make(a.strategy, lookback=a.lookback, rebalance=a.rebalance,
                    rsi_threshold=a.rsi, max_hold=a.max_hold)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")


def _cash_returns(panel):
    return panel.close[CASH].pct_change().fillna(0.0)


def _compare(r, spy, panel, strat) -> dict:
    """The comparison and verdict pre-registered for this strategy."""
    cash = _cash_returns(panel)
    c = metrics.compare(r, spy, cash)
    if strat.name in ("blend", "static"):
        c["verdict"] = metrics.verdict_blend(c["strategy"], c["spy"])
    elif strat.name == "rotation":
        c["sharpe_diff"] = metrics.sharpe_difference(r, spy, level=0.98, cash=cash)
        c["verdict"] = metrics.verdict_rotation(c["strategy"], c["spy"], c["sharpe_diff"])
    return c


def _block(title: str, c: dict) -> str:
    s, b, d = c["strategy"], c["spy"], c["sharpe_diff"]
    rows = [("total return", "total_return_pct", "{:+.1f}%"), ("per year (CAGR)", "cagr_pct", "{:+.1f}%"),
            ("volatility", "vol_pct", "{:.1f}%"), ("Sharpe", "sharpe", "{:.2f}"),
            ("excess Sharpe", "excess_sharpe", "{:.2f}"),
            ("max drawdown", "max_drawdown_pct", "{:.1f}%"), ("Calmar", "calmar", "{:.2f}"),
            ("worst month", "worst_month_pct", "{:+.1f}%"), ("months up", "pct_months_up", "{:.0f}%")]
    out = [title, f"  {s['start']} to {s['end']}, {s['days']} days", f"  {'':18s}{'strategy':>12s}{'SPY':>12s}"]
    for name, key, fmt in rows:
        if key not in s:
            continue
        out.append(f"  {name:18s}{fmt.format(s[key]):>12s}{fmt.format(b[key]):>12s}")
    lvl = f"{100 * d.get('level', 0.9):.0f}%"
    kind = "Excess Sharpe" if d.get("excess") else "Sharpe"
    out.append(f"  {kind} difference {d['diff']:+.2f}, {lvl} interval {d['ci90_low']:+.2f} to {d['ci90_high']:+.2f}, "
               f"better than SPY in {100 * d['p_better']:.0f}% of resamples")
    out.append(f"VERDICT  {c['verdict']}")
    return "\n".join(out) + "\n"


def _activity(res) -> str:
    years = len(res.returns) / 252
    invested = 1 - res.weights[CASH].mean()
    return (f"  activity: {res.rebalances / years:.0f} rebalances a year, turnover {res.turnover.sum() / years:.1f}x "
            f"equity a year, costs {100 * res.costs.sum() / years:.2f}% a year, invested {100 * invested:.0f}% "
            f"of the time on average\n")


def _save(settings, kind, strat, a, panel, feed, summary):
    return store.save_run(settings.db_path, kind=kind, strategy=strat.name, params=strat.params(),
                          exec_cfg={"cost_bps": a.cost_bps, "timeframe": "1d"}, universe=strat.universe,
                          start=panel.dates[0].date(), end=panel.dates[-1].date(), feed=feed,
                          summary=summary, trades=pd.DataFrame())


def cmd_fetch(a, settings):
    panel, feed, hold = _panel(a, settings)
    print(f"{len(panel.close.columns)} ETFs, {len(panel.dates)} days, {panel.dates[0].date()} to "
          f"{panel.dates[-1].date()}, feed {feed}. Swing holdout starts {hold.date()}.")


def cmd_backtest(a, settings):
    strat = _strategy(a)
    full, feed, hold = _panel(a, settings)
    panel = full.truncate(hold)
    res = run(panel, strat, WARMUP, a.cost_bps)
    spy = run(panel, BuyAndHold(BENCHMARK), WARMUP, a.cost_bps).returns
    c = _compare(res.returns, spy, panel, strat)
    print(f"{strat.label()}, costs {a.cost_bps} bps a side. RESEARCH DATA only (holdout from {hold.date()} untouched).\n")
    print(_block("RESULT vs SPY bought and held, same days, same costs", c) + _activity(res))
    if not a.no_save:
        print(f"saved as run {_save(settings, 'swing_backtest', strat, a, panel, feed, c)} in {settings.db_path}")


def cmd_sweep(a, settings):
    full, feed, hold = _panel(a, settings)
    panel = full.truncate(hold)
    wf = walk_forward(panel, a.strategy, a.cost_bps)
    f = wf["folds"].copy()
    for col in ("sharpe_train", "sharpe_test", "spy_sharpe_test"):
        f[col] = f[col].map("{:.2f}".format)
    t = wf["table"].copy()
    for col, fmt in (("sharpe", "{:.2f}"), ("cagr_pct", "{:+.1f}"), ("max_dd_pct", "{:.1f}"),
                     ("turnover_yr", "{:.1f}"), ("cost_drag_pct_yr", "{:.2f}")):
        t[col] = t[col].map(fmt.format)
    print(f"{a.strategy}: 6 pre-registered variants, costs {a.cost_bps} bps a side. RESEARCH DATA "
          f"{panel.dates[WARMUP].date()} to {panel.dates[-1].date()}; holdout from {hold.date()} untouched.\n")
    print("WALK-FORWARD  (best Sharpe on the past, scored on the next block)")
    print(f.to_string(index=False) + "\n")
    print(_block("OUT OF SAMPLE, 4 test blocks stitched, vs SPY on the same days", wf["oos"]))
    print(f"  {wf['distinct_choices']} different variants chosen across the 4 folds (1 is stable, 4 is noise).\n")
    print("ALL VARIANTS, whole research period (context, not for picking)")
    print(t.to_string(index=False))
    sp = wf["spy_research"]
    print(f"  SPY over the same period: Sharpe {sp['sharpe']:.2f}, {sp['cagr_pct']:+.1f}% a year, "
          f"max drawdown {sp['max_drawdown_pct']:.1f}%")
    cand = wf["candidate"]
    print(f"\nCANDIDATE FOR THE HOLDOUT  {cand.label()}")
    print("  Only if the out-of-sample verdict above is PASS. Otherwise the holdout stays untouched.")
    if not a.no_save:
        rid = store.save_run(settings.db_path, kind="swing_sweep", strategy=a.strategy, params={"grid": "pre-registered"},
                             exec_cfg={"cost_bps": a.cost_bps}, universe=cand.universe, start=panel.dates[0].date(),
                             end=panel.dates[-1].date(), feed=feed,
                             summary={"oos": wf["oos"], "folds": wf["folds"].to_dict("records"),
                                      "variants": wf["table"].to_dict("records")}, trades=pd.DataFrame())
        print(f"\nsaved as run {rid} in {settings.db_path}")


def cmd_holdout(a, settings):
    strat = _strategy(a)
    views = store.holdout_views(settings.db_path, HOLDOUT_KIND, strat.name)
    if views and not a.again:
        raise SystemExit(f"the swing holdout has already been looked at {views} time(s). Every look leaks it "
                         f"into your choices. Re-run with --again only if you accept that.")
    full, feed, hold = _panel(a, settings)
    res = run(full, strat, WARMUP, a.cost_bps)
    spy = run(full, BuyAndHold(BENCHMARK), WARMUP, a.cost_bps).returns
    keep = res.returns.index >= hold
    c = _compare(res.returns[keep], spy[keep], full, strat)
    print(f"SWING HOLDOUT LOOK #{views + 1}: {strat.label()}, costs {a.cost_bps} bps a side.\n")
    print(_block(f"HOLDOUT from {hold.date()} vs SPY", c))
    rid = _save(settings, HOLDOUT_KIND, strat, a, full, feed, c)
    print(f"recorded as run {rid} in {settings.db_path}")


def add_parser(sub):
    p = sub.add_parser("swing", help="daily-bar strategies from PREREGISTRATION.md")
    ss = p.add_subparsers(dest="swing_cmd", required=True)

    def common(q, strategy=True):
        q.add_argument("--start", default=DEFAULT_START)
        q.add_argument("--end", help="YYYY-MM-DD (default: today)")
        q.add_argument("--feed", choices=["sip", "iex"], default="sip")
        q.add_argument("--refresh", action="store_true")
        q.add_argument("--cost-bps", type=float, default=3.0)
        q.add_argument("--no-save", action="store_true")
        if strategy:
            q.add_argument("--strategy", choices=["trend", "meanrev", "blend", "static", "rotation"], required=True)
            q.add_argument("--lookback", type=int, default=252, help="trend: 63, 126 or 252 days")
            q.add_argument("--rebalance", choices=["W", "M"], default="M", help="trend: weekly or monthly")
            q.add_argument("--rsi", type=float, default=10, help="meanrev: 5, 10 or 20")
            q.add_argument("--max-hold", type=int, default=10, help="meanrev: 5 or 10 days")

    q = ss.add_parser("fetch", help="download and cache daily bars for every ETF")
    common(q, strategy=False)
    q.set_defaults(func=cmd_fetch)
    q = ss.add_parser("backtest", help="one variant vs SPY, research data")
    common(q)
    q.set_defaults(func=cmd_backtest)
    q = ss.add_parser("sweep", help="walk-forward over the pre-registered grid")
    common(q, strategy=False)
    q.add_argument("--strategy", choices=["trend", "meanrev"], required=True)
    q.set_defaults(func=cmd_sweep)
    q = ss.add_parser("holdout", help="one frozen variant on the locked swing holdout")
    common(q)
    q.add_argument("--again", action="store_true")
    q.set_defaults(func=cmd_holdout)
