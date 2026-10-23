"""aptrade command line.

  aptrade swing fetch|backtest|sweep|holdout   daily-bar portfolios and strategies
  aptrade export                               precompute the app's results (no raw prices)
  aptrade app                                  open the local web app
  aptrade intraday ...                         the archived intraday ORB research
  aptrade runs | show RUN_ID                   the SQLite journal of every run
  aptrade target set|show                      the portfolio APtrade maintains
  aptrade live status|plan|execute|alerts|kill manage a paper or real Alpaca account
  aptrade test-portfolio --weights ...         any weights vs SPY (add --json for agents)
"""
from __future__ import annotations

import argparse
import sys

from .config import Settings
from .data import DataError


def build_parser() -> argparse.ArgumentParser:
    from .intraday import cli as intraday
    from .swing.cli import add_parser as add_swing

    p = argparse.ArgumentParser(prog="aptrade", description="Test portfolios and strategies honestly against SPY.")
    sub = p.add_subparsers(dest="cmd", required=True)
    add_swing(sub)

    q = sub.add_parser("intraday", help="archived intraday ORB research")
    intraday.add_commands(q.add_subparsers(dest="intraday_cmd", required=True))

    q = sub.add_parser("runs", help="list saved runs")
    q.set_defaults(func=intraday.cmd_runs)
    q = sub.add_parser("show", help="report of a saved run")
    q.add_argument("run_id", type=int)
    q.set_defaults(func=intraday.cmd_show)

    try:
        from .export import add_parser as add_export
        add_export(sub)
    except ImportError:
        pass
    from .live.cli import add_parsers as add_live
    add_live(sub)

    q = sub.add_parser("app", help="open the local web app (Streamlit)")
    q.set_defaults(func=_cmd_app)
    return p


def _cmd_app(a, settings):
    import subprocess
    from pathlib import Path
    home = Path(__file__).resolve().parent.parent / "app" / "Home.py"
    if not home.is_file():
        raise SystemExit(f"app not found at {home}")
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(home)]))


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
