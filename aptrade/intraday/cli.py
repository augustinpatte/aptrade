"""Intraday commands, mounted as `aptrade intraday ...` (research archive).

  aptrade intraday fetch                       download and cache 5-minute bars
  aptrade backtest                    one strategy: per-trade edge + portfolio simulation
  aptrade sweep                       walk-forward over the parameter grid (research data only)
  aptrade holdout                     score ONE frozen variant on the locked holdout
  aptrade runs                        list saved runs
  aptrade show RUN_ID                 report of a saved run
  aptrade swing ...                   daily-bar strategies (see PREREGISTRATION.md)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from . import report, stats
from .. import store
from .backtest import ExecConfig, run
from ..config import BAR_MINUTES, DEFAULT_UNIVERSE, OPEN_MIN, PortfolioConfig, Settings
from ..data import DataError, load_bars
from .portfolio import equity_stats, simulate_portfolio
from .sessions import coverage, split_sessions
from .strategy import ORB
from .validation import walk_forward

HOLDOUT_KEY = "holdout_start"


def _date(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


def _last_entry_bar(text: str | None) -> int | None:
    """'11:30' -> index of the last bar whose CLOSE is at or before 11:30."""
    if not text:
        return None
    hh, mm = (int(x) for x in text.split(":"))
    idx = (hh * 60 + mm - OPEN_MIN) // BAR_MINUTES - 1
    if idx < 0:
        raise SystemExit(f"--last-entry {text} is before the first bar closes")
    return idx


def _period(a) -> tuple[datetime, datetime]:
    end = _date(a.end) if a.end else date.today()
    start = _date(a.start) if a.start else end - timedelta(days=730)
    return (datetime(start.year, start.month, start.day, tzinfo=timezone.utc),
            datetime(end.year, end.month, end.day, tzinfo=timezone.utc))


def _symbols(a) -> list[str]:
    return [s.strip().upper() for s in a.symbols.split(",")] if a.symbols else list(DEFAULT_UNIVERSE)


def _exec(a) -> ExecConfig:
    if getattr(a, "parity", False):
        return ExecConfig.parity()
    return ExecConfig(fill=a.fill, cost_bps=a.cost_bps, commission_per_share=a.commission)


def _portfolio(a) -> PortfolioConfig:
    try:
        return PortfolioConfig(capital=a.capital, risk_pct=a.risk_pct, daily_loss_pct=a.daily_loss_pct,
                               max_positions=a.max_positions, max_trades_per_day=a.max_trades_per_day)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")


def _load(a, settings, part: str):
    """Sessions of the requested part of the data: 'research' (before the holdout)
    or 'holdout'. Applies the coverage filter and fixes the holdout date on first use."""
    start, end = _period(a)
    syms = _symbols(a)
    print(f"loading {len(syms)} symbols, {start.date()} to {end.date()}", file=sys.stderr)
    bars, feed = load_bars(syms, start, end, settings, feed=a.feed, refresh=a.refresh)
    by_sym = {s: (split_sessions(bars[s], s) if s in bars else []) for s in syms}
    cov, kept, calendar = coverage(by_sym)
    if not calendar:
        raise SystemExit("no complete sessions in the data")

    hold = store.get_meta(settings.db_path, HOLDOUT_KEY)
    if hold is None:
        hold_day = calendar[int(len(calendar) * (1 - a.holdout_frac))]
        store.set_meta(settings.db_path, HOLDOUT_KEY, str(hold_day))
        print(f"holdout locked: every day from {hold_day} on is reserved (stored in {settings.db_path})",
              file=sys.stderr)
    else:
        hold_day = _date(hold)
    cal = set(calendar)
    keep = (lambda d: d < hold_day) if part == "research" else (lambda d: d >= hold_day)
    sessions = [s for sym in kept for s in by_sym[sym] if s.day in cal and keep(s.day)]
    days = sorted(d for d in calendar if keep(d))
    if not sessions:
        raise SystemExit(f"no {part} sessions (holdout starts {hold_day})")
    ctx = {"feed": feed, "start": start.date(), "end": end.date(), "symbols": kept,
           "requested": syms, "coverage": cov, "holdout_start": hold_day, "days": days, "part": part}
    return sessions, ctx


def _orb_from(a) -> ORB:
    return ORB(or_minutes=a.or_minutes, stop_rule=a.stop_rule, target_r=a.target_r,
               side=a.side, last_entry_bar=_last_entry_bar(a.last_entry))


def _evaluate(sessions, ctx, strat, cfg, pcfg):
    trades, counters = run(sessions, strat, cfg)
    ledger, eq, pcount = simulate_portfolio(trades, pcfg, all_days=ctx["days"])
    est = equity_stats(eq, ledger, pcfg.capital)
    taken = ledger[ledger["taken"].astype(bool)] if not ledger.empty else ledger
    return trades, counters, ledger, eq, pcount, est, taken


# ------------------------------------------------------------------ commands

def cmd_fetch(a, settings):
    start, end = _period(a)
    bars, feed = load_bars(_symbols(a), start, end, settings, feed=a.feed, refresh=a.refresh)
    for sym, df in sorted(bars.items()):
        print(f"{sym:6s} {len(df):7d} bars  {df.index.min().date()} to {df.index.max().date()}")
    print(f"feed: {feed}, cache: {settings.data_dir / 'cache' / feed}")


def _run_one(a, settings, part: str):
    strat, cfg, pcfg = _orb_from(a), _exec(a), _portfolio(a)     # refuse bad limits before any download
    sessions, ctx = _load(a, settings, part)
    trades, counters, ledger, eq, pcount, est, taken = _evaluate(sessions, ctx, strat, cfg, pcfg)
    label = "RESEARCH DATA" if part == "research" else "HOLDOUT DATA"
    header = (f"ORB {strat.params()}\nexecution {cfg}\n{label}: {ctx['days'][0]} to {ctx['days'][-1]}, "
              f"{len(ctx['symbols'])} symbols, feed {ctx['feed']} (holdout starts {ctx['holdout_start']})")
    print(report.coverage_block(ctx["coverage"]))
    print(report.full_report(trades, counters, header))
    print(report.portfolio_block(est, pcount, stats.summarize(taken)))
    summary = {**stats.summarize(trades), "portfolio": est, "portfolio_rejected": pcount.get("rejected", {}),
               "holdout_start": str(ctx["holdout_start"])}
    if not a.no_save or part == "holdout":       # holdout looks are always recorded
        rid = store.save_run(settings.db_path, kind="backtest" if part == "research" else "holdout",
                             strategy=strat.name, params=strat.params(),
                             exec_cfg={**counters["exec"], "portfolio": pcount.get("config")},
                             universe=ctx["symbols"], start=ctx["days"][0], end=ctx["days"][-1],
                             feed=ctx["feed"], summary=summary, trades=ledger)
        print(f"saved as run {rid} in {settings.db_path}")
    if a.csv and not ledger.empty:
        ledger.to_csv(a.csv, index=False)
        print(f"trades written to {a.csv}")
    return summary


def cmd_backtest(a, settings):
    _run_one(a, settings, "research")


def cmd_holdout(a, settings):
    views = store.holdout_views(settings.db_path)
    if views and not a.again:
        raise SystemExit(f"the holdout has already been looked at {views} time(s). Every look leaks it into "
                         f"your choices. Re-run with --again only if you accept that.")
    print(f"HOLDOUT LOOK #{views + 1}. Score it, then stop tuning: this number is the closest thing to "
          f"live performance you have.\n")
    _run_one(a, settings, "holdout")


def cmd_sweep(a, settings):
    sessions, ctx = _load(a, settings, "research")
    cfg = _exec(a)
    print(report.coverage_block(ctx["coverage"]))
    try:
        wf = walk_forward(sessions, cfg, folds=a.folds, last_entry_bar=_last_entry_bar(a.last_entry))
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")
    print(f"RESEARCH DATA {ctx['days'][0]} to {ctx['days'][-1]} ({wf['research_days']} days), "
          f"{len(ctx['symbols'])} symbols, feed {ctx['feed']}. Holdout from {ctx['holdout_start']} is untouched.\n"
          f"execution {cfg}\n")
    print(report.sweep_report(wf))
    if not a.no_save:
        summary = {"oos": wf["oos_summary"], "final": wf["final"], "folds": wf["folds"].to_dict("records"),
                   "variants": wf["table"].to_dict("records"), "trades": wf["oos_summary"].get("trades"),
                   "avg_r_net": wf["oos_summary"].get("avg_r_net")}
        rid = store.save_run(settings.db_path, kind="sweep", strategy="orb", params={"folds": a.folds},
                             exec_cfg=vars(cfg), universe=ctx["symbols"], start=ctx["days"][0],
                             end=ctx["days"][-1], feed=ctx["feed"], summary=summary, trades=pd.DataFrame())
        print(f"saved as run {rid} in {settings.db_path}")


def cmd_runs(a, settings):
    df = store.list_runs(settings.db_path)
    print(df.to_string(index=False) if not df.empty else "no runs yet")


def cmd_show(a, settings):
    run_, trades = store.load_run(settings.db_path, a.run_id)
    if run_["kind"] == "sweep":
        print(run_["summary"]["final"])
        print(pd.DataFrame(run_["summary"]["folds"]).to_string(index=False))
        return
    trades["day"] = pd.to_datetime(trades["day"]).dt.date
    counters = {"sessions": "?", "signals": "?", "trades": len(trades)}
    header = f"run {run_['id']} ({run_['kind']})  {run_['created_utc']}\nORB {run_['params']}\nexecution {run_['exec']}"
    print(report.full_report(trades.drop(columns="run_id"), counters, header))
    s = run_["summary"]
    if s.get("portfolio"):
        taken = trades[trades["taken"] == 1]
        print(report.portfolio_block(s["portfolio"], {"rejected": s.get("portfolio_rejected", {})},
                                     stats.summarize(taken)))


# ------------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    """Standalone parser (used by the tests): the intraday commands at top level."""
    p = argparse.ArgumentParser(prog="aptrade intraday", description="Intraday ORB research archive.")
    add_commands(p.add_subparsers(dest="cmd", required=True))
    return p


def add_commands(sub) -> None:

    def data_args(q):
        q.add_argument("--symbols", help="comma-separated tickers (default: the 50-name universe)")
        q.add_argument("--start", help="YYYY-MM-DD (default: two years before --end)")
        q.add_argument("--end", help="YYYY-MM-DD (default: today)")
        q.add_argument("--feed", choices=["sip", "iex"], default="sip")
        q.add_argument("--refresh", action="store_true", help="ignore the cache and download again")
        q.add_argument("--holdout-frac", type=float, default=0.25,
                       help="share of days reserved, used only the first time the holdout is locked")

    def exec_args(q):
        q.add_argument("--fill", choices=["next_open", "close"], default="next_open")
        q.add_argument("--cost-bps", type=float, default=3.0, help="per side, basis points (default 3)")
        q.add_argument("--commission", type=float, default=0.0, help="per share, per side")
        q.add_argument("--last-entry", help="no new signal after this New York time, e.g. 11:30")
        q.add_argument("--no-save", action="store_true")

    def strategy_args(q):
        q.add_argument("--or-minutes", type=int, default=15)
        q.add_argument("--stop-rule", choices=["or_mid", "or_far"], default="or_mid")
        q.add_argument("--target-r", type=float, default=1.0)
        q.add_argument("--side", choices=["long", "short", "both"], default="long")
        q.add_argument("--parity", action="store_true",
                       help="the original repo's optimistic execution: fill at the signal close, no costs")
        q.add_argument("--csv", help="also write the trades to this CSV")

    def portfolio_args(q):
        d = PortfolioConfig()
        q.add_argument("--capital", type=float, default=d.capital)
        q.add_argument("--risk-pct", type=float, default=d.risk_pct, help="%% of equity risked per trade")
        q.add_argument("--daily-loss-pct", type=float, default=d.daily_loss_pct)
        q.add_argument("--max-positions", type=int, default=d.max_positions)
        q.add_argument("--max-trades-per-day", type=int, default=d.max_trades_per_day)

    q = sub.add_parser("fetch", help="download and cache bars")
    data_args(q)
    q.set_defaults(func=cmd_fetch)

    for name, func, text in (("backtest", cmd_backtest, "per-trade edge and portfolio, research data"),
                             ("holdout", cmd_holdout, "score one frozen variant on the locked holdout")):
        q = sub.add_parser(name, help=text)
        data_args(q)
        exec_args(q)
        strategy_args(q)
        portfolio_args(q)
        if name == "holdout":
            q.add_argument("--again", action="store_true", help="accept looking at the holdout again")
        q.set_defaults(func=func)

    q = sub.add_parser("sweep", help="walk-forward over the parameter grid, research data only")
    data_args(q)
    exec_args(q)
    q.add_argument("--folds", type=int, default=4)
    q.set_defaults(func=cmd_sweep)

    q = sub.add_parser("runs", help="list saved runs")
    q.set_defaults(func=cmd_runs)

    q = sub.add_parser("show", help="report of a saved run")
    q.add_argument("run_id", type=int)
    q.set_defaults(func=cmd_show)


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    try:
        a.func(a, Settings.from_env())
    except DataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
